"""Item name + image in inventory, mail, vault, market and gift codes (public/admin.js, public/admin.css).

The helpers are run with node when it is installed (skipped otherwise); the wiring is checked statically.
"""

import os
import re
import shutil
import subprocess
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from test_confirm_ui import function_body, read  # noqa: E402

HELPERS = ("escapeHtml", "itemIconSrc", "itemIconHtml", "itemChipHtml")


class ItemHelpersRunWithNodeTest(unittest.TestCase):
    def run_js(self, check):
        node = shutil.which("node")
        if not node:
            self.skipTest("node is not installed")
        js = read("public", "admin.js")
        consts = "\n".join(re.findall(r"^  var (?:ITEM_[A-Z_]+) = .*?;\n", js, re.M | re.S))
        sources = "\n".join(function_body(js, name) for name in HELPERS)
        script = (
            "const assert = require('node:assert/strict');\n"
            "var state = {branding: {item_icons_url: '/admin/item-icons/'}};\n"
            "function t(s, p) { return s; }\n" + consts + "\n" + sources + "\n" + check
        )
        result = subprocess.run([node, "-e", script], capture_output=True, text=True, timeout=30)
        self.assertEqual(result.returncode, 0, result.stderr)

    def test_a_known_item_shows_the_image_the_name_and_the_id(self):
        self.run_js("""
          const html = itemChipHtml({entry: 5001, name: 'Red Potion', icon: 'item_5001.png', quality: 'common'});
          assert.match(html, /<img class="item-icon__img" src="\\/admin\\/item-icons\\/item_5001\\.png" alt="Red Potion" width="32" height="32"/);
          assert.match(html, /class="item-icon quality--common"/);
          assert.match(html, />Red Potion</);
          assert.match(html, />#5001</);
        """)

    def test_the_decorative_icon_is_hidden_from_screen_readers_and_has_a_real_alt(self):
        self.run_js("""
          const html = itemChipHtml({entry: 5001, name: 'Red Potion', icon: 'item_5001.png', quality: 'rare'});
          assert.match(html, /<span class="item-icon quality--rare" aria-hidden="true">/);
          assert.doesNotMatch(html, /alt=""/);
        """)

    def test_without_an_icon_base_url_or_a_file_name_there_is_a_placeholder_and_no_image(self):
        self.run_js("""
          const item = {entry: 5001, name: 'Red Potion', icon: 'item_5001.png', quality: 'rare'};
          for (const base of ['', undefined, null]) {
            state.branding.item_icons_url = base;
            const html = itemChipHtml(item);
            assert.doesNotMatch(html, /<img/);
            assert.match(html, /item-icon[^"]* is-missing/);
            assert.match(html, /<svg/);
            assert.match(html, />Red Potion</);
          }
          state.branding.item_icons_url = '/admin/item-icons/';
          const none = itemChipHtml({entry: 5001, name: 'Red Potion', icon: null, quality: null});
          assert.doesNotMatch(none, /<img/);
          assert.doesNotMatch(none, /quality--/);
        """)

    def test_an_unknown_item_is_shown_by_id_once(self):
        self.run_js("""
          const html = itemChipHtml({entry: 424242, name: null, icon: null, quality: null});
          assert.equal((html.match(/#424242/g) || []).length, 1);
        """)

    def test_hostile_values_cannot_inject_markup_or_leave_the_icon_folder(self):
        self.run_js("""
          const bases = ['/admin/item-icons/', 'javascript:alert(1)//', '//evil.example/', 'https://evil.example/', '/a b/', '/a"onerror=x/'];
          const icons = ['../x.png', 'a/b.png', 'x.gif', 'x y.png', '"><img src=x onerror=alert(1)>.png', 'x.png"', 'javascript:alert(1).png'];
          for (const base of bases) {
            state.branding.item_icons_url = base;
            for (const icon of icons) {
              const html = itemChipHtml({entry: 1, name: '<script>alert(1)</script>', icon: icon, quality: '"><b onmouseover=x>'});
              assert.doesNotMatch(html, /<script/i, base + ' ' + icon);
              assert.doesNotMatch(html, /onmouseover=/i);
              assert.doesNotMatch(html, /<b /);
              assert.doesNotMatch(html, /<img[^>]*src="(?!\\/admin\\/item-icons\\/)/, base + ' ' + icon);
              assert.doesNotMatch(html, /quality--"/);
            }
          }
          state.branding.item_icons_url = '/admin/item-icons/';
          const ok = itemChipHtml({entry: 1, name: 'x', icon: 'a_b-1.webp', quality: 'mythic'});
          assert.match(ok, /src="\\/admin\\/item-icons\\/a_b-1\\.webp"/);
          assert.match(ok, /quality--mythic/);
          assert.doesNotMatch(itemChipHtml({entry: 1, name: 'x', icon: 'a.png', quality: 'legendary rare'}), /quality--/);
        """)

    def test_a_missing_image_file_is_swapped_for_the_placeholder_without_inline_handlers(self):
        js = read("public", "admin.js")
        self.assertRegex(js, r"addEventListener\('error',\s*handleItemIconError,\s*true\)")
        handler = function_body(js, "handleItemIconError")
        self.assertIn("item-icon__img", handler)
        self.assertIn("is-missing", handler)
        self.assertNotRegex(js, r"onerror\s*=")


class ItemWiringTest(unittest.TestCase):
    def setUp(self):
        self.js = read("public", "admin.js")

    def test_inventory_vault_market_and_gift_codes_use_the_shared_chip(self):
        for name in ("renderInventory", "renderAccountVault", "renderMarketTable", "giftCodeRewardsHtml"):
            self.assertIn("itemChipHtml(", function_body(self.js, name), name)

    def test_mail_attachments_and_items_use_the_chip_and_currency_stays_text(self):
        body = function_body(self.js, "renderMailAttachments")
        self.assertIn("itemChipHtml(", body)
        self.assertIn("Currency {entry}: {amount}", body)

    def test_the_icon_base_url_comes_from_the_branding_config(self):
        self.assertIn("state.branding.item_icons_url", function_body(self.js, "itemIconSrc"))


class ItemCssTest(unittest.TestCase):
    def setUp(self):
        self.css = read("public", "admin.css")

    def test_the_chip_icon_and_every_quality_have_rules(self):
        for selector in (".item-chip", ".item-icon", ".item-icon__img", ".item-icon.is-missing"):
            self.assertIn(selector, self.css)
        for quality in ("common", "fine", "rare", "legendary", "mythic"):
            self.assertIn(".quality--%s" % quality, self.css)

    def test_the_icon_has_a_fixed_box_so_loading_does_not_move_the_table(self):
        body = re.search(r"\.item-icon \{([^}]*)\}", self.css).group(1)
        for prop in ("width:", "height:", "flex-shrink: 0"):
            self.assertIn(prop, body)

    def test_a_long_name_wraps_instead_of_forcing_horizontal_scroll(self):
        body = re.search(r"\.item-chip__text \{([^}]*)\}", self.css).group(1)
        self.assertRegex(body, r"min-width:\s*0")
        self.assertRegex(body, r"overflow-wrap:\s*anywhere|word-break:\s*break-word")


if __name__ == "__main__":
    unittest.main()
