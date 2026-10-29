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
from contextlib import closing
from datetime import datetime, timedelta, timezone
from http.server import ThreadingHTTPServer

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
import server

# Table shapes of the web player portal (konsor-ro3 windows/player_api.py init_vault_tables). The panel only reads them.
VAULT_DDL = """
CREATE TABLE account_vip (account TEXT PRIMARY KEY COLLATE NOCASE, is_vip INTEGER NOT NULL DEFAULT 1, vip_until TEXT, created_utc TEXT NOT NULL);
CREATE TABLE account_vault (
    id INTEGER PRIMARY KEY AUTOINCREMENT, account TEXT NOT NULL COLLATE NOCASE, entry INTEGER NOT NULL,
    stack INTEGER NOT NULL DEFAULT 1, pack INTEGER NOT NULL DEFAULT 1, attrs TEXT, enchantments TEXT,
    is_locked INTEGER NOT NULL DEFAULT 0, str_attrs TEXT, bind_type INTEGER NOT NULL DEFAULT 0,
    bind_expire INTEGER NOT NULL DEFAULT 0, deposited_by_role_id INTEGER, deposited_by_name TEXT, deposited_utc TEXT NOT NULL
);
"""
MARKET_DDL = """
CREATE TABLE web_market (
    id INTEGER PRIMARY KEY AUTOINCREMENT, seller_account TEXT NOT NULL COLLATE NOCASE, seller_role_id INTEGER NOT NULL,
    seller_role_name TEXT NOT NULL, entry INTEGER NOT NULL, stack INTEGER NOT NULL DEFAULT 1, pack INTEGER NOT NULL DEFAULT 1,
    price_zeny INTEGER NOT NULL DEFAULT 0, attrs TEXT DEFAULT '', enchantments TEXT DEFAULT '', is_locked INTEGER NOT NULL DEFAULT 0,
    str_attrs TEXT DEFAULT '', bind_type INTEGER NOT NULL DEFAULT 0, bind_expire INTEGER NOT NULL DEFAULT 0,
    status TEXT NOT NULL DEFAULT 'active', buyer_account TEXT COLLATE NOCASE, buyer_role_id INTEGER, buyer_role_name TEXT,
    created_utc TEXT NOT NULL, updated_utc TEXT NOT NULL
);
CREATE TABLE web_market_claim (
    id INTEGER PRIMARY KEY AUTOINCREMENT, account TEXT NOT NULL COLLATE NOCASE, role_id INTEGER NOT NULL, role_name TEXT NOT NULL,
    amount_zeny INTEGER NOT NULL DEFAULT 0, market_id INTEGER NOT NULL, item_name TEXT NOT NULL, is_claimed INTEGER NOT NULL DEFAULT 0,
    created_utc TEXT NOT NULL, claimed_utc TEXT
);
"""


class VaultMarketTestCase(unittest.TestCase):
    with_vault = True
    with_market = True

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(ignore_cleanup_errors=True)
        self.addCleanup(self.tmp.cleanup)
        self.db_path = os.path.join(self.tmp.name, "ro3emu.db")
        with closing(sqlite3.connect(self.db_path)) as con:
            con.executescript("""
                CREATE TABLE account (name TEXT PRIMARY KEY, password_hash BLOB, salt BLOB, created_utc TEXT);
                CREATE TABLE admin_gm (account TEXT PRIMARY KEY, added_utc TEXT);
                INSERT INTO account VALUES ('alice', x'00', x'00', '2026-01-01');
                INSERT INTO account VALUES ('bob', x'00', x'00', '2026-01-01');
                INSERT INTO account VALUES ('Ñandú', x'00', x'00', '2026-01-01');
            """)
            if self.with_vault:
                con.executescript(VAULT_DDL)
            if self.with_market:
                con.executescript(MARKET_DDL)
            con.commit()
        self.names_path = os.path.join(self.tmp.name, "items.json")
        with open(self.names_path, "w", encoding="utf-8") as f:
            json.dump({"5001": "Red Potion", "5002": "Blue Gem", "5003": "Poción 100%"}, f)
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
        self.token = self.call("/api/admin/login", {"username": "boss", "password": "Pw-123456"}, token=False)[1]["token"]

    def _restore(self):
        self.httpd.shutdown()
        self.httpd.server_close()
        server.DB_PATH = self._saved[0]
        server.CONFIG.clear()
        server.CONFIG.update(self._saved[1])
        server.ITEM_NAMES_STATE.clear()
        server.ITEM_NAMES_STATE.update(self._saved[2])
        server.ACTIVE_SESSIONS.clear()

    def call(self, path, payload=None, token=None, lang=None):
        headers = {"Content-Type": "application/json"}
        if token is None:
            token = self.token
        if token:
            headers["Authorization"] = "Bearer " + token
        if lang:
            headers["X-Panel-Lang"] = lang
        data = json.dumps(payload).encode() if payload is not None else None
        req = urllib.request.Request(self.base + path, data=data, method="POST" if data is not None else "GET", headers=headers)
        try:
            with urllib.request.urlopen(req, timeout=10) as resp:
                return resp.status, json.loads(resp.read())
        except urllib.error.HTTPError as e:
            with e:
                return e.code, json.loads(e.read())

    def sql(self, statement, *args):
        with closing(sqlite3.connect(self.db_path)) as con:
            con.execute(statement, args)
            con.commit()

    def snapshot(self):
        """Every row of every table except the panel's own session/audit tables, to prove nothing was written."""
        with closing(sqlite3.connect(self.db_path)) as con:
            tables = sorted(r[0] for r in con.execute("SELECT name FROM sqlite_master WHERE type='table'"))
            return {
                t: con.execute("SELECT * FROM %s" % t).fetchall()
                for t in tables
                if t not in ("admin_session", "admin_audit_log", "sqlite_sequence")
            }


def vault_row(account, entry, **kw):
    return (account, entry, kw.get("stack", 1), kw.get("pack", 1), kw.get("locked", 0), kw.get("by", "pj1"), kw.get("when", "2026-10-29 10:00:00"))


class TestAccountVault(VaultMarketTestCase):
    def add_item(self, account, entry, **kw):
        self.sql(
            "INSERT INTO account_vault (account, entry, stack, pack, is_locked, deposited_by_role_id, deposited_by_name, deposited_utc)"
            " VALUES (?, ?, ?, ?, ?, 7, ?, ?)",
            *vault_row(account, entry, **kw),
        )

    def vault(self, account="alice", query="", **kw):
        return self.call("/api/admin/accounts/%s/vault%s" % (urllib.parse.quote(account), query), **kw)

    def test_lists_the_items_of_that_account_only_newest_first(self):
        self.add_item("alice", 5001, stack=5, pack=1)
        self.add_item("ALICE", 5002, stack=1, pack=2, locked=1, by="pj2", when="2026-10-29 11:00:00")
        self.add_item("bob", 5003)
        status, body = self.vault()
        self.assertEqual(status, 200)
        self.assertIs(body["available"], True)
        self.assertEqual((body["account"], body["total"], body["page"], body["pages"], body["page_size"]), ("alice", 2, 1, 1, 50))
        self.assertEqual([i["entry"] for i in body["items"]], [5002, 5001])
        first, second = body["items"]
        self.assertEqual(second["name"], "Red Potion")
        self.assertEqual((second["stack"], second["pack"], second["pack_name"], second["locked"]), (5, 1, "Items", False))
        self.assertEqual((first["locked"], first["deposited_by_name"], first["deposited_by_role_id"]), (True, "pj2", 7))
        self.assertEqual(first["deposited_utc"], "2026-10-29 11:00:00")
        self.assertEqual(set(first), {"id", "entry", "name", "stack", "pack", "pack_name", "locked", "bind_type", "bind_expire",
                                      "deposited_by_name", "deposited_by_role_id", "deposited_utc"})

    def test_an_item_without_a_known_name_has_a_null_name(self):
        self.add_item("alice", 9999)
        self.assertIsNone(self.vault()[1]["items"][0]["name"])

    def test_paging(self):
        for i in range(7):
            self.add_item("alice", 5001, when="2026-10-29 10:00:0%d" % i)
        _, p1 = self.vault(query="?page=1&page_size=3")
        _, p3 = self.vault(query="?page=3&page_size=3")
        _, p9 = self.vault(query="?page=9&page_size=3")
        self.assertEqual((len(p1["items"]), p1["pages"], p1["total"]), (3, 3, 7))
        self.assertEqual(len(p3["items"]), 1)
        self.assertEqual((p9["items"], p9["total"], p9["pages"]), ([], 7, 3))

    def test_a_non_ascii_account_name_works(self):
        self.add_item("Ñandú", 5001)
        status, body = self.vault("Ñandú")
        self.assertEqual((status, body["total"]), (200, 1))

    def test_unknown_account_is_404(self):
        status, body = self.vault("nobody")
        self.assertEqual((status, body["error"]), (404, "Account not found"))

    def test_vip_status_precedence_and_expiry(self):
        future = (datetime.now(timezone.utc) + timedelta(days=3)).strftime("%Y-%m-%dT%H:%M:%SZ")
        past = (datetime.now(timezone.utc) - timedelta(days=3)).strftime("%Y-%m-%dT%H:%M:%SZ")
        self.assertEqual(self.vault("alice")[1]["vip"], {"is_vip": False, "vip_until": None, "source": "none"})
        self.sql("INSERT INTO account_vip VALUES ('alice', 1, NULL, '2026-10-01')")
        self.assertEqual(self.vault("alice")[1]["vip"], {"is_vip": True, "vip_until": None, "source": "vip"})
        self.sql("UPDATE account_vip SET vip_until = ? WHERE account = 'alice'", future)
        self.assertEqual(self.vault("alice")[1]["vip"], {"is_vip": True, "vip_until": future, "source": "vip"})
        self.sql("UPDATE account_vip SET vip_until = ? WHERE account = 'alice'", past)
        self.assertEqual(self.vault("alice")[1]["vip"], {"is_vip": False, "vip_until": None, "source": "none"})
        self.sql("UPDATE account_vip SET vip_until = NULL, is_vip = 0 WHERE account = 'alice'")
        self.assertIs(self.vault("alice")[1]["vip"]["is_vip"], False)
        self.sql("INSERT INTO admin_gm VALUES ('ALICE', '2026-10-28')")
        self.assertEqual(self.vault("alice")[1]["vip"], {"is_vip": True, "vip_until": None, "source": "gm"})

    def test_a_vip_note_counts(self):
        self.sql("INSERT INTO admin_account_meta (name, notes) VALUES ('bob', 'friend [vip] of the staff')")
        self.assertEqual(self.vault("bob")[1]["vip"], {"is_vip": True, "vip_until": None, "source": "note"})

    def test_a_gm_wins_over_an_expired_vip_row(self):
        self.sql("INSERT INTO account_vip VALUES ('alice', 1, '2020-01-01T00:00:00Z', '2020-01-01')")
        self.sql("INSERT INTO admin_gm VALUES ('alice', '2026-10-28')")
        self.assertEqual(self.vault("alice")[1]["vip"]["source"], "gm")

    def test_requires_an_admin_session(self):
        self.assertEqual(self.vault(token=False)[0], 401)

    def test_it_only_reads(self):
        self.add_item("alice", 5001)
        before = self.snapshot()
        self.vault()
        self.vault("bob", "?page=2")
        self.assertEqual(self.snapshot(), before)


class TestAccountVaultUnavailable(VaultMarketTestCase):
    with_vault = False

    def test_without_the_vault_table_it_says_so_and_creates_nothing(self):
        tables_before = set(self.snapshot())
        status, body = self.call("/api/admin/accounts/alice/vault")
        self.assertEqual(status, 200)
        self.assertIs(body["available"], False)
        self.assertEqual(body["reason"], "The account vault is not available yet: the web player portal creates it the first time it runs")
        self.assertEqual((body["items"], body["total"], body["pages"]), ([], 0, 1))
        self.assertEqual(body["vip"], {"is_vip": False, "vip_until": None, "source": "none"})
        self.assertEqual(set(self.snapshot()), tables_before)
        _, es = self.call("/api/admin/accounts/alice/vault", lang="es")
        self.assertEqual(es["reason"], "La bóveda de la cuenta todavía no está disponible: el portal web de jugadores la crea la primera vez que se ejecuta")

    def test_a_gm_is_still_reported_as_vip(self):
        self.sql("INSERT INTO admin_gm VALUES ('alice', '2026-10-28')")
        self.assertEqual(self.call("/api/admin/accounts/alice/vault")[1]["vip"]["source"], "gm")


def listing(seller, entry, price, status="active", **kw):
    return (
        seller, kw.get("role_id", 1), kw.get("role", "pj_" + seller), entry, kw.get("stack", 1), kw.get("pack", 1), price,
        kw.get("locked", 0), status, kw.get("buyer"), kw.get("buyer_role"), kw.get("created", "2026-10-29 09:00:00"),
        kw.get("updated", "2026-10-29 09:30:00"),
    )


class TestWebMarket(VaultMarketTestCase):
    def add_listing(self, *args, **kw):
        self.sql(
            "INSERT INTO web_market (seller_account, seller_role_id, seller_role_name, entry, stack, pack, price_zeny, is_locked,"
            " status, buyer_account, buyer_role_name, created_utc, updated_utc) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)",
            *listing(*args, **kw),
        )

    def market(self, query="", **kw):
        return self.call("/api/admin/market" + query, **kw)

    def seed(self):
        self.add_listing("alice", 5001, 1000, created="2026-10-29 09:00:01")
        self.add_listing("bob", 5002, 2500, created="2026-10-29 09:00:02")
        self.add_listing("alice", 5001, 700, "sold", buyer="bob", buyer_role="Buyer_Char", created="2026-10-28 09:00:00")
        self.add_listing("bob", 5003, 300, "cancelled", created="2026-10-27 09:00:00")

    def test_default_is_active_newest_first_with_the_summary_of_everything(self):
        self.seed()
        self.sql("INSERT INTO web_market_claim (account, role_id, role_name, amount_zeny, market_id, item_name, is_claimed, created_utc)"
                 " VALUES ('alice', 1, 'pj_alice', 700, 3, 'Red Potion', 0, '2026-10-28')")
        self.sql("INSERT INTO web_market_claim (account, role_id, role_name, amount_zeny, market_id, item_name, is_claimed, created_utc)"
                 " VALUES ('alice', 1, 'pj_alice', 111, 9, 'Old', 1, '2026-10-20')")
        status, body = self.market()
        self.assertEqual(status, 200)
        self.assertIs(body["available"], True)
        self.assertEqual(body["status"], "active")
        self.assertEqual([l["entry"] for l in body["listings"]], [5002, 5001])
        self.assertEqual(body["summary"], {"active": 2, "sold": 1, "cancelled": 1, "active_zeny": 3500, "sold_zeny": 700,
                                          "pending_claims": 1, "pending_zeny": 700})
        self.assertEqual((body["total"], body["page"], body["pages"], body["page_size"]), (2, 1, 1, 50))

    def test_a_row_has_the_contract_fields(self):
        self.add_listing("alice", 5001, 1000, "sold", buyer="bob", buyer_role="pj_bob", stack=5, pack=2, locked=1)
        row = self.market("?status=sold")[1]["listings"][0]
        self.assertEqual(row["name"], "Red Potion")
        self.assertEqual((row["seller_account"], row["seller_role_name"], row["buyer_account"], row["buyer_role_name"]),
                         ("alice", "pj_alice", "bob", "pj_bob"))
        self.assertEqual((row["stack"], row["pack"], row["pack_name"], row["price_zeny"], row["locked"], row["status"]),
                         (5, 2, "Equipment", 1000, True, "sold"))
        self.assertEqual(set(row), {"id", "seller_account", "seller_role_id", "seller_role_name", "entry", "name", "stack", "pack",
                                    "pack_name", "price_zeny", "locked", "status", "buyer_account", "buyer_role_name",
                                    "created_utc", "updated_utc"})

    def test_status_filter(self):
        self.seed()
        self.assertEqual(len(self.market("?status=sold")[1]["listings"]), 1)
        self.assertEqual(len(self.market("?status=cancelled")[1]["listings"]), 1)
        all_rows = self.market("?status=all")[1]
        self.assertEqual((all_rows["total"], len(all_rows["listings"])), (4, 4))

    def test_an_unknown_status_is_a_400(self):
        status, body = self.market("?status=hacked")
        self.assertEqual(status, 400)
        self.assertEqual(body["error"], "Invalid market status. Allowed values: active, sold, cancelled, all")

    def test_search_matches_people_and_item_names_literally(self):
        self.seed()
        entries = lambda q: sorted(l["entry"] for l in self.market("?status=all&q=" + urllib.parse.quote(q))[1]["listings"])
        self.assertEqual(entries("ALICE"), [5001, 5001])           # seller account, any case
        self.assertEqual(entries("buyer_char"), [5001])            # buyer character, any case
        self.assertEqual(entries("pj_bob"), [5002, 5003])  # the seller character of bob's two listings
        self.assertEqual(entries("blue"), [5002])                  # item name from item_names_file
        self.assertEqual(entries("5003"), [5003])                  # item id
        self.assertEqual(entries("100%"), [5003])                  # a % is a literal character, not a wildcard
        self.assertEqual(entries("%"), [5003])
        self.assertEqual(entries("nothing like this"), [])

    def test_paging_and_page_size_cap(self):
        for i in range(5):
            self.add_listing("alice", 5001, 100 + i)
        _, p2 = self.market("?page=2&page_size=2")
        _, p9 = self.market("?page=9&page_size=2")
        _, big = self.market("?page_size=100000")
        self.assertEqual((len(p2["listings"]), p2["pages"], p2["total"]), (2, 3, 5))
        self.assertEqual((p9["listings"], p9["total"]), ([], 5))
        self.assertEqual(big["page_size"], server.LIST_PAGE_SIZE_MAX)

    def test_invalid_numbers_are_sanitized(self):
        self.seed()
        for query in ("?page=abc", "?page=-4", "?page_size=abc", "?page_size=0"):
            with self.subTest(query=query):
                status, body = self.market(query)
                self.assertEqual(status, 200)
                self.assertGreaterEqual(body["page"], 1)

    def test_requires_an_admin_session(self):
        self.assertEqual(self.market(token=False)[0], 401)

    def test_it_only_reads(self):
        self.seed()
        before = self.snapshot()
        self.market("?status=all&q=alice")
        self.market("?status=sold&page=3")
        self.assertEqual(self.snapshot(), before)

    def test_without_the_claim_table_pending_is_zero(self):
        self.seed()
        self.sql("DROP TABLE web_market_claim")
        summary = self.market()[1]["summary"]
        self.assertEqual((summary["pending_claims"], summary["pending_zeny"]), (0, 0))
        self.assertEqual(summary["active"], 2)


class TestWebMarketUnavailable(VaultMarketTestCase):
    with_market = False

    def test_without_the_market_table_it_says_so_and_creates_nothing(self):
        tables_before = set(self.snapshot())
        status, body = self.call("/api/admin/market")
        self.assertEqual(status, 200)
        self.assertIs(body["available"], False)
        self.assertEqual(body["reason"], "The web market is not available yet: the web player portal creates it the first time it runs")
        self.assertEqual((body["listings"], body["total"], body["pages"]), ([], 0, 1))
        self.assertEqual(set(body["summary"]), {"active", "sold", "cancelled", "active_zeny", "sold_zeny", "pending_claims", "pending_zeny"})
        self.assertEqual(set(self.snapshot()), tables_before)
        _, es = self.call("/api/admin/market", lang="es")
        self.assertEqual(es["reason"], "El mercado web todavía no está disponible: el portal web de jugadores lo crea la primera vez que se ejecuta")


if __name__ == "__main__":
    unittest.main()
