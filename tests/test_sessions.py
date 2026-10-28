"""HTTP-level tests for admin sessions persisted in SQLite (issue #3)."""

import contextlib
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
from http.server import ThreadingHTTPServer
from unittest import mock

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
import server

ADMIN_USER = "boss"
ADMIN_PASS = "Pw-123456"


def token_hash(token):
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


class SessionTestBase(unittest.TestCase):
    create_db = True

    def setUp(self):
        # Restore every module global BEFORE mutating it.
        self.addCleanup(setattr, server, "DB_PATH", server.DB_PATH)
        self.addCleanup(setattr, server, "CONFIG", server.CONFIG)
        self.addCleanup(setattr, server, "ACTIVE_SESSIONS", server.ACTIVE_SESSIONS)

        tmp = tempfile.TemporaryDirectory(ignore_cleanup_errors=True)
        self.addCleanup(tmp.cleanup)
        self.db_path = os.path.join(tmp.name, "ro3emu.db")

        if self.create_db:
            with contextlib.closing(sqlite3.connect(self.db_path)) as con:
                con.execute("CREATE TABLE account (name TEXT PRIMARY KEY, password_hash BLOB, salt BLOB, created_utc TEXT)")
                con.execute("CREATE TABLE auth_token (token TEXT, kind TEXT, account TEXT, expires_utc INTEGER)")
                con.commit()

        server.DB_PATH = self.db_path
        server.CONFIG = dict(server.CONFIG)
        server.CONFIG["admin_users"] = [{"username": ADMIN_USER, "password": ADMIN_PASS}]
        server.ACTIVE_SESSIONS = {}
        server.init_tables()

        patcher = mock.patch.object(server.CPanelRequestHandler, "log_message", lambda *a, **k: None)
        patcher.start()
        self.addCleanup(patcher.stop)

        self.start_server()

    def start_server(self):
        httpd = ThreadingHTTPServer(("127.0.0.1", 0), server.CPanelRequestHandler)
        threading.Thread(target=httpd.serve_forever, daemon=True).start()
        self.addCleanup(self._stop, httpd)
        self.httpd = httpd
        self.base = "http://127.0.0.1:%d" % httpd.server_address[1]

    @staticmethod
    def _stop(httpd):
        if httpd.socket.fileno() != -1:
            httpd.shutdown()
            httpd.server_close()

    def restart_server(self):
        """Simulate a process restart: drop the in-memory state and serve from a new server."""
        self._stop(self.httpd)
        server.ACTIVE_SESSIONS = {}
        server.init_tables()
        self.start_server()

    def request(self, method, path, payload=None, token=None):
        headers = {"Content-Type": "application/json"}
        if token:
            headers["Authorization"] = "Bearer " + token
        data = json.dumps(payload).encode() if payload is not None else None
        req = urllib.request.Request(self.base + path, data=data, headers=headers, method=method)
        try:
            with urllib.request.urlopen(req, timeout=10) as resp:
                return resp.status, json.loads(resp.read())
        except urllib.error.HTTPError as err:
            with err:
                return err.code, json.loads(err.read())

    def login(self):
        status, body = self.request("POST", "/api/admin/login", {"username": ADMIN_USER, "password": ADMIN_PASS})
        self.assertEqual(status, 200, body)
        return body["token"]

    def session_status(self, token):
        return self.request("GET", "/api/admin/session", token=token)[1]

    def rows(self):
        with contextlib.closing(sqlite3.connect(self.db_path)) as con:
            con.row_factory = sqlite3.Row
            return [dict(r) for r in con.execute("SELECT * FROM admin_session")]

    def execute(self, sql, params=()):
        with contextlib.closing(sqlite3.connect(self.db_path)) as con:
            con.execute(sql, params)
            con.commit()


class PersistentSessionTest(SessionTestBase):
    def test_session_survives_a_server_restart(self):
        token = self.login()

        self.restart_server()

        self.assertEqual(self.session_status(token), {"authenticated": True, "user": ADMIN_USER, "role": "admin"})
        status, body = self.request("GET", "/api/admin/audit-log", token=token)
        self.assertEqual(status, 200, body)

    def test_database_stores_a_hash_of_the_token_not_the_token(self):
        token = self.login()

        rows = self.rows()
        self.assertEqual(len(rows), 1)
        row = rows[0]
        self.assertEqual(row["token_hash"], token_hash(token))
        self.assertEqual(row["admin_user"], ADMIN_USER)
        self.assertEqual(row["ip_address"], "127.0.0.1")
        for column, value in row.items():
            self.assertNotIn(token, str(value), "raw token leaked into column %r" % column)
        self.assertEqual(server.ACTIVE_SESSIONS, {})

    def test_logout_deletes_the_row(self):
        token = self.login()
        other = self.login()

        status, body = self.request("POST", "/api/admin/logout", {}, token=token)

        self.assertEqual(status, 200, body)
        self.assertEqual([r["token_hash"] for r in self.rows()], [token_hash(other)])
        self.assertEqual(self.session_status(token), {"authenticated": False})
        self.assertTrue(self.session_status(other)["authenticated"])

    def test_expired_session_is_rejected_and_its_row_deleted(self):
        token = self.login()
        self.execute("UPDATE admin_session SET expires_utc = ? WHERE token_hash = ?", (int(time.time()) - 10, token_hash(token)))

        status, body = self.request("GET", "/api/admin/audit-log", token=token)

        self.assertEqual(status, 401, body)
        self.assertEqual(self.rows(), [])
        self.assertEqual(self.session_status(token), {"authenticated": False})

    def test_activity_slides_the_expiry(self):
        token = self.login()
        self.execute("UPDATE admin_session SET expires_utc = ? WHERE token_hash = ?", (int(time.time()) + 5, token_hash(token)))

        before = int(time.time())
        self.assertTrue(self.session_status(token)["authenticated"])

        expires = self.rows()[0]["expires_utc"]
        self.assertGreaterEqual(expires, before + server.SESSION_TTL_SECONDS)
        self.assertLessEqual(expires, int(time.time()) + server.SESSION_TTL_SECONDS)

    def test_session_of_a_removed_admin_is_rejected_and_deleted(self):
        token = self.login()
        server.CONFIG["admin_users"] = [{"username": "someone-else", "password": "Other-123456"}]

        self.assertFalse(self.session_status(token)["authenticated"])
        self.assertEqual(self.rows(), [])

    def test_admin_match_is_case_insensitive(self):
        token = self.login()
        server.CONFIG["admin_users"] = [{"username": ADMIN_USER.upper(), "password": ADMIN_PASS}]

        self.assertTrue(self.session_status(token)["authenticated"])

    def test_recent_activity_does_not_rewrite_the_expiry(self):
        # Each authenticated request must not write to the live game DB; the
        # expiry is only renewed once it would move by SESSION_SLIDE_MIN_SECONDS.
        token = self.login()
        nearly_fresh = int(time.time()) + server.SESSION_TTL_SECONDS - 60
        self.execute("UPDATE admin_session SET expires_utc = ? WHERE token_hash = ?", (nearly_fresh, token_hash(token)))

        self.assertTrue(self.session_status(token)["authenticated"])

        self.assertEqual(self.rows()[0]["expires_utc"], nearly_fresh)

    def test_login_purges_expired_rows(self):
        self.execute(
            "INSERT INTO admin_session (token_hash, admin_user, ip_address, created_utc, expires_utc) VALUES (?, ?, ?, ?, ?)",
            ("stale", ADMIN_USER, "10.0.0.1", 1, 2),
        )

        token = self.login()

        self.assertEqual([r["token_hash"] for r in self.rows()], [token_hash(token)])

    def test_startup_purges_expired_rows(self):
        token = self.login()
        self.execute(
            "INSERT INTO admin_session (token_hash, admin_user, ip_address, created_utc, expires_utc) VALUES (?, ?, ?, ?, ?)",
            ("stale", ADMIN_USER, "10.0.0.1", 1, 2),
        )

        self.restart_server()

        self.assertEqual([r["token_hash"] for r in self.rows()], [token_hash(token)])


class MissingDatabaseFallbackTest(SessionTestBase):
    create_db = False

    def test_login_still_works_with_the_in_memory_store(self):
        self.assertFalse(os.path.exists(self.db_path))

        token = self.login()

        self.assertEqual(self.session_status(token), {"authenticated": True, "user": ADMIN_USER, "role": "admin"})
        # The fallback store is keyed by the token hash too.
        self.assertEqual(list(server.ACTIVE_SESSIONS), [token_hash(token)])

        status, _ = self.request("POST", "/api/admin/logout", {}, token=token)
        self.assertEqual(status, 200)
        self.assertEqual(server.ACTIVE_SESSIONS, {})
        self.assertEqual(self.session_status(token), {"authenticated": False})
        self.assertFalse(os.path.exists(self.db_path))


if __name__ == "__main__":
    unittest.main()
