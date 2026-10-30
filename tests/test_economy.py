"""HTTP-level tests for the read-only economy log viewer (GET /api/admin/economy).

The fixture schema for economy_entry / operation_receipt mirrors the upstream RO3Emu DDL in
src/Ro3Emu.Server/Accounts/Persistence/EconomySchemaPlan.cs (aethai/ro3emu-server).
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
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from http.server import ThreadingHTTPServer

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
import server

ADMIN_USER = "boss"
ADMIN_PASS = "Pw-123456"

BASE_SCHEMA = """
CREATE TABLE account (
    name TEXT PRIMARY KEY,
    password_hash BLOB,
    salt BLOB,
    created_utc TEXT
);
CREATE TABLE auth_token (
    token TEXT PRIMARY KEY,
    account TEXT,
    kind TEXT,
    expires_utc TEXT
);
CREATE TABLE role (
    id INTEGER PRIMARY KEY,
    account TEXT NOT NULL,
    name TEXT NOT NULL,
    deleted_time INTEGER DEFAULT 0
);
"""

# Verbatim column set from upstream EconomySchemaPlan.cs (CREATE TABLE operation_receipt / economy_entry).
ECONOMY_SCHEMA = """
CREATE TABLE operation_receipt (
    operation_id TEXT PRIMARY KEY,
    realm_id TEXT NOT NULL,
    commit_seq INTEGER NOT NULL UNIQUE,
    actor_account TEXT NOT NULL,
    actor_role INTEGER NOT NULL,
    command_kind TEXT NOT NULL,
    request_fingerprint TEXT NOT NULL,
    intent_hash TEXT NOT NULL,
    intent_payload BLOB NOT NULL,
    source_key TEXT NOT NULL UNIQUE,
    recorded_utc_ms INTEGER NOT NULL,
    effective_utc_ms INTEGER NOT NULL,
    outcome BLOB NOT NULL,
    child_receipts BLOB NOT NULL,
    before_revisions TEXT NOT NULL,
    after_revisions TEXT NOT NULL,
    leg_count INTEGER NOT NULL CHECK(leg_count>=0 AND (command_kind<>'npc-shop-buy' OR leg_count>0))
);
CREATE TABLE economy_entry (
    entry_id INTEGER PRIMARY KEY AUTOINCREMENT,
    commit_seq INTEGER NOT NULL,
    operation_id TEXT NOT NULL,
    leg_no INTEGER NOT NULL,
    recorded_utc_ms INTEGER NOT NULL,
    effective_utc_ms INTEGER NOT NULL,
    owner_kind INTEGER NOT NULL,
    owner_id TEXT NOT NULL,
    compartment_kind INTEGER NOT NULL,
    compartment_key TEXT NOT NULL,
    instance_key TEXT NOT NULL,
    asset_kind INTEGER NOT NULL,
    asset_id INTEGER NOT NULL,
    asset_epoch TEXT NOT NULL,
    delta INTEGER NOT NULL,
    reason_code INTEGER NOT NULL,
    leg_kind INTEGER NOT NULL,
    edge_no INTEGER NOT NULL,
    counterparty_owner_kind INTEGER,
    counterparty_owner_id TEXT,
    counterparty_compartment_kind INTEGER,
    counterparty_compartment_key TEXT,
    counterparty_instance_key TEXT,
    before_fingerprint TEXT,
    after_fingerprint TEXT,
    source_key TEXT NOT NULL,
    UNIQUE(operation_id,leg_no),
    FOREIGN KEY(operation_id) REFERENCES operation_receipt(operation_id)
);
"""


def utc_ms(iso):
    return int(datetime.fromisoformat(iso).replace(tzinfo=timezone.utc).timestamp() * 1000)


# (operation_id, commit_seq, actor_account, actor_role, command_kind, recorded_utc_ms)
RECEIPTS = [
    ("op-1", 1, "alice", 10, "npc-shop-buy", utc_ms("2026-01-01T10:00:00")),
    ("op-2", 2, "bob", 11, "mail-claim", utc_ms("2026-01-02T00:00:00")),
    ("op-3", 3, "carol", 12, "trade", utc_ms("2026-01-03T23:59:59.999")),
    ("op-4", 4, "alice", 10, "guild-donate", utc_ms("2026-01-04T00:00:00")),
    ("op-5", 5, "o'brien", 13, "npc-shop-buy", utc_ms("2026-01-05T12:00:00")),
]

# (operation_id, leg_no, owner_kind, owner_id, asset_kind, asset_id, delta, reason_code)
ENTRIES = [
    ("op-1", 0, 1, "10", 2, 1, -500, 10),     # Alice pays 500 Zeny
    ("op-1", 1, 1, "10", 1, 501, 1, 9),       # Alice gets item 501
    ("op-2", 0, 1, "11", 2, 1, 1000, 25),     # Bob claims 1000 Zeny
    ("op-3", 0, 1, "12", 1, 700, -1, 28),     # Carol trades away item 700
    ("op-4", 0, 1, "10", 3, 1, -50, 34),      # Alice spends guild money
    ("op-4", 1, 1, "11", 2, 1, 50, 34),       # leg owned by Bob inside Alice's operation
    ("op-5", 0, 1, "13", 2, 1, -10, 10),      # O'Brien pays 10 Zeny
]

ROLES = [
    (10, "alice", "Alice"),
    (11, "bob", "Bob"),
    (12, "carol", "Carol"),
    (13, "o'brien", "O'Brien"),
]


class EconomyApiTestBase(unittest.TestCase):
    with_economy = True

    def setUp(self):
        tmp = tempfile.TemporaryDirectory(ignore_cleanup_errors=True)
        self.addCleanup(tmp.cleanup)
        self.db_path = os.path.join(tmp.name, "ro3emu.db")

        # Register restores BEFORE mutating module state.
        self.addCleanup(setattr, server, "DB_PATH", server.DB_PATH)
        self.addCleanup(setattr, server, "CONFIG", server.CONFIG)
        self.addCleanup(setattr, server, "ACTIVE_SESSIONS", server.ACTIVE_SESSIONS)

        self._build_db()

        server.DB_PATH = self.db_path
        server.CONFIG = dict(server.CONFIG)
        server.CONFIG["admin_users"] = [{"username": ADMIN_USER, "password": ADMIN_PASS}]
        server.ACTIVE_SESSIONS = {}
        server.init_tables()

        httpd = ThreadingHTTPServer(("127.0.0.1", 0), server.CPanelRequestHandler)
        thread = threading.Thread(target=httpd.serve_forever, daemon=True)
        thread.start()
        self.addCleanup(httpd.server_close)
        self.addCleanup(httpd.shutdown)
        self.base_url = "http://127.0.0.1:%d" % httpd.server_address[1]
        self.token = self._login()

    def _build_db(self):
        with contextlib.closing(sqlite3.connect(self.db_path)) as con:
            con.executescript(BASE_SCHEMA)
            con.executemany("INSERT INTO role (id, account, name) VALUES (?, ?, ?)", ROLES)
            if self.with_economy:
                con.executescript(ECONOMY_SCHEMA)
                for op_id, seq, account, role, kind, recorded in RECEIPTS:
                    legs = sum(1 for e in ENTRIES if e[0] == op_id)
                    con.execute(
                        "INSERT INTO operation_receipt (operation_id, realm_id, commit_seq, actor_account, actor_role,"
                        " command_kind, request_fingerprint, intent_hash, intent_payload, source_key, recorded_utc_ms,"
                        " effective_utc_ms, outcome, child_receipts, before_revisions, after_revisions, leg_count)"
                        " VALUES (?, 'realm', ?, ?, ?, ?, 'fp', 'ih', X'', ?, ?, ?, X'', X'', '', '', ?)",
                        (op_id, seq, account, role, kind, "src-" + op_id, recorded, recorded, legs),
                    )
                recorded_by_op = {r[0]: (r[1], r[5]) for r in RECEIPTS}
                for op_id, leg_no, owner_kind, owner_id, asset_kind, asset_id, delta, reason in ENTRIES:
                    seq, recorded = recorded_by_op[op_id]
                    con.execute(
                        "INSERT INTO economy_entry (commit_seq, operation_id, leg_no, recorded_utc_ms, effective_utc_ms,"
                        " owner_kind, owner_id, compartment_kind, compartment_key, instance_key, asset_kind, asset_id,"
                        " asset_epoch, delta, reason_code, leg_kind, edge_no, source_key)"
                        " VALUES (?, ?, ?, ?, ?, ?, ?, 2, 'k', '', ?, ?, '', ?, ?, 3, 0, ?)",
                        (seq, op_id, leg_no, recorded, recorded, owner_kind, owner_id, asset_kind, asset_id,
                         delta, reason, "src-" + op_id),
                    )
            con.commit()

    def _login(self):
        req = urllib.request.Request(
            self.base_url + "/api/admin/login",
            data=json.dumps({"username": ADMIN_USER, "password": ADMIN_PASS}).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=10) as resp:
            return json.loads(resp.read().decode("utf-8"))["token"]

    def get(self, params=None, token="default"):
        url = self.base_url + "/api/admin/economy"
        if params:
            url += "?" + urllib.parse.urlencode(params)
        headers = {}
        if token == "default":
            token = self.token
        if token:
            headers["Authorization"] = "Bearer " + token
        req = urllib.request.Request(url, headers=headers)
        try:
            with urllib.request.urlopen(req, timeout=10) as resp:
                return resp.status, json.loads(resp.read().decode("utf-8"))
        except urllib.error.HTTPError as err:
            body = err.read().decode("utf-8")
            err.close()
            return err.code, json.loads(body)

    def snapshot_economy(self):
        with contextlib.closing(sqlite3.connect(self.db_path)) as con:
            entries = con.execute("SELECT * FROM economy_entry ORDER BY entry_id").fetchall()
            receipts = con.execute("SELECT * FROM operation_receipt ORDER BY operation_id").fetchall()
        return entries, receipts


class TestEconomyApi(EconomyApiTestBase):
    def test_unauthenticated_request_is_rejected(self):
        status, body = self.get(token=None)
        self.assertEqual(status, 401)
        self.assertIn("error", body)

    def test_lists_all_entries_newest_first_with_default_paging(self):
        status, body = self.get()
        self.assertEqual(status, 200)
        self.assertTrue(body["available"])
        self.assertEqual(body["total"], len(ENTRIES))
        self.assertEqual(body["page"], 1)
        self.assertEqual(body["page_size"], 50)
        self.assertEqual(body["pages"], 1)
        ids = [e["entry_id"] for e in body["entries"]]
        self.assertEqual(ids, sorted(ids, reverse=True))
        self.assertEqual(len(ids), len(ENTRIES))

    def test_entry_shape_and_labels(self):
        status, body = self.get({"account": "bob"})
        self.assertEqual(status, 200)
        self.assertEqual(len(body["entries"]), 1)
        entry = body["entries"][0]
        self.assertEqual(entry["operation_id"], "op-2")
        self.assertEqual(entry["command_kind"], "mail-claim")
        self.assertEqual(entry["actor_account"], "bob")
        self.assertEqual(entry["actor_role"], 11)
        self.assertEqual(entry["actor_role_name"], "Bob")
        self.assertEqual(entry["owner_kind"], 1)
        self.assertEqual(entry["owner_id"], "11")
        self.assertEqual(entry["owner_name"], "Bob")
        self.assertEqual(entry["owner_account"], "bob")
        self.assertEqual(entry["asset_kind"], 2)
        self.assertEqual(entry["asset_id"], 1)
        self.assertEqual(entry["asset_label"], "Zeny")
        self.assertEqual(entry["delta"], 1000)
        self.assertEqual(entry["reason_code"], 25)
        self.assertEqual(entry["recorded_utc"], "2026-01-02T00:00:00.000+00:00")

    def test_non_zeny_asset_is_not_labelled_zeny(self):
        status, body = self.get({"account": "carol"})
        self.assertEqual(status, 200)
        self.assertEqual(body["entries"][0]["asset_kind"], 1)
        self.assertNotEqual(body["entries"][0]["asset_label"], "Zeny")

    def test_account_filter_is_exact_and_case_insensitive(self):
        status, body = self.get({"account": "ALICE"})
        self.assertEqual(status, 200)
        self.assertEqual(body["total"], 4)
        self.assertEqual({e["operation_id"] for e in body["entries"]}, {"op-1", "op-4"})
        status, body = self.get({"account": "ali"})
        self.assertEqual(body["total"], 0)

    def test_character_filter_matches_actor_role_or_owned_leg(self):
        status, body = self.get({"character": "bob"})
        self.assertEqual(status, 200)
        # op-2 (Bob is the actor) plus the op-4 leg owned by Bob.
        self.assertEqual(body["total"], 2)
        self.assertEqual({(e["operation_id"], e["owner_id"]) for e in body["entries"]},
                         {("op-2", "11"), ("op-4", "11")})

    def test_character_filter_unknown_name_returns_empty(self):
        status, body = self.get({"character": "Nobody"})
        self.assertEqual(status, 200)
        self.assertEqual(body["total"], 0)
        self.assertEqual(body["entries"], [])

    def test_combined_filters(self):
        status, body = self.get({"account": "alice", "character": "Bob"})
        self.assertEqual(status, 200)
        self.assertEqual(body["total"], 1)
        self.assertEqual(body["entries"][0]["operation_id"], "op-4")

    def test_date_range_bounds_are_inclusive_days(self):
        status, body = self.get({"from": "2026-01-02", "to": "2026-01-03"})
        self.assertEqual(status, 200)
        # op-2 at exactly 00:00:00.000 is in; op-3 at 23:59:59.999 is in; op-4 at 01-04 00:00 is out.
        self.assertEqual({e["operation_id"] for e in body["entries"]}, {"op-2", "op-3"})

    def test_from_only_and_to_only(self):
        status, body = self.get({"from": "2026-01-04"})
        self.assertEqual({e["operation_id"] for e in body["entries"]}, {"op-4", "op-5"})
        status, body = self.get({"to": "2026-01-01"})
        self.assertEqual({e["operation_id"] for e in body["entries"]}, {"op-1"})

    def test_invalid_dates_return_400(self):
        for params in ({"from": "2026-13-01"}, {"to": "abc"}, {"from": "2026/01/01"}, {"to": "2026-02-30"}):
            status, body = self.get(params)
            self.assertEqual(status, 400, params)
            self.assertIn("date", body["error"].lower())

    def test_pagination_math(self):
        status, body = self.get({"page_size": 3})
        self.assertEqual(body["total"], 7)
        self.assertEqual(body["pages"], 3)
        self.assertEqual(len(body["entries"]), 3)
        self.assertEqual([e["entry_id"] for e in body["entries"]], [7, 6, 5])
        status, body = self.get({"page_size": 3, "page": 2})
        self.assertEqual([e["entry_id"] for e in body["entries"]], [4, 3, 2])
        status, body = self.get({"page_size": 3, "page": 3})
        self.assertEqual(body["page"], 3)
        self.assertEqual([e["entry_id"] for e in body["entries"]], [1])
        status, body = self.get({"page_size": 3, "page": 9})
        self.assertEqual(body["entries"], [])

    def test_page_and_page_size_are_clamped(self):
        status, body = self.get({"page_size": 0, "page": 0})
        self.assertEqual((body["page"], body["page_size"]), (1, 1))
        self.assertEqual(body["pages"], 7)
        status, body = self.get({"page_size": 5000})
        self.assertEqual(body["page_size"], 200)
        status, body = self.get({"page_size": "abc", "page": "-x"})
        self.assertEqual((body["page"], body["page_size"]), (1, 50))

    def test_injection_like_input_is_treated_literally(self):
        status, body = self.get({"account": "x' OR '1'='1"})
        self.assertEqual(status, 200)
        self.assertEqual(body["total"], 0)
        status, body = self.get({"character": "' OR 1=1 --"})
        self.assertEqual(status, 200)
        self.assertEqual(body["total"], 0)
        status, body = self.get({"account": "O'Brien"})
        self.assertEqual(body["total"], 1)
        self.assertEqual(body["entries"][0]["operation_id"], "op-5")
        status, body = self.get({"character": "o'brien"})
        self.assertEqual(body["total"], 1)

    def test_requests_never_modify_economy_tables(self):
        before = self.snapshot_economy()
        self.get()
        self.get({"account": "x'; DELETE FROM economy_entry; --"})
        self.get({"character": "'); DROP TABLE operation_receipt; --"})
        self.get({"from": "2026-01-01", "to": "2026-12-31", "page": 2, "page_size": 2})
        self.get({"from": "bad"})
        self.assertEqual(self.snapshot_economy(), before)


class TestEconomyApiWithoutEconomyTables(EconomyApiTestBase):
    with_economy = False

    def test_missing_tables_report_unavailable(self):
        status, body = self.get({"account": "alice", "from": "2026-01-01"})
        self.assertEqual(status, 200)
        self.assertFalse(body["available"])
        self.assertEqual(body["entries"], [])
        self.assertEqual(body["total"], 0)


if __name__ == "__main__":
    unittest.main()
