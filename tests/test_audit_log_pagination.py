import json
import os
import sqlite3
import sys
import tempfile
import threading
import unittest
import urllib.error
import urllib.request
from contextlib import closing
from http.server import ThreadingHTTPServer

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
import server

SEEDED = 120  # plus the row the admin login itself writes


class AuditLogPaginationTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(ignore_cleanup_errors=True)
        self.addCleanup(self.tmp.cleanup)
        self.db_path = os.path.join(self.tmp.name, "ro3emu.db")
        with closing(sqlite3.connect(self.db_path)) as con:
            con.execute("CREATE TABLE account (name TEXT PRIMARY KEY, password_hash BLOB, salt BLOB, created_utc TEXT)")
        self._saved = (server.DB_PATH, dict(server.CONFIG))
        server.DB_PATH = self.db_path
        server.CONFIG["admin_users"] = [{"username": "boss", "password": "Pw-123456"}]
        server.CONFIG["default_language"] = "en"
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

    def seed(self, count=SEEDED):
        with closing(sqlite3.connect(self.db_path)) as con:
            con.executemany(
                "INSERT INTO admin_audit_log (admin_user, action, target, details, ip_address) VALUES (?, ?, ?, ?, ?)",
                [("boss", "seed_%03d" % i, "acc%d" % i, "Account created by admin", "127.0.0.1") for i in range(count)],
            )
            con.commit()

    def all_ids_newest_first(self):
        with closing(sqlite3.connect(self.db_path)) as con:
            return [r[0] for r in con.execute("SELECT id FROM admin_audit_log ORDER BY id DESC")]

    def logs(self, query=""):
        status, body = self.call("GET", "/api/admin/audit-log" + query)
        self.assertEqual(status, 200, body)
        return body


class TestPages(AuditLogPaginationTest):
    def test_first_page_is_the_newest_rows_with_paging_info(self):
        self.seed()
        total = SEEDED + 1
        body = self.logs()
        ids = self.all_ids_newest_first()
        self.assertEqual([r["id"] for r in body["logs"]], ids[:50])
        self.assertEqual((body["total"], body["page"], body["page_size"], body["pages"]), (total, 1, 50, 3))

    def test_pages_are_contiguous_and_do_not_overlap(self):
        self.seed()
        ids = self.all_ids_newest_first()
        seen = []
        for page in (1, 2, 3):
            body = self.logs("?page=%d" % page)
            seen.extend(r["id"] for r in body["logs"])
            self.assertEqual(body["page"], page)
        self.assertEqual(seen, ids)

    def test_last_page_is_partial(self):
        self.seed()
        body = self.logs("?page=3")
        self.assertEqual(len(body["logs"]), SEEDED + 1 - 100)

    def test_page_size_is_honoured_and_capped_at_100(self):
        self.seed()
        self.assertEqual(len(self.logs("?page_size=10")["logs"]), 10)
        body = self.logs("?page_size=1000")
        self.assertEqual((len(body["logs"]), body["page_size"]), (100, 100))

    def test_limit_still_works_as_page_size(self):
        self.seed()
        body = self.logs("?limit=7")
        self.assertEqual((len(body["logs"]), body["page_size"], body["pages"]), (7, 7, -(-(SEEDED + 1) // 7)))
        self.assertEqual(len(self.logs("?limit=500")["logs"]), 100)

    def test_page_beyond_the_last_is_empty_but_keeps_the_totals(self):
        self.seed()
        body = self.logs("?page=99")
        self.assertEqual((body["logs"], body["total"], body["pages"], body["page"]), ([], SEEDED + 1, 3, 99))

    def test_invalid_values_are_sanitized_and_never_dump_the_whole_table(self):
        self.seed()
        for query in ("?page=abc", "?page=0", "?page=-3", "?page_size=abc", "?page_size=0", "?limit=-1", "?limit=abc"):
            with self.subTest(query=query):
                body = self.logs(query)
                self.assertGreaterEqual(body["page"], 1)
                self.assertTrue(1 <= len(body["logs"]) <= 100)

    def test_empty_log_still_has_one_page(self):
        with closing(sqlite3.connect(self.db_path)) as con:
            con.execute("DELETE FROM admin_audit_log")
            con.commit()
        body = self.logs()
        self.assertEqual((body["logs"], body["total"], body["pages"], body["page"]), ([], 0, 1, 1))

    def test_rows_keep_their_shape_and_are_translated_per_request(self):
        self.seed(1)
        keys = {"id", "admin_user", "action", "target", "details", "ip_address", "created_utc"}
        en = self.logs()["logs"][0]
        self.assertEqual(set(en), keys)
        self.assertEqual(en["details"], "Account created by admin")
        status, es = self.call("GET", "/api/admin/audit-log?page=1", lang="es")
        self.assertEqual(es["logs"][0]["details"], "Cuenta creada por admin")

    def test_requires_an_admin_session(self):
        status, _ = self.call("GET", "/api/admin/audit-log?page=2", token=False)
        self.assertEqual(status, 401)


if __name__ == "__main__":
    unittest.main()
