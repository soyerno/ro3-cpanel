import contextlib
import json
import os
import sqlite3
import sys
import tempfile
import threading
import unittest
import urllib.error
import urllib.request
from http.server import ThreadingHTTPServer
from unittest import mock

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
import server

ADMIN_USER = "boss"
ADMIN_PASSWORD = "Pw-123456"
SITE = "https://www.example.test"

CONFIG_KEYS = (
    "admin_users", "public_api_enabled", "public_api_cache_seconds", "player_api_enabled",
    "player_registration_enabled", "api_allowed_origins", "turnstile_secret_key",
)


class WebsiteAPITestBase(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory(ignore_cleanup_errors=True)
        self.addCleanup(tmp.cleanup)
        self.db_path = os.path.join(tmp.name, "ro3emu.db")

        saved = {k: server.CONFIG.get(k) for k in CONFIG_KEYS}
        original = (server.DB_PATH, server.PLAYER_LOGIN_THROTTLE, server.PLAYER_REGISTER_THROTTLE)

        def restore():
            for k, v in saved.items():
                if v is None:
                    server.CONFIG.pop(k, None)
                else:
                    server.CONFIG[k] = v
            server.DB_PATH, server.PLAYER_LOGIN_THROTTLE, server.PLAYER_REGISTER_THROTTLE = original
            server.PUBLIC_CACHE.clear()

        self.addCleanup(restore)

        server.DB_PATH = self.db_path
        server.PLAYER_LOGIN_THROTTLE = server.LoginThrottle(max_failures=5, window_seconds=900)
        server.PLAYER_REGISTER_THROTTLE = server.LoginThrottle(max_failures=3, window_seconds=3600)
        server.PUBLIC_CACHE.clear()
        server.CONFIG.update({
            "admin_users": [{"username": ADMIN_USER, "password": ADMIN_PASSWORD}],
            "public_api_enabled": True,
            "public_api_cache_seconds": 0,
            "player_api_enabled": True,
            "player_registration_enabled": True,
            "api_allowed_origins": [SITE],
            "turnstile_secret_key": "",
        })

        self.create_schema()
        server.init_tables()

        probe = mock.patch.object(server, "probe_ro3_status", return_value=(True, 7))
        probe.start()
        self.addCleanup(probe.stop)

        httpd = ThreadingHTTPServer(("127.0.0.1", 0), server.CPanelRequestHandler)
        thread = threading.Thread(target=httpd.serve_forever, daemon=True)
        thread.start()

        def stop_server():
            httpd.shutdown()
            httpd.server_close()
            thread.join(timeout=10)

        self.addCleanup(stop_server)
        self.base_url = "http://127.0.0.1:%d" % httpd.server_address[1]

    def create_schema(self):
        with contextlib.closing(sqlite3.connect(self.db_path)) as con:
            con.execute("CREATE TABLE account (name TEXT PRIMARY KEY, password_hash BLOB, salt BLOB, created_utc TEXT)")
            con.execute("CREATE TABLE auth_token (token TEXT PRIMARY KEY, account TEXT, kind TEXT, expires_utc TEXT)")
            con.execute("""
                CREATE TABLE role (
                    id INTEGER PRIMARY KEY, account TEXT NOT NULL, name TEXT NOT NULL,
                    sex INTEGER DEFAULT 1, career INTEGER DEFAULT 1000, level INTEGER DEFAULT 1,
                    job_level INTEGER DEFAULT 1, exp INTEGER DEFAULT 0, job_exp INTEGER DEFAULT 0,
                    stats TEXT DEFAULT '', currency TEXT DEFAULT '', bonus_points INTEGER DEFAULT 0,
                    scene_entry INTEGER DEFAULT 0, pos_x REAL DEFAULT 0, pos_y REAL DEFAULT 0, pos_z REAL DEFAULT 0,
                    last_login_time INTEGER DEFAULT 0, create_time INTEGER DEFAULT 0,
                    deleted_time INTEGER NOT NULL DEFAULT 0, emblems BLOB
                )
            """)
            con.execute("CREATE TABLE guild (id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT NOT NULL UNIQUE COLLATE NOCASE, state BLOB NOT NULL)")
            con.execute("CREATE TABLE guild_member (role_id INTEGER PRIMARY KEY, guild_id INTEGER NOT NULL REFERENCES guild(id))")
            con.commit()

    def add_account(self, name, password):
        pw_hash, salt = server.hash_ro3_password(password)
        with contextlib.closing(sqlite3.connect(self.db_path)) as con:
            con.execute("INSERT INTO account (name, password_hash, salt, created_utc) VALUES (?, ?, ?, '2026-01-01')",
                        (name, pw_hash, salt))
            con.commit()

    def add_role(self, role_id, name, account, level=1, currency="", deleted_time=0):
        with contextlib.closing(sqlite3.connect(self.db_path)) as con:
            con.execute(
                "INSERT INTO role (id, account, name, level, currency, deleted_time, pos_x) VALUES (?, ?, ?, ?, ?, ?, 12.5)",
                (role_id, account, name, level, currency, deleted_time),
            )
            con.commit()

    def query(self, sql, args=()):
        with contextlib.closing(sqlite3.connect(self.db_path)) as con:
            return con.execute(sql, args).fetchall()

    def request(self, method, path, body=None, cookie=None, headers=None):
        data = json.dumps(body).encode("utf-8") if body is not None else None
        req = urllib.request.Request(self.base_url + path, data=data, method=method)
        if data is not None:
            req.add_header("Content-Type", "application/json")
        if cookie:
            req.add_header("Cookie", cookie)
        for k, v in (headers or {}).items():
            req.add_header(k, v)
        try:
            with urllib.request.urlopen(req, timeout=15) as resp:
                raw = resp.read()
                return resp.status, (json.loads(raw) if raw else None), resp.headers
        except urllib.error.HTTPError as e:
            with e:
                raw = e.read()
                return e.code, (json.loads(raw) if raw else None), e.headers

    @staticmethod
    def session_cookie(headers):
        set_cookie = headers.get("Set-Cookie") or ""
        first = set_cookie.split(";")[0]
        return first if first.startswith(server.PLAYER_SESSION_COOKIE + "=") else None

    def login(self, username, password, **kwargs):
        status, data, headers = self.request("POST", "/api/player/login",
                                             {"username": username, "password": password}, **kwargs)
        return status, data, self.session_cookie(headers)


class PublicAPITest(WebsiteAPITestBase):
    def test_disabled_by_default_answers_not_found(self):
        server.CONFIG["public_api_enabled"] = False
        status, _, _ = self.request("GET", "/api/public/status")
        self.assertEqual(status, 404)
        self.assertFalse(server.DEFAULT_CONFIG["public_api_enabled"])
        self.assertFalse(server.DEFAULT_CONFIG["player_api_enabled"])

    def test_status_reports_counts(self):
        self.add_account("alice", "secret1")
        self.add_role(1, "Hero", "alice")
        self.add_role(2, "Gone", "alice", deleted_time=5)
        status, data, _ = self.request("GET", "/api/public/status")
        self.assertEqual(status, 200)
        self.assertEqual(data, {"online": True, "players_online": 7, "accounts": 1, "characters": 1, "guilds": 0})

    def test_rankings_never_expose_account_names(self):
        self.add_role(1, "Low", "alice", level=10)
        self.add_role(2, "High", "bob", level=50)
        status, data, _ = self.request("GET", "/api/public/rankings?type=level")
        self.assertEqual(status, 200)
        self.assertEqual([r["name"] for r in data["rankings"]], ["High", "Low"])
        self.assertEqual([r["rank"] for r in data["rankings"]], [1, 2])
        for row in data["rankings"]:
            self.assertNotIn("account", row)

    def test_rankings_limit_is_capped_and_type_checked(self):
        status, data, _ = self.request("GET", "/api/public/rankings?type=level&limit=500")
        self.assertEqual(status, 200)
        self.assertEqual(data["limit"], server.PUBLIC_LIST_MAX_LIMIT)
        status, _, _ = self.request("GET", "/api/public/rankings?type=accounts")
        self.assertEqual(status, 400)

    def test_guilds_are_listed_by_size(self):
        self.add_role(1, "A", "alice", level=5)
        self.add_role(2, "B", "bob", level=5)
        with contextlib.closing(sqlite3.connect(self.db_path)) as con:
            con.execute("INSERT INTO guild (id, name, state) VALUES (1, 'Small', '{}'), (2, 'Big', '{\"Level\": 3}')")
            con.execute("INSERT INTO guild_member (role_id, guild_id) VALUES (1, 2), (2, 2)")
            con.commit()
        status, data, _ = self.request("GET", "/api/public/guilds")
        self.assertEqual(status, 200)
        self.assertEqual([g["name"] for g in data["guilds"]], ["Big", "Small"])
        self.assertEqual(data["guilds"][0]["level"], 3)
        self.assertEqual(data["total"], 2)

    def test_cors_echoes_only_allowed_origins(self):
        _, _, headers = self.request("GET", "/api/public/status", headers={"Origin": SITE})
        self.assertEqual(headers.get("Access-Control-Allow-Origin"), SITE)
        _, _, headers = self.request("GET", "/api/public/status", headers={"Origin": "https://evil.test"})
        self.assertIsNone(headers.get("Access-Control-Allow-Origin"))
        server.CONFIG["api_allowed_origins"] = ["*"]
        _, _, headers = self.request("GET", "/api/public/status", headers={"Origin": "https://any.test"})
        self.assertEqual(headers.get("Access-Control-Allow-Origin"), "*")

    def test_replies_are_cached(self):
        server.CONFIG["public_api_cache_seconds"] = 60
        _, first, headers = self.request("GET", "/api/public/status")
        self.assertEqual(headers.get("Cache-Control"), "public, max-age=60")
        self.add_account("alice", "secret1")
        _, second, _ = self.request("GET", "/api/public/status")
        self.assertEqual(first, second)

    def test_missing_database_answers_service_unavailable(self):
        server.DB_PATH = os.path.join(os.path.dirname(self.db_path), "missing.db")
        status, data, _ = self.request("GET", "/api/public/status")
        self.assertEqual(status, 503)
        self.assertIn("error", data)

    def test_public_api_does_not_open_admin_endpoints(self):
        status, _, _ = self.request("GET", "/api/admin/stats")
        self.assertEqual(status, 401)


class PlayerAPITest(WebsiteAPITestBase):
    def test_disabled_answers_not_found(self):
        server.CONFIG["player_api_enabled"] = False
        status, _, _ = self.login("alice", "secret1")
        self.assertEqual(status, 404)

    def test_register_creates_a_ro3emu_compatible_account_and_signs_in(self):
        status, data, headers = self.request("POST", "/api/player/register", {"username": "Alice_1", "password": "secret1"})
        self.assertEqual(status, 201)
        self.assertEqual(data["account"], "Alice_1")
        cookie_header = headers.get("Set-Cookie")
        for attribute in ("HttpOnly", "SameSite=Lax", "Secure", "Path=/api/player"):
            self.assertIn(attribute, cookie_header)
        pw_hash, salt = self.query("SELECT password_hash, salt FROM account WHERE name='Alice_1'")[0]
        self.assertEqual(len(salt), 16)
        self.assertTrue(server.verify_ro3_password("secret1", pw_hash, salt))
        status, me, _ = self.request("GET", "/api/player/me", cookie=self.session_cookie(headers))
        self.assertEqual(status, 200)
        self.assertEqual(me["account"], "Alice_1")
        self.assertEqual(self.query("SELECT action FROM admin_audit_log")[-1][0], "player_register")

    def test_register_validation(self):
        cases = [
            ({"username": "ab", "password": "secret1"}, 400),
            ({"username": "bad name", "password": "secret1"}, 400),
            ({"username": "alice", "password": "123"}, 400),
            ({"username": "alice", "password": 123456}, 400),
        ]
        for body, expected in cases:
            with self.subTest(body=body):
                status, _, _ = self.request("POST", "/api/player/register", body)
                self.assertEqual(status, expected)

    def test_register_refuses_taken_names_ignoring_case_and_admin_names(self):
        self.add_account("Alice", "secret1")
        status, _, _ = self.request("POST", "/api/player/register", {"username": "alice", "password": "secret1"})
        self.assertEqual(status, 409)
        status, _, _ = self.request("POST", "/api/player/register", {"username": "BOSS", "password": "secret1"})
        self.assertEqual(status, 409)
        self.assertEqual(self.query("SELECT COUNT(*) FROM account")[0][0], 1)

    def test_register_can_be_closed(self):
        server.CONFIG["player_registration_enabled"] = False
        status, _, _ = self.request("POST", "/api/player/register", {"username": "alice", "password": "secret1"})
        self.assertEqual(status, 403)

    def test_register_is_rate_limited_per_ip(self):
        for i in range(3):
            status, _, _ = self.request("POST", "/api/player/register", {"username": f"user{i}", "password": "secret1"})
            self.assertEqual(status, 201)
        status, data, headers = self.request("POST", "/api/player/register", {"username": "user9", "password": "secret1"})
        self.assertEqual(status, 429)
        self.assertGreater(int(headers.get("Retry-After")), 0)

    def test_register_requires_turnstile_when_configured(self):
        server.CONFIG["turnstile_secret_key"] = "test-secret"
        real_urlopen = urllib.request.urlopen
        answer = {"body": b'{"success": false}'}
        sent = []

        def fake_urlopen(req, *args, **kwargs):
            if getattr(req, "full_url", "") != server.TURNSTILE_VERIFY_URL:
                return real_urlopen(req, *args, **kwargs)
            sent.append(req)
            resp = mock.MagicMock()
            resp.__enter__.return_value.read.return_value = answer["body"]
            return resp

        with mock.patch.object(urllib.request, "urlopen", side_effect=fake_urlopen):
            status, _, _ = self.request("POST", "/api/player/register",
                                        {"username": "alice", "password": "secret1", "turnstile_token": "x"})
            self.assertEqual(status, 400)
            answer["body"] = b'{"success": true}'
            status, _, _ = self.request("POST", "/api/player/register",
                                        {"username": "alice", "password": "secret1", "turnstile_token": "x"})
            self.assertEqual(status, 201)
            # Without a token the server refuses before asking Cloudflare.
            status, _, _ = self.request("POST", "/api/player/register", {"username": "bob", "password": "secret1"})
            self.assertEqual(status, 400)
        self.assertEqual(len(sent), 2)
        self.assertIn(b"secret=test-secret", sent[0].data)

    def test_login_and_me_show_only_own_characters(self):
        self.add_account("alice", "secret1")
        self.add_account("bob", "secret2")
        self.add_role(1, "Mine", "alice", level=9, currency="1:500,7:3")
        self.add_role(2, "NotMine", "bob")
        status, _, _ = self.login("alice", "wrong-pass")
        self.assertEqual(status, 401)
        status, data, cookie = self.login("alice", "secret1")
        self.assertEqual(status, 200)
        self.assertEqual(data, {"success": True, "account": "alice"})
        status, me, _ = self.request("GET", "/api/player/me", cookie=cookie)
        self.assertEqual(status, 200)
        self.assertEqual([c["name"] for c in me["characters"]], ["Mine"])
        self.assertEqual(me["characters"][0]["currency"], {"zeny": 500})
        self.assertNotIn("pos", me["characters"][0])
        self.assertFalse(me["banned"])

    def test_login_is_exact_case_and_throttled(self):
        self.add_account("alice", "secret1")
        status, _, _ = self.login("ALICE", "secret1")
        self.assertEqual(status, 401)
        for _ in range(4):
            self.login("alice", "nope-nope")
        status, data, _ = self.login("alice", "secret1")
        self.assertEqual(status, 429)
        self.assertIn("retry_after", data)

    def test_me_requires_a_player_session(self):
        status, _, _ = self.request("GET", "/api/player/me")
        self.assertEqual(status, 401)
        status, data, _ = self.request("GET", "/api/player/session")
        self.assertEqual(data, {"authenticated": False})

    def test_player_session_is_not_an_admin_session(self):
        self.add_account(ADMIN_USER, ADMIN_PASSWORD)
        _, _, cookie = self.login(ADMIN_USER, ADMIN_PASSWORD)
        token = cookie.split("=", 1)[1]
        for headers in ({"Cookie": "ro3_admin_session=" + token}, {"Authorization": "Bearer " + token}):
            status, _, _ = self.request("GET", "/api/admin/stats", headers=headers)
            self.assertEqual(status, 401)

    def test_change_password(self):
        self.add_account("alice", "secret1")
        with contextlib.closing(sqlite3.connect(self.db_path)) as con:
            con.execute("INSERT INTO auth_token (token, account, kind, expires_utc) VALUES ('t', 'alice', 'login', '')")
            con.commit()
        _, _, cookie = self.login("alice", "secret1")
        _, _, other = self.login("alice", "secret1")

        status, _, _ = self.request("POST", "/api/player/change-password",
                                    {"current_password": "bad-pass", "new_password": "secret2"}, cookie=cookie)
        self.assertEqual(status, 400)
        status, _, _ = self.request("POST", "/api/player/change-password",
                                    {"current_password": "secret1", "new_password": "secret2"}, cookie=cookie)
        self.assertEqual(status, 200)

        self.assertEqual(self.request("GET", "/api/player/me", cookie=cookie)[0], 200)
        self.assertEqual(self.request("GET", "/api/player/me", cookie=other)[0], 401)
        self.assertEqual(self.query("SELECT COUNT(*) FROM auth_token")[0][0], 0)
        self.assertEqual(self.login("alice", "secret1")[0], 401)
        self.assertEqual(self.login("alice", "secret2")[0], 200)

    def test_logout_ends_the_session(self):
        self.add_account("alice", "secret1")
        _, _, cookie = self.login("alice", "secret1")
        status, _, headers = self.request("POST", "/api/player/logout", {}, cookie=cookie)
        self.assertEqual(status, 200)
        self.assertIn("Max-Age=0", headers.get("Set-Cookie"))
        self.assertEqual(self.request("GET", "/api/player/me", cookie=cookie)[0], 401)

    def test_admin_actions_end_player_sessions(self):
        self.add_account("alice", "secret1")
        _, _, cookie = self.login("alice", "secret1")
        status, admin, _ = self.request("POST", "/api/admin/login", {"username": ADMIN_USER, "password": ADMIN_PASSWORD})
        self.assertEqual(status, 200)
        status, _, _ = self.request("POST", "/api/admin/accounts/update-password",
                                    {"username": "alice", "new_password": "secret9"},
                                    headers={"Authorization": "Bearer " + admin["token"]})
        self.assertEqual(status, 200)
        self.assertEqual(self.request("GET", "/api/player/me", cookie=cookie)[0], 401)

    def test_deleted_account_ends_its_session(self):
        self.add_account("alice", "secret1")
        _, _, cookie = self.login("alice", "secret1")
        with contextlib.closing(sqlite3.connect(self.db_path)) as con:
            con.execute("DELETE FROM account WHERE name='alice'")
            con.commit()
        self.assertEqual(self.request("GET", "/api/player/me", cookie=cookie)[0], 401)

    def test_cross_site_posts_need_an_allowed_origin(self):
        self.add_account("alice", "secret1")
        status, _, _ = self.login("alice", "secret1", headers={"Origin": "https://evil.test"})
        self.assertEqual(status, 403)
        status, _, headers = self.request("POST", "/api/player/login", {"username": "alice", "password": "secret1"},
                                          headers={"Origin": SITE})
        self.assertEqual(status, 200)
        self.assertEqual(headers.get("Access-Control-Allow-Origin"), SITE)
        self.assertEqual(headers.get("Access-Control-Allow-Credentials"), "true")

    def test_wildcard_origin_never_applies_to_player_api(self):
        server.CONFIG["api_allowed_origins"] = ["*"]
        self.add_account("alice", "secret1")
        status, _, _ = self.login("alice", "secret1", headers={"Origin": "https://evil.test"})
        self.assertEqual(status, 403)

    def test_preflight(self):
        status, _, headers = self.request("OPTIONS", "/api/player/login", headers={"Origin": SITE})
        self.assertEqual(status, 204)
        self.assertEqual(headers.get("Access-Control-Allow-Origin"), SITE)
        self.assertIn("POST", headers.get("Access-Control-Allow-Methods"))
        status, _, headers = self.request("OPTIONS", "/api/player/login", headers={"Origin": "https://evil.test"})
        self.assertIsNone(headers.get("Access-Control-Allow-Origin"))


if __name__ == "__main__":
    unittest.main()
