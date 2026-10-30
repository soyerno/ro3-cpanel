"""Admin VIP toggle: POST /api/admin/accounts/vip writes the web portal's account_vip table."""

import os
import sqlite3
import sys
import unittest
from contextlib import closing
from datetime import datetime, timedelta, timezone

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
import server
from test_vault_market import VaultMarketTestCase

VIP_PATH = "/api/admin/accounts/vip"


def iso(delta):
    return (datetime.now(timezone.utc) + delta).strftime("%Y-%m-%dT%H:%M:%SZ")


class AccountVipTestCase(VaultMarketTestCase):
    with_market = False

    def rows(self, statement, *args):
        with closing(sqlite3.connect(self.db_path)) as con:
            return con.execute(statement, args).fetchall()

    def vip_row(self, account):
        rows = self.rows("SELECT account, is_vip, vip_until, created_utc FROM account_vip WHERE account = ?", account)
        return rows[0] if rows else None

    def audit(self, action):
        return self.rows("SELECT admin_user, target, details FROM admin_audit_log WHERE action = ?", action)


class TestGrantVip(AccountVipTestCase):
    def test_grant_creates_a_permanent_vip_row_and_audits_it(self):
        status, body = self.call(VIP_PATH, {"username": "alice", "vip": True})
        self.assertEqual(status, 200, body)
        self.assertTrue(body["success"])
        self.assertEqual(body["vip"], {"is_vip": True, "vip_until": None, "source": "vip"})
        account, is_vip, until, created = self.vip_row("alice")
        self.assertEqual((account, is_vip, until), ("alice", 1, None))
        self.assertRegex(created, r"^\d{4}-\d\d-\d\dT\d\d:\d\d:\d\dZ$")
        self.assertEqual(self.audit("vip_grant"), [("boss", "alice", "VIP granted by admin")])

    def test_grant_re_enables_a_disabled_row_and_keeps_its_creation_date(self):
        self.sql("INSERT INTO account_vip VALUES ('alice', 0, NULL, '2026-01-02T03:04:05Z')")
        status, body = self.call(VIP_PATH, {"username": "alice", "vip": True})
        self.assertEqual(status, 200, body)
        self.assertEqual(self.vip_row("alice"), ("alice", 1, None, "2026-01-02T03:04:05Z"))

    def test_grant_keeps_a_future_expiry(self):
        until = iso(timedelta(days=10))
        self.sql("INSERT INTO account_vip VALUES ('alice', 0, ?, '2026-01-02T03:04:05Z')", until)
        status, body = self.call(VIP_PATH, {"username": "alice", "vip": True})
        self.assertEqual(status, 200, body)
        self.assertEqual(self.vip_row("alice")[1:3], (1, until))
        self.assertEqual(body["vip"]["vip_until"], until)

    def test_grant_clears_an_expired_expiry_so_the_vip_becomes_permanent(self):
        self.sql("INSERT INTO account_vip VALUES ('alice', 1, ?, '2026-01-02T03:04:05Z')", iso(timedelta(days=-1)))
        status, body = self.call(VIP_PATH, {"username": "alice", "vip": True})
        self.assertEqual(status, 200, body)
        self.assertEqual(self.vip_row("alice")[1:3], (1, None))
        self.assertEqual(body["vip"]["source"], "vip")

    def test_row_matches_the_account_case_insensitively(self):
        self.sql("INSERT INTO account_vip VALUES ('ALICE', 0, NULL, '2026-01-02T03:04:05Z')")
        status, body = self.call(VIP_PATH, {"username": "alice", "vip": True})
        self.assertEqual(status, 200, body)
        self.assertEqual(self.rows("SELECT COUNT(*), MAX(is_vip) FROM account_vip"), [(1, 1)])


class TestRevokeVip(AccountVipTestCase):
    def test_revoke_disables_the_row_and_audits_it(self):
        until = iso(timedelta(days=10))
        self.sql("INSERT INTO account_vip VALUES ('alice', 1, ?, '2026-01-02T03:04:05Z')", until)
        status, body = self.call(VIP_PATH, {"username": "alice", "vip": False})
        self.assertEqual(status, 200, body)
        self.assertEqual(body["vip"]["source"], "none")
        self.assertFalse(body["vip"]["is_vip"])
        self.assertEqual(self.vip_row("alice"), ("alice", 0, until, "2026-01-02T03:04:05Z"))
        self.assertEqual(self.audit("vip_revoke"), [("boss", "alice", "VIP revoked by admin")])

    def test_revoke_without_a_row_writes_a_disabled_row_so_the_portal_does_not_re_grant(self):
        status, body = self.call(VIP_PATH, {"username": "bob", "vip": False})
        self.assertEqual(status, 200, body)
        self.assertEqual(self.vip_row("bob")[1:3], (0, None))


class TestVipTableMissing(AccountVipTestCase):
    with_vault = False

    def test_the_table_is_created_with_the_portal_schema(self):
        self.assertEqual(self.rows("SELECT name FROM sqlite_master WHERE name = 'account_vip'"), [])
        status, body = self.call(VIP_PATH, {"username": "alice", "vip": True})
        self.assertEqual(status, 200, body)
        columns = [(r[1], r[2], r[3], r[4], r[5]) for r in self.rows("PRAGMA table_info(account_vip)")]
        self.assertEqual(columns, [
            ("account", "TEXT", 0, None, 1),
            ("is_vip", "INTEGER", 1, "1", 0),
            ("vip_until", "TEXT", 0, None, 0),
            ("created_utc", "TEXT", 1, None, 0),
        ])
        ddl = self.rows("SELECT sql FROM sqlite_master WHERE name = 'account_vip'")[0][0]
        self.assertIn("COLLATE NOCASE", ddl)
        self.assertEqual(self.vip_row("alice")[1:3], (1, None))

    def test_unknown_account_creates_nothing(self):
        status, body = self.call(VIP_PATH, {"username": "ghost", "vip": True})
        self.assertEqual(status, 404, body)
        self.assertEqual(self.rows("SELECT name FROM sqlite_master WHERE name = 'account_vip'"), [])


class TestVipValidation(AccountVipTestCase):
    def test_unknown_account_is_404_and_writes_nothing(self):
        status, body = self.call(VIP_PATH, {"username": "ghost", "vip": True})
        self.assertEqual(status, 404, body)
        self.assertEqual(body["error"], "Account 'ghost' does not exist")
        self.assertEqual(self.rows("SELECT COUNT(*) FROM account_vip"), [(0,)])
        self.assertEqual(self.audit("vip_grant"), [])

    def test_sign_in_is_required(self):
        status, body = self.call(VIP_PATH, {"username": "alice", "vip": True}, token=False)
        self.assertEqual(status, 401, body)
        self.assertEqual(self.rows("SELECT COUNT(*) FROM account_vip"), [(0,)])

    def test_vip_must_be_a_boolean(self):
        for value in ("yes", 1, None, "true"):
            with self.subTest(value=value):
                status, body = self.call(VIP_PATH, {"username": "alice", "vip": value})
                self.assertEqual(status, 400, body)
        status, body = self.call(VIP_PATH, {"username": "alice"})
        self.assertEqual(status, 400, body)
        self.assertEqual(self.rows("SELECT COUNT(*) FROM account_vip"), [(0,)])

    def test_username_is_required(self):
        status, body = self.call(VIP_PATH, {"username": "  ", "vip": True})
        self.assertEqual(status, 400, body)

    def test_messages_follow_the_panel_language(self):
        status, body = self.call(VIP_PATH, {"username": "alice", "vip": True}, lang="es")
        self.assertEqual(status, 200, body)
        self.assertEqual(body["message"], "VIP activado para la cuenta 'alice'.")
        status, body = self.call(VIP_PATH, {"username": "alice", "vip": False}, lang="es")
        self.assertEqual(body["message"], "VIP desactivado para la cuenta 'alice'.")
        status, body = self.call(VIP_PATH, {"username": "alice", "vip": "x"}, lang="es")
        self.assertEqual(body["error"], server.ES_MESSAGES["Invalid VIP value: it must be true or false"])

    def test_audit_details_are_translated(self):
        for key in ("VIP granted by admin", "VIP revoked by admin"):
            self.assertIn(key, server.ES_MESSAGES)


class TestAccountDetailVip(AccountVipTestCase):
    def setUp(self):
        super().setUp()
        self.sql("CREATE TABLE auth_token (token TEXT, account TEXT, kind TEXT, expires_utc TEXT)")
        self.sql("CREATE TABLE role (id INTEGER PRIMARY KEY, account TEXT, name TEXT, deleted_time INTEGER DEFAULT 0)")

    def test_detail_exposes_the_vip_status(self):
        status, body = self.call("/api/admin/accounts/alice")
        self.assertEqual(status, 200, body)
        self.assertEqual(body["vip"], {"is_vip": False, "vip_until": None, "source": "none"})
        self.call(VIP_PATH, {"username": "alice", "vip": True})
        status, body = self.call("/api/admin/accounts/alice")
        self.assertEqual(body["vip"]["source"], "vip")


if __name__ == "__main__":
    unittest.main()
