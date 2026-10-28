import json
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
    """The ban only lives in the panel; RO3Emu does not check it at login."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.db_path = os.path.join(self.tmp.name, "ro3emu.db")
        with sqlite3.connect(self.db_path) as con:
            con.executescript("""
                CREATE TABLE account (name TEXT PRIMARY KEY, password_hash BLOB, salt BLOB, created_utc TEXT);
                CREATE TABLE auth_token (token TEXT PRIMARY KEY, kind TEXT, account TEXT, expires_utc INTEGER);
                CREATE TABLE role (id INTEGER PRIMARY KEY, account TEXT, deleted_time INTEGER DEFAULT 0);
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
        with urllib.request.urlopen(req) as resp:
            return json.loads(resp.read())

    def test_ban_reports_it_is_not_enforced_and_still_revokes_tokens(self):
        token = self._post("/api/admin/login", {"username": "boss", "password": "Pw-123456"})["token"]
        result = self._post("/api/admin/accounts/ban", {"username": "player1", "reason": "cheating"}, token)

        self.assertTrue(result["success"])
        self.assertIs(result["enforced"], False)
        self.assertIn("RO3Emu", result["message"])
        with sqlite3.connect(self.db_path) as con:
            self.assertEqual(con.execute("SELECT COUNT(*) FROM auth_token WHERE account='player1'").fetchone()[0], 0)
            self.assertEqual(con.execute("SELECT is_banned FROM admin_account_meta WHERE name='player1'").fetchone()[0], 1)


if __name__ == "__main__":
    unittest.main()
