"""HTTP-level tests for POST /api/admin/characters/delete (logical delete of one character).

The endpoint sets role.deleted_time (the same logical delete the account delete uses). It is admin-only,
JSON-only, needs the character's exact name as confirmation, refuses admin accounts and online accounts,
fails closed when the online state cannot be read, is rate limited and writes its audit row in the same
transaction as the delete.
"""

import contextlib
import json
import os
import sqlite3
import sys
import tempfile
import threading
import unittest
import urllib.error
import urllib.request
from http.server import ThreadingHTTPServer
from unittest import mock

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
import server

ADMIN_USER = "boss"
ADMIN_PASS = "Pw-123456"
PATH = "/api/admin/characters/delete"


class CharacterDeleteBase(unittest.TestCase):
    def setUp(self):
        self.addCleanup(setattr, server, "DB_PATH", server.DB_PATH)
        self.addCleanup(setattr, server, "CONFIG", server.CONFIG)
        self.addCleanup(setattr, server, "ACTIVE_SESSIONS", server.ACTIVE_SESSIONS)
        self.addCleanup(setattr, server, "CHARACTER_DELETE_THROTTLE", server.CHARACTER_DELETE_THROTTLE)

        tmp = tempfile.TemporaryDirectory(ignore_cleanup_errors=True)
        self.addCleanup(tmp.cleanup)
        self.db_path = os.path.join(tmp.name, "ro3emu.db")

        with contextlib.closing(sqlite3.connect(self.db_path)) as con:
            con.execute("CREATE TABLE account (name TEXT PRIMARY KEY, password_hash BLOB, salt BLOB, created_utc TEXT)")
            con.execute("CREATE TABLE auth_token (token TEXT, kind TEXT, account TEXT, expires_utc TEXT)")
            con.execute(
                """CREATE TABLE role (
                    id INTEGER PRIMARY KEY AUTOINCREMENT, account TEXT, name TEXT, sex INTEGER,
                    career INTEGER, level INTEGER, job_level INTEGER, last_login_time INTEGER,
                    create_time INTEGER, currency TEXT, stats TEXT, scene_entry INTEGER,
                    pos_x REAL, pos_y REAL, pos_z REAL, deleted_time INTEGER DEFAULT 0, mailbox BLOB)"""
            )
            con.execute("CREATE TABLE item (guid INTEGER PRIMARY KEY, role_id INTEGER, entry INTEGER, stack INTEGER)")
            # The admin has no account row: with one, the panel login would check that account's password.
            for acc in ("owner", "other"):
                con.execute("INSERT INTO account (name, password_hash, salt, created_utc) VALUES (?, x'00', x'00', '2024-01-01T00:00:00Z')", (acc,))
            self.role_ids = {}
            for acc, name, deleted in (
                ("owner", "Alpha", 0), ("owner", "Beta", 0), ("other", "Gamma", 0),
                (ADMIN_USER, "GmChar", 0), ("owner", "Gone", 1700000000),
            ):
                cur = con.execute(
                    "INSERT INTO role (account, name, sex, career, level, job_level, last_login_time, create_time,"
                    " currency, stats, scene_entry, pos_x, pos_y, pos_z, deleted_time)"
                    " VALUES (?, ?, 1, 1000, 10, 5, 1700000000, 1700000000, '2:100', '1,2,3,4,5,6', 10100, 1.0, 2.0, 3.0, ?)",
                    (acc, name, deleted),
                )
                self.role_ids[name] = cur.lastrowid
            con.execute("INSERT INTO item (guid, role_id, entry, stack) VALUES (1, ?, 501, 3)", (self.role_ids["Alpha"],))
            con.commit()

        server.DB_PATH = self.db_path
        server.CONFIG = dict(server.CONFIG)
        server.CONFIG["admin_users"] = [{"username": ADMIN_USER, "password": ADMIN_PASS}]
        server.ACTIVE_SESSIONS = {}
        server.CHARACTER_DELETE_THROTTLE = server.LoginThrottle(max_failures=1000, window_seconds=60)
        server.init_tables()

        for patcher in (
            mock.patch.object(server.CPanelRequestHandler, "log_message", lambda *a, **k: None),
            mock.patch.object(server, "fetch_ro3_json", return_value=[]),
        ):
            patcher.start()
            self.addCleanup(patcher.stop)
        self.online = server.fetch_ro3_json

        self.httpd = ThreadingHTTPServer(("127.0.0.1", 0), server.CPanelRequestHandler)
        thread = threading.Thread(target=self.httpd.serve_forever, daemon=True)
        thread.start()
        self.addCleanup(thread.join, 10)
        self.addCleanup(self.httpd.server_close)
        self.addCleanup(self.httpd.shutdown)
        self.base = "http://127.0.0.1:%d" % self.httpd.server_address[1]
        self.token = self._login()

    def _login(self):
        req = urllib.request.Request(
            self.base + "/api/admin/login",
            data=json.dumps({"username": ADMIN_USER, "password": ADMIN_PASS}).encode("utf-8"),
            headers={"Content-Type": "application/json"}, method="POST",
        )
        with urllib.request.urlopen(req, timeout=10) as resp:
            return json.loads(resp.read().decode("utf-8"))["token"]

    def post(self, body, auth=True, content_type="application/json", raw=None):
        headers = {}
        if content_type:
            headers["Content-Type"] = content_type
        if auth:
            headers["Authorization"] = "Bearer " + self.token
        data = raw if raw is not None else json.dumps(body).encode("utf-8")
        req = urllib.request.Request(self.base + PATH, data=data, headers=headers, method="POST")
        try:
            with urllib.request.urlopen(req, timeout=10) as resp:
                return resp.status, json.loads(resp.read().decode("utf-8")), resp.headers
        except urllib.error.HTTPError as err:
            with err:
                return err.code, json.loads(err.read().decode("utf-8")), err.headers

    def delete(self, name, **kwargs):
        return self.post({"role_id": self.role_ids[name], "confirm_name": name}, **kwargs)

    def row(self, name):
        with contextlib.closing(sqlite3.connect(self.db_path)) as con:
            return con.execute("SELECT deleted_time, account FROM role WHERE id = ?", (self.role_ids[name],)).fetchone()

    def audit_rows(self):
        with contextlib.closing(sqlite3.connect(self.db_path)) as con:
            return con.execute("SELECT admin_user, action, target, details, ip_address FROM admin_audit_log WHERE action = 'delete_character'").fetchall()

    def assert_untouched(self, name):
        self.assertEqual(self.row(name)[0], 0, "the character must not be deleted")
        self.assertEqual(self.audit_rows(), [])


class CharacterDeleteTest(CharacterDeleteBase):
    # --- the delete itself ---

    def test_deletes_logically_and_keeps_the_row_and_its_items(self):
        status, data, _ = self.delete("Alpha")
        self.assertEqual(status, 200, data)
        self.assertTrue(data["success"])
        self.assertEqual(data["role_id"], self.role_ids["Alpha"])
        self.assertGreater(self.row("Alpha")[0], 0)
        self.assertEqual(self.row("Beta")[0], 0, "a sibling character is not touched")
        with contextlib.closing(sqlite3.connect(self.db_path)) as con:
            self.assertEqual(con.execute("SELECT COUNT(*) FROM item WHERE role_id = ?", (self.role_ids["Alpha"],)).fetchone()[0], 1)

    def test_a_deleted_character_leaves_the_account_detail(self):
        self.delete("Alpha")
        req = urllib.request.Request(self.base + "/api/admin/accounts/owner", headers={"Authorization": "Bearer " + self.token})
        with urllib.request.urlopen(req, timeout=10) as resp:
            names = [c["name"] for c in json.loads(resp.read().decode("utf-8"))["characters"]]
        self.assertEqual(names, ["Beta"])

    def test_writes_one_audit_row_with_who_what_and_where_from(self):
        self.post({"role_id": self.role_ids["Alpha"], "confirm_name": "Alpha"})
        (row,) = self.audit_rows()
        self.assertEqual(row[0], ADMIN_USER)
        self.assertIn("Alpha", row[2])
        self.assertIn(str(self.role_ids["Alpha"]), row[2])
        self.assertIn("owner", row[3])
        self.assertTrue(row[4])

    def test_no_delete_without_its_audit_row(self):
        with mock.patch.object(server, "insert_audit", side_effect=sqlite3.OperationalError("disk full")):
            status, _, _ = self.delete("Alpha")
        self.assertEqual(status, 500)
        self.assertEqual(self.row("Alpha")[0], 0)

    # --- who can call it, and how ---

    def test_requires_an_admin_session(self):
        status, _, _ = self.delete("Alpha", auth=False)
        self.assertEqual(status, 401)
        self.assert_untouched("Alpha")

    def test_a_session_whose_admin_was_removed_is_refused(self):
        server.CONFIG["admin_users"] = [{"username": "someone-else", "password": "x"}]
        status, _, _ = self.delete("Alpha")
        self.assertEqual(status, 401)
        self.assert_untouched("Alpha")

    def test_a_garbage_token_is_refused(self):
        self.token = "not-a-session"
        status, _, _ = self.delete("Alpha")
        self.assertEqual(status, 401)
        self.assert_untouched("Alpha")

    def test_only_json_is_accepted_so_a_cross_site_form_cannot_trigger_it(self):
        for content_type in ("text/plain", "application/x-www-form-urlencoded", "multipart/form-data", None):
            status, _, _ = self.post(None, content_type=content_type, raw=json.dumps({"role_id": self.role_ids["Alpha"], "confirm_name": "Alpha"}).encode())
            self.assertEqual(status, 415, content_type)
        self.assert_untouched("Alpha")

    def test_a_json_content_type_with_charset_is_accepted(self):
        status, _, _ = self.delete("Alpha", content_type="application/json; charset=utf-8")
        self.assertEqual(status, 200)

    def test_it_is_not_reachable_with_get(self):
        req = urllib.request.Request(self.base + PATH, headers={"Authorization": "Bearer " + self.token})
        with self.assertRaises(urllib.error.HTTPError) as ctx:
            urllib.request.urlopen(req, timeout=10)
        with ctx.exception:
            self.assertEqual(ctx.exception.code, 404)
        self.assert_untouched("Alpha")

    # --- input ---

    def test_rejects_a_bad_role_id(self):
        for bad in (None, 0, -1, "abc", "1 OR 1=1", True, 1.5, 2 ** 63, [1], {"a": 1}, ""):
            status, _, _ = self.post({"role_id": bad, "confirm_name": "Alpha"})
            self.assertEqual(status, 400, repr(bad))
        self.assert_untouched("Alpha")

    def test_rejects_a_body_that_is_not_an_object(self):
        for body in ([], [1], "x", 5, None):
            status, _, _ = self.post(body)
            self.assertEqual(status, 400, repr(body))
        status, _, _ = self.post(None, raw=b"{not json")
        self.assertEqual(status, 400)
        self.assert_untouched("Alpha")

    def test_the_confirmation_must_be_the_exact_character_name(self):
        for typed in (None, "", "alpha", "ALPHA", " Alpha", "Alpha ", "Beta", 5, ["Alpha"]):
            status, _, _ = self.post({"role_id": self.role_ids["Alpha"], "confirm_name": typed})
            self.assertEqual(status, 400, repr(typed))
        self.assert_untouched("Alpha")

    def test_an_unknown_character_is_404(self):
        status, _, _ = self.post({"role_id": 99999, "confirm_name": "Nobody"})
        self.assertEqual(status, 404)

    def test_an_already_deleted_character_is_404_and_its_time_is_kept(self):
        status, _, _ = self.delete("Gone")
        self.assertEqual(status, 404)
        self.assertEqual(self.row("Gone")[0], 1700000000)
        self.assertEqual(self.audit_rows(), [])

    def test_a_character_of_an_admin_account_cannot_be_deleted(self):
        status, data, _ = self.delete("GmChar")
        self.assertEqual(status, 400)
        self.assertIn("administrator", data["error"].lower())
        self.assert_untouched("GmChar")

    def test_a_character_deleted_meanwhile_is_not_deleted_twice(self):
        """Another admin deletes it between the confirmation and the transaction: no overwrite, no audit row."""
        def concurrent_delete(account):
            with contextlib.closing(sqlite3.connect(self.db_path)) as con:
                con.execute("UPDATE role SET deleted_time = 1700000001 WHERE id = ?", (self.role_ids["Alpha"],))
                con.commit()
            return False

        with mock.patch.object(server, "account_is_online", side_effect=concurrent_delete):
            status, _, _ = self.delete("Alpha")
        self.assertEqual(status, 409)
        self.assertEqual(self.row("Alpha")[0], 1700000001)
        self.assertEqual(self.audit_rows(), [])

    # --- the account must be offline, and we must know it ---

    def test_an_online_account_blocks_the_delete(self):
        self.online.return_value = [{"account": "owner", "role": "Beta"}]
        status, _, _ = self.delete("Alpha")
        self.assertEqual(status, 409)
        self.assert_untouched("Alpha")

    def test_the_online_match_ignores_case_and_spaces(self):
        self.online.return_value = [{"account": " OWNER ", "role": "Beta"}]
        status, _, _ = self.delete("Alpha")
        self.assertEqual(status, 409)

    def test_another_account_being_online_does_not_block(self):
        self.online.return_value = [{"account": "other", "role": "Gamma"}]
        status, _, _ = self.delete("Alpha")
        self.assertEqual(status, 200)

    def test_fails_closed_when_the_online_state_cannot_be_read(self):
        for failure in (server.Ro3EmuUnavailable("down"), RuntimeError("boom")):
            self.online.side_effect = failure
            status, _, _ = self.delete("Alpha")
            self.assertEqual(status, 503, repr(failure))
        self.assert_untouched("Alpha")

    def test_fails_closed_when_the_online_answer_is_not_a_list(self):
        self.online.return_value = {"unexpected": True}
        status, _, _ = self.delete("Alpha")
        self.assertEqual(status, 503)
        self.assert_untouched("Alpha")

    # --- abuse ---

    def test_attempts_are_rate_limited_per_admin(self):
        server.CHARACTER_DELETE_THROTTLE = server.LoginThrottle(max_failures=5, window_seconds=60)
        for _ in range(5):
            self.post({"role_id": 99999, "confirm_name": "x"})
        status, data, headers = self.delete("Alpha")
        self.assertEqual(status, 429)
        self.assertTrue(headers.get("Retry-After"))
        self.assert_untouched("Alpha")

    def test_the_rate_limit_does_not_touch_the_login_limiter(self):
        server.CHARACTER_DELETE_THROTTLE = server.LoginThrottle(max_failures=5, window_seconds=60)
        for _ in range(5):
            self.post({"role_id": 99999, "confirm_name": "x"})
        self.assertEqual(server.LOGIN_THROTTLE.failure_count("user:" + ADMIN_USER), 0)


class ExistingAccountActionsStillWork(CharacterDeleteBase):
    """Routing in do_POST changed: the neighbouring protected endpoints keep their behaviour."""

    def test_account_delete_still_requires_a_session(self):
        req = urllib.request.Request(
            self.base + "/api/admin/accounts/delete", data=b'{"username": "other"}',
            headers={"Content-Type": "application/json"}, method="POST",
        )
        with self.assertRaises(urllib.error.HTTPError) as ctx:
            urllib.request.urlopen(req, timeout=10)
        with ctx.exception:
            self.assertEqual(ctx.exception.code, 401)

    def test_account_delete_still_deletes_with_a_session(self):
        req = urllib.request.Request(
            self.base + "/api/admin/accounts/delete", data=b'{"username": "other"}',
            headers={"Content-Type": "application/json", "Authorization": "Bearer " + self.token}, method="POST",
        )
        with urllib.request.urlopen(req, timeout=10) as resp:
            self.assertEqual(resp.status, 200)
        self.assertGreater(self.row("Gamma")[0], 0)


if __name__ == "__main__":
    unittest.main()
