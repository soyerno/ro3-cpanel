"""Online players and server metrics proxied from RO3Emu's loopback-only diagnostics.

A fake RO3Emu HTTP server serves fixtures shaped like upstream aethai/ro3emu-server:
- GET /ro3emu/online  (src/Ro3Emu.Server/ServerHost.cs): array of {account, role, scene, x, z, remote}
- GET /ro3emu/metrics (src/Ro3Emu.Server/Diagnostics/ServerMetrics.cs Snapshot())
"""

import json
import os
import re
import socket
import sqlite3
import sys
import tempfile
import threading
import time
import unittest
import urllib.error
import urllib.request
from contextlib import closing
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
import server

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))

ONLINE_FIXTURE = [
    {"account": "alice", "role": "Aria", "scene": 10100, "x": 12.345, "z": -3.21, "remote": "203.0.113.7:51234"},
    {"account": "bob", "role": None, "scene": None, "x": 0.0, "z": 0.0, "remote": "198.51.100.2:40000"},
    {"account": "carol", "role": "Cora", "scene": 99999, "x": 1.0, "z": 2.0, "remote": "192.0.2.9:1234"},
]

METRICS_FIXTURE = {
    "schemaVersion": 1,
    "epoch": "0f1e2d3c",
    "capturedUtc": "2026-10-28T12:00:00+00:00",
    "elapsedSeconds": 3725.5,
    "semantics": "Cumulative epoch counters",
    "loop": {"ticks": 100, "overruns": 0},
    "wire": {"framesIn": 10, "bytesIn": 1000, "connections": 3, "connectionQueueBytes": []},
    "database": {"statements": 120, "commits": 40, "loopStatements": 100, "otherStatements": 20,
                 "opens": 2, "operations": {"select/role": {"count": 5}}},
    "sessions": {
        "capturedUtc": "2026-10-28T11:59:59+00:00",
        "login": 1,
        "loading": 1,
        "inWorld": 2,
        "byMap": [
            {"map": 10100, "line": 1, "kind": "Public", "runtimeId": 1, "sceneId": 5, "count": 1, "loading": 0},
            {"map": 10100, "line": 2, "kind": "Public", "runtimeId": 2, "sceneId": 5, "count": 2, "loading": 1},
            {"map": 99999, "line": 1, "kind": "Private", "runtimeId": 3, "sceneId": 7, "count": 1, "loading": 0},
        ],
    },
    "runtime": {"gen0": 4, "workingSetBytes": 157286400, "threadPoolQueueLength": 0},
    "errors": {"exceptions": 1, "errorLogs": 2},
}


class FakeRo3EmuHandler(BaseHTTPRequestHandler):
    # path -> (status, body bytes, delay seconds); set per test on the server instance.
    def do_GET(self):
        route = self.server.routes.get(self.path)
        if route is None:
            status, body, delay = 404, b"", 0
        else:
            status, body, delay = route
        if delay:
            time.sleep(delay)
        try:
            self.send_response(status)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
        except OSError:
            pass  # the panel gave up (timeout) and closed the socket

    def log_message(self, format, *args):
        pass


def json_route(payload, status=200, delay=0):
    return (status, json.dumps(payload).encode("utf-8"), delay)


class TestRo3BaseUrl(unittest.TestCase):
    def setUp(self):
        saved = (server.RO3_STATUS_URL, dict(server.CONFIG))
        self.addCleanup(self._restore, saved)

    def _restore(self, saved):
        server.RO3_STATUS_URL = saved[0]
        server.CONFIG.clear()
        server.CONFIG.update(saved[1])

    def test_derived_from_status_url(self):
        server.CONFIG.pop("ro3_base_url", None)
        server.RO3_STATUS_URL = "http://127.0.0.1:5380/ro3emu/status"
        self.assertEqual(server.ro3_base_url(), "http://127.0.0.1:5380")
        server.RO3_STATUS_URL = "http://10.0.0.5:5380/game/ro3emu/status/"
        self.assertEqual(server.ro3_base_url(), "http://10.0.0.5:5380/game")

    def test_status_url_without_known_suffix_falls_back_to_origin(self):
        server.CONFIG.pop("ro3_base_url", None)
        server.RO3_STATUS_URL = "http://127.0.0.1:5380/health"
        self.assertEqual(server.ro3_base_url(), "http://127.0.0.1:5380")

    def test_explicit_config_key_wins(self):
        server.CONFIG["ro3_base_url"] = "http://127.0.0.1:6000/"
        server.RO3_STATUS_URL = "http://127.0.0.1:5380/ro3emu/status"
        self.assertEqual(server.ro3_base_url(), "http://127.0.0.1:6000")


class TestOnlineAndMetricsEndpoints(unittest.TestCase):
    def setUp(self):
        saved = {
            "db": server.DB_PATH,
            "status": server.RO3_STATUS_URL,
            "config": dict(server.CONFIG),
            "timeout": server.RO3_HTTP_TIMEOUT,
            "max_bytes": server.RO3_MAX_RESPONSE_BYTES,
        }
        self.addCleanup(self._restore, saved)

        tmp = tempfile.TemporaryDirectory(ignore_cleanup_errors=True)
        self.addCleanup(tmp.cleanup)
        db_path = os.path.join(tmp.name, "ro3emu.db")
        with closing(sqlite3.connect(db_path)) as con:
            con.execute("CREATE TABLE account (name TEXT PRIMARY KEY, password_hash BLOB, salt BLOB, created_utc TEXT)")
            con.commit()

        self.fake = ThreadingHTTPServer(("127.0.0.1", 0), FakeRo3EmuHandler)
        self.fake.routes = {
            "/ro3emu/status": json_route({"online": True, "players": 2}),
            "/ro3emu/online": json_route(ONLINE_FIXTURE),
            "/ro3emu/metrics": json_route(METRICS_FIXTURE),
        }
        threading.Thread(target=self.fake.serve_forever, kwargs={"poll_interval": 0.05}, daemon=True).start()
        self.addCleanup(self._stop, self.fake)

        server.DB_PATH = db_path
        server.RO3_STATUS_URL = "http://127.0.0.1:%d/ro3emu/status" % self.fake.server_address[1]
        server.CONFIG.pop("ro3_base_url", None)
        server.CONFIG.pop("show_player_ips", None)
        server.CONFIG["admin_users"] = [{"username": "boss", "password": "Pw-123456"}]
        server.init_tables()

        self.panel = ThreadingHTTPServer(("127.0.0.1", 0), server.CPanelRequestHandler)
        threading.Thread(target=self.panel.serve_forever, kwargs={"poll_interval": 0.05}, daemon=True).start()
        self.addCleanup(self._stop, self.panel)
        self.base = "http://127.0.0.1:%d" % self.panel.server_address[1]
        self.token = self._login()

    @staticmethod
    def _stop(httpd):
        httpd.shutdown()
        httpd.server_close()

    @staticmethod
    def _restore(saved):
        server.DB_PATH = saved["db"]
        server.RO3_STATUS_URL = saved["status"]
        server.RO3_HTTP_TIMEOUT = saved["timeout"]
        server.RO3_MAX_RESPONSE_BYTES = saved["max_bytes"]
        server.CONFIG.clear()
        server.CONFIG.update(saved["config"])
        server.ACTIVE_SESSIONS.clear()

    def _login(self):
        req = urllib.request.Request(
            self.base + "/api/admin/login",
            data=json.dumps({"username": "boss", "password": "Pw-123456"}).encode(),
            headers={"Content-Type": "application/json"},
        )
        with urllib.request.urlopen(req, timeout=10) as resp:
            return json.loads(resp.read())["token"]

    def _get(self, path, token="default"):
        token = self.token if token == "default" else token
        headers = {"Authorization": "Bearer " + token} if token else {}
        req = urllib.request.Request(self.base + path, headers=headers)
        with urllib.request.urlopen(req, timeout=10) as resp:
            raw = resp.read()
            return resp.status, json.loads(raw), raw.decode("utf-8")

    # --- available path ---

    def test_metrics_returns_selected_verified_fields(self):
        status, data, _ = self._get("/api/admin/metrics")

        self.assertEqual(status, 200)
        self.assertIs(data["available"], True)
        m = data["metrics"]
        self.assertEqual(m["captured_utc"], "2026-10-28T12:00:00+00:00")
        self.assertEqual(m["uptime_seconds"], 3725.5)
        self.assertEqual(m["connections"], 3)
        self.assertEqual(m["sessions"]["login"], 1)
        self.assertEqual(m["sessions"]["loading"], 1)
        self.assertEqual(m["sessions"]["in_world"], 2)
        self.assertEqual(m["sessions"]["by_map"], [
            {"map": 10100, "scene_name": "Prontera", "count": 3},
            {"map": 99999, "scene_name": "Mapa 99999", "count": 1},
        ])
        self.assertEqual(m["database"], {"statements": 120, "commits": 40})
        self.assertEqual(m["runtime"], {"working_set_bytes": 157286400})
        self.assertEqual(m["errors"], {"exceptions": 1, "error_logs": 2})
        # Only selected fields leave the panel, never the raw snapshot.
        for raw_key in ("loop", "wire", "epoch", "semantics", "operations"):
            self.assertNotIn(raw_key, m)

    def test_metrics_missing_sections_degrade_to_null(self):
        self.fake.routes["/ro3emu/metrics"] = json_route({"elapsedSeconds": 10})
        _, data, _ = self._get("/api/admin/metrics")

        self.assertIs(data["available"], True)
        m = data["metrics"]
        self.assertEqual(m["uptime_seconds"], 10)
        self.assertIsNone(m["connections"])
        self.assertIsNone(m["sessions"]["in_world"])
        self.assertEqual(m["sessions"]["by_map"], [])
        self.assertIsNone(m["runtime"]["working_set_bytes"])

    def test_online_lists_players_with_scene_names_and_hides_ips_by_default(self):
        status, data, raw = self._get("/api/admin/online")

        self.assertEqual(status, 200)
        self.assertIs(data["available"], True)
        self.assertIs(data["show_ips"], False)
        self.assertEqual(data["count"], 3)
        self.assertEqual(data["players"][0], {
            "account": "alice", "character": "Aria", "scene_id": 10100,
            "scene_name": "Prontera", "x": 12.3, "z": -3.2,
        })
        self.assertEqual(data["players"][1]["character"], None)
        self.assertEqual(data["players"][1]["scene_id"], None)
        self.assertEqual(data["players"][1]["scene_name"], None)
        self.assertEqual(data["players"][2]["scene_name"], "Mapa 99999")
        for player in data["players"]:
            self.assertNotIn("remote", player)
        for ip in ("203.0.113.7", "198.51.100.2", "192.0.2.9"):
            self.assertNotIn(ip, raw)

    def test_online_shows_ips_only_when_enabled(self):
        server.CONFIG["show_player_ips"] = True
        _, data, _ = self._get("/api/admin/online")

        self.assertIs(data["show_ips"], True)
        self.assertEqual(data["players"][0]["remote"], "203.0.113.7:51234")

    def test_online_truthy_non_boolean_flag_keeps_ips_hidden(self):
        server.CONFIG["show_player_ips"] = "false"
        _, data, raw = self._get("/api/admin/online")

        self.assertIs(data["show_ips"], False)
        self.assertNotIn("203.0.113.7", raw)

    def test_explicit_base_url_is_used(self):
        server.RO3_STATUS_URL = "http://127.0.0.1:9/ro3emu/status"
        server.CONFIG["ro3_base_url"] = "http://127.0.0.1:%d" % self.fake.server_address[1]
        _, data, _ = self._get("/api/admin/online")

        self.assertIs(data["available"], True)

    # --- degraded paths: always 200 with available:false ---

    def assert_unavailable(self, path, reason_fragment):
        status, data, _ = self._get(path)
        self.assertEqual(status, 200)
        self.assertIs(data["available"], False)
        self.assertIn(reason_fragment, data["reason"])
        return data

    def test_missing_endpoints_report_loopback_requirement(self):
        del self.fake.routes["/ro3emu/online"]
        del self.fake.routes["/ro3emu/metrics"]

        self.assert_unavailable("/api/admin/online", "loopback")
        self.assert_unavailable("/api/admin/metrics", "loopback")

    def test_server_error_is_reported(self):
        self.fake.routes["/ro3emu/metrics"] = (500, b"boom", 0)
        self.assert_unavailable("/api/admin/metrics", "HTTP 500")

    def test_slow_endpoint_times_out(self):
        server.RO3_HTTP_TIMEOUT = 0.3
        self.fake.routes["/ro3emu/online"] = json_route(ONLINE_FIXTURE, delay=1.5)
        self.fake.routes["/ro3emu/metrics"] = json_route(METRICS_FIXTURE, delay=1.5)

        started = time.monotonic()
        self.assert_unavailable("/api/admin/online", "a tiempo")
        self.assert_unavailable("/api/admin/metrics", "a tiempo")
        self.assertLess(time.monotonic() - started, 2.5)

    def test_invalid_json(self):
        self.fake.routes["/ro3emu/online"] = (200, b"{not json", 0)
        self.fake.routes["/ro3emu/metrics"] = (200, b"\xff\xfe garbage", 0)

        self.assert_unavailable("/api/admin/online", "JSON")
        self.assert_unavailable("/api/admin/metrics", "JSON")

    def test_oversize_body_is_rejected(self):
        server.RO3_MAX_RESPONSE_BYTES = 1024
        big = [dict(ONLINE_FIXTURE[0], account="p%d" % i) for i in range(200)]
        self.fake.routes["/ro3emu/online"] = json_route(big)

        self.assert_unavailable("/api/admin/online", "tamaño")

    def test_unexpected_shape(self):
        self.fake.routes["/ro3emu/online"] = json_route({"players": []})
        self.fake.routes["/ro3emu/metrics"] = json_route([1, 2, 3])

        self.assert_unavailable("/api/admin/online", "formato")
        self.assert_unavailable("/api/admin/metrics", "formato")

    def test_unreachable_ro3emu(self):
        with closing(socket.socket()) as s:
            s.bind(("127.0.0.1", 0))
            free_port = s.getsockname()[1]
        server.RO3_STATUS_URL = "http://127.0.0.1:%d/ro3emu/status" % free_port

        # A closed port is refused at once on Linux/macOS, but Windows retries the
        # connection and the request ends as a timeout; both mean "unavailable".
        for path in ("/api/admin/online", "/api/admin/metrics"):
            with self.subTest(path=path):
                status, data, _ = self._get(path)
                self.assertEqual(status, 200)
                self.assertIs(data["available"], False)
                self.assertTrue(
                    "conectar" in data["reason"] or "a tiempo" in data["reason"],
                    data["reason"],
                )

    # --- auth ---

    def test_endpoints_require_admin_session(self):
        for path in ("/api/admin/online", "/api/admin/metrics"):
            with self.subTest(path=path):
                with self.assertRaises(urllib.error.HTTPError) as ctx:
                    self._get(path, token=None)
                self.assertEqual(ctx.exception.code, 401)
                ctx.exception.close()


class TestDashboardMarkup(unittest.TestCase):
    """Every element id admin.js looks up must exist in index.html."""

    def test_admin_js_element_ids_exist_in_index_html(self):
        with open(os.path.join(ROOT, "public", "admin.js"), encoding="utf-8") as f:
            js = f.read()
        with open(os.path.join(ROOT, "public", "index.html"), encoding="utf-8") as f:
            html = f.read()
        ids = set(re.findall(r"getElementById\('([^']+)'\)", js))
        for required in ("metrics-panel", "metrics-unavailable", "online-tbody", "online-unavailable"):
            self.assertIn(required, ids)
        missing = sorted(i for i in ids if 'id="%s"' % i not in html)
        self.assertEqual(missing, [])


if __name__ == "__main__":
    unittest.main()
