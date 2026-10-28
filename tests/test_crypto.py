import unittest
import hashlib
import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
import server

class TestCrypto(unittest.TestCase):
    def test_hash_ro3_password(self):
        password = "SuperTestPassword123!"
        pw_hash, salt = server.hash_ro3_password(password)

        self.assertEqual(len(salt), 16)
        self.assertEqual(len(pw_hash), 32)

        # Manually compute and verify
        expected = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, 100000, 32)
        self.assertEqual(pw_hash, expected)

    def test_verify_ro3_password(self):
        password = "AnotherTestPassword!"
        pw_hash, salt = server.hash_ro3_password(password)

        self.assertTrue(server.verify_ro3_password(password, pw_hash, salt))
        self.assertFalse(server.verify_ro3_password("WrongPassword", pw_hash, salt))

if __name__ == "__main__":
    unittest.main()
