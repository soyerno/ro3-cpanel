"""The character card on the account screen (static checks over public/admin.js, admin.css and es.json)."""

import json
import os
import re
import shutil
import subprocess
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from test_confirm_ui import function_body, read  # noqa: E402


def run_js(test, check, functions, constants=r"^  var (?:ITEM_[A-Z_]+|AUDIT_[A-Z_]+) = .*?;\n"):
    """Runs the real helpers of public/admin.js with node; skipped when node is not installed."""
    node = shutil.which("node")
    if not node:
        test.skipTest("node is not installed")
    js = read("public", "admin.js")
    consts = "\n".join(re.findall(constants, js, re.M | re.S))
    sources = "\n".join(function_body(js, name) for name in functions)
    script = (
        "const assert = require('node:assert/strict');\n"
        "var state = {branding: {item_icons_url: '/admin/item-icons/'}};\n"
        "function t(s, p) { return p ? s.replace(/\\{(\\w+)\\}/g, (m, k) => p[k]) : s; }\n"
        "function formatNumber(n) { return String(n); }\n" + consts + "\n" + sources + "\n" + check
    )
    result = subprocess.run([node, "-e", script], capture_output=True, text=True, timeout=30)
    test.assertEqual(result.returncode, 0, result.stderr)


class InventoryAndMailToggleEachOtherTest(unittest.TestCase):
    """Opening the mail closes the inventory and the other way round; a slow load never reopens a closed panel."""

    def setUp(self):
        self.js = read("public", "admin.js")

    def test_one_function_decides_which_panel_of_the_card_is_open(self):
        body = function_body(self.js, "setCharacterPanel")
        self.assertIn("data-panel", body)
        self.assertRegex(body, r"which !== 'inventory'")
        self.assertRegex(body, r"which !== 'mail'")
        for label in ("Hide inventory", "View inventory", "Hide mail", "View mail"):
            self.assertIn("t('%s')" % label, body)
        self.assertGreaterEqual(body.count("aria-expanded"), 2)

    def test_opening_the_inventory_goes_through_it_and_closing_it_again_does_too(self):
        body = function_body(self.js, "toggleCharacterInventory")
        self.assertIn("setCharacterPanel(card, 'inventory')", body)
        self.assertIn("setCharacterPanel(card, null)", body)

    def test_a_slow_inventory_load_does_not_reappear_after_the_admin_moved_to_the_mail(self):
        body = function_body(self.js, "toggleCharacterInventory")
        self.assertRegex(body, r"getAttribute\('data-panel'\) !== 'inventory'\) return")

    def test_the_mail_button_toggles_through_the_same_function(self):
        self.assertRegex(self.js, r"btn-view-mail'\)\) \{[\s\S]*?setCharacterPanel\(card, 'mail'\)[\s\S]*?loadCharacterMail\(roleId, 1\)")
        self.assertRegex(self.js, r"getAttribute\('data-panel'\) === 'mail'\) \{\s*setCharacterPanel\(card, null\)")

    def test_both_buttons_start_closed_and_keep_their_aria_controls(self):
        card = function_body(self.js, "renderCharacterCard")
        self.assertEqual(card.count('aria-expanded="false"'), 2)
        self.assertIn('aria-controls="char-inventory-', card)
        self.assertIn('aria-controls="char-mail-', card)

    def test_the_new_label_is_translated(self):
        es = json.loads(read("public", "locales", "es.json"))
        self.assertTrue(es.get("Hide mail", "").strip())


class CurrenciesAsAListTest(unittest.TestCase):
    """Every currency of a character is a row with its image, its name and its amount (Zeny first)."""

    FUNCTIONS = ("escapeHtml", "itemIconSrc", "itemIconHtml", "currencyRowHtml")

    def test_a_known_currency_shows_image_name_and_amount(self):
        run_js(self, """
          const html = currencyRowHtml(2, {name: 'Minted Coin', icon: 'item_2.png', quality: 'rare'}, 1500);
          assert.match(html, /^<li class="char-currency">/);
          assert.match(html, /<img class="item-icon__img" src="\/admin\/item-icons\/item_2\.png" alt="Minted Coin"/);
          assert.match(html, /class="item-icon quality--rare"/);
          assert.match(html, /<span class="char-currency__name">Minted Coin<\/span>/);
          assert.match(html, /<span class="char-currency__amount">1500<\/span>/);
        """, self.FUNCTIONS)

    def test_an_unnamed_currency_is_labelled_by_its_id_and_zeny_always_has_a_name(self):
        run_js(self, """
          const unknown = currencyRowHtml(99999, {name: null, icon: null, quality: null}, 7);
          assert.match(unknown, /<span class="char-currency__name">Currency 99999<\/span>/);
          assert.doesNotMatch(unknown, /<img/);
          const zeny = currencyRowHtml(1, {name: null, icon: null, quality: null}, 5);
          assert.match(zeny, /<span class="char-currency__name">Zeny<\/span>/);
        """, self.FUNCTIONS)

    def test_hostile_names_and_icons_cannot_inject_markup(self):
        run_js(self, """
          const html = currencyRowHtml(3, {name: '<img src=x onerror=alert(1)>', icon: '../../x.png', quality: '"><b>'}, '<i>');
          assert.doesNotMatch(html, /<img src=x/);
          assert.doesNotMatch(html, /<b>|<i>/);
          assert.doesNotMatch(html, /quality--"/);
        """, self.FUNCTIONS)

    def test_the_card_lists_zeny_first_then_the_others_and_the_old_other_currencies_line_is_gone(self):
        js = read("public", "admin.js")
        body = function_body(js, "renderCharacterCurrencies")
        self.assertIn("c.currency.zeny_item", body)
        self.assertIn("c.currency.zeny", body)
        self.assertIn("currencyRowHtml(", body)
        self.assertLess(body.index("c.currency.zeny_item"), body.index("c.currency.others"))
        self.assertIn("char-currencies", body)
        self.assertNotIn("Other currencies:", js)
        self.assertNotIn("formatOtherCurrencies", js)

    def test_a_long_list_scrolls_inside_itself_and_can_be_reached_with_the_keyboard(self):
        body = function_body(read("public", "admin.js"), "renderCharacterCurrencies")
        self.assertIn('tabindex="0"', body)
        self.assertIn("aria-label", body)
        css = read("public", "admin.css")
        self.assertRegex(re.search(r"\.char-currencies \{([^}]*)\}", css).group(1), r"overflow-y:\s*auto")

    def test_mail_currency_attachments_use_the_same_image_and_name(self):
        body = function_body(read("public", "admin.js"), "renderMailAttachments")
        self.assertIn("currencyRowHtml(", body)
        self.assertNotIn("Currency {entry}: {amount}", body)

    def test_new_and_removed_labels_in_spanish(self):
        es = json.loads(read("public", "locales", "es.json"))
        self.assertTrue(es.get("Currencies", "").strip())
        self.assertTrue(es.get("Currency {id}", "").strip())
        self.assertNotIn("Other currencies:", es)
        self.assertNotIn("Currency {entry}: {amount}", es)


class StatsAsACompactVerticalListTest(unittest.TestCase):
    def setUp(self):
        self.js = read("public", "admin.js")
        self.css = read("public", "admin.css")

    def test_the_six_stats_are_one_vertical_description_list(self):
        body = function_body(self.js, "renderCharacterStats")
        self.assertIn('<dl class="char-stats"', body)
        for key in ("str", "agi", "vit", "int", "dex", "luk"):
            self.assertIn("'%s'" % key, body)
        self.assertIn('<div class="char-stat">', body)
        self.assertIn("<dt>", body)
        self.assertIn("<dd>", body)

    def test_the_old_wide_stat_grid_is_gone(self):
        self.assertNotIn("stats-grid-mini", self.js + self.css)
        self.assertNotIn("stat-box-", self.js + self.css)

    def test_the_stats_sit_beside_the_facts_and_currencies_instead_of_under_them(self):
        card = function_body(self.js, "renderCharacterCard")
        self.assertIn('class="char-card-body"', card)
        self.assertLess(card.index("char-card-main"), card.index("renderCharacterStats("))
        body = re.search(r"\.char-card-body \{([^}]*)\}", self.css).group(1)
        self.assertRegex(body, r"display:\s*grid")
        self.assertRegex(body, r"grid-template-columns:\s*minmax\(0,\s*1fr\)\s+\d+px")

    def test_on_a_narrow_screen_everything_stacks(self):
        blocks = re.findall(r"@media \(max-width: 560px\)\s*\{(.*?)\n\}", self.css, re.S)
        self.assertTrue(any(re.search(r"\.char-card-body \{[^}]*grid-template-columns:\s*minmax\(0,\s*1fr\)", b) for b in blocks))

    def test_a_stat_row_is_small_text_with_the_value_pushed_to_the_right(self):
        row = re.search(r"\.char-stat \{([^}]*)\}", self.css).group(1)
        self.assertRegex(row, r"display:\s*flex")
        self.assertRegex(row, r"justify-content:\s*space-between")


if __name__ == "__main__":
    unittest.main()
