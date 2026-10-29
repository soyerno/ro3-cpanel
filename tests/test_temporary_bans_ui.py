"""Temporary bans (issue #40): static checks over public/index.html, public/admin.js and es.json."""

import json
import os
import re
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PUBLIC = os.path.join(ROOT, "public")


def _read(*parts):
    with open(os.path.join(PUBLIC, *parts), encoding="utf-8") as f:
        return f.read()


class TestTemporaryBansUi(unittest.TestCase):
    def setUp(self):
        self.html = _read("index.html")
        self.js = _read("admin.js")

    def test_ban_form_offers_permanent_and_temporary_durations(self):
        select = re.search(r'<select id="ban-days"[^>]*>(.*?)</select>', self.html, re.S)
        self.assertIsNotNone(select)
        values = re.findall(r'<option value="(\d*)"', select.group(1))
        self.assertEqual(values, ["", "1", "7", "30"])
        self.assertIn('for="ban-days"', self.html)

    def test_the_form_sends_days_only_for_a_temporary_ban(self):
        start = self.js.index("function handleBanAccount")
        end = self.js.index("function handleUnbanAccount")
        handler = self.js[start:end]
        self.assertIn("getElementById('ban-days')", handler)
        self.assertIn("body.days = days", handler)

    def test_the_end_of_a_ban_is_shown(self):
        self.assertIn("banned_until", self.js)
        self.assertIn("'Banned until {until} ({reason})'", self.js)

    def test_new_strings_have_spanish_translations(self):
        es = json.loads(_read("locales", "es.json"))
        for key in ("Duration", "Permanent", "1 day", "7 days", "30 days", "Banned until {until} ({reason})",
                    "Suspended until {until}"):
            with self.subTest(key=key):
                self.assertIn(key, es)


if __name__ == "__main__":
    unittest.main()
