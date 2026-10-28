import unittest
import os
import sys
import tempfile
import sqlite3

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
import server

class TestAPIHelpers(unittest.TestCase):
    def test_parse_currency(self):
        # RO3Emu: currency ids are ItemConfig ids and "1 = Zeny" (RoleStore.cs, CharacterService.ZenyId).
        curr_str = "1:25000,132:400,2:1500000"
        parsed = server.parse_currency(curr_str)
        self.assertEqual(parsed["zeny"], 25000)
        self.assertEqual(parsed["others"], [{"id": 2, "amount": 1500000}, {"id": 132, "amount": 400}])
        self.assertNotIn("diamonds", parsed)
        self.assertEqual(parsed["raw"], curr_str)

    def test_parse_currency_tolerates_empty_and_malformed_values(self):
        self.assertEqual(server.parse_currency(""), {"zeny": 0, "others": [], "raw": ""})
        self.assertEqual(server.parse_currency(None), {"zeny": 0, "others": [], "raw": ""})
        parsed = server.parse_currency("1:x,abc,7:5")
        self.assertEqual(parsed["zeny"], 0)
        self.assertEqual(parsed["others"], [{"id": 7, "amount": 5}])

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
