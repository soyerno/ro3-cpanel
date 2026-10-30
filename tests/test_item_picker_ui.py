"""Reusable item picker (typeahead combobox) in public/admin.js, public/admin.css and public/index.html.

The pure helpers are run with node when it is installed (skipped otherwise); the wiring is checked statically.
"""

import json
import os
import re
import shutil
import subprocess
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from test_confirm_ui import function_body, read  # noqa: E402

HELPERS = (
    "normalizeItemQuery", "nextActiveIndex", "itemPickerKeyAction", "createStaleGuard", "itemPickerDebounce",
    "itemSearchUrl", "parseItemEntry",
)


class PickerHelpersRunWithNodeTest(unittest.TestCase):
    def run_js(self, check):
        node = shutil.which("node")
        if not node:
            self.skipTest("node is not installed")
        js = read("public", "admin.js")
        consts = "\n".join(re.findall(r"^  var (?:ITEM_PICKER_[A-Z_]+) = .*?;\n", js, re.M | re.S))
        sources = "\n".join(function_body(js, name) for name in HELPERS)
        script = "const assert = require('node:assert/strict');\n" + consts + "\n" + sources + "\n" + check
        result = subprocess.run([node, "-e", script], capture_output=True, text=True, timeout=30)
        self.assertEqual(result.returncode, 0, result.stderr)

    def test_query_normalisation_trims_collapses_spaces_and_caps_at_64(self):
        self.run_js("""
          assert.equal(normalizeItemQuery('  red   potion \\t'), 'red potion');
          assert.equal(normalizeItemQuery(null), '');
          assert.equal(normalizeItemQuery(undefined), '');
          assert.equal(normalizeItemQuery('x'.repeat(100)).length, 64);
          assert.equal(normalizeItemQuery('Ñandú'), 'Ñandú');
        """)

    def test_arrow_keys_wrap_and_home_end_jump(self):
        self.run_js("""
          assert.equal(nextActiveIndex(0, 5, 'ArrowDown'), 1);
          assert.equal(nextActiveIndex(4, 5, 'ArrowDown'), 0);
          assert.equal(nextActiveIndex(0, 5, 'ArrowUp'), 4);
          assert.equal(nextActiveIndex(3, 5, 'ArrowUp'), 2);
          assert.equal(nextActiveIndex(-1, 5, 'ArrowDown'), 0);
          assert.equal(nextActiveIndex(-1, 5, 'ArrowUp'), 4);
          assert.equal(nextActiveIndex(3, 5, 'Home'), 0);
          assert.equal(nextActiveIndex(1, 5, 'End'), 4);
          assert.equal(nextActiveIndex(2, 0, 'ArrowDown'), -1);
          assert.equal(nextActiveIndex(2, 5, 'a'), 2);
        """)

    def test_key_actions_for_an_open_popup(self):
        self.run_js("""
          const open = {open: true, count: 3, active: 1, status: 'results'};
          assert.equal(itemPickerKeyAction('ArrowDown', open), 'move');
          assert.equal(itemPickerKeyAction('ArrowUp', open), 'move');
          assert.equal(itemPickerKeyAction('Home', open), 'move');
          assert.equal(itemPickerKeyAction('End', open), 'move');
          assert.equal(itemPickerKeyAction('Enter', open), 'select');
          assert.equal(itemPickerKeyAction('Escape', open), 'close');
          assert.equal(itemPickerKeyAction('Tab', open), 'none');
          assert.equal(itemPickerKeyAction('a', open), 'none');
          assert.equal(itemPickerKeyAction('Enter', {open: true, count: 3, active: -1, status: 'results'}), 'none');
        """)

    def test_key_actions_for_a_closed_popup(self):
        self.run_js("""
          const closed = {open: false, count: 0, active: -1, status: 'idle', text: 'pot'};
          assert.equal(itemPickerKeyAction('ArrowDown', closed), 'open');
          assert.equal(itemPickerKeyAction('ArrowUp', closed), 'open');
          assert.equal(itemPickerKeyAction('Home', closed), 'none');
          assert.equal(itemPickerKeyAction('Enter', closed), 'none');
          assert.equal(itemPickerKeyAction('Escape', closed), 'clear');
          assert.equal(itemPickerKeyAction('Escape', {open: false, count: 0, active: -1, status: 'idle', text: ''}), 'none');
        """)

    def test_enter_retries_after_an_error_and_never_selects_a_status_row(self):
        self.run_js("""
          assert.equal(itemPickerKeyAction('Enter', {open: true, count: 0, active: -1, status: 'error'}), 'retry');
          assert.equal(itemPickerKeyAction('Enter', {open: true, count: 0, active: -1, status: 'empty'}), 'none');
          assert.equal(itemPickerKeyAction('Enter', {open: true, count: 0, active: -1, status: 'loading'}), 'none');
          assert.equal(itemPickerKeyAction('ArrowDown', {open: true, count: 0, active: -1, status: 'empty'}), 'none');
          assert.equal(itemPickerKeyAction('Escape', {open: true, count: 0, active: -1, status: 'error'}), 'close');
        """)

    def test_a_stale_response_is_ignored(self):
        self.run_js("""
          const guard = createStaleGuard();
          const first = guard.next();
          assert.equal(guard.isCurrent(first), true);
          const second = guard.next();
          assert.equal(guard.isCurrent(first), false);
          assert.equal(guard.isCurrent(second), true);
          guard.next();
          assert.equal(guard.isCurrent(second), false);
        """)

    def test_debounce_waits_and_keeps_only_the_last_call_and_can_be_cancelled(self):
        self.run_js("""
          const calls = [];
          const debounced = itemPickerDebounce(function (v) { calls.push(v); }, 30);
          debounced('a'); debounced('b'); debounced('c');
          assert.deepEqual(calls, []);
          const cancelled = itemPickerDebounce(function (v) { calls.push('never'); }, 30);
          cancelled('x'); cancelled.cancel();
          setTimeout(function () {
            assert.deepEqual(calls, ['c']);
          }, 120);
        """)

    def test_the_debounce_delay_is_200ms(self):
        self.assertRegex(read("public", "admin.js"), r"var ITEM_PICKER_DEBOUNCE_MS = 200;")

    def test_the_search_url_encodes_the_text_and_sets_the_limit(self):
        self.run_js("""
          assert.equal(itemSearchUrl('red potion'), '/api/admin/items/search?q=red%20potion&limit=20');
          assert.equal(itemSearchUrl("a&b=c#d%"), '/api/admin/items/search?q=a%26b%3Dc%23d%25&limit=20');
          assert.equal(itemSearchUrl(''), '/api/admin/items/search?q=&limit=20');
        """)

    def test_a_typed_id_is_a_positive_whole_number_or_nothing(self):
        self.run_js("""
          assert.equal(parseItemEntry('5001'), 5001);
          assert.equal(parseItemEntry(' 12 '), 12);
          for (const bad of ['', '0', '-3', '1.5', 'abc', '12abc', '9'.repeat(30), null, undefined]) {
            assert.equal(parseItemEntry(bad), null, String(bad));
          }
        """)


class PickerWiringTest(unittest.TestCase):
    def setUp(self):
        self.js = read("public", "admin.js")
        self.html = read("public", "index.html")
        self.css = read("public", "admin.css")
        self.es = json.loads(read("public", "locales", "es.json"))
        self.picker = function_body(self.js, "createItemPicker")

    def test_the_input_is_an_aria_1_2_combobox_with_a_listbox_popup(self):
        for needle in (
            'role="combobox"', 'aria-expanded="false"', 'aria-autocomplete="list"', "aria-controls", 'role="listbox"',
            "aria-activedescendant", "role=\"option\"", "aria-selected",
        ):
            with self.subTest(needle=needle):
                self.assertTrue(needle in self.picker or needle.replace('"', "'") in self.picker, needle)

    def test_options_show_the_shared_item_icon_and_name(self):
        self.assertIn("itemChipHtml(", self.picker)

    def test_mouse_and_touch_pick_without_taking_focus_from_the_input(self):
        self.assertIn("pointerdown", self.picker)
        self.assertIn("preventDefault", self.picker)

    def test_the_search_is_debounced_and_responses_are_guarded(self):
        self.assertIn("itemPickerDebounce(", self.picker)
        self.assertIn("createStaleGuard()", self.picker)
        self.assertIn("isCurrent(", self.picker)

    def test_it_closes_on_outside_click_and_when_focus_leaves(self):
        self.assertRegex(self.picker, r"focusout|document\.addEventListener\('pointerdown'")

    def test_escape_inside_the_popup_does_not_close_the_modal(self):
        self.assertIn("stopPropagation", self.picker)

    def test_it_degrades_to_a_numeric_input_when_there_is_no_list(self):
        self.assertIn("available === false", self.js)
        self.assertIn("inputmode", self.picker)

    def test_the_items_are_not_set_through_inline_styles_or_handlers(self):
        self.assertNotIn("style=", self.picker)
        self.assertNotRegex(self.picker, r"\bon[a-z]+\s*=")

    def test_the_list_never_scrolls_smoothly(self):
        self.assertNotIn("smooth", self.picker)

    def test_the_gift_code_rows_use_the_picker(self):
        body = function_body(self.js, "addGiftCodeItemRow")
        self.assertIn("createItemPicker(", body)
        self.assertNotIn("giftcode-item-entry", body)
        submit = function_body(self.js, "handleCreateGiftCode")
        self.assertIn("getValue()", submit)

    def test_removing_a_reward_row_releases_its_picker(self):
        self.assertIn("destroy()", self.js)

    def test_the_market_tab_filters_by_entry_with_the_picker(self):
        self.assertIn("params.set('entry'", function_body(self.js, "loadMarket"))
        self.assertIn('id="market-item-picker"', self.html)
        reset = function_body(self.js, "resetMarketFilters")
        self.assertIn("entry", reset)

    def test_the_market_keeps_the_text_search_for_accounts_and_characters(self):
        self.assertIn('id="market-search-input"', self.html)
        self.assertIn("params.set('q'", function_body(self.js, "loadMarket"))

    def test_picker_css_exists_and_stays_inside_the_viewport(self):
        for selector in (".item-picker", ".item-picker__popup", ".item-picker__option", ".item-picker__chip"):
            with self.subTest(selector=selector):
                self.assertIn(selector, self.css)
        popup = re.search(r"\.item-picker__popup\s*\{([^}]*)\}", self.css).group(1)
        self.assertIn("max-height", popup)
        self.assertRegex(popup, r"left:\s*0")
        self.assertRegex(popup, r"right:\s*0")
        self.assertIn("overflow-y: auto", popup)
        option = re.search(r"\.item-picker__option\[aria-selected=\"true\"\]\s*\{([^}]*)\}", self.css)
        self.assertIsNotNone(option, "the active option needs a visible style")

    def test_picker_css_uses_tokens_not_hex_colours(self):
        start = self.css.index("/* Item picker */")
        end = self.css.index("/* ", start + 5)
        self.assertEqual(re.findall(r"#[0-9a-fA-F]{3,8}\b", self.css[start:end]), [])

    def test_new_strings_have_spanish_translations(self):
        for key in (
            "Search item by name or ID", "Item name or ID", "Searching items...", "No items found", "One result",
            "{count} results", "Could not load the item list. Press Enter to retry.", "Clear item", "Item list",
            "Selected: {name}", "No item list is configured: enter the item ID as a number.",
        ):
            with self.subTest(key=key):
                self.assertIn(key, self.es)


if __name__ == "__main__":
    unittest.main()
