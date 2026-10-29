"""Bans live in RO3Emu's `account_ban` table: the panel writes it, RO3Emu reads it at login (cpanel issue #1).

The fixture creates `account_ban` the way RO3Emu does, to stand for a server that supports bans.
`MissingTableTests` leaves it out, to stand for an older RO3Emu.
"""

import json
import os
import sqlite3
import sys
import tempfile
import threading
import time
import unittest
import urllib.error
import urllib.parse
import urllib.request
from contextlib import closing
from http.server import ThreadingHTTPServer
from unittest import mock

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
import server

ADMIN_USER = "boss"
ADMIN_PASS = "Pw-123456"

# The table RO3Emu creates (contract S1). The panel never creates it.
ACCOUNT_BAN_SQL = """
    CREATE TABLE account_ban (
        account TEXT NOT NULL PRIMARY KEY,
        reason TEXT NOT NULL DEFAULT '',
        banned_utc INTEGER NOT NULL,
        until_utc INTEGER,
        banned_by TEXT
    )
"""

BASE_SCHEMA = """
    CREATE TABLE account (name TEXT PRIMARY KEY, password_hash BLOB, salt BLOB, created_utc TEXT);
    CREATE TABLE auth_token (token TEXT PRIMARY KEY, kind TEXT, account TEXT, expires_utc INTEGER);
    CREATE TABLE role (
        id INTEGER PRIMARY KEY AUTOINCREMENT, account TEXT, name TEXT, sex INTEGER,
        career INTEGER, level INTEGER, job_level INTEGER, last_login_time INTEGER,
        create_time INTEGER, currency TEXT, stats TEXT, scene_entry INTEGER,
        pos_x REAL, pos_y REAL, pos_z REAL, deleted_time INTEGER DEFAULT 0);
    INSERT INTO account VALUES ('player1', x'00', x'00', '2026-01-01');
    INSERT INTO account VALUES ('player2', x'00', x'00', '2026-01-02');
    INSERT INTO account VALUES ('legacy', x'00', x'00', '2026-01-03');
    INSERT INTO auth_token VALUES ('tok1', 'sdk', 'player1', 9999999999);
    INSERT INTO auth_token VALUES ('tok2', 'sdk', 'player2', 9999999999);
"""


class _PanelFixture(unittest.TestCase):
    with_ban_table = True

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.db_path = os.path.join(self.tmp.name, "ro3emu.db")
        with closing(sqlite3.connect(self.db_path)) as con:
            con.executescript(BASE_SCHEMA)
            if self.with_ban_table:
                con.execute(ACCOUNT_BAN_SQL)
            con.commit()

        saved = (server.DB_PATH, dict(server.CONFIG), server.RO3_STATUS_URL)
        server.DB_PATH = self.db_path
        server.CONFIG["admin_users"] = [{"username": ADMIN_USER, "password": ADMIN_PASS}]
        # Port 9 (discard) refuses at once, so /api/admin/stats does not wait for a live RO3Emu.
        server.RO3_STATUS_URL = "http://127.0.0.1:9/ro3emu/status"
        server.init_tables()

        # A ban written by an older panel, in the panel's own table. It is not migrated.
        with closing(sqlite3.connect(self.db_path)) as con:
            con.execute("INSERT INTO admin_account_meta (name, is_banned, ban_reason) VALUES ('legacy', 1, 'old')")
            con.commit()

        patcher = mock.patch.object(server.CPanelRequestHandler, "log_message", lambda *a, **k: None)
        patcher.start()
        self.addCleanup(patcher.stop)

        self.httpd = ThreadingHTTPServer(("127.0.0.1", 0), server.CPanelRequestHandler)
        thread = threading.Thread(target=self.httpd.serve_forever, daemon=True)
        thread.start()
        self.base = "http://127.0.0.1:%d" % self.httpd.server_address[1]

        def restore():
            self.httpd.shutdown()
            self.httpd.server_close()
            thread.join(10)
            server.DB_PATH, config, server.RO3_STATUS_URL = saved
            server.CONFIG.clear()
            server.CONFIG.update(config)
            server.ACTIVE_SESSIONS.clear()

        self.addCleanup(restore)
        self.token = self._call("POST", "/api/admin/login", {"username": ADMIN_USER, "password": ADMIN_PASS})[1]["token"]

    def _call(self, method, path, payload=None, lang=None):
        headers = {"Content-Type": "application/json"}
        if getattr(self, "token", None):
            headers["Authorization"] = "Bearer " + self.token
        if lang:
            headers["X-Panel-Lang"] = lang
        data = json.dumps(payload).encode() if payload is not None else None
        req = urllib.request.Request(self.base + path, data=data, headers=headers, method=method)
        try:
            with urllib.request.urlopen(req, timeout=10) as resp:
                return resp.status, json.loads(resp.read())
        except urllib.error.HTTPError as e:
            with e:
                return e.code, json.loads(e.read())

    def _rows(self, sql, args=()):
        with closing(sqlite3.connect(self.db_path)) as con:
            return con.execute(sql, args).fetchall()

    def _ban_row(self, account):
        rows = self._rows("SELECT account, reason, banned_utc, until_utc, banned_by FROM account_ban WHERE account=?", (account,))
        return rows[0] if rows else None

    def _insert_ban(self, account, until_utc, reason="r"):
        with closing(sqlite3.connect(self.db_path)) as con:
            con.execute(
                "INSERT INTO account_ban (account, reason, banned_utc, until_utc, banned_by) VALUES (?, ?, ?, ?, 'boss')",
                (account, reason, int(time.time()) - 60, until_utc),
            )
            con.commit()

    def _accounts(self, status="all"):
        query = urllib.parse.urlencode({"status": status, "page_size": 100})
        return self._call("GET", "/api/admin/accounts?" + query)[1]

    def _detail(self, account):
        return self._call("GET", "/api/admin/accounts/" + urllib.parse.quote(account))[1]

    def _banned_count(self):
        return self._call("GET", "/api/admin/stats")[1]["counts"]["banned"]


class BanWritesServerTableTests(_PanelFixture):
    def test_ban_writes_the_row_revokes_tokens_and_audits(self):
        before = int(time.time())
        status, body = self._call("POST", "/api/admin/accounts/ban", {"username": "player1", "reason": "cheating"})
        after = int(time.time())

        self.assertEqual(status, 200)
        self.assertTrue(body["success"])
        self.assertIs(body["enforced"], True)
        account, reason, banned_utc, until_utc, banned_by = self._ban_row("player1")
        self.assertEqual((account, reason, until_utc, banned_by), ("player1", "cheating", None, ADMIN_USER))
        self.assertTrue(before <= banned_utc <= after)
        self.assertEqual(self._rows("SELECT COUNT(*) FROM auth_token WHERE account='player1'")[0][0], 0)
        self.assertEqual(self._rows("SELECT COUNT(*) FROM auth_token WHERE account='player2'")[0][0], 1)
        self.assertEqual(
            self._rows("SELECT admin_user, target, details FROM admin_audit_log WHERE action='ban_account'"),
            [(ADMIN_USER, "player1", "Reason: cheating")],
        )

    def test_ban_again_replaces_the_row(self):
        self._insert_ban("player1", int(time.time()) - 10, reason="expired")
        status, _ = self._call("POST", "/api/admin/accounts/ban", {"username": "player1", "reason": "again"})

        self.assertEqual(status, 200)
        _, reason, _, until_utc, _ = self._ban_row("player1")
        self.assertEqual((reason, until_utc), ("again", None))
        self.assertEqual(self._rows("SELECT COUNT(*) FROM account_ban")[0][0], 1)

    def test_unban_deletes_the_row_and_audits(self):
        self._call("POST", "/api/admin/accounts/ban", {"username": "player1", "reason": "cheating"})
        status, body = self._call("POST", "/api/admin/accounts/unban", {"username": "player1"})

        self.assertEqual(status, 200)
        self.assertTrue(body["success"])
        self.assertIsNone(self._ban_row("player1"))
        self.assertEqual(
            self._rows("SELECT admin_user, target FROM admin_audit_log WHERE action='unban_account'"),
            [(ADMIN_USER, "player1")],
        )

    def test_ban_and_audit_share_one_transaction(self):
        with closing(sqlite3.connect(self.db_path)) as con:
            con.execute("DROP TABLE admin_audit_log")
            con.commit()
        try:
            self._call("POST", "/api/admin/accounts/ban", {"username": "player1", "reason": "cheating"})
        except Exception:  # the handler fails on the audit insert; the connection may just close
            pass

        self.assertIsNone(self._ban_row("player1"))
        self.assertEqual(self._rows("SELECT COUNT(*) FROM auth_token WHERE account='player1'")[0][0], 1)

    def test_admin_account_still_cannot_be_banned(self):
        with closing(sqlite3.connect(self.db_path)) as con:
            con.execute("INSERT INTO account VALUES ('boss', x'00', x'00', '2026-01-01')")
            con.commit()
        status, _ = self._call("POST", "/api/admin/accounts/ban", {"username": "boss"})

        self.assertEqual(status, 400)
        self.assertIsNone(self._ban_row("boss"))

    def test_unknown_account_is_404_and_writes_nothing(self):
        status, _ = self._call("POST", "/api/admin/accounts/ban", {"username": "ghost"})

        self.assertEqual(status, 404)
        self.assertEqual(self._rows("SELECT COUNT(*) FROM account_ban")[0][0], 0)


class BanStatusReadsServerTableTests(_PanelFixture):
    def test_list_filter_detail_and_counts_read_account_ban(self):
        self._insert_ban("player1", None, reason="cheating")

        banned = self._accounts("banned")
        self.assertEqual([a["name"] for a in banned["accounts"]], ["player1"])
        self.assertEqual(banned["accounts"][0]["ban_reason"], "cheating")
        self.assertTrue(banned["accounts"][0]["banned_at"])
        self.assertIs(banned["bans_supported"], True)
        self.assertEqual(sorted(a["name"] for a in self._accounts("active")["accounts"]), ["legacy", "player2"])
        flags = {a["name"]: a["is_banned"] for a in self._accounts()["accounts"]}
        self.assertEqual(flags, {"player1": True, "player2": False, "legacy": False})

        detail = self._detail("player1")
        self.assertIs(detail["is_banned"], True)
        self.assertEqual(detail["ban_reason"], "cheating")
        self.assertIs(detail["bans_supported"], True)
        self.assertEqual(self._banned_count(), 1)

    def test_legacy_panel_flag_is_not_a_ban(self):
        self.assertIs(self._detail("legacy")["is_banned"], False)
        self.assertEqual(self._accounts("banned")["accounts"], [])
        self.assertEqual(self._banned_count(), 0)

    def test_expired_ban_shows_as_not_banned(self):
        self._insert_ban("player1", int(time.time()) - 1)
        self._insert_ban("player2", int(time.time()) + 3600)

        self.assertEqual([a["name"] for a in self._accounts("banned")["accounts"]], ["player2"])
        self.assertIs(self._detail("player1")["is_banned"], False)
        self.assertEqual(self._detail("player1")["ban_reason"], "")
        self.assertIs(self._detail("player2")["is_banned"], True)
        self.assertEqual(self._banned_count(), 1)

    def test_notes_still_live_in_admin_account_meta(self):
        self._insert_ban("legacy", None)
        with closing(sqlite3.connect(self.db_path)) as con:
            con.execute("UPDATE admin_account_meta SET notes='keep me' WHERE name='legacy'")
            con.commit()

        detail = self._detail("legacy")
        self.assertEqual(detail["notes"], "keep me")
        self.assertIs(detail["is_banned"], True)


class MissingTableTests(_PanelFixture):
    """An RO3Emu without `account_ban` cannot enforce a ban: the panel says so and never creates the table."""

    with_ban_table = False

    def assert_no_ban_table(self):
        self.assertEqual(self._rows("SELECT name FROM sqlite_master WHERE name='account_ban'"), [])

    def test_ban_answers_update_ro3emu_and_changes_nothing(self):
        status, body = self._call("POST", "/api/admin/accounts/ban", {"username": "player1", "reason": "x"})

        self.assertEqual(status, 409)
        self.assertEqual(body["error"], "Update RO3Emu: this server does not support account bans")
        self.assert_no_ban_table()
        self.assertEqual(self._rows("SELECT COUNT(*) FROM auth_token WHERE account='player1'")[0][0], 1)
        self.assertEqual(self._rows("SELECT COUNT(*) FROM admin_audit_log WHERE action='ban_account'")[0][0], 0)

    def test_unban_answers_update_ro3emu(self):
        status, body = self._call("POST", "/api/admin/accounts/unban", {"username": "player1"})

        self.assertEqual(status, 409)
        self.assertEqual(body["error"], "Update RO3Emu: this server does not support account bans")
        self.assert_no_ban_table()

    def test_error_is_localized(self):
        _, body = self._call("POST", "/api/admin/accounts/ban", {"username": "player1"}, lang="es")

        self.assertEqual(body["error"], server.ES_MESSAGES["Update RO3Emu: this server does not support account bans"])
        self.assertIn("RO3Emu", body["error"])

    def test_reads_show_nobody_banned_and_bans_unsupported(self):
        listing = self._accounts()
        self.assertIs(listing["bans_supported"], False)
        self.assertTrue(all(a["is_banned"] is False for a in listing["accounts"]))
        self.assertEqual(self._accounts("banned")["accounts"], [])
        self.assertEqual(self._accounts("banned")["total"], 0)
        self.assertEqual(self._accounts("active")["total"], 3)
        detail = self._detail("legacy")
        self.assertIs(detail["is_banned"], False)
        self.assertIs(detail["bans_supported"], False)
        stats = self._call("GET", "/api/admin/stats")[1]
        self.assertEqual(stats["counts"]["banned"], 0)
        self.assertIs(stats["bans_supported"], False)
        self.assert_no_ban_table()


if __name__ == "__main__":
    unittest.main()
