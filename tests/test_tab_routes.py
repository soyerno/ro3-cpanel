"""Every panel tab has its own URL (/market, /audit, ...): the standalone server answers those deep links with the
app shell (SPA fallback) while /api paths, unknown paths and missing static files keep their JSON errors.
"""

import json
import os
import sys
import threading
import unittest
import urllib.error
import urllib.request
from http.server import ThreadingHTTPServer
from unittest import mock

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
import server

TABS = ("dashboard", "accounts", "rankings", "guilds", "economy", "auctions", "giftcodes", "market", "audit")


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, *args, **kwargs):
        return None


class TabRouteFallbackTest(unittest.TestCase):
    def setUp(self):
        patcher = mock.patch.object(server.CPanelRequestHandler, "log_message", lambda *a, **k: None)
        patcher.start()
        self.addCleanup(patcher.stop)
        self.httpd = ThreadingHTTPServer(("127.0.0.1", 0), server.CPanelRequestHandler)
        threading.Thread(target=self.httpd.serve_forever, daemon=True).start()
        self.addCleanup(self.httpd.server_close)
        self.addCleanup(self.httpd.shutdown)
        self.base = "http://127.0.0.1:%d" % self.httpd.server_address[1]
        self.opener = urllib.request.build_opener(NoRedirect)

    def get(self, path):
        try:
            with self.opener.open(self.base + path, timeout=10) as resp:
                return resp.status, resp.headers, resp.read()
        except urllib.error.HTTPError as e:
            with e:
                return e.code, e.headers, e.read()

    def assert_app_shell(self, path):
        status, headers, body = self.get(path)
        self.assertEqual(status, 200, path)
        self.assertEqual(headers.get("Content-Type"), "text/html; charset=utf-8")
        self.assertEqual(headers.get("Cache-Control"), "no-cache")
        self.assertIn(b'<script src="admin.js"></script>', body)

    def test_every_tab_path_serves_the_app_shell(self):
        for tab in TABS:
            with self.subTest(tab=tab):
                self.assert_app_shell("/" + tab)

    def test_tab_paths_under_the_admin_prefix_serve_the_app_shell(self):
        for path in ("/admin/market", "/admin/audit", "/admin/accounts?x=1"):
            with self.subTest(path=path):
                self.assert_app_shell(path)

    def test_a_trailing_slash_redirects_to_the_slug_so_relative_assets_still_resolve(self):
        for path, target in (("/market/", "/market"), ("/admin/audit/?page=2", "/admin/audit?page=2")):
            with self.subTest(path=path):
                status, headers, _ = self.get(path)
                self.assertEqual(status, 301)
                self.assertEqual(headers.get("Location"), target)

    # Without a session the API answers 401 before it looks the endpoint up (404); either way it is JSON.
    def assert_json_error(self, path):
        status, headers, body = self.get(path)
        self.assertIn(status, (401, 404), path)
        self.assertTrue(headers.get("Content-Type", "").startswith("application/json"), path)
        self.assertIn("error", json.loads(body))

    def test_api_paths_keep_their_json_errors(self):
        for path in ("/api/x", "/api/market", "/api/admin/market", "/api/market/"):
            with self.subTest(path=path):
                self.assert_json_error(path)

    def test_unknown_paths_and_files_with_an_extension_are_not_the_app_shell(self):
        for path in ("/missing.js", "/market.js", "/admin/missing.css", "/nope", "/market/extra", "/admin/admin/market"):
            with self.subTest(path=path):
                self.assert_json_error(path)

    def test_static_assets_are_still_served(self):
        for path, ctype in (("/admin.js", "application/javascript"), ("/admin.css", "text/css"),
                            ("/admin/admin.js", "application/javascript")):
            with self.subTest(path=path):
                status, headers, _ = self.get(path)
                self.assertEqual(status, 200)
                self.assertTrue(headers.get("Content-Type").startswith(ctype))


if __name__ == "__main__":
    unittest.main()
