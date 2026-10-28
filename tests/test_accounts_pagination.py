"""HTTP-level tests for server-side pagination of GET /api/admin/accounts (issue #4)."""

import contextlib
import json
import math
import os
import sqlite3
import sys
import tempfile
import threading
import unittest
import urllib.parse
import urllib.request
from http.server import ThreadingHTTPServer
from unittest import mock

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
import server

ADMIN_USER = "boss"
ADMIN_PASS = "Pw-123456"

# (name, created_utc, banned, tokens, [(role_name, deleted_time), ...])
NAMED_ACCOUNTS = [
    ("alpha", "2024-01-01T00:00:00Z", False, 2, [("Knight_One", 0), ("Ghost", 1700000000)]),
    ("Bravo", "2024-02-01T00:00:00Z", True, 0, [("mage%x", 0), ("Archer", 0)]),
    ("charlie", "2024-03-01T00:00:00Z", False, 1, []),
    ("delta_1", "2024-04-01T00:00:00Z", False, 0, [("Zed", 0)]),
    ("echo", None, False, 0, [("Hidden", 5)]),
    ("Ñandú", "2024-05-01T00:00:00Z", True, 0, [("Pájaro", 0)]),
]
FILLER_COUNT = 55


def build_dataset():
    accounts = list(NAMED_ACCOUNTS)
    for i in range(FILLER_COUNT):
        roles = [("hero%03d_%d" % (i, k), 0) for k in range(i % 3)]
        accounts.append(("zz%03d" % i, "2023-%02d-%02dT00:00:00Z" % (1 + i % 12, 1 + i % 28), i % 7 == 0, i % 2, roles))
    return accounts


DATASET = build_dataset()


def reference_names(q="", status="all", sort="created_desc"):
    """Pure-Python model of the pre-pagination handle_accounts_list filtering and sorting."""
    q = q.strip().lower()
    status = status.strip().lower()
    rows = []
    for name, created, banned, _tokens, roles in DATASET:
        live = [r for r, deleted in roles if deleted == 0]
        if status == "banned" and not banned:
            continue
        if status == "active" and banned:
            continue
        if q and not (q in name.lower() or any(q in r.lower() for r in live)):
            continue
        rows.append({"name": name, "created_utc": created, "character_count": len(live)})
    if sort == "name_asc":
        rows.sort(key=lambda x: x["name"].lower())
    elif sort == "created_asc":
        rows.sort(key=lambda x: x.get("created_utc") or "")
    elif sort == "chars_desc":
        rows.sort(key=lambda x: x["character_count"], reverse=True)
    else:
        rows.sort(key=lambda x: x.get("created_utc") or "", reverse=True)
    return rows


def sort_key(sort, row):
    if sort == "name_asc":
        return row["name"].lower()
    if sort == "chars_desc":
        return row["character_count"]
    return row.get("created_utc") or ""


class AccountsPaginationTest(unittest.TestCase):
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
            con.execute("CREATE TABLE auth_token (token TEXT, kind TEXT, account TEXT, expires_utc TEXT)")
            con.execute(
                """CREATE TABLE role (
                    id INTEGER PRIMARY KEY AUTOINCREMENT, account TEXT, name TEXT, sex INTEGER,
                    career INTEGER, level INTEGER, job_level INTEGER, last_login_time INTEGER,
                    create_time INTEGER, currency TEXT, stats TEXT, scene_entry INTEGER,
                    pos_x REAL, pos_y REAL, pos_z REAL, deleted_time INTEGER DEFAULT 0)"""
            )
            con.commit()

        server.DB_PATH = self.db_path
        server.CONFIG = dict(server.CONFIG)
        server.CONFIG["admin_users"] = [{"username": ADMIN_USER, "password": ADMIN_PASS}]
        server.ACTIVE_SESSIONS = {}
        server.init_tables()

        with contextlib.closing(sqlite3.connect(self.db_path)) as con:
            for idx, (name, created, banned, tokens, roles) in enumerate(DATASET):
                con.execute("INSERT INTO account (name, password_hash, salt, created_utc) VALUES (?, x'00', x'00', ?)", (name, created))
                for t in range(tokens):
                    con.execute("INSERT INTO auth_token VALUES (?, 'session', ?, '2099-01-01')", ("tok-%s-%d" % (name, t), name))
                for k, (role_name, deleted) in enumerate(roles):
                    con.execute(
                        "INSERT INTO role (account, name, sex, career, level, job_level, last_login_time, create_time,"
                        " currency, stats, scene_entry, pos_x, pos_y, pos_z, deleted_time)"
                        " VALUES (?, ?, 1, 1000, 10, 5, ?, 1700000000, '2:100', '1,2,3,4,5,6', 10100, 1.0, 2.0, 3.0, ?)",
                        (name, role_name, 1700000000 + idx * 10 + k, deleted),
                    )
                if banned:
                    con.execute("INSERT INTO admin_account_meta (name, is_banned, ban_reason) VALUES (?, 1, 'test')", (name,))
            con.commit()

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

    def _login(self):
        req = urllib.request.Request(
            self.base + "/api/admin/login",
            data=json.dumps({"username": ADMIN_USER, "password": ADMIN_PASS}).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=10) as resp:
            return json.loads(resp.read().decode("utf-8"))["token"]

    def get_accounts(self, **params):
        url = self.base + "/api/admin/accounts"
        if params:
            url += "?" + urllib.parse.urlencode(params)
        req = urllib.request.Request(url, headers={"Authorization": "Bearer " + self.token})
        with urllib.request.urlopen(req, timeout=10) as resp:
            self.assertEqual(resp.status, 200)
            return json.loads(resp.read().decode("utf-8"))

    def names(self, data):
        return [a["name"] for a in data["accounts"]]

    # --- pagination ---

    def test_default_request_returns_first_page_of_50(self):
        data = self.get_accounts()
        self.assertEqual(data["total"], len(DATASET))
        self.assertEqual(data["page"], 1)
        self.assertEqual(data["page_size"], 50)
        self.assertEqual(data["pages"], 2)
        expected = [r["name"] for r in reference_names()][:50]
        self.assertEqual(self.names(data), expected)

    def test_page_and_page_size_slice_the_sorted_result(self):
        ref = [r["name"] for r in reference_names(sort="name_asc")]
        expected_pages = math.ceil(len(ref) / 7)
        collected = []
        for page in range(1, expected_pages + 1):
            data = self.get_accounts(sort="name_asc", page=page, page_size=7)
            self.assertEqual(data["page"], page)
            self.assertEqual(data["page_size"], 7)
            self.assertEqual(data["pages"], expected_pages)
            self.assertEqual(data["total"], len(ref))
            self.assertEqual(self.names(data), ref[(page - 1) * 7:page * 7])
            collected.extend(self.names(data))
        self.assertEqual(collected, ref)

    def test_page_beyond_last_returns_empty_list_with_totals(self):
        data = self.get_accounts(page=99, page_size=10)
        self.assertEqual(data["accounts"], [])
        self.assertEqual(data["total"], len(DATASET))
        self.assertEqual(data["pages"], math.ceil(len(DATASET) / 10))
        self.assertEqual(data["page"], 99)

    def test_pages_is_at_least_one_when_nothing_matches(self):
        data = self.get_accounts(q="no-such-account-anywhere")
        self.assertEqual(data["accounts"], [])
        self.assertEqual(data["total"], 0)
        self.assertEqual(data["pages"], 1)

    def test_invalid_page_params_fall_back_to_defaults(self):
        for params, page, page_size in [
            ({"page": "abc", "page_size": "xyz"}, 1, 50),
            ({"page": "0"}, 1, 50),
            ({"page": "-4"}, 1, 50),
            ({"page_size": "0"}, 1, 1),
            ({"page_size": "-10"}, 1, 1),
            ({"page_size": "100000"}, 1, 200),
            ({"page": "1.5", "page_size": ""}, 1, 50),
            ({"page": str(10 ** 30)}, 10 ** 30, 50),
        ]:
            with self.subTest(params=params):
                data = self.get_accounts(**params)
                self.assertEqual(data["page"], page)
                self.assertEqual(data["page_size"], page_size)
                self.assertEqual(data["total"], len(DATASET))
                self.assertLessEqual(len(data["accounts"]), page_size)

    def test_total_counts_all_matches_not_just_the_page(self):
        ref = reference_names(status="active")
        data = self.get_accounts(status="active", page_size=5)
        self.assertEqual(data["total"], len(ref))
        self.assertEqual(len(data["accounts"]), 5)
        self.assertEqual(data["pages"], math.ceil(len(ref) / 5))

    # --- filters ---

    def test_q_matches_account_name_case_insensitive(self):
        data = self.get_accounts(q="BRAV", page_size=200)
        self.assertEqual(self.names(data), ["Bravo"])

    def test_q_matches_live_character_name(self):
        data = self.get_accounts(q="knight", page_size=200)
        self.assertEqual(self.names(data), ["alpha"])

    def test_q_ignores_deleted_characters(self):
        self.assertEqual(self.get_accounts(q="ghost", page_size=200)["total"], 0)
        self.assertEqual(self.get_accounts(q="hidden", page_size=200)["total"], 0)

    def test_q_treats_like_wildcards_literally(self):
        self.assertEqual(self.names(self.get_accounts(q="%", page_size=200)), ["Bravo"])
        self.assertEqual(self.names(self.get_accounts(q="a_1", page_size=200)), ["delta_1"])
        self.assertEqual(self.get_accounts(q="\\", page_size=200)["total"], 0)

    def test_q_lowercases_non_ascii_like_python(self):
        self.assertEqual(self.names(self.get_accounts(q="ÑAN", page_size=200)), ["Ñandú"])
        self.assertEqual(self.names(self.get_accounts(q="pájaro", page_size=200)), ["Ñandú"])

    def test_status_filters(self):
        banned = self.get_accounts(status="banned", page_size=200)
        self.assertTrue(banned["accounts"])
        self.assertTrue(all(a["is_banned"] for a in banned["accounts"]))
        self.assertEqual(set(self.names(banned)), {r["name"] for r in reference_names(status="banned")})
        active = self.get_accounts(status="active", page_size=200)
        self.assertTrue(all(not a["is_banned"] for a in active["accounts"]))
        self.assertEqual(banned["total"] + active["total"], len(DATASET))

    # --- sorting ---

    def test_each_sort_order(self):
        for sort in ["name_asc", "created_asc", "chars_desc", "created_desc", "bogus"]:
            with self.subTest(sort=sort):
                data = self.get_accounts(sort=sort, page_size=200)
                rows = [{"name": a["name"], "created_utc": a["created_utc"], "character_count": a["character_count"]}
                        for a in data["accounts"]]
                ref = reference_names(sort=sort)
                self.assertEqual([sort_key(sort, r) for r in rows], [sort_key(sort, r) for r in ref])

    def test_sort_is_stable_across_pages(self):
        full = self.names(self.get_accounts(sort="chars_desc", page_size=200))
        first = self.get_accounts(sort="chars_desc", page=1, page_size=10)
        paged = self.names(first)
        for page in range(2, first["pages"] + 1):
            paged.extend(self.names(self.get_accounts(sort="chars_desc", page=page, page_size=10)))
        self.assertEqual(paged, full)

    def test_existing_q_status_sort_semantics_preserved(self):
        for q in ["", "a", "zz00", "hero", "%"]:
            for status in ["all", "banned", "active", "weird"]:
                for sort in ["created_desc", "name_asc", "created_asc", "chars_desc"]:
                    with self.subTest(q=q, status=status, sort=sort):
                        data = self.get_accounts(q=q, status=status, sort=sort, page_size=200)
                        ref = reference_names(q=q, status=status, sort=sort)
                        self.assertEqual(set(self.names(data)), {r["name"] for r in ref})
                        self.assertEqual(data["total"], len(ref))
                        self.assertEqual(
                            [sort_key(sort, a) for a in data["accounts"]],
                            [sort_key(sort, r) for r in ref],
                        )

    # --- response shape ---

    def test_account_entries_keep_their_shape(self):
        data = self.get_accounts(q="alpha")
        acc = data["accounts"][0]
        self.assertEqual(acc["name"], "alpha")
        self.assertEqual(acc["character_count"], 1)
        self.assertEqual([c["name"] for c in acc["characters"]], ["Knight_One"])
        self.assertEqual(acc["active_tokens"], 2)
        self.assertFalse(acc["is_admin"])
        self.assertFalse(acc["is_banned"])
        self.assertIsNotNone(acc["last_login"])
        char = acc["characters"][0]
        for key in ["id", "name", "sex", "career", "career_name", "level", "job_level", "currency",
                    "stats", "scene_id", "scene_name", "pos", "last_login", "created_at"]:
            self.assertIn(key, char)
        for key in ["created_utc", "ban_reason", "banned_at", "notes"]:
            self.assertIn(key, acc)

    def test_account_detail_still_formats_characters(self):
        req = urllib.request.Request(self.base + "/api/admin/accounts/Bravo",
                                     headers={"Authorization": "Bearer " + self.token})
        with urllib.request.urlopen(req, timeout=10) as resp:
            detail = json.loads(resp.read().decode("utf-8"))
        self.assertEqual([c["name"] for c in detail["characters"]], ["mage%x", "Archer"])
        char = detail["characters"][0]
        self.assertEqual(list(char.keys()), [
            "id", "name", "sex", "career", "career_name", "level", "job_level", "exp", "job_exp",
            "currency", "stats", "bonus_points", "scene_id", "scene_name", "pos", "last_login", "created_at",
        ])

    # --- bounded work per request ---

    def test_rows_materialized_do_not_depend_on_account_count(self):
        counter = {"rows": 0}
        lock = threading.Lock()
        original_get_db = server.get_db

        def counting_row(cursor, row):
            with lock:
                counter["rows"] += 1
            return sqlite3.Row(cursor, row)

        def counting_get_db():
            con = original_get_db()
            con.row_factory = counting_row
            return con

        with mock.patch.object(server, "get_db", counting_get_db):
            self.get_accounts(page_size=5)
        # page rows + their roles (<= 2 live each) + token rows + count row
        self.assertLessEqual(counter["rows"], 5 + 5 * 2 + 5 + 2)


if __name__ == "__main__":
    unittest.main()
