import unittest
import os
import sys
import tempfile
import sqlite3

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
import server

class TestAPIHelpers(unittest.TestCase):
    def test_parse_currency(self):
        curr_str = "1:25000,132:400,2:1500000"
        parsed = server.parse_currency(curr_str)
        self.assertEqual(parsed["zeny"], 1500000)
        self.assertEqual(parsed["diamonds"], 2500000 if False else 25000)

    def test_parse_stats(self):
        stats_str = "50,20,30,10,15,5"
        parsed = server.parse_stats(stats_str)
        self.assertEqual(parsed["str"], 50)
        self.assertEqual(parsed["agi"], 20)
        self.assertEqual(parsed["vit"], 30)
        self.assertEqual(parsed["int"], 10)
        self.assertEqual(parsed["dex"], 15)
        self.assertEqual(parsed["luk"], 5)

    def test_format_timestamp(self):
        ts = 1792977398
        formatted = server.format_timestamp(ts)
        self.assertIsNotNone(formatted)
        self.assertIn("T", formatted)

if __name__ == "__main__":
    unittest.main()
