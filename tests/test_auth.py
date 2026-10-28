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

    def test_authenticate_admin_non_existent(self):
        valid, user = server.authenticate_admin("unknown_user", "AnyPassword")
        self.assertFalse(valid)
        self.assertIsNone(user)

if __name__ == "__main__":
    unittest.main()
