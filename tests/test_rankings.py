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

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
import server

ADMIN_USER = "boss"
ADMIN_PASSWORD = "Pw-123456"


def power_blob(current_normal, current_season, history_normal=0, history_season=0):
    """Mirrors RO3Emu's EmblemService.EmblemState serialized with default System.Text.Json options."""
    state = {
        "Plans": {"0": {"Slots": {}, "Name": ""}},
        "CurrentPlan": 0,
        "HistorySeasonPower": 0,
        "Power": {
            "CurrentNormal": current_normal,
            "CurrentSeason": current_season,
            "HistoryNormal": history_normal,
            "HistorySeason": history_season,
        },
    }
    return json.dumps(state).encode("utf-8")


class RankingsAPITest(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory(ignore_cleanup_errors=True)
        self.addCleanup(tmp.cleanup)
        self.db_path = os.path.join(tmp.name, "ro3emu.db")

        # Register restoration of globals BEFORE mutating them.
        original_db_path = server.DB_PATH
        original_admins = server.CONFIG.get("admin_users")
        original_sessions = dict(server.ACTIVE_SESSIONS)

        def restore():
            server.DB_PATH = original_db_path
            server.CONFIG["admin_users"] = original_admins
            server.ACTIVE_SESSIONS.clear()
            server.ACTIVE_SESSIONS.update(original_sessions)

        self.addCleanup(restore)

        server.DB_PATH = self.db_path
        server.CONFIG["admin_users"] = [{"username": ADMIN_USER, "password": ADMIN_PASSWORD}]

        self.create_schema(with_guilds=True)
        server.init_tables()

        httpd = ThreadingHTTPServer(("127.0.0.1", 0), server.CPanelRequestHandler)
        thread = threading.Thread(target=httpd.serve_forever, daemon=True)
        thread.start()

        def stop_server():
            httpd.shutdown()
            httpd.server_close()
            thread.join(timeout=10)

        self.addCleanup(stop_server)
        self.base_url = "http://127.0.0.1:%d" % httpd.server_address[1]
        self.token = self.login()

    # --- Fixture helpers ---

    def create_schema(self, with_guilds):
        with contextlib.closing(sqlite3.connect(self.db_path)) as con:
            con.execute("CREATE TABLE account (name TEXT PRIMARY KEY, password_hash BLOB, salt BLOB, created_utc TEXT)")
            con.execute("CREATE TABLE auth_token (token TEXT PRIMARY KEY, account TEXT, kind TEXT, expires_utc TEXT)")
            con.execute("""
                CREATE TABLE role (
                    id INTEGER PRIMARY KEY,
                    account TEXT NOT NULL,
                    name TEXT NOT NULL,
                    sex INTEGER DEFAULT 1,
                    career INTEGER DEFAULT 1000,
                    level INTEGER DEFAULT 1,
                    job_level INTEGER DEFAULT 1,
                    exp INTEGER DEFAULT 0,
                    job_exp INTEGER DEFAULT 0,
                    stats TEXT DEFAULT '',
                    currency TEXT DEFAULT '',
                    deleted_time INTEGER NOT NULL DEFAULT 0,
                    emblems BLOB
                )
            """)
            if with_guilds:
                con.execute("CREATE TABLE guild (id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT NOT NULL UNIQUE COLLATE NOCASE, state BLOB NOT NULL)")
                con.execute("CREATE TABLE guild_member (role_id INTEGER PRIMARY KEY, guild_id INTEGER NOT NULL REFERENCES guild(id))")
            con.commit()

    def add_role(self, role_id, name, account="acc", career=1000, level=1, job_level=1, exp=0,
                 currency="", deleted_time=0, emblems=None):
        with contextlib.closing(sqlite3.connect(self.db_path)) as con:
            con.execute(
                "INSERT INTO role (id, account, name, career, level, job_level, exp, currency, deleted_time, emblems) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (role_id, account, name, career, level, job_level, exp, currency, deleted_time, emblems),
            )
            con.commit()

    def add_guild(self, guild_id, name, member_ids):
        with contextlib.closing(sqlite3.connect(self.db_path)) as con:
            con.execute("INSERT INTO guild (id, name, state) VALUES (?, ?, ?)", (guild_id, name, b"{}"))
            for role_id in member_ids:
                con.execute("INSERT INTO guild_member (role_id, guild_id) VALUES (?, ?)", (role_id, guild_id))
            con.commit()

    def drop_guild_tables(self):
        with contextlib.closing(sqlite3.connect(self.db_path)) as con:
            con.execute("DROP TABLE guild_member")
            con.execute("DROP TABLE guild")
            con.commit()

    # --- HTTP helpers ---

    def request(self, method, path, body=None, token=None):
        data = json.dumps(body).encode("utf-8") if body is not None else None
        req = urllib.request.Request(self.base_url + path, data=data, method=method)
        if data is not None:
            req.add_header("Content-Type", "application/json")
        if token:
            req.add_header("Authorization", "Bearer " + token)
        try:
            with urllib.request.urlopen(req, timeout=10) as resp:
                return resp.status, json.loads(resp.read().decode("utf-8"))
        except urllib.error.HTTPError as err:
            with err:
                return err.code, json.loads(err.read().decode("utf-8"))

    def login(self):
        status, data = self.request("POST", "/api/admin/login",
                                    {"username": ADMIN_USER, "password": ADMIN_PASSWORD})
        self.assertEqual(status, 200, data)
        return data["token"]

    def rankings(self, query):
        return self.request("GET", "/api/admin/rankings?" + query, token=self.token)

    # --- Tests ---

    def test_unauthenticated_request_is_rejected(self):
        status, data = self.request("GET", "/api/admin/rankings?type=level")
        self.assertEqual(status, 401)
        self.assertIn("error", data)

    def test_unknown_type_returns_400_in_spanish(self):
        status, data = self.rankings("type=pvp")
        self.assertEqual(status, 400)
        self.assertIn("Tipo de ranking inválido", data["error"])

    def test_level_ranking_orders_by_level_job_level_exp_and_excludes_deleted(self):
        self.add_role(1, "Low", level=10, job_level=5)
        self.add_role(2, "TopExp", account="other", career=1200, level=50, job_level=20, exp=900)
        self.add_role(3, "TopLessExp", level=50, job_level=20, exp=100)
        self.add_role(4, "HighJob", level=50, job_level=30, exp=0)
        self.add_role(5, "Deleted", level=99, job_level=50, deleted_time=1700000000)

        status, data = self.rankings("type=level")

        self.assertEqual(status, 200, data)
        self.assertEqual(data["type"], "level")
        self.assertEqual(data["total"], 4)
        self.assertEqual([r["name"] for r in data["rankings"]], ["HighJob", "TopExp", "TopLessExp", "Low"])
        self.assertEqual([r["rank"] for r in data["rankings"]], [1, 2, 3, 4])
        second = data["rankings"][1]
        self.assertEqual(second["id"], 2)
        self.assertEqual(second["account"], "other")
        self.assertEqual(second["career"], 1200)
        self.assertEqual(second["career_name"], "Knight")
        self.assertEqual(second["level"], 50)
        self.assertEqual(second["job_level"], 20)
        self.assertEqual(second["value"], 50)

    def test_unknown_career_uses_fallback_name(self):
        self.add_role(1, "Mystery", career=9999, level=5)
        status, data = self.rankings("type=level")
        self.assertEqual(status, 200, data)
        self.assertEqual(data["rankings"][0]["career_name"], "Clase 9999")

    def test_limit_and_page_paginate_with_global_rank(self):
        for i in range(1, 8):
            self.add_role(i, "Char%d" % i, level=100 - i)

        status, data = self.rankings("type=level&limit=3&page=2")

        self.assertEqual(status, 200, data)
        self.assertEqual(data["limit"], 3)
        self.assertEqual(data["page"], 2)
        self.assertEqual(data["total"], 7)
        self.assertEqual([r["name"] for r in data["rankings"]], ["Char4", "Char5", "Char6"])
        self.assertEqual([r["rank"] for r in data["rankings"]], [4, 5, 6])

    def test_limit_is_clamped_and_defaults_apply(self):
        for i in range(1, 4):
            self.add_role(i, "Char%d" % i, level=i)

        status, data = self.rankings("type=level&limit=1000&page=0")
        self.assertEqual(status, 200, data)
        self.assertEqual(data["limit"], 100)
        self.assertEqual(data["page"], 1)

        status, data = self.rankings("type=level&limit=0")
        self.assertEqual(data["limit"], 1)
        self.assertEqual(len(data["rankings"]), 1)

        status, data = self.rankings("type=level&limit=abc&page=xyz")
        self.assertEqual(status, 200, data)
        self.assertEqual(data["limit"], 20)
        self.assertEqual(data["page"], 1)

    def test_default_type_is_level(self):
        self.add_role(1, "Solo", level=3)
        status, data = self.rankings("")
        self.assertEqual(status, 200, data)
        self.assertEqual(data["type"], "level")

    def test_zeny_ranking_uses_currency_item_1_and_excludes_deleted(self):
        self.add_role(1, "Poor", currency="1:10,2:999999")
        self.add_role(2, "Rich", currency="2:5,1:5000")
        self.add_role(3, "Middle", currency="1:700")
        self.add_role(4, "Broke", currency="")
        self.add_role(5, "GoneRich", currency="1:99999999", deleted_time=1)
        self.add_role(6, "Garbage", currency="1:notanumber,oops")

        status, data = self.rankings("type=zeny")

        self.assertEqual(status, 200, data)
        self.assertEqual(data["type"], "zeny")
        names = [r["name"] for r in data["rankings"]]
        self.assertNotIn("GoneRich", names)
        self.assertEqual(names[:3], ["Rich", "Middle", "Poor"])
        self.assertEqual([r["value"] for r in data["rankings"]][:3], [5000, 700, 10])
        self.assertEqual(data["total"], 5)

    def test_power_ranking_reads_emblem_blob_and_skips_unparsable(self):
        self.add_role(1, "Weak", emblems=power_blob(100, 50))
        self.add_role(2, "Strong", emblems=power_blob(9000, 1000, 9500, 1200))
        self.add_role(3, "NeverPublished", emblems=json.dumps({"Plans": {}, "CurrentPlan": 0, "Power": None}).encode())
        self.add_role(4, "Corrupt", emblems=b"\xff\xfe not json")
        self.add_role(5, "NoBlob", emblems=None)
        self.add_role(6, "DeletedStrong", emblems=power_blob(99999, 0), deleted_time=1)
        self.add_role(7, "BadShape", emblems=json.dumps({"Power": {"CurrentNormal": "x"}}).encode())
        self.add_role(8, "JsonList", emblems=b"[1, 2, 3]")

        status, data = self.rankings("type=power")

        self.assertEqual(status, 200, data)
        self.assertEqual(data["type"], "power")
        self.assertEqual([r["name"] for r in data["rankings"]], ["Strong", "Weak"])
        self.assertEqual([r["value"] for r in data["rankings"]], [10000, 150])
        self.assertEqual(data["total"], 2)

    def test_guild_ranking_counts_active_members_and_summed_level(self):
        self.add_role(1, "A1", level=10)
        self.add_role(2, "A2", level=20)
        self.add_role(3, "B1", level=90)
        self.add_role(4, "B2", level=80)
        self.add_role(5, "B3gone", level=99, deleted_time=1)
        self.add_role(6, "C1", level=5)
        self.add_role(7, "C2", level=5)
        self.add_role(8, "C3", level=1)
        self.add_guild(1, "Alpha", [1, 2])
        self.add_guild(2, "Bravo", [3, 4, 5])
        self.add_guild(3, "Charlie", [6, 7, 8])

        status, data = self.rankings("type=guilds")

        self.assertEqual(status, 200, data)
        self.assertEqual(data["type"], "guilds")
        self.assertTrue(data["available"])
        self.assertEqual(data["total"], 3)
        rows = data["rankings"]
        # Member count first, summed level as tie-breaker; deleted characters do not count.
        self.assertEqual([r["name"] for r in rows], ["Charlie", "Bravo", "Alpha"])
        self.assertEqual([r["member_count"] for r in rows], [3, 2, 2])
        self.assertEqual([r["total_level"] for r in rows], [11, 170, 30])
        self.assertEqual([r["value"] for r in rows], [3, 2, 2])
        self.assertEqual([r["rank"] for r in rows], [1, 2, 3])
        self.assertEqual(rows[1]["id"], 2)

    def test_guild_ranking_without_guild_tables_returns_empty_not_500(self):
        self.drop_guild_tables()

        status, data = self.rankings("type=guilds")

        self.assertEqual(status, 200, data)
        self.assertEqual(data["rankings"], [])
        self.assertEqual(data["total"], 0)
        self.assertFalse(data["available"])


if __name__ == "__main__":
    unittest.main()
