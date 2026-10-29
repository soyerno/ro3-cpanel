import unittest
import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
import server

class TestAuth(unittest.TestCase):
    def setUp(self):
        # Configure test admin user
        server.CONFIG["admin_users"] = [
            {"username": "testadmin", "password": "TestPassword123!"}
        ]

    def test_authenticate_admin_success(self):
        valid, user = server.authenticate_admin("testadmin", "TestPassword123!")
        self.assertTrue(valid)
        self.assertEqual(user, "testadmin")

    def test_authenticate_admin_case_insensitive(self):
        valid, user = server.authenticate_admin("TESTADMIN", "TestPassword123!")
        self.assertTrue(valid)
        self.assertEqual(user, "testadmin")

    def test_authenticate_admin_wrong_password(self):
        valid, user = server.authenticate_admin("testadmin", "WrongPassword")
        self.assertFalse(valid)
        self.assertIsNone(user)

    def test_authenticate_admin_with_client_password_hash(self):
        # Test authenticating with client-side derived PBKDF2 hash (non-plaintext)
        import sqlite3, tempfile, hashlib
        with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as tf:
            db_path = tf.name
        try:
            con = sqlite3.connect(db_path)
            con.execute("CREATE TABLE account (name TEXT PRIMARY KEY, password_hash BLOB, salt BLOB, created_utc TEXT)")
            salt = b"1234567890123456"
            pw_hash = hashlib.pbkdf2_hmac("sha256", b"MySecretGamePass", salt, 100000, 32)
            con.execute("INSERT INTO account VALUES ('erno', ?, ?, '2026-10-25')", (pw_hash, salt))
            con.commit()
            con.close()

            server.CONFIG["admin_users"] = [{"username": "erno"}]
            server.DB_PATH = db_path

            # Successful auth with client-derived hash
            valid, user = server.authenticate_admin("erno", password_hash=pw_hash.hex())
            self.assertTrue(valid)
            self.assertEqual(user, "erno")

            # Mismatched hash
            valid, user = server.authenticate_admin("erno", password_hash="00" * 32)
            self.assertFalse(valid)

            # Plain password fallback still works
            valid, user = server.authenticate_admin("erno", password="MySecretGamePass")
            self.assertTrue(valid)
        finally:
            if os.path.exists(db_path):
                os.remove(db_path)

    def test_authenticate_admin_non_existent(self):
        valid, user = server.authenticate_admin("unknown_user", "AnyPassword")
        self.assertFalse(valid)
        self.assertIsNone(user)

if __name__ == "__main__":
    unittest.main()
