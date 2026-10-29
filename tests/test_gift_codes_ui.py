"""Gift Codes admin tab: static checks over public/index.html, public/admin.js and es.json."""

import json
import os
import re
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PUBLIC = os.path.join(ROOT, "public")


def _read(*parts):
    with open(os.path.join(PUBLIC, *parts), encoding="utf-8") as f:
        return f.read()


class TestGiftCodesMarkup(unittest.TestCase):
    def setUp(self):
        self.html = _read("index.html")

    def test_tab_button_after_economy(self):
        self.assertIn('data-tab="giftcodes"', self.html)
        self.assertLess(self.html.index('data-tab="economy"'), self.html.index('data-tab="giftcodes"'))

    def test_tab_section_exists_and_starts_hidden(self):
        self.assertRegex(self.html, r'<section id="tab-view-giftcodes"[^>]*\bhidden\b')

    def test_list_elements_exist(self):
        for element_id in (
            "giftcodes-tbody",
            "giftcodes-unavailable",
            "btn-giftcodes-refresh",
            "btn-new-giftcode",
        ):
            with self.subTest(element_id=element_id):
                self.assertIn('id="%s"' % element_id, self.html)

    def test_list_table_has_required_columns(self):
        for label in (
            "Code", "Rewards", "Uses", "Per account", "Starts", "Expires", "Status", "Created by", "Note", "Actions",
        ):
            with self.subTest(label=label):
                self.assertIn('data-i18n="%s"' % label, self.html)

    def test_form_elements_exist(self):
        for element_id in (
            "modal-giftcode",
            "form-giftcode",
            "giftcode-code",
            "giftcode-items",
            "btn-giftcode-add-item",
            "giftcode-max-uses",
            "giftcode-per-account",
            "giftcode-starts",
            "giftcode-expires",
            "giftcode-note",
            "giftcode-error",
        ):
            with self.subTest(element_id=element_id):
                self.assertIn('id="%s"' % element_id, self.html)

    def test_datetime_local_inputs(self):
        for element_id in ("giftcode-starts", "giftcode-expires"):
            with self.subTest(element_id=element_id):
                self.assertRegex(self.html, r'<input[^>]*type="datetime-local"[^>]*id="%s"|<input[^>]*id="%s"[^>]*type="datetime-local"' % (element_id, element_id))

    def test_inputs_have_labels(self):
        for element_id in (
            "giftcode-code",
            "giftcode-max-uses",
            "giftcode-per-account",
            "giftcode-starts",
            "giftcode-expires",
            "giftcode-note",
        ):
            with self.subTest(element_id=element_id):
                self.assertIn('for="%s"' % element_id, self.html)

    def test_code_input_limits_length(self):
        self.assertRegex(self.html, r'<input[^>]*id="giftcode-code"[^>]*maxlength="64"')

    def test_modal_is_an_accessible_dialog(self):
        self.assertRegex(self.html, r'<div id="modal-giftcode"[^>]*role="dialog"[^>]*aria-modal="true"')

    def test_buttons_are_not_submit_by_default(self):
        for element_id in ("btn-new-giftcode", "btn-giftcodes-refresh", "btn-giftcode-add-item"):
            with self.subTest(element_id=element_id):
                self.assertRegex(self.html, r'<button[^>]*id="%s"[^>]*type="button"|<button[^>]*type="button"[^>]*id="%s"' % (element_id, element_id))


class TestGiftCodesScript(unittest.TestCase):
    def setUp(self):
        self.js = _read("admin.js")

    def test_calls_the_four_endpoints(self):
        for needle in ("/api/admin/gift-codes", "'/disable'", "'/enable'"):
            with self.subTest(needle=needle):
                self.assertIn(needle, self.js)

    def test_tab_is_wired_into_switch_tab(self):
        self.assertIn("tab-view-giftcodes", self.js)
        self.assertRegex(self.js, r"tabId === 'giftcodes'")

    def test_datetime_converted_to_unix_seconds(self):
        self.assertRegex(self.js, r"Math\.floor\([^;]*getTime\(\)\s*/\s*1000\)")
        self.assertRegex(self.js, r"expires\s*<=\s*starts|expires <= starts")

    def test_server_text_is_escaped(self):
        for field in ("c.code", "c.note", "c.created_by", "item.name"):
            with self.subTest(field=field):
                self.assertRegex(self.js, r"escapeHtml\(%s\)" % re.escape(field))

    def test_status_badge_texts_are_literal_keys(self):
        for text in ("Active", "Disabled", "Scheduled", "Expired", "Exhausted"):
            with self.subTest(text=text):
                self.assertIn("t('%s')" % text, self.js)

    def test_unlimited_and_unavailable_states(self):
        self.assertIn("t('unlimited')", self.js)
        self.assertRegex(self.js, r"data\.available\s*===\s*false")

    def test_no_console_calls(self):
        self.assertNotRegex(self.js, r"\bconsole\.(log|error|warn)\b")

    def test_no_hardcoded_hex_in_gift_code_code(self):
        start = self.js.index("// --- Gift Codes ---")
        end = self.js.index("// --- Tabs Switching ---")
        self.assertNotRegex(self.js[start:end], r"#[0-9a-fA-F]{3,8}\b")


class TestGiftCodesLocale(unittest.TestCase):
    def test_new_strings_have_spanish_translations(self):
        with open(os.path.join(PUBLIC, "locales", "es.json"), encoding="utf-8") as f:
            es = json.load(f)
        for key in ("🎁 Gift Codes", "Create Gift Code", "Rewards", "Scheduled", "Exhausted", "unlimited"):
            with self.subTest(key=key):
                self.assertIn(key, es)


if __name__ == "__main__":
    unittest.main()
