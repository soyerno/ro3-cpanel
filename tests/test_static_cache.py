import os
import sys
import threading
import unittest
import urllib.request
from http.server import ThreadingHTTPServer
from unittest import mock

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
import server


class TestStaticCacheHeaders(unittest.TestCase):
    """A deploy must show up on the next page load, without waiting for a cache to expire."""

    def setUp(self):
        patcher = mock.patch.object(server.CPanelRequestHandler, "log_message", lambda *a, **k: None)
        patcher.start()
        self.addCleanup(patcher.stop)
        self.httpd = ThreadingHTTPServer(("127.0.0.1", 0), server.CPanelRequestHandler)
        threading.Thread(target=self.httpd.serve_forever, daemon=True).start()
        self.addCleanup(self.httpd.server_close)
        self.addCleanup(self.httpd.shutdown)
        self.base = "http://127.0.0.1:%d" % self.httpd.server_address[1]

    def cache_control(self, path):
        with urllib.request.urlopen(self.base + path, timeout=10) as resp:
            self.assertEqual(resp.status, 200)
            return resp.headers.get("Cache-Control")

    def test_app_shell_is_revalidated_on_every_load(self):
        for path in ("/", "/admin.js", "/admin.css"):
            with self.subTest(path=path):
                self.assertEqual(self.cache_control(path), "no-cache")

    def test_favicon_keeps_its_one_hour_cache(self):
        self.assertEqual(self.cache_control("/favicon.svg"), "public, max-age=3600")


if __name__ == "__main__":
    unittest.main()
