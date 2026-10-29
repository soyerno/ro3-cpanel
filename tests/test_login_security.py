import io
import json
import os
import sys
import tempfile
import threading
import unittest
import urllib.error
import urllib.request
from contextlib import redirect_stderr, redirect_stdout
from http.server import ThreadingHTTPServer
from unittest import mock

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
import server


class FakeClock:
    def __init__(self, start=1000.0):
        self.now = start

    def __call__(self):
        return self.now

    def advance(self, seconds):
        self.now += seconds


class TestLoginThrottle(unittest.TestCase):
    def setUp(self):
        self.clock = FakeClock()
        self.throttle = server.LoginThrottle(max_failures=3, window_seconds=60, clock=self.clock)

    def test_allows_below_max_failures(self):
        self.throttle.record_failure("ip:1.2.3.4")
        self.throttle.record_failure("ip:1.2.3.4")
        self.assertEqual(self.throttle.retry_after("ip:1.2.3.4"), 0)

    def test_blocks_at_max_failures(self):
        for _ in range(3):
            self.throttle.record_failure("ip:1.2.3.4")
        retry = self.throttle.retry_after("ip:1.2.3.4")
        self.assertGreater(retry, 0)
        self.assertLessEqual(retry, 60)

    def test_block_applies_to_any_of_the_given_keys(self):
        for _ in range(3):
            self.throttle.record_failure("user:admin")
        self.assertGreater(self.throttle.retry_after("ip:9.9.9.9", "user:admin"), 0)
        self.assertEqual(self.throttle.retry_after("ip:9.9.9.9", "user:other"), 0)

    def test_record_failure_counts_every_key(self):
        for _ in range(3):
            self.throttle.record_failure("ip:1.2.3.4", "user:admin")
        self.assertGreater(self.throttle.retry_after("ip:1.2.3.4"), 0)
        self.assertGreater(self.throttle.retry_after("user:admin"), 0)

    def test_unblocks_after_window(self):
        for _ in range(3):
            self.throttle.record_failure("ip:1.2.3.4")
        self.clock.advance(59)
        self.assertGreater(self.throttle.retry_after("ip:1.2.3.4"), 0)
        self.clock.advance(1.5)
        self.assertEqual(self.throttle.retry_after("ip:1.2.3.4"), 0)

    def test_sliding_window_drops_only_old_failures(self):
        self.throttle.record_failure("ip:1.2.3.4")
        self.clock.advance(40)
        self.throttle.record_failure("ip:1.2.3.4")
        self.throttle.record_failure("ip:1.2.3.4")
        self.assertGreater(self.throttle.retry_after("ip:1.2.3.4"), 0)
        self.clock.advance(21)
        # First failure expired; the two recent ones remain (below max).
        self.assertEqual(self.throttle.retry_after("ip:1.2.3.4"), 0)
        self.throttle.record_failure("ip:1.2.3.4")
        self.assertGreater(self.throttle.retry_after("ip:1.2.3.4"), 0)

    def test_reset_clears_failures(self):
        for _ in range(3):
            self.throttle.record_failure("ip:1.2.3.4", "user:admin")
        self.throttle.reset("ip:1.2.3.4", "user:admin")
        self.assertEqual(self.throttle.retry_after("ip:1.2.3.4", "user:admin"), 0)

    def test_concurrent_failures_are_all_counted(self):
        throttle = server.LoginThrottle(max_failures=1000, window_seconds=60, clock=self.clock)
        threads = [
            threading.Thread(target=lambda: [throttle.record_failure("ip:x") for _ in range(50)])
            for _ in range(8)
        ]
        for t in threads:
            t.start()
        for t in threads:
            t.join()
        self.assertEqual(throttle.failure_count("ip:x"), 400)

    def test_reserve_admits_at_most_max_failures_under_a_parallel_burst(self):
        # Check and record must be one atomic step, or a burst gets extra guesses.
        throttle = server.LoginThrottle(max_failures=5, window_seconds=60, clock=self.clock)
        barrier = threading.Barrier(40)
        admitted = []

        def attempt():
            barrier.wait()
            if throttle.reserve("ip:x", "user:admin") == 0:
                admitted.append(1)

        threads = [threading.Thread(target=attempt) for _ in range(40)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()
        self.assertEqual(len(admitted), 5)
        self.assertEqual(throttle.failure_count("user:admin"), 5)

    def test_reserve_does_not_record_a_blocked_attempt(self):
        throttle = server.LoginThrottle(max_failures=2, window_seconds=60, clock=self.clock)
        self.assertEqual(throttle.reserve("user:a"), 0)
        self.assertEqual(throttle.reserve("user:a"), 0)
        self.assertGreater(throttle.reserve("user:a"), 0)
        self.assertEqual(throttle.failure_count("user:a"), 2)


class TestAdminPasswordHash(unittest.TestCase):
    def setUp(self):
        original_admins = server.CONFIG.get("admin_users")
        self.addCleanup(server.CONFIG.__setitem__, "admin_users", original_admins)
        original_db = server.DB_PATH
        self.addCleanup(setattr, server, "DB_PATH", original_db)
        tmp = tempfile.TemporaryDirectory(ignore_cleanup_errors=True)
        self.addCleanup(tmp.cleanup)
        server.DB_PATH = os.path.join(tmp.name, "missing.db")

    def test_hash_format(self):
        encoded = server.make_admin_password_hash("s3cret", iterations=1000, salt=b"\x01" * 16)
        parts = encoded.split("$")
        self.assertEqual(len(parts), 4)
        self.assertEqual(parts[0], "pbkdf2_sha256")
        self.assertEqual(parts[1], "1000")
        self.assertEqual(parts[2], "01" * 16)
        self.assertEqual(len(bytes.fromhex(parts[3])), 32)

    def test_default_hash_uses_ro3emu_parameters(self):
        encoded = server.make_admin_password_hash("s3cret")
        _, iterations, salt_hex, hash_hex = encoded.split("$")
        self.assertEqual(iterations, "100000")
        self.assertEqual(len(bytes.fromhex(salt_hex)), 16)
        self.assertEqual(len(bytes.fromhex(hash_hex)), 32)

    def test_random_salt_per_hash(self):
        a = server.make_admin_password_hash("same", iterations=1000)
        b = server.make_admin_password_hash("same", iterations=1000)
        self.assertNotEqual(a, b)

    def test_roundtrip(self):
        encoded = server.make_admin_password_hash("s3cret", iterations=1000)
        self.assertTrue(server.verify_admin_password_hash("s3cret", encoded))

    def test_wrong_password(self):
        encoded = server.make_admin_password_hash("s3cret", iterations=1000)
        self.assertFalse(server.verify_admin_password_hash("wrong", encoded))

    def test_malformed_hashes_return_false(self):
        valid = server.make_admin_password_hash("s3cret", iterations=1000)
        _, it, salt_hex, hash_hex = valid.split("$")
        malformed = [
            "",
            "garbage",
            None,
            12345,
            f"md5${it}${salt_hex}${hash_hex}",
            f"pbkdf2_sha256$abc${salt_hex}${hash_hex}",
            f"pbkdf2_sha256$0${salt_hex}${hash_hex}",
            f"pbkdf2_sha256$-5${salt_hex}${hash_hex}",
            f"pbkdf2_sha256${it}$zz${hash_hex}",
            f"pbkdf2_sha256${it}${salt_hex}$nothex",
            f"pbkdf2_sha256${it}${salt_hex}$",
            f"pbkdf2_sha256${it}${salt_hex}",
            f"pbkdf2_sha256${it}${salt_hex}${hash_hex}$extra",
        ]
        for encoded in malformed:
            with self.subTest(encoded=encoded):
                self.assertFalse(server.verify_admin_password_hash("s3cret", encoded))

    def test_non_string_password_returns_false(self):
        encoded = server.make_admin_password_hash("s3cret", iterations=1000)
        self.assertFalse(server.verify_admin_password_hash(None, encoded))

    def test_authenticate_with_password_hash(self):
        server.CONFIG["admin_users"] = [
            {"username": "hashadmin", "password_hash": server.make_admin_password_hash("Hashed!1", iterations=1000)}
        ]
        self.assertEqual(server.authenticate_admin("HashAdmin", "Hashed!1"), (True, "hashadmin"))
        self.assertEqual(server.authenticate_admin("hashadmin", "nope"), (False, None))

    def test_password_hash_takes_precedence_over_password(self):
        server.CONFIG["admin_users"] = [
            {
                "username": "both",
                "password": "PlainOne",
                "password_hash": server.make_admin_password_hash("HashedOne", iterations=1000),
            }
        ]
        self.assertEqual(server.authenticate_admin("both", "HashedOne"), (True, "both"))
        self.assertEqual(server.authenticate_admin("both", "PlainOne"), (False, None))

    def test_malformed_password_hash_rejects_login(self):
        server.CONFIG["admin_users"] = [
            {"username": "broken", "password": "PlainOne", "password_hash": "not-a-hash"}
        ]
        self.assertEqual(server.authenticate_admin("broken", "PlainOne"), (False, None))

    def test_plain_password_still_works(self):
        server.CONFIG["admin_users"] = [{"username": "plain", "password": "Plain!1"}]
        self.assertEqual(server.authenticate_admin("plain", "Plain!1"), (True, "plain"))
        self.assertEqual(server.authenticate_admin("plain", "Plain!2"), (False, None))

    def test_non_string_password_is_rejected(self):
        server.CONFIG["admin_users"] = [{"username": "plain", "password": "Plain!1"}]
        self.assertEqual(server.authenticate_admin("plain", 12345), (False, None))


class TestPlaintextPasswordWarning(unittest.TestCase):
    def test_warns_only_for_plain_password_entries(self):
        admins = [
            {"username": "plain", "password": "x"},
            {"username": "hashed", "password_hash": "pbkdf2_sha256$1$00$00"},
            {"username": "both", "password": "x", "password_hash": "pbkdf2_sha256$1$00$00"},
        ]
        stream = io.StringIO()
        warned = server.warn_plaintext_admin_passwords(admins, stream=stream)
        self.assertEqual(warned, ["plain"])
        output = stream.getvalue()
        self.assertIn("plain", output)
        self.assertIn("--hash-password", output)
        self.assertNotIn("hashed", output)


class TestHashPasswordCli(unittest.TestCase):
    def test_default_args_do_not_request_hashing(self):
        self.assertFalse(server.parse_args([]).hash_password)

    def test_hash_password_prints_verifiable_hash_without_starting_server(self):
        out = io.StringIO()
        with mock.patch("getpass.getpass", side_effect=["Cli!Pass1", "Cli!Pass1"]), \
                mock.patch.object(server, "ThreadingHTTPServer") as fake_server, \
                redirect_stdout(out):
            code = server.main(["--hash-password"])
        self.assertEqual(code, 0)
        fake_server.assert_not_called()
        encoded = out.getvalue().strip()
        self.assertTrue(encoded.startswith("pbkdf2_sha256$100000$"))
        self.assertTrue(server.verify_admin_password_hash("Cli!Pass1", encoded))

    def test_hash_password_rejects_mismatch(self):
        out, err = io.StringIO(), io.StringIO()
        with mock.patch("getpass.getpass", side_effect=["one", "two"]), \
                redirect_stdout(out), redirect_stderr(err):
            code = server.main(["--hash-password"])
        self.assertEqual(code, 1)
        self.assertEqual(out.getvalue(), "")
        self.assertIn("do not match", err.getvalue())

    def test_hash_password_rejects_empty(self):
        err = io.StringIO()
        with mock.patch("getpass.getpass", side_effect=["", ""]), redirect_stderr(err):
            code = server.main(["--hash-password"])
        self.assertEqual(code, 1)


class TestLoginEndpointThrottling(unittest.TestCase):
    MAX_FAILURES = 3
    WINDOW = 60

    def setUp(self):
        for name in ("DB_PATH", "LOGIN_THROTTLE", "ACTIVE_SESSIONS"):
            self.addCleanup(setattr, server, name, getattr(server, name))
        original_admins = server.CONFIG.get("admin_users")
        self.addCleanup(server.CONFIG.__setitem__, "admin_users", original_admins)

        tmp = tempfile.TemporaryDirectory(ignore_cleanup_errors=True)
        self.addCleanup(tmp.cleanup)
        server.DB_PATH = os.path.join(tmp.name, "missing.db")
        server.ACTIVE_SESSIONS = {}
        server.CONFIG["admin_users"] = [{"username": "webadmin", "password": "Correct!1"}]
        self.clock = FakeClock()
        server.LOGIN_THROTTLE = server.LoginThrottle(
            max_failures=self.MAX_FAILURES, window_seconds=self.WINDOW, clock=self.clock
        )

        self.httpd = ThreadingHTTPServer(("127.0.0.1", 0), server.CPanelRequestHandler)
        thread = threading.Thread(target=self.httpd.serve_forever, daemon=True)
        thread.start()
        self.addCleanup(self.httpd.server_close)
        self.addCleanup(self.httpd.shutdown)
        self.base_url = f"http://127.0.0.1:{self.httpd.server_address[1]}"

    def login(self, username, password, ip="10.0.0.1"):
        data = json.dumps({"username": username, "password": password}).encode("utf-8")
        req = urllib.request.Request(
            self.base_url + "/api/admin/login",
            data=data,
            headers={"Content-Type": "application/json", "X-Forwarded-For": ip},
            method="POST",
        )
        try:
            with urllib.request.urlopen(req, timeout=10) as resp:
                return resp.status, dict(resp.headers), json.loads(resp.read().decode("utf-8"))
        except urllib.error.HTTPError as err:
            body = err.read().decode("utf-8")
            err.close()
            return err.code, dict(err.headers), json.loads(body)

    def fail_n_times(self, n, username="webadmin", ip="10.0.0.1"):
        for _ in range(n):
            status, _, _ = self.login(username, "Wrong!", ip=ip)
            self.assertEqual(status, 401)

    def test_blocks_after_max_failures_even_with_correct_password(self):
        self.fail_n_times(self.MAX_FAILURES)
        status, headers, body = self.login("webadmin", "Correct!1")
        self.assertEqual(status, 429)
        self.assertIn("error", body)
        self.assertGreater(int(headers["Retry-After"]), 0)
        self.assertNotIn("token", body)

    def test_same_ip_is_blocked_across_usernames(self):
        for i in range(self.MAX_FAILURES):
            status, _, _ = self.login(f"ghost{i}", "Wrong!", ip="10.0.0.7")
            self.assertEqual(status, 401)
        status, headers, _ = self.login("webadmin", "Correct!1", ip="10.0.0.7")
        self.assertEqual(status, 429)
        self.assertGreater(int(headers["Retry-After"]), 0)

    def test_same_username_blocked_from_different_forwarded_ip(self):
        self.fail_n_times(self.MAX_FAILURES, ip="10.0.0.1")
        status, headers, _ = self.login("WebAdmin", "Correct!1", ip="203.0.113.50")
        self.assertEqual(status, 429)
        self.assertGreater(int(headers["Retry-After"]), 0)

    def test_unblocks_after_window_expires(self):
        self.fail_n_times(self.MAX_FAILURES)
        self.assertEqual(self.login("webadmin", "Correct!1")[0], 429)
        self.clock.advance(self.WINDOW + 1)
        status, _, body = self.login("webadmin", "Correct!1")
        self.assertEqual(status, 200)
        self.assertTrue(body["success"])

    def test_success_resets_failures(self):
        self.fail_n_times(self.MAX_FAILURES - 1)
        status, _, _ = self.login("webadmin", "Correct!1")
        self.assertEqual(status, 200)
        # Counter was reset: another MAX_FAILURES - 1 failures must not block.
        self.fail_n_times(self.MAX_FAILURES - 1)
        status, _, _ = self.login("webadmin", "Correct!1")
        self.assertEqual(status, 200)

    def test_username_exceeding_max_characters_returns_400(self):
        long_user = "a" * 33
        status, _, body = self.login(long_user, "ValidPass123!")
        self.assertEqual(status, 400)
        self.assertIn("error", body)

    def test_password_exceeding_max_characters_returns_400(self):
        long_pass = "p" * 129
        status, _, body = self.login("webadmin", long_pass)
        self.assertEqual(status, 400)
        self.assertIn("error", body)

    def test_failed_attempt_reports_remaining_attempts(self):
        status, _, body = self.login("webadmin", "WrongPass")
        self.assertEqual(status, 401)
        self.assertEqual(body.get("remaining_attempts"), self.MAX_FAILURES - 1)
        self.assertIn("attempt(s) remaining", body["error"])

    def test_temporary_ban_response_includes_flag_and_retry_after(self):
        self.fail_n_times(self.MAX_FAILURES)
        status, headers, body = self.login("webadmin", "Correct!1")
        self.assertEqual(status, 429)
        self.assertTrue(body.get("temporary_ban"))
        self.assertGreater(body.get("retry_after"), 0)
        self.assertIn("Temporary ban active", body["error"])

    def test_rapid_empty_requests_trigger_lockout(self):
        for _ in range(self.MAX_FAILURES - 1):
            status, _, _ = self.login("", "")
            self.assertEqual(status, 400)
        status, headers, body = self.login("", "")
        self.assertEqual(status, 429)
        self.assertTrue(body.get("temporary_ban"))
        self.assertGreater(int(headers["Retry-After"]), 0)


if __name__ == "__main__":
    unittest.main()
