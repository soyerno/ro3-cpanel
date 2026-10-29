"""HTTP-level tests for the read-only guild and auction views (issue #9, part A).

The fixture DDL mirrors aethai/ro3emu-server:
- guild / guild_member: src/Ro3Emu.Server/Accounts/Persistence/GuildStorePlans.cs (GuildSchemaPlan)
- auction_item / auction_prebuy: src/Ro3Emu.Server/Accounts/Persistence/CoreSchemaPlans.cs (AuctionSchemaPlan)
  plus the columns AuctionItemColumns.Migrate adds (settled, auction_type, run_id, end_time).
guild.state is the System.Text.Json serialization of GuildStore.State (default options, PascalCase).
"""

import contextlib
import hashlib
import json
import os
import sqlite3
import sys
import tempfile
import threading
import unittest
import urllib.error
import urllib.parse
import urllib.request
from http.server import ThreadingHTTPServer
from unittest import mock

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
import server

ADMIN_USER = "boss"
ADMIN_PASS = "Pw-123456"

GUILD_DDL = """
CREATE TABLE guild (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL UNIQUE COLLATE NOCASE,
    state BLOB NOT NULL
);
CREATE TABLE guild_member (
    role_id INTEGER PRIMARY KEY,
    guild_id INTEGER NOT NULL REFERENCES guild(id)
);
CREATE INDEX guild_member_guild ON guild_member(guild_id);
"""

AUCTION_DDL = """
CREATE TABLE auction_item (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    source_key TEXT NOT NULL UNIQUE,
    state BLOB NOT NULL,
    settled INTEGER NOT NULL DEFAULT 0,
    auction_type INTEGER NOT NULL DEFAULT 0,
    run_id INTEGER NOT NULL DEFAULT 0,
    end_time INTEGER NOT NULL DEFAULT 0
);
CREATE TABLE auction_prebuy (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    role_id INTEGER NOT NULL,
    auction_type INTEGER NOT NULL,
    src_type INTEGER NOT NULL,
    item_id INTEGER NOT NULL,
    quantity INTEGER NOT NULL,
    unit_price INTEGER NOT NULL,
    currency INTEGER NOT NULL,
    revision INTEGER NOT NULL DEFAULT 0,
    processed INTEGER NOT NULL DEFAULT 0,
    requested_id INTEGER NOT NULL DEFAULT 0,
    paused INTEGER NOT NULL DEFAULT 0
);
"""

READ_TABLES = ["guild", "guild_member", "role", "auction_item", "auction_prebuy"]


def guild_state(guild_id, name, level):
    return json.dumps({"Id": guild_id, "Name": name, "Level": level, "Members": {}}).encode("utf-8")


# (id, name, level-in-state or None for an undecodable blob)
GUILDS = [
    (1, "Valkyrie", 3),
    (2, "Midgard Knights", 5),
    (3, "Ñandú Clan", 1),
    (4, "Broken", None),
]
# (role_id, account, name, career, level, deleted_time, guild_id)
ROLES = [
    (10, "alpha", "Leader", 1200, 40, 0, 1),
    (11, "alpha", "Second", 2100, 25, 0, 1),
    (12, "bravo", "Ghost", 3100, 99, 1700000000, 1),
    (13, "bravo", "Paladin", 9999, 60, 0, 2),
    (14, "charlie", "Solo", 1000, 1, 0, None),
]
FILLER_GUILDS = 25  # ids 5..29, no members


class GuildsAuctionsTest(unittest.TestCase):
    def setUp(self):
        # Restore module globals BEFORE mutating them.
        self.addCleanup(setattr, server, "DB_PATH", server.DB_PATH)
        self.addCleanup(setattr, server, "CONFIG", server.CONFIG)
        self.addCleanup(setattr, server, "ACTIVE_SESSIONS", server.ACTIVE_SESSIONS)

        tmp = tempfile.TemporaryDirectory(ignore_cleanup_errors=True)
        self.addCleanup(tmp.cleanup)
        self.db_path = os.path.join(tmp.name, "ro3emu.db")

        with contextlib.closing(sqlite3.connect(self.db_path)) as con:
            con.execute("CREATE TABLE account (name TEXT PRIMARY KEY, password_hash BLOB, salt BLOB, created_utc TEXT)")
            con.execute(
                """CREATE TABLE role (
                    id INTEGER PRIMARY KEY AUTOINCREMENT, account TEXT, name TEXT, sex INTEGER,
                    career INTEGER, level INTEGER, job_level INTEGER, last_login_time INTEGER,
                    create_time INTEGER, currency TEXT, stats TEXT, scene_entry INTEGER,
                    pos_x REAL, pos_y REAL, pos_z REAL, deleted_time INTEGER DEFAULT 0)"""
            )
            con.executescript(GUILD_DDL)
            con.executescript(AUCTION_DDL)
            for gid, name, level in GUILDS:
                state = guild_state(gid, name, level) if level is not None else b"\x00not-json"
                con.execute("INSERT INTO guild (id, name, state) VALUES (?, ?, ?)", (gid, name, state))
            for i in range(FILLER_GUILDS):
                gid = 5 + i
                con.execute("INSERT INTO guild (id, name, state) VALUES (?, ?, ?)",
                            (gid, "zz-filler-%02d" % i, guild_state(gid, "f", 1)))
            for rid, account, name, career, level, deleted, gid in ROLES:
                con.execute(
                    "INSERT INTO role (id, account, name, sex, career, level, job_level, deleted_time)"
                    " VALUES (?, ?, ?, 1, ?, ?, 1, ?)",
                    (rid, account, name, career, level, deleted),
                )
                if gid is not None:
                    con.execute("INSERT INTO guild_member (role_id, guild_id) VALUES (?, ?)", (rid, gid))
            for i in range(1, 8):
                con.execute(
                    "INSERT INTO auction_item (id, source_key, state, settled, auction_type, run_id, end_time)"
                    " VALUES (?, ?, x'7b7d', ?, ?, ?, ?)",
                    (i, "src-%d" % i, i % 2, 100 + i, 0 if i < 5 else 42, 1700000000 + i),
                )
            con.execute(
                "INSERT INTO auction_prebuy (id, role_id, auction_type, src_type, item_id, quantity, unit_price,"
                " currency, processed, paused) VALUES (1, 10, 2, 3, 5001, 4, 250, 2, 0, 1)"
            )
            con.execute(
                "INSERT INTO auction_prebuy (id, role_id, auction_type, src_type, item_id, quantity, unit_price,"
                " currency, processed, paused) VALUES (2, 777, 1, 1, 6001, 1, 99, 1, 1, 0)"
            )
            con.commit()

        server.DB_PATH = self.db_path
        server.CONFIG = dict(server.CONFIG)
        server.CONFIG["admin_users"] = [{"username": ADMIN_USER, "password": ADMIN_PASS}]
        server.ACTIVE_SESSIONS = {}
        server.init_tables()

        patcher = mock.patch.object(server.CPanelRequestHandler, "log_message", lambda *a, **k: None)
        patcher.start()
        self.addCleanup(patcher.stop)

        self.httpd = ThreadingHTTPServer(("127.0.0.1", 0), server.CPanelRequestHandler)
        thread = threading.Thread(target=self.httpd.serve_forever, daemon=True)
        thread.start()
        self.addCleanup(thread.join, 10)
        self.addCleanup(self.httpd.server_close)
        self.addCleanup(self.httpd.shutdown)
        self.base = "http://127.0.0.1:%d" % self.httpd.server_address[1]
        self.token = self._login()

    # --- helpers ---

    def _login(self):
        req = urllib.request.Request(
            self.base + "/api/admin/login",
            data=json.dumps({"username": ADMIN_USER, "password": ADMIN_PASS}).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=10) as resp:
            return json.loads(resp.read().decode("utf-8"))["token"]

    def request(self, path, auth=True, **params):
        url = self.base + path
        if params:
            url += "?" + urllib.parse.urlencode(params)
        headers = {"Authorization": "Bearer " + self.token} if auth else {}
        req = urllib.request.Request(url, headers=headers)
        try:
            with urllib.request.urlopen(req, timeout=10) as resp:
                return resp.status, json.loads(resp.read().decode("utf-8"))
        except urllib.error.HTTPError as err:
            with err:
                return err.code, json.loads(err.read().decode("utf-8"))

    def get_ok(self, path, **params):
        status, data = self.request(path, **params)
        self.assertEqual(status, 200, data)
        return data

    def table_digest(self):
        digest = hashlib.sha256()
        with contextlib.closing(sqlite3.connect(self.db_path)) as con:
            for table in READ_TABLES:
                exists = con.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name=?", (table,)).fetchone()
                if not exists:
                    continue
                for row in con.execute("SELECT * FROM %s ORDER BY rowid" % table):
                    digest.update(repr(row).encode("utf-8"))
        return digest.hexdigest()

    def drop_tables(self, *tables):
        with contextlib.closing(sqlite3.connect(self.db_path)) as con:
            for table in tables:
                con.execute("DROP TABLE %s" % table)
            con.commit()

    # --- guild list ---

    def test_guild_list_counts_live_members_and_their_levels(self):
        data = self.get_ok("/api/admin/guilds")
        self.assertTrue(data["available"])
        self.assertEqual(data["total"], len(GUILDS) + FILLER_GUILDS)
        self.assertEqual(data["page"], 1)
        self.assertEqual(data["page_size"], 50)
        self.assertEqual(data["pages"], 1)
        by_id = {g["id"]: g for g in data["guilds"]}
        self.assertEqual([g["id"] for g in data["guilds"]], sorted(by_id))
        self.assertEqual(by_id[1], {"id": 1, "name": "Valkyrie", "level": 3, "member_count": 2, "total_level": 65})
        self.assertEqual(by_id[2], {"id": 2, "name": "Midgard Knights", "level": 5, "member_count": 1, "total_level": 60})
        self.assertEqual(by_id[3]["member_count"], 0)
        self.assertEqual(by_id[3]["total_level"], 0)
        self.assertIsNone(by_id[4]["level"])

    def test_guild_list_pages(self):
        first = self.get_ok("/api/admin/guilds", page=1, page_size=10)
        self.assertEqual((first["page"], first["page_size"], first["pages"]), (1, 10, 3))
        self.assertEqual([g["id"] for g in first["guilds"]], list(range(1, 11)))
        last = self.get_ok("/api/admin/guilds", page=3, page_size=10)
        self.assertEqual([g["id"] for g in last["guilds"]], list(range(21, 30)))
        beyond = self.get_ok("/api/admin/guilds", page=9, page_size=10)
        self.assertEqual(beyond["guilds"], [])
        self.assertEqual(beyond["total"], len(GUILDS) + FILLER_GUILDS)
        clamped = self.get_ok("/api/admin/guilds", page=0, page_size=100000)
        self.assertEqual((clamped["page"], clamped["page_size"]), (1, 200))
        junk = self.get_ok("/api/admin/guilds", page="x", page_size="y")
        self.assertEqual((junk["page"], junk["page_size"]), (1, 50))

    def test_guild_search_is_case_insensitive_literal_substring(self):
        data = self.get_ok("/api/admin/guilds", q="KNIGHT")
        self.assertEqual([g["id"] for g in data["guilds"]], [2])
        self.assertEqual(data["total"], 1)
        unicode = self.get_ok("/api/admin/guilds", q="ñandú")
        self.assertEqual([g["id"] for g in unicode["guilds"]], [3])
        wildcard = self.get_ok("/api/admin/guilds", q="%")
        self.assertEqual(wildcard["guilds"], [])
        self.assertEqual(wildcard["total"], 0)

    # --- guild detail ---

    def test_guild_detail_lists_live_members_only(self):
        data = self.get_ok("/api/admin/guilds/1")
        self.assertTrue(data["available"])
        self.assertEqual(data["guild"], {"id": 1, "name": "Valkyrie", "level": 3, "member_count": 2, "total_level": 65})
        self.assertEqual(data["members"], [
            {"role_id": 10, "name": "Leader", "account": "alpha", "career": 1200, "career_name": "Knight", "level": 40},
            {"role_id": 11, "name": "Second", "account": "alpha", "career": 2100, "career_name": "Magician", "level": 25},
        ])

    def test_guild_detail_unknown_career_uses_fallback_label(self):
        data = self.get_ok("/api/admin/guilds/2")
        self.assertEqual(data["members"][0]["career_name"], "Class 9999")

    def test_guild_detail_unknown_or_invalid_id_is_404(self):
        for path in ("/api/admin/guilds/999", "/api/admin/guilds/abc", "/api/admin/guilds/1;DROP",
                     "/api/admin/guilds/99999999999999999999999"):
            status, data = self.request(path)
            self.assertEqual(status, 404, path)
            self.assertEqual(data["error"], "Guild not found")

    # --- auctions ---

    def test_auction_lots_newest_first_with_verified_columns(self):
        data = self.get_ok("/api/admin/auctions")
        self.assertTrue(data["available"])
        self.assertEqual(data["view"], "lots")
        self.assertEqual(data["total"], 7)
        self.assertEqual([r["id"] for r in data["rows"]], [7, 6, 5, 4, 3, 2, 1])
        self.assertEqual(data["rows"][0], {
            "id": 7, "source_key": "src-7", "settled": True, "auction_type": 107,
            "run_id": 42, "end_time": 1700000007,
        })
        paged = self.get_ok("/api/admin/auctions", page=2, page_size=3)
        self.assertEqual([r["id"] for r in paged["rows"]], [4, 3, 2])
        self.assertEqual(paged["pages"], 3)

    def test_auction_prebuy_view_joins_role_name(self):
        data = self.get_ok("/api/admin/auctions", view="prebuy")
        self.assertEqual(data["view"], "prebuy")
        self.assertEqual(data["total"], 2)
        self.assertEqual(data["rows"], [
            {"id": 2, "role_id": 777, "role_name": None, "auction_type": 1, "src_type": 1, "item_id": 6001,
             "quantity": 1, "unit_price": 99, "currency": 1, "processed": True, "paused": False},
            {"id": 1, "role_id": 10, "role_name": "Leader", "auction_type": 2, "src_type": 3, "item_id": 5001,
             "quantity": 4, "unit_price": 250, "currency": 2, "processed": False, "paused": True},
        ])

    def test_auction_unknown_view_falls_back_to_lots(self):
        data = self.get_ok("/api/admin/auctions", view="nope")
        self.assertEqual(data["view"], "lots")

    def test_auction_lots_before_column_migration_report_null(self):
        with contextlib.closing(sqlite3.connect(self.db_path)) as con:
            con.execute("DROP TABLE auction_item")
            con.execute("CREATE TABLE auction_item (id INTEGER PRIMARY KEY AUTOINCREMENT,"
                        " source_key TEXT NOT NULL UNIQUE, state BLOB NOT NULL)")
            con.execute("INSERT INTO auction_item (id, source_key, state) VALUES (1, 'old', x'7b7d')")
            con.commit()
        data = self.get_ok("/api/admin/auctions")
        self.assertEqual(data["rows"], [{
            "id": 1, "source_key": "old", "settled": None, "auction_type": None, "run_id": None, "end_time": None,
        }])

    # --- missing tables ---

    def test_missing_guild_tables_report_unavailable(self):
        self.drop_tables("guild_member", "guild")
        data = self.get_ok("/api/admin/guilds")
        self.assertFalse(data["available"])
        self.assertEqual(data["guilds"], [])
        self.assertEqual(data["total"], 0)
        detail = self.get_ok("/api/admin/guilds/1")
        self.assertFalse(detail["available"])

    def test_missing_auction_tables_report_unavailable(self):
        self.drop_tables("auction_item", "auction_prebuy")
        for view in ("lots", "prebuy"):
            data = self.get_ok("/api/admin/auctions", view=view)
            self.assertFalse(data["available"])
            self.assertEqual(data["rows"], [])
            self.assertEqual(data["total"], 0)

    # --- auth and read-only ---

    def test_endpoints_require_auth(self):
        for path in ("/api/admin/guilds", "/api/admin/guilds/1", "/api/admin/auctions"):
            status, data = self.request(path, auth=False)
            self.assertEqual(status, 401, path)
            self.assertIn("error", data)

    def test_read_only_connection_refuses_writes(self):
        with server.get_db() as con:
            server.open_read_only(con)
            with self.assertRaises(sqlite3.OperationalError):
                con.execute("DELETE FROM guild")

    def test_requests_leave_tables_unchanged(self):
        before = self.table_digest()
        self.get_ok("/api/admin/guilds", q="a", page=2, page_size=5)
        self.get_ok("/api/admin/guilds/1")
        self.request("/api/admin/guilds/999")
        self.get_ok("/api/admin/auctions")
        self.get_ok("/api/admin/auctions", view="prebuy")
        self.assertEqual(self.table_digest(), before)


if __name__ == "__main__":
    unittest.main()
