import hashlib
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
from unittest import mock

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
import server

CONFIG_PW = "Config-Pw-1"
GAME_PW = "Game-Pw-1"
NEW_PW = "Game-Pw-2"


class SharedPasswordTestCase(unittest.TestCase):
    """The game account is the one source of truth for an admin's password when it exists."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(ignore_cleanup_errors=True)
        self.addCleanup(self.tmp.cleanup)
        self.db_path = os.path.join(self.tmp.name, "ro3emu.db")
        pw_hash, salt = server.hash_ro3_password(GAME_PW)
        with closing(sqlite3.connect(self.db_path)) as con:
            con.executescript("""
                CREATE TABLE account (name TEXT PRIMARY KEY, password_hash BLOB, salt BLOB, created_utc TEXT);
                CREATE TABLE auth_token (token TEXT PRIMARY KEY, kind TEXT, account TEXT, expires_utc INTEGER);
            """)
            con.execute("INSERT INTO account VALUES ('boss', ?, ?, '2026-01-01')", (pw_hash, salt))
            con.execute("INSERT INTO account VALUES ('plain', ?, ?, '2026-01-01')", (pw_hash, salt))
            con.execute("INSERT INTO auth_token VALUES ('tok1', 'sdk', 'boss', 9999999999)")
            con.commit()
        self._saved = (server.DB_PATH, dict(server.CONFIG), server.LOGIN_THROTTLE)
        server.DB_PATH = self.db_path
        server.CONFIG["default_language"] = "en"
        server.CONFIG["admin_users"] = [
            {"username": "boss", "password": CONFIG_PW},                      # also a game account
            {"username": "root", "password": CONFIG_PW},                      # config only, no game account
            {"username": "hashed", "password_hash": server.make_admin_password_hash(CONFIG_PW)},
            {"username": "plain", "password": CONFIG_PW},
        ]
        server.LOGIN_THROTTLE = server.LoginThrottle(max_failures=1000, window_seconds=60)
        server.init_tables()
        self.httpd = ThreadingHTTPServer(("127.0.0.1", 0), server.CPanelRequestHandler)
        threading.Thread(target=self.httpd.serve_forever, daemon=True).start()
        self.base = "http://127.0.0.1:%d" % self.httpd.server_address[1]
        self.addCleanup(self._restore)

    def _restore(self):
        self.httpd.shutdown()
        self.httpd.server_close()
        server.DB_PATH = self._saved[0]
        server.CONFIG.clear()
        server.CONFIG.update(self._saved[1])
        server.LOGIN_THROTTLE = self._saved[2]
        server.ACTIVE_SESSIONS.clear()

    def call(self, path, payload=None, token=None):
        headers = {"Content-Type": "application/json"}
        if token:
            headers["Authorization"] = "Bearer " + token
        data = json.dumps(payload).encode() if payload is not None else None
        req = urllib.request.Request(self.base + path, data=data, method="POST" if data is not None else "GET", headers=headers)
        try:
            with urllib.request.urlopen(req, timeout=10) as resp:
                return resp.status, json.loads(resp.read())
        except urllib.error.HTTPError as e:
            with e:
                return e.code, json.loads(e.read())

    def login(self, user, password):
        return self.call("/api/admin/login", {"username": user, "password": password})

    def token(self, user, password):
        status, body = self.login(user, password)
        self.assertEqual(status, 200, body)
        return body["token"]

    def alive(self, token):
        return self.call("/api/admin/session", token=token)[1].get("authenticated") is True

    def change_password(self, token, username, new_password):
        return self.call("/api/admin/accounts/update-password", {"username": username, "new_password": new_password}, token)


class TestOneSourceOfTruth(SharedPasswordTestCase):
    def test_game_password_signs_in_and_the_config_password_does_not(self):
        self.assertEqual(self.login("boss", GAME_PW)[0], 200)
        self.assertEqual(self.login("boss", CONFIG_PW)[0], 401)

    def test_config_hash_entry_is_also_ignored_when_the_game_account_exists(self):
        with closing(sqlite3.connect(self.db_path)) as con:
            pw_hash, salt = server.hash_ro3_password(GAME_PW)
            con.execute("INSERT INTO account VALUES ('hashed', ?, ?, '2026-01-01')", (pw_hash, salt))
            con.commit()
        self.assertEqual(self.login("hashed", CONFIG_PW)[0], 401)
        self.assertEqual(self.login("hashed", GAME_PW)[0], 200)

    def test_client_side_hash_still_works_for_the_game_account(self):
        with closing(sqlite3.connect(self.db_path)) as con:
            salt = con.execute("SELECT salt FROM account WHERE name='boss'").fetchone()[0]
        derived = hashlib.pbkdf2_hmac("sha256", GAME_PW.encode(), salt, 100000, 32).hex()
        status, body = self.call("/api/admin/login", {"username": "boss", "password_hash": derived})
        self.assertEqual(status, 200, body)

    def test_account_name_match_ignores_case(self):
        self.assertEqual(self.login("BOSS", GAME_PW)[0], 200)
        self.assertEqual(self.login("BOSS", CONFIG_PW)[0], 401)

    def test_config_admin_without_a_game_account_keeps_its_config_password(self):
        self.assertEqual(self.login("root", CONFIG_PW)[0], 200)
        self.assertEqual(self.login("root", GAME_PW)[0], 401)

    def test_config_password_is_the_fallback_when_the_database_is_unavailable(self):
        server.DB_PATH = os.path.join(self.tmp.name, "missing.db")
        self.assertEqual(self.login("root", CONFIG_PW)[0], 200)
        self.assertEqual(self.login("boss", CONFIG_PW)[0], 200)


class TestHardening(SharedPasswordTestCase):
    """Verifier findings: case-variant accounts, malformed rows and database errors."""

    def add_account(self, name, password=None, hash_value=..., salt_value=...):
        pw_hash, salt = server.hash_ro3_password(password or "x-unused")
        with closing(sqlite3.connect(self.db_path)) as con:
            con.execute(
                "INSERT INTO account VALUES (?, ?, ?, '2026-01-01')",
                (name, pw_hash if hash_value is ... else hash_value, salt if salt_value is ... else salt_value),
            )
            con.commit()

    def test_the_admins_own_account_wins_over_a_case_variant(self):
        self.add_account("Boss", "pw-upper")
        self.assertEqual(self.login("boss", GAME_PW)[0], 200, "the exact-case account of the admin signs in")
        self.assertEqual(self.login("boss", "pw-upper")[0], 401, "a case-variant account is not the admin")
        self.assertEqual(self.login("boss", CONFIG_PW)[0], 401)

    def test_a_case_variant_registration_cannot_take_over_an_admin_without_a_game_account(self):
        self.add_account("Root", "attacker-pw")
        self.assertEqual(self.login("root", "attacker-pw")[0], 401)
        self.assertEqual(self.login("root", CONFIG_PW)[0], 200, "the real admin keeps signing in with the config password")

    def test_ambiguous_variants_with_no_exact_account_are_not_an_admin_login(self):
        self.add_account("ROOT", "pw-a")
        self.add_account("rOOt", "pw-b")
        self.assertEqual(self.login("root", "pw-a")[0], 401)
        self.assertEqual(self.login("root", "pw-b")[0], 401)
        self.assertEqual(self.login("root", CONFIG_PW)[0], 200)

    def test_a_malformed_game_account_row_never_crashes_and_falls_back_to_the_config_password(self):
        cases = {
            "nullh": dict(hash_value=None),
            "emptyh": dict(hash_value=b""),
            "texth": dict(hash_value="abcd"),
            "nulls": dict(salt_value=None),
        }
        for name, kwargs in cases.items():
            with self.subTest(name):
                self.add_account(name, **kwargs)
                server.CONFIG["admin_users"].append({"username": name, "password": CONFIG_PW})
                self.assertEqual(self.login(name, CONFIG_PW)[0], 200)
                self.assertEqual(self.login(name, "wrong")[0], 401)

    def test_a_database_error_fails_closed_instead_of_reopening_the_config_password(self):
        real_get_db = server.get_db

        def failing_get_db():
            raise sqlite3.OperationalError("database is locked")

        with mock.patch.object(server, "get_db", failing_get_db):
            self.assertEqual(server.authenticate_admin("boss", CONFIG_PW), (False, None))
            self.assertEqual(server.authenticate_admin("boss", GAME_PW), (False, None))
            self.assertEqual(server.authenticate_admin("root", CONFIG_PW), (False, None))
        self.assertEqual(self.login("boss", GAME_PW)[0], 200, "back to normal once the database answers")

    def test_a_database_without_an_account_table_still_allows_the_config_password(self):
        bare = os.path.join(self.tmp.name, "bare.db")
        with closing(sqlite3.connect(bare)) as con:
            con.execute("CREATE TABLE unrelated (x INTEGER)")
            con.commit()
        server.DB_PATH = bare
        self.assertEqual(server.authenticate_admin("root", CONFIG_PW)[0], True)


class TestChangePassword(SharedPasswordTestCase):
    def test_changing_the_password_replaces_it_everywhere(self):
        token = self.token("boss", GAME_PW)
        status, _ = self.change_password(token, "boss", NEW_PW)
        self.assertEqual(status, 200)
        self.assertEqual(self.login("boss", GAME_PW)[0], 401, "the old game password is gone")
        self.assertEqual(self.login("boss", CONFIG_PW)[0], 401, "the config password never comes back")
        self.assertEqual(self.login("boss", NEW_PW)[0], 200, "the new one signs in to the panel")
        with closing(sqlite3.connect(self.db_path)) as con:
            row = con.execute("SELECT password_hash, salt FROM account WHERE name='boss'").fetchone()
            self.assertTrue(server.verify_ro3_password(NEW_PW, row[0], row[1]), "the game account holds the new password")
            self.assertEqual(con.execute("SELECT COUNT(*) FROM auth_token WHERE account='boss'").fetchone()[0], 0)

    def test_own_password_change_keeps_this_session_and_ends_the_others(self):
        current = self.token("boss", GAME_PW)
        other_browser = self.token("boss", GAME_PW)
        self.assertEqual(self.change_password(current, "boss", NEW_PW)[0], 200)
        self.assertTrue(self.alive(current))
        self.assertFalse(self.alive(other_browser))

    def test_another_admin_changing_the_password_ends_every_session_of_that_account(self):
        victim_a = self.token("boss", GAME_PW)
        victim_b = self.token("boss", GAME_PW)
        actor = self.token("root", CONFIG_PW)
        self.assertEqual(self.change_password(actor, "boss", NEW_PW)[0], 200)
        self.assertFalse(self.alive(victim_a))
        self.assertFalse(self.alive(victim_b))
        self.assertTrue(self.alive(actor), "the acting admin keeps their session")

    def test_sessions_of_other_accounts_are_untouched(self):
        boss = self.token("boss", GAME_PW)
        root = self.token("root", CONFIG_PW)
        plain = self.token("plain", GAME_PW)
        self.assertEqual(self.change_password(root, "boss", NEW_PW)[0], 200)
        self.assertFalse(self.alive(boss))
        self.assertTrue(self.alive(root))
        self.assertTrue(self.alive(plain))

    def test_session_user_is_matched_ignoring_case(self):
        token = self.token("BOSS", GAME_PW)
        actor = self.token("root", CONFIG_PW)
        self.assertEqual(self.change_password(actor, "boss", NEW_PW)[0], 200)
        self.assertFalse(self.alive(token))

    def test_in_memory_sessions_are_revoked_too(self):
        now = int(time.time())
        server.ACTIVE_SESSIONS["h-boss"] = {"user": "boss", "created_at": now, "expires_at": now + 3600, "ip": ""}
        server.ACTIVE_SESSIONS["h-root"] = {"user": "root", "created_at": now, "expires_at": now + 3600, "ip": ""}
        actor = self.token("root", CONFIG_PW)
        self.assertEqual(self.change_password(actor, "boss", NEW_PW)[0], 200)
        self.assertNotIn("h-boss", server.ACTIVE_SESSIONS)
        self.assertIn("h-root", server.ACTIVE_SESSIONS)

    def test_failed_change_revokes_nothing(self):
        boss = self.token("boss", GAME_PW)
        actor = self.token("root", CONFIG_PW)
        self.assertEqual(self.change_password(actor, "boss", "short")[0], 400)
        self.assertEqual(self.change_password(actor, "nobody", NEW_PW)[0], 404)
        self.assertTrue(self.alive(boss))
        self.assertEqual(self.login("boss", GAME_PW)[0], 200)

    def test_change_is_audited(self):
        actor = self.token("root", CONFIG_PW)
        self.change_password(actor, "boss", NEW_PW)
        with closing(sqlite3.connect(self.db_path)) as con:
            rows = con.execute("SELECT admin_user, action, target FROM admin_audit_log WHERE action='update_password'").fetchall()
        self.assertEqual(rows, [("root", "update_password", "boss")])


if __name__ == "__main__":
    unittest.main()
