import json
from contextlib import closing
import os
import sqlite3
import sys
import tempfile
import threading
import unittest
import urllib.request
from http.server import ThreadingHTTPServer

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
import server


class TestBanEndpoint(unittest.TestCase):
    """A ban is a row in RO3Emu's `account_ban` table, which RO3Emu reads at login."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.db_path = os.path.join(self.tmp.name, "ro3emu.db")
        with closing(sqlite3.connect(self.db_path)) as con:
            con.executescript("""
                CREATE TABLE account (name TEXT PRIMARY KEY, password_hash BLOB, salt BLOB, created_utc TEXT);
                CREATE TABLE auth_token (token TEXT PRIMARY KEY, kind TEXT, account TEXT, expires_utc INTEGER);
                CREATE TABLE role (id INTEGER PRIMARY KEY, account TEXT, deleted_time INTEGER DEFAULT 0);
                CREATE TABLE account_ban (account TEXT NOT NULL PRIMARY KEY, reason TEXT NOT NULL DEFAULT '',
                                          banned_utc INTEGER NOT NULL, until_utc INTEGER, banned_by TEXT);
                INSERT INTO account VALUES ('player1', x'00', x'00', '2026-01-01');
                INSERT INTO auth_token VALUES ('tok1', 'sdk', 'player1', 9999999999);
            """)
        self._saved = (server.DB_PATH, dict(server.CONFIG))
        server.DB_PATH = self.db_path
        server.CONFIG["admin_users"] = [{"username": "boss", "password": "Pw-123456"}]
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
        server.ACTIVE_SESSIONS.clear()

    def _post(self, path, payload, token=None):
        req = urllib.request.Request(
            self.base + path,
            data=json.dumps(payload).encode(),
            headers={"Content-Type": "application/json", **({"Authorization": "Bearer " + token} if token else {})},
        )
        with urllib.request.urlopen(req, timeout=10) as resp:
            return json.loads(resp.read())

    def test_ban_is_enforced_by_ro3emu_and_revokes_tokens(self):
        token = self._post("/api/admin/login", {"username": "boss", "password": "Pw-123456"})["token"]
        result = self._post("/api/admin/accounts/ban", {"username": "player1", "reason": "cheating"}, token)

        self.assertTrue(result["success"])
        self.assertIs(result["enforced"], True)
        self.assertIn("RO3Emu", result["message"])
        with closing(sqlite3.connect(self.db_path)) as con:
            self.assertEqual(con.execute("SELECT COUNT(*) FROM auth_token WHERE account='player1'").fetchone()[0], 0)
            self.assertEqual(
                con.execute("SELECT reason, until_utc, banned_by FROM account_ban WHERE account='player1'").fetchall(),
                [("cheating", None, "boss")],
            )


if __name__ == "__main__":
    unittest.main()
