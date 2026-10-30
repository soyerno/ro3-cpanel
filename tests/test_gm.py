"""HTTP-level tests for POST /api/admin/gm, the GM tools relay to RO3Emu's loopback endpoint (issue #11).

Upstream contract (aethai/ro3emu-server, src/Ro3Emu.Server/ServerHost.cs, MapPost("/ro3emu/gm")):
loopback only (404 otherwise), account in the `account` query parameter, the body is one `!command` line,
400 "not in game" when the account has no character online, 200 "done" otherwise, and 503 for every POST
while the game loop is not Accepting.
"""

import contextlib
import json
import os
import socket
import sqlite3
import sys
import tempfile
import threading
import time
import unittest
import urllib.error
import urllib.parse
import urllib.request
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from unittest import mock

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
import server

ADMIN_USER = "boss"
ADMIN_PASS = "Pw-123456"


class FakeRo3Emu:
    """A stand-in for RO3Emu's HTTP host: records each request and answers with a configurable reply."""

    def __init__(self):
        self.requests = []
        self.status = 200
        self.body = b'"done"'
        self.delay = 0.0
        self.location = None
        self.stall_after_body = 0.0  # >0: announce Content-Length 100, send self.body, then stall this long
        self.replies = []  # optional queue of (status, body), consumed one per request before status/body
        fake = self

        class Handler(BaseHTTPRequestHandler):
            def log_message(self, *args):
                pass

            def do_GET(self):
                self.do_POST()

            def do_POST(self):
                length = int(self.headers.get("Content-Length", 0))
                body = self.rfile.read(length).decode("utf-8")
                parts = urllib.parse.urlsplit(self.path)
                fake.requests.append({
                    "method": self.command,
                    "path": parts.path,
                    "query": urllib.parse.parse_qs(parts.query, keep_blank_values=True),
                    "body": body,
                })
                if fake.delay:
                    time.sleep(fake.delay)
                status, reply_body = fake.replies.pop(0) if fake.replies else (fake.status, fake.body)
                self.send_response(status)
                if fake.location:
                    self.send_header("Location", fake.location)
                self.send_header("Content-Type", "application/json; charset=utf-8")
                if fake.stall_after_body:
                    self.send_header("Content-Length", "100")
                    self.end_headers()
                    self.wfile.write(reply_body)
                    self.wfile.flush()
                    time.sleep(fake.stall_after_body)
                    self.close_connection = True
                    return
                self.send_header("Content-Length", str(len(reply_body)))
                self.end_headers()
                self.wfile.write(reply_body)

        self.httpd = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        self.thread = threading.Thread(target=self.httpd.serve_forever, kwargs={"poll_interval": 0.05}, daemon=True)
        self.thread.start()
        self.base = "http://127.0.0.1:%d" % self.httpd.server_address[1]

    def close(self):
        self.httpd.shutdown()
        self.httpd.server_close()
        self.thread.join(10)


def closed_port():
    with contextlib.closing(socket.socket(socket.AF_INET, socket.SOCK_STREAM)) as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


class GmEndpointTest(unittest.TestCase):
    def setUp(self):
        # Restore module globals BEFORE mutating them.
        self.addCleanup(setattr, server, "DB_PATH", server.DB_PATH)
        self.addCleanup(setattr, server, "CONFIG", server.CONFIG)
        self.addCleanup(setattr, server, "ACTIVE_SESSIONS", server.ACTIVE_SESSIONS)
        self.addCleanup(setattr, server, "RO3_STATUS_URL", server.RO3_STATUS_URL)

        tmp = tempfile.TemporaryDirectory(ignore_cleanup_errors=True)
        self.addCleanup(tmp.cleanup)
        self.db_path = os.path.join(tmp.name, "ro3emu.db")
        with contextlib.closing(sqlite3.connect(self.db_path)) as con:
            con.execute("CREATE TABLE account (name TEXT PRIMARY KEY, password_hash BLOB, salt BLOB, created_utc TEXT)")
            con.execute("CREATE TABLE auth_token (token TEXT, kind TEXT, account TEXT, expires_utc TEXT)")
            con.execute("CREATE TABLE role (id INTEGER PRIMARY KEY, account TEXT, deleted_time INTEGER DEFAULT 0)")
            con.execute("INSERT INTO account VALUES ('player1', x'00', x'00', '2026-01-01')")
            con.commit()

        server.DB_PATH = self.db_path
        server.CONFIG = dict(server.CONFIG)
        server.CONFIG["admin_users"] = [{"username": ADMIN_USER, "password": ADMIN_PASS}]
        server.CONFIG.pop("gm_allowed_commands", None)
        server.CONFIG.pop("gm_unstuck_scene", None)
        server.ACTIVE_SESSIONS = {}
        server.init_tables()

        self.fake = FakeRo3Emu()
        self.addCleanup(self.fake.close)
        server.CONFIG["ro3_base_url"] = self.fake.base

        patcher = mock.patch.object(server.CPanelRequestHandler, "log_message", lambda *a, **k: None)
        patcher.start()
        self.addCleanup(patcher.stop)

        self.httpd = ThreadingHTTPServer(("127.0.0.1", 0), server.CPanelRequestHandler)
        thread = threading.Thread(target=self.httpd.serve_forever, kwargs={"poll_interval": 0.05}, daemon=True)
        thread.start()
        self.addCleanup(thread.join, 10)
        self.addCleanup(self.httpd.server_close)
        self.addCleanup(self.httpd.shutdown)
        self.base = "http://127.0.0.1:%d" % self.httpd.server_address[1]
        self.token = self._post("/api/admin/login", {"username": ADMIN_USER, "password": ADMIN_PASS}, None)[1]["token"]

    # --- helpers ---

    def _post(self, path, payload, token="default", raw=None):
        headers = {"Content-Type": "application/json"}
        if token == "default":
            token = self.token
        if token:
            headers["Authorization"] = "Bearer " + token
        data = raw if raw is not None else json.dumps(payload).encode("utf-8")
        req = urllib.request.Request(self.base + path, data=data, headers=headers, method="POST")
        try:
            with urllib.request.urlopen(req, timeout=10) as resp:
                return resp.status, json.loads(resp.read().decode("utf-8"))
        except urllib.error.HTTPError as e:
            with e:
                return e.code, json.loads(e.read().decode("utf-8"))

    def gm(self, payload, **kw):
        return self._post("/api/admin/gm", payload, **kw)

    def audit_rows(self):
        with contextlib.closing(sqlite3.connect(self.db_path)) as con:
            con.row_factory = sqlite3.Row
            return [dict(r) for r in con.execute(
                "SELECT admin_user, action, target, details, ip_address FROM admin_audit_log"
                " WHERE action = 'gm_command' ORDER BY id")]

    def assert_rejected(self, payload, status=400):
        before = len(self.audit_rows())
        code, data = self.gm(payload)
        self.assertEqual(code, status, data)
        self.assertIn("error", data)
        self.assertEqual(self.fake.requests, [], "nothing must reach RO3Emu")
        rows = self.audit_rows()
        self.assertEqual(len(rows), before + 1, "every attempt is audit-logged")
        self.assertEqual(rows[-1]["admin_user"], ADMIN_USER)
        self.assertIn("rejected", rows[-1]["details"])
        return data, rows[-1]

    # --- allowed commands ---

    def test_warp_with_point_sends_exact_line_to_loopback_endpoint(self):
        code, data = self.gm({"account": "player1", "command": "warp", "args": {"scene": 10111, "x": 150, "z": 190}})

        self.assertEqual(code, 200, data)
        self.assertTrue(data["success"])
        self.assertEqual(data["sent"], "!warp 10111 150 190")
        self.assertEqual(len(self.fake.requests), 1)
        req = self.fake.requests[0]
        self.assertEqual(req["method"], "POST")
        self.assertEqual(req["path"], "/ro3emu/gm")
        self.assertEqual(req["query"], {"account": ["player1"]})
        self.assertEqual(req["body"], "!warp 10111 150 190")
        rows = self.audit_rows()
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["admin_user"], ADMIN_USER)
        self.assertEqual(rows[0]["target"], "player1")
        self.assertIn("!warp 10111 150 190", rows[0]["details"])
        self.assertIn("sent", rows[0]["details"])
        self.assertEqual(rows[0]["ip_address"], "127.0.0.1")

    def test_warp_without_point_and_negative_coordinates(self):
        self.assertEqual(self.gm({"account": "player1", "command": "warp", "args": {"scene": 10100}})[0], 200)
        self.assertEqual(self.gm({"account": "player1", "command": "warp", "args": {"scene": 10100, "x": -5, "z": 0}})[0], 200)
        self.assertEqual([r["body"] for r in self.fake.requests], ["!warp 10100", "!warp 10100 -5 0"])

    def test_account_lookup_is_case_insensitive_and_sends_stored_name(self):
        code, _ = self.gm({"account": "PLAYER1", "command": "warp", "args": {"scene": 10100}})
        self.assertEqual(code, 200)
        self.assertEqual(self.fake.requests[0]["query"], {"account": ["player1"]})

    def test_unstuck_warps_to_configured_scene_without_point(self):
        code, data = self.gm({"account": "player1", "command": "unstuck"})
        self.assertEqual(code, 200, data)
        self.assertEqual(self.fake.requests[0]["body"], "!warp 10111")

        server.CONFIG["gm_unstuck_scene"] = 10100
        self.gm({"account": "player1", "command": "unstuck", "args": {}})
        self.assertEqual(self.fake.requests[1]["body"], "!warp 10100")

    def test_target_derived_from_status_url_when_no_base_url(self):
        del server.CONFIG["ro3_base_url"]
        server.RO3_STATUS_URL = self.fake.base + "/ro3emu/status"
        code, _ = self.gm({"account": "player1", "command": "warp", "args": {"scene": 10100}})
        self.assertEqual(code, 200)
        self.assertEqual(self.fake.requests[0]["path"], "/ro3emu/gm")

    # --- allowlist and validation ---

    def test_command_not_in_allowlist_is_rejected(self):
        self.assert_rejected({"account": "player1", "command": "zeny", "args": {"amount": 999999}})

    def test_allowlisted_command_without_panel_builder_is_rejected(self):
        server.CONFIG["gm_allowed_commands"] = ["warp", "item", "zeny"]
        self.assert_rejected({"account": "player1", "command": "item", "args": {"id": 1}})

    def test_warp_removed_from_allowlist_blocks_warp_and_unstuck(self):
        server.CONFIG["gm_allowed_commands"] = []
        self.assert_rejected({"account": "player1", "command": "warp", "args": {"scene": 10100}})
        self.assert_rejected({"account": "player1", "command": "unstuck"})

    def test_unstuck_only_allowlist_still_blocks_free_warp(self):
        server.CONFIG["gm_allowed_commands"] = ["unstuck"]
        self.assert_rejected({"account": "player1", "command": "warp", "args": {"scene": 10100}})
        self.assertEqual(self.gm({"account": "player1", "command": "unstuck"})[0], 200)

    def test_invalid_warp_args_are_rejected(self):
        bad_args = [
            None,
            {},
            {"scene": "10111"},
            {"scene": 10111.5},
            {"scene": True},
            {"scene": 0},
            {"scene": -10111},
            {"scene": 10111, "x": 150},
            {"scene": 10111, "z": 190},
            {"scene": 10111, "x": "150", "z": 190},
            {"scene": 10111, "x": 150, "z": 190, "y": 3},
            {"scene": 10111, "x": 10 ** 9, "z": 0},
            [10111, 150, 190],
            "10111 150 190",
        ]
        for args in bad_args:
            with self.subTest(args=args):
                self.assert_rejected({"account": "player1", "command": "warp", "args": args})

    def test_fieldexp_is_off_unless_it_is_in_the_allowlist(self):
        self.assert_rejected({"account": "player1", "command": "fieldexp", "args": {"action": "clear"}})
        server.CONFIG["gm_allowed_commands"] = ["warp"]
        self.assert_rejected({"account": "player1", "command": "fieldexp", "args": {"action": "reset"}})

    def test_fieldexp_sends_the_exact_lines_to_the_loopback_endpoint(self):
        server.CONFIG["gm_allowed_commands"] = ["fieldexp"]
        cases = [
            ({"action": "set", "rules": [{"min": 20, "max": 40, "percent": 300}]}, "!fieldexp set 20 40 300"),
            ({"action": "set", "rules": [{"min": 20, "max": 36, "percent": 300}, {"min": 37, "max": 40, "percent": 500}]},
             "!fieldexp set 20 36 300 37 40 500"),
            ({"action": "clear"}, "!fieldexp clear"),
            ({"action": "reset"}, "!fieldexp reset"),
        ]
        for args, line in cases:
            with self.subTest(line=line):
                code, data = self.gm({"account": "player1", "command": "fieldexp", "args": args})
                self.assertEqual(code, 200, data)
                self.assertEqual(data["sent"], line)
                self.assertEqual(self.fake.requests[-1]["body"], line)
        self.assertEqual(len(self.audit_rows()), len(cases), "every attempt is audit-logged")

    def test_fieldexp_allowlist_does_not_open_other_commands(self):
        server.CONFIG["gm_allowed_commands"] = ["fieldexp"]
        self.assert_rejected({"account": "player1", "command": "warp", "args": {"scene": 10100}})
        self.assert_rejected({"account": "player1", "command": "unstuck"})

    def test_invalid_fieldexp_args_are_rejected(self):
        server.CONFIG["gm_allowed_commands"] = ["fieldexp"]
        rule = {"min": 20, "max": 40, "percent": 300}
        bad_args = [
            None,
            {},
            {"action": "show"},
            {"action": "set"},  # no rules
            {"action": "set", "rules": []},
            {"action": "set", "rules": "20 40 300"},
            {"action": "set", "rules": [rule] * 11},
            {"action": "set", "rules": [{"min": 20, "max": 40}]},
            {"action": "set", "rules": [dict(rule, extra=1)]},
            {"action": "set", "rules": [[20, 40, 300]]},
            {"action": "set", "rules": [dict(rule, min=0)]},
            {"action": "set", "rules": [dict(rule, max=1000)]},
            {"action": "set", "rules": [dict(rule, min=41)]},  # min above max
            {"action": "set", "rules": [dict(rule, percent=0)]},
            {"action": "set", "rules": [dict(rule, percent=10001)]},
            {"action": "set", "rules": [dict(rule, percent="300")]},
            {"action": "set", "rules": [dict(rule, percent=True)]},
            {"action": "set", "rules": [dict(rule, percent="300\n!zeny 999999")]},
            {"action": "clear", "rules": [rule]},
            {"action": "reset", "rules": []},
            {"action": "clear\n!zeny 999999"},
            {"action": "set", "rules": [rule], "extra": 1},
        ]
        for args in bad_args:
            with self.subTest(args=args):
                self.assert_rejected({"account": "player1", "command": "fieldexp", "args": args})

    def test_unstuck_rejects_arguments(self):
        self.assert_rejected({"account": "player1", "command": "unstuck", "args": {"scene": 10100}})

    def test_injection_attempts_are_rejected(self):
        payloads = [
            {"account": "player1", "command": "warp\n!zeny 999999", "args": {"scene": 10100}},
            {"account": "player1", "command": "!warp", "args": {"scene": 10100}},
            {"account": "player1", "command": "warp 10100 !zeny", "args": {"scene": 10100}},
            {"account": "player1", "command": "WARP", "args": {"scene": 10100}},
            {"account": "player1", "command": "warp", "args": {"scene": "10100\n!zeny 999999"}},
            {"account": "player1", "command": "warp", "args": {"scene": "10100 !zeny 1"}},
            {"account": "player1\n!zeny 999", "command": "warp", "args": {"scene": 10100}},
            {"account": "player1 !zeny", "command": "warp", "args": {"scene": 10100}},
            {"account": "player 1", "command": "warp", "args": {"scene": 10100}},
            {"account": "player1&account=other", "command": "warp", "args": {"scene": 10100}},
            {"account": "", "command": "warp", "args": {"scene": 10100}},
            {"account": ["player1"], "command": "warp", "args": {"scene": 10100}},
            {"account": "player1", "command": ["warp"], "args": {"scene": 10100}},
        ]
        for payload in payloads:
            with self.subTest(payload=payload):
                self.assert_rejected(payload)

    def test_invalid_json_body_is_rejected_and_logged(self):
        before = len(self.audit_rows())
        code, data = self.gm(None, raw=b"{not json")
        self.assertEqual(code, 400)
        self.assertEqual(len(self.audit_rows()), before + 1)
        code, data = self.gm(None, raw=b"[1, 2]")
        self.assertEqual(code, 400)
        self.assertEqual(len(self.audit_rows()), before + 2)
        self.assertEqual(self.fake.requests, [])

    def test_unknown_account_is_404(self):
        self.assert_rejected({"account": "ghost", "command": "warp", "args": {"scene": 10100}}, status=404)

    # --- loopback guard ---

    def test_non_loopback_target_is_refused(self):
        for url in ["http://10.0.0.5:5380", "http://example.com:5380", "http://127.0.0.1.example.com:5380",
                    "http://0.0.0.0:5380", "ftp://127.0.0.1:5380", "not a url"]:
            with self.subTest(url=url):
                server.CONFIG["ro3_base_url"] = url
                data, _ = self.assert_rejected({"account": "player1", "command": "warp", "args": {"scene": 10100}})
                self.assertIn("same host", data["error"])

    def test_base_url_with_userinfo_is_refused(self):
        port = self.fake.httpd.server_address[1]
        for url in ["http://evil.com@127.0.0.1:%d" % port, "http://user:pw@127.0.0.1:%d" % port]:
            with self.subTest(url=url):
                server.CONFIG["ro3_base_url"] = url
                data, row = self.assert_rejected({"account": "player1", "command": "warp", "args": {"scene": 10100}})
                self.assertIn("username", data["error"])
                self.assertIn("rejected", row["details"])

    def test_loopback_host_helper(self):
        for host in ["127.0.0.1", "127.8.9.10", "::1", "localhost", "LOCALHOST"]:
            self.assertTrue(server.is_loopback_host(host), host)
        for host in ["10.0.0.1", "0.0.0.0", "example.com", "127.0.0.1.example.com", "", None, "::"]:
            self.assertFalse(server.is_loopback_host(host), host)

    # --- upstream responses ---

    def assert_failed(self, status, text):
        code, data = self.gm({"account": "player1", "command": "warp", "args": {"scene": 10100}})
        self.assertEqual(code, status, data)
        self.assertIn(text, data["error"])
        rows = self.audit_rows()
        self.assertEqual(len(rows), 1)
        self.assertIn("!warp 10100", rows[0]["details"])
        self.assertIn("failed", rows[0]["details"])
        return data

    def test_not_in_game_maps_to_409(self):
        self.fake.status, self.fake.body = 400, b'"not in game"'
        self.assert_failed(409, "not in the game")
        self.assertEqual(len(self.fake.requests), 1)

    def test_loop_not_accepting_maps_to_503(self):
        self.fake.status, self.fake.body = 503, b""
        self.assert_failed(503, "RO3Emu")

    def test_upstream_404_maps_to_502(self):
        self.fake.status, self.fake.body = 404, b""
        self.assert_failed(502, "same host")

    def test_unexpected_upstream_status_maps_to_502(self):
        self.fake.status, self.fake.body = 500, b"boom"
        self.assert_failed(502, "RO3Emu")

    def test_unreachable_endpoint_maps_to_502(self):
        server.CONFIG["ro3_base_url"] = "http://127.0.0.1:%d" % closed_port()
        self.assert_failed(502, "GM endpoint unavailable")

    def test_timeout_maps_to_502(self):
        self.fake.delay = 1.0
        with mock.patch.object(server, "GM_TIMEOUT_SECONDS", 0.2):
            self.assert_failed(502, "GM endpoint unavailable")

    def test_error_body_that_stalls_still_answers_and_is_audited(self):
        # RO3Emu sends 400 headers announcing 100 bytes, writes 3 of them, then stalls past the GM timeout.
        self.fake.status, self.fake.body, self.fake.stall_after_body = 400, b"not", 1.0
        with mock.patch.object(server, "GM_TIMEOUT_SECONDS", 0.2):
            code, data = self.gm({"account": "player1", "command": "warp", "args": {"scene": 10100}})
        self.assertGreaterEqual(code, 400)
        self.assertLess(code, 600)
        self.assertIn("error", data)
        self.assertEqual(data["sent"], "!warp 10100")
        rows = self.audit_rows()
        self.assertEqual(len(rows), 1)
        self.assertIn("!warp 10100", rows[0]["details"])
        self.assertIn("failed", rows[0]["details"])

    def test_upstream_redirect_is_not_followed(self):
        self.fake.status, self.fake.body = 302, b""
        self.fake.location = self.fake.base + "/elsewhere"
        self.assert_failed(502, "RO3Emu")
        self.assertEqual([r["path"] for r in self.fake.requests], ["/ro3emu/gm"])

    # --- auth ---

    def test_requires_authentication(self):
        code, data = self.gm({"account": "player1", "command": "warp", "args": {"scene": 10100}}, token=None)
        self.assertEqual(code, 401)
        self.assertEqual(self.fake.requests, [])


if __name__ == "__main__":
    unittest.main()
