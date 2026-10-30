"""VIP checkbox on the account screen: static checks of index.html, admin.js and the locales."""

import json
import os
import re
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PUBLIC = os.path.join(ROOT, "public")


def _read(*parts):
    with open(os.path.join(PUBLIC, *parts), encoding="utf-8") as f:
        return f.read()


def _function_body(js, name):
    match = re.search(r"\n  function %s\(.*?(?=\n  function |\n  // ---|\Z)" % re.escape(name), js, re.S)
    return match.group(0) if match else ""


class TestVipToggleMarkup(unittest.TestCase):
    def setUp(self):
        html = _read("index.html")
        start = html.index('<header class="account-header">')
        self.header = html[start:html.index("</header>", start)]

    def test_header_holds_a_labelled_vip_checkbox_next_to_the_badges(self):
        self.assertRegex(self.header, r'<input[^>]*type="checkbox"[^>]*id="account-vip-toggle"|<input[^>]*id="account-vip-toggle"[^>]*type="checkbox"')
        self.assertRegex(self.header, r'<label[^>]*for="account-vip-toggle"|<label[^>]*>\s*<input[^>]*id="account-vip-toggle"')
        self.assertIn('data-i18n="VIP"', self.header)
        self.assertLess(self.header.index('id="account-badges"'), self.header.index('id="account-vip-toggle"'))

    def test_checkbox_starts_disabled_until_the_account_loads(self):
        tag = re.search(r'<input[^>]*id="account-vip-toggle"[^>]*>', self.header).group(0)
        self.assertRegex(tag, r"\bdisabled\b")


class TestVipToggleScript(unittest.TestCase):
    def setUp(self):
        self.js = _read("admin.js")

    def test_change_handler_confirms_then_posts_the_new_state(self):
        body = _function_body(self.js, "handleVipToggle")
        self.assertTrue(body, "handleVipToggle is missing")
        self.assertIn("askConfirm(", body)
        self.assertIn("'/api/admin/accounts/vip'", body)
        self.assertRegex(body, r"vip:\s*\w+")
        self.assertIn("showToast(", body)
        self.assertIn("renderAccountBadges()", body)
        self.assertRegex(self.js, r"accountVipToggle\.addEventListener\('change', handleVipToggle\)")

    def test_cancelled_or_failed_change_restores_the_checkbox(self):
        body = _function_body(self.js, "handleVipToggle")
        self.assertRegex(body, r"\.checked = !\w+")

    def test_checkbox_reflects_the_loaded_vip_status(self):
        body = _function_body(self.js, "renderVipToggle")
        self.assertTrue(body, "renderVipToggle is missing")
        self.assertIn(".checked", body)
        self.assertIn("'gm'", body)  # a GM is always VIP: the box is locked
        self.assertIn("renderVipToggle(", _function_body(self.js, "renderAccountBadges"))

    def test_badges_use_the_account_payload_before_the_vault_loads(self):
        body = _function_body(self.js, "renderAccountBadges")
        self.assertRegex(body, r"acc\.vip")

    def test_vip_audit_targets_link_to_the_account(self):
        actions = re.search(r"var AUDIT_ACCOUNT_ACTIONS = \[(.*?)\];", self.js).group(1)
        self.assertIn("'vip_grant'", actions)
        self.assertIn("'vip_revoke'", actions)


class TestVipToggleLocales(unittest.TestCase):
    KEYS = (
        "VIP",
        "Grant VIP",
        "Revoke VIP",
        "Grant VIP to account \"{name}\"? The web portal treats it as a permanent VIP.",
        "Revoke VIP from account \"{name}\"? The portal will not grant it again on its own.",
        "Error updating VIP: {message}",
        "GM accounts are always VIP",
    )

    def test_every_key_is_used_and_translated_in_every_locale(self):
        js = _read("admin.js")
        for name in os.listdir(os.path.join(PUBLIC, "locales")):
            if not name.endswith(".json"):
                continue
            locale = json.loads(_read("locales", name))
            for key in self.KEYS:
                with self.subTest(locale=name, key=key):
                    self.assertIn(key, locale)
                    self.assertTrue(locale[key].strip())
        for key in self.KEYS[1:]:
            with self.subTest(key=key):
                self.assertIn(key, js.replace('\\"', '"'))


if __name__ == "__main__":
    unittest.main()
