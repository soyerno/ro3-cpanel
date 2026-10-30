import json
import os
import sqlite3
import sys
import tempfile
import threading
import time
import unittest
import urllib.error
import urllib.request
from contextlib import closing
from http.server import ThreadingHTTPServer

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
import server

# Table shapes from the RO3Emu gift-code contract (aethai/ro3emu-server docs/systems/gift-codes.md).
# The server creates them; the panel must never create or alter them.
GIFT_SCHEMA = """
    CREATE TABLE gift_code (
        code TEXT PRIMARY KEY COLLATE NOCASE,
        items TEXT NOT NULL,
        max_uses INTEGER NOT NULL DEFAULT 0,
        per_account INTEGER NOT NULL DEFAULT 1,
        starts_utc INTEGER,
        expires_utc INTEGER,
        disabled INTEGER NOT NULL DEFAULT 0,
        created_by TEXT,
        created_utc INTEGER NOT NULL DEFAULT (strftime('%s','now')),
        note TEXT
    );
    CREATE TABLE gift_code_redemption (
        redemption_key TEXT PRIMARY KEY,
        code TEXT NOT NULL,
        account TEXT NOT NULL,
        role_id INTEGER NOT NULL,
        redeemed_utc INTEGER NOT NULL
    );
"""
NOW = int(time.time())
HOUR = 3600


class GiftCodeTestCase(unittest.TestCase):
    with_gift_tables = True

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(ignore_cleanup_errors=True)
        self.addCleanup(self.tmp.cleanup)
        self.db_path = os.path.join(self.tmp.name, "ro3emu.db")
        with closing(sqlite3.connect(self.db_path)) as con:
            con.executescript("CREATE TABLE account (name TEXT PRIMARY KEY, password_hash BLOB, salt BLOB, created_utc TEXT);")
            if self.with_gift_tables:
                con.executescript(GIFT_SCHEMA)
        self.names_path = os.path.join(self.tmp.name, "items.json")
        with open(self.names_path, "w", encoding="utf-8") as f:
            json.dump({"10001": "Red Potion", "10002": "Blue Gem"}, f)
        self._saved = (server.DB_PATH, dict(server.CONFIG), dict(server.ITEM_NAMES_STATE))
        server.DB_PATH = self.db_path
        server.CONFIG["admin_users"] = [{"username": "boss", "password": "Pw-123456"}]
        server.CONFIG["item_names_file"] = self.names_path
        server.CONFIG["default_language"] = "en"
        server.ITEM_NAMES_STATE.update({"key": None, "names": None, "warned": set()})
        server.init_tables()
        self.httpd = ThreadingHTTPServer(("127.0.0.1", 0), server.CPanelRequestHandler)
        threading.Thread(target=self.httpd.serve_forever, daemon=True).start()
        self.base = "http://127.0.0.1:%d" % self.httpd.server_address[1]
        self.addCleanup(self._restore)
        self.token = self.call("POST", "/api/admin/login", {"username": "boss", "password": "Pw-123456"}, token=False)[1]["token"]

    def _restore(self):
        self.httpd.shutdown()
        self.httpd.server_close()
        server.DB_PATH = self._saved[0]
        server.CONFIG.clear()
        server.CONFIG.update(self._saved[1])
        server.ITEM_NAMES_STATE.clear()
        server.ITEM_NAMES_STATE.update(self._saved[2])
        server.ACTIVE_SESSIONS.clear()

    def call(self, method, path, payload=None, token=None, lang=None):
        headers = {"Content-Type": "application/json"}
        if token is None:
            token = self.token
        if token:
            headers["Authorization"] = "Bearer " + token
        if lang:
            headers["X-Panel-Lang"] = lang
        data = json.dumps(payload).encode() if payload is not None else None
        req = urllib.request.Request(self.base + path, data=data, method=method, headers=headers)
        try:
            with urllib.request.urlopen(req, timeout=10) as resp:
                return resp.status, json.loads(resp.read())
        except urllib.error.HTTPError as e:
            with e:
                return e.code, json.loads(e.read())

    def insert(self, code, items=None, **cols):
        row = {
            "code": code, "items": json.dumps(items if items is not None else [[10001, 5]]),
            "max_uses": 0, "per_account": 1, "starts_utc": None, "expires_utc": None,
            "disabled": 0, "created_by": "seed", "created_utc": NOW, "note": None,
        }
        row.update(cols)
        with closing(sqlite3.connect(self.db_path)) as con:
            con.execute(
                "INSERT INTO gift_code (code, items, max_uses, per_account, starts_utc, expires_utc, disabled,"
                " created_by, created_utc, note) VALUES (:code, :items, :max_uses, :per_account, :starts_utc,"
                " :expires_utc, :disabled, :created_by, :created_utc, :note)", row)
            con.commit()

    def redeem(self, code, account, n=1):
        with closing(sqlite3.connect(self.db_path)) as con:
            con.execute(
                "INSERT INTO gift_code_redemption VALUES (?, ?, ?, 1, ?)",
                ("giftcode:%d:%s:%d:%s" % (len(code), code, n, account), code, account, NOW))
            con.commit()

    def rows(self, sql, *args):
        with closing(sqlite3.connect(self.db_path)) as con:
            con.row_factory = sqlite3.Row
            return [dict(r) for r in con.execute(sql, args)]

    def audit(self):
        return self.rows("SELECT admin_user, action, target FROM admin_audit_log ORDER BY id")

    def tables(self):
        return {r["name"] for r in self.rows("SELECT name FROM sqlite_master WHERE type='table'")}

    def create(self, **overrides):
        body = {"code": "SPRING25", "items": [{"entry": 10001, "count": 5}], "max_uses": 100, "per_account": 1}
        body.update(overrides)
        return self.call("POST", "/api/admin/gift-codes", body)


class TestListGiftCodes(GiftCodeTestCase):
    def test_lists_codes_with_items_names_and_usage(self):
        self.insert("SPRING25", [[10001, 5], [20003, 1]], max_uses=10, per_account=2, note="spring event", created_utc=NOW - 10)
        self.redeem("SPRING25", "alice")
        self.redeem("SPRING25", "alice", n=2)
        self.redeem("SPRING25", "bob")
        status, body = self.call("GET", "/api/admin/gift-codes")
        self.assertEqual(status, 200)
        self.assertIs(body["available"], True)
        [row] = body["codes"]
        self.assertEqual(row["code"], "SPRING25")
        self.assertEqual(row["items"], [
            {"entry": 10001, "count": 5, "name": "Red Potion", "icon": None, "quality": None},
            {"entry": 20003, "count": 1, "name": None, "icon": None, "quality": None},
        ])
        self.assertEqual((row["max_uses"], row["per_account"], row["uses"]), (10, 2, 3))
        self.assertEqual((row["created_by"], row["note"], row["disabled"]), ("seed", "spring event", False))
        self.assertEqual(row["status"], "active")

    def test_newest_first(self):
        self.insert("OLD", created_utc=NOW - 100)
        self.insert("NEW", created_utc=NOW - 1)
        _, body = self.call("GET", "/api/admin/gift-codes")
        self.assertEqual([c["code"] for c in body["codes"]], ["NEW", "OLD"])

    def test_status_follows_dates_limit_and_disabled_flag(self):
        self.insert("ACTIVE", starts_utc=NOW - HOUR, expires_utc=NOW + HOUR)
        self.insert("OFF", disabled=1)
        self.insert("LATER", starts_utc=NOW + HOUR)
        self.insert("GONE", expires_utc=NOW - 1)
        self.insert("USEDUP", max_uses=1)
        self.redeem("USEDUP", "alice")
        self.insert("OFFANDGONE", disabled=1, expires_utc=NOW - 1)
        _, body = self.call("GET", "/api/admin/gift-codes")
        status = {c["code"]: c["status"] for c in body["codes"]}
        self.assertEqual(status, {
            "ACTIVE": "active", "OFF": "disabled", "LATER": "scheduled", "GONE": "expired",
            "USEDUP": "exhausted", "OFFANDGONE": "disabled",
        })

    def test_unlimited_codes_are_never_exhausted(self):
        self.insert("FREE", max_uses=0)
        for i in range(5):
            self.redeem("FREE", "acc%d" % i)
        _, body = self.call("GET", "/api/admin/gift-codes")
        self.assertEqual((body["codes"][0]["uses"], body["codes"][0]["status"]), (5, "active"))

    def test_row_with_malformed_items_is_listed_without_rewards(self):
        self.insert("BROKEN")
        with closing(sqlite3.connect(self.db_path)) as con:
            con.execute("UPDATE gift_code SET items='not json' WHERE code='BROKEN'")
            con.commit()
        status, body = self.call("GET", "/api/admin/gift-codes")
        self.assertEqual(status, 200)
        self.assertEqual(body["codes"][0]["items"], [])

    def test_missing_tables_report_unavailable_in_the_request_language(self):
        with closing(sqlite3.connect(self.db_path)) as con:
            con.executescript("DROP TABLE gift_code; DROP TABLE gift_code_redemption;")
        _, en = self.call("GET", "/api/admin/gift-codes")
        _, es = self.call("GET", "/api/admin/gift-codes", lang="es")
        self.assertEqual(en["available"], False)
        self.assertEqual(en["reason"], "Update RO3Emu: this server does not support gift codes")
        self.assertEqual(es["reason"], "Actualice RO3Emu: este servidor no admite códigos de regalo")
        self.assertNotIn("gift_code", self.tables())

    def test_missing_redemption_table_counts_zero_uses(self):
        self.insert("SPRING25")
        with closing(sqlite3.connect(self.db_path)) as con:
            con.execute("DROP TABLE gift_code_redemption")
            con.commit()
        _, body = self.call("GET", "/api/admin/gift-codes")
        self.assertEqual((body["available"], body["codes"][0]["uses"]), (True, 0))


class TestCreateGiftCode(GiftCodeTestCase):
    def test_creates_a_row_exactly_as_the_server_contract_reads_it(self):
        start, end = NOW + HOUR, NOW + 2 * HOUR
        status, body = self.create(code="  Spring25  ", items=[{"entry": 10001, "count": 5}, {"entry": 10002, "count": 1}],
                                   max_uses=100, per_account=2, starts_utc=start, expires_utc=end, note="  spring  ")
        self.assertEqual(status, 200)
        self.assertEqual((body["success"], body["code"]), (True, "Spring25"))
        [row] = self.rows("SELECT * FROM gift_code")
        self.assertEqual(row["code"], "Spring25")
        self.assertEqual(json.loads(row["items"]), [[10001, 5], [10002, 1]])
        self.assertEqual((row["max_uses"], row["per_account"]), (100, 2))
        self.assertEqual((row["starts_utc"], row["expires_utc"], row["disabled"]), (start, end, 0))
        self.assertEqual((row["created_by"], row["note"]), ("boss", "spring"))
        self.assertLessEqual(abs(row["created_utc"] - int(time.time())), 10)  # not NOW: it is fixed at import
        self.assertEqual(self.audit()[-1], {"admin_user": "boss", "action": "gift_code_create", "target": "Spring25"})

    def test_defaults_match_the_contract(self):
        status, _ = self.call("POST", "/api/admin/gift-codes", {"code": "MINIMAL", "items": [{"entry": 10001, "count": 1}]})
        self.assertEqual(status, 200)
        [row] = self.rows("SELECT max_uses, per_account, starts_utc, expires_utc, note FROM gift_code")
        self.assertEqual(row, {"max_uses": 0, "per_account": 1, "starts_utc": None, "expires_utc": None, "note": None})

    def test_rejects_invalid_input_and_writes_nothing(self):
        cases = {
            "empty code": {"code": "   "},
            "code too long": {"code": "X" * 65},
            "code not a string": {"code": 12345},
            "no items": {"items": []},
            "items not a list": {"items": "10001"},
            "item not an object": {"items": [[10001, 5]]},
            "entry not an int": {"items": [{"entry": "10001", "count": 5}]},
            "entry is a bool": {"items": [{"entry": True, "count": 5}]},
            "entry zero": {"items": [{"entry": 0, "count": 5}]},
            "count zero": {"items": [{"entry": 10001, "count": 0}]},
            "count negative": {"items": [{"entry": 10001, "count": -1}]},
            "count float": {"items": [{"entry": 10001, "count": 1.5}]},
            "max uses negative": {"max_uses": -1},
            "max uses not an int": {"max_uses": "10"},
            "per account zero": {"per_account": 0},
            "start not an int": {"starts_utc": "tomorrow"},
            "expiry before start": {"starts_utc": NOW + HOUR, "expires_utc": NOW},
            "expiry equals start": {"starts_utc": NOW + HOUR, "expires_utc": NOW + HOUR},
            "note not a string": {"note": 5},
            "max uses beyond SQLite integers": {"max_uses": 10 ** 30},
            "item count beyond SQLite integers": {"items": [{"entry": 10001, "count": 2 ** 63}]},
            "expiry beyond SQLite integers": {"expires_utc": 2 ** 63},
        }
        for name, override in cases.items():
            with self.subTest(name):
                status, body = self.create(**override)
                self.assertEqual(status, 400, body)
                self.assertIn("error", body)
        self.assertEqual(self.rows("SELECT * FROM gift_code"), [])

    def test_code_is_unique_ignoring_case(self):
        self.assertEqual(self.create(code="Spring25")[0], 200)
        status, body = self.create(code="SPRING25")
        self.assertEqual(status, 409)
        self.assertEqual(body["error"], "The gift code 'SPRING25' already exists")
        self.assertEqual(len(self.rows("SELECT * FROM gift_code")), 1)

    def test_missing_table_is_refused_and_never_created(self):
        with closing(sqlite3.connect(self.db_path)) as con:
            con.executescript("DROP TABLE gift_code; DROP TABLE gift_code_redemption;")
        status, body = self.create()
        self.assertEqual(status, 503)
        self.assertEqual(body["error"], "Update RO3Emu: this server does not support gift codes")
        self.assertNotIn("gift_code", self.tables())

    def test_errors_follow_the_request_language(self):
        status, body = self.call("POST", "/api/admin/gift-codes", {"code": "", "items": []}, lang="es")
        self.assertEqual(status, 400)
        self.assertEqual(body["error"], "El código debe tener entre 1 y 64 caracteres")

    def test_panel_never_writes_redemptions(self):
        self.create()
        self.assertEqual(self.rows("SELECT * FROM gift_code_redemption"), [])


class TestToggleGiftCode(GiftCodeTestCase):
    def test_disable_then_enable_flips_the_flag_and_audits(self):
        self.insert("SPRING25")
        status, body = self.call("POST", "/api/admin/gift-codes/disable", {"code": "spring25"})
        self.assertEqual((status, body["success"]), (200, True))
        self.assertEqual(self.rows("SELECT disabled FROM gift_code")[0]["disabled"], 1)
        status, _ = self.call("POST", "/api/admin/gift-codes/enable", {"code": "SPRING25"})
        self.assertEqual(status, 200)
        self.assertEqual(self.rows("SELECT disabled FROM gift_code")[0]["disabled"], 0)
        self.assertEqual(
            [(a["action"], a["target"]) for a in self.audit() if a["action"].startswith("gift_code")],
            [("gift_code_disable", "SPRING25"), ("gift_code_enable", "SPRING25")],
        )

    def test_toggle_changes_nothing_else(self):
        self.insert("SPRING25", [[10001, 5]], max_uses=7, note="keep")
        before = self.rows("SELECT code, items, max_uses, per_account, starts_utc, expires_utc, created_by, created_utc, note FROM gift_code")
        self.call("POST", "/api/admin/gift-codes/disable", {"code": "SPRING25"})
        self.call("POST", "/api/admin/gift-codes/enable", {"code": "SPRING25"})
        after = self.rows("SELECT code, items, max_uses, per_account, starts_utc, expires_utc, created_by, created_utc, note FROM gift_code")
        self.assertEqual(before, after)

    def test_unknown_code_is_404_and_audits_nothing(self):
        for action in ("disable", "enable"):
            status, body = self.call("POST", "/api/admin/gift-codes/" + action, {"code": "NOPE"})
            self.assertEqual(status, 404)
            self.assertEqual(body["error"], "The gift code 'NOPE' does not exist")
        self.assertEqual([a for a in self.audit() if a["action"].startswith("gift_code")], [])

    def test_missing_code_field_is_400(self):
        status, _ = self.call("POST", "/api/admin/gift-codes/disable", {})
        self.assertEqual(status, 400)


class TestMissingTableToggle(GiftCodeTestCase):
    with_gift_tables = False

    def test_toggle_without_tables_is_503(self):
        for action in ("disable", "enable"):
            status, body = self.call("POST", "/api/admin/gift-codes/" + action, {"code": "X"})
            self.assertEqual(status, 503)
            self.assertEqual(body["error"], "Update RO3Emu: this server does not support gift codes")
        self.assertNotIn("gift_code", self.tables())


class TestGiftCodeAuth(GiftCodeTestCase):
    def test_every_endpoint_requires_an_admin_session(self):
        self.insert("SPRING25")
        for method, path, payload in (
            ("GET", "/api/admin/gift-codes", None),
            ("POST", "/api/admin/gift-codes", {"code": "A", "items": [{"entry": 1, "count": 1}]}),
            ("POST", "/api/admin/gift-codes/disable", {"code": "SPRING25"}),
            ("POST", "/api/admin/gift-codes/enable", {"code": "SPRING25"}),
        ):
            with self.subTest(path=path):
                status, _ = self.call(method, path, payload, token=False)
                self.assertEqual(status, 401)
        self.assertEqual(self.rows("SELECT disabled FROM gift_code")[0]["disabled"], 0)
        self.assertEqual(len(self.rows("SELECT * FROM gift_code")), 1)


if __name__ == "__main__":
    unittest.main()
