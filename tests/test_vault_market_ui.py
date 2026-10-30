"""Static checks for the read-only account vault and web market admin views.

These tests only read public/index.html, public/admin.js, public/admin.css and
public/locales/es.json; they do not start the server.
"""

import json
import os
import re
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PUBLIC = os.path.join(ROOT, "public")

# t('...') with a simple string literal (same shape tests/test_i18n_client.py enforces).
T_CALL_RE = re.compile(r"""(?<![\w.$])t\(\s*'((?:[^'\\\n]|\\.)*)'""")
HEX_COLOR_RE = re.compile(r"#[0-9a-fA-F]{3,8}\b")


def _read(*parts):
    with open(os.path.join(PUBLIC, *parts), encoding="utf-8") as f:
        return f.read()


def _function_body(js, name):
    """Return the source of `function name(...) { ... }` up to the next top-level function."""
    match = re.search(r"\n  function %s\(.*?(?=\n  function |\n  // ---|\Z)" % re.escape(name), js, re.S)
    return match.group(0) if match else ""


class TestMarketTabMarkup(unittest.TestCase):
    def setUp(self):
        self.html = _read("index.html")

    def test_tab_button_after_gift_codes(self):
        giftcodes = self.html.index('data-tab="giftcodes"')
        market = self.html.index('data-tab="market"')
        self.assertGreater(market, giftcodes)
        self.assertRegex(self.html, r'<button[^>]*class="tab-btn"[^>]*data-tab="market"')

    def test_section_exists_and_hidden_by_default(self):
        self.assertRegex(self.html, r'<section id="tab-view-market" hidden>')
        self.assertGreater(self.html.index('id="tab-view-market"'), self.html.index('id="tab-view-giftcodes"'))

    def test_filter_controls_exist(self):
        for element_id in (
            "market-filter-form",
            "market-status-select",
            "market-search-input",
            "market-clear",
            "market-unavailable",
            "market-tbody",
        ):
            with self.subTest(element_id=element_id):
                self.assertIn('id="%s"' % element_id, self.html)
        for status in ("active", "sold", "cancelled", "all"):
            with self.subTest(status=status):
                self.assertIn('<option value="%s"' % status, self.html)
        self.assertRegex(self.html, r'<option value="active" selected')

    def test_filter_controls_are_labelled_and_typed(self):
        self.assertRegex(self.html, r'<label[^>]*for="market-status-select"')
        self.assertRegex(self.html, r'<label[^>]*for="market-search-input"')
        self.assertRegex(self.html, r'<button[^>]*type="submit"[^>]*>[^<]*Filter')
        self.assertRegex(self.html, r'<button type="button" id="market-clear"')

    def test_summary_cards_exist(self):
        for element_id in (
            "market-stat-active",
            "market-stat-sold",
            "market-stat-active-zeny",
            "market-stat-pending-zeny",
            "market-stat-pending-sub",
        ):
            with self.subTest(element_id=element_id):
                self.assertIn('id="%s"' % element_id, self.html)
        section = self.html[self.html.index('id="tab-view-market"'):]
        self.assertIn('class="stat-card"', section)

    def test_pager_exists_with_aria_label(self):
        self.assertRegex(self.html, r'<nav id="market-pager" class="pager" aria-label="[^"]+" data-i18n-aria-label="[^"]+"')
        for element_id in ("market-pager-prev", "market-pager-next", "market-pager-info"):
            with self.subTest(element_id=element_id):
                self.assertIn('id="%s"' % element_id, self.html)
        self.assertRegex(self.html, r'<button id="market-pager-prev" type="button"')
        self.assertRegex(self.html, r'<button id="market-pager-next" type="button"')

    def test_table_has_all_columns(self):
        section = self.html[self.html.index('id="tab-view-market"'):]
        section = section[:section.index("</section>")]
        for column in ("Item", "Qty", "Price (Zeny)", "Seller", "Status", "Buyer", "Listed", "Updated"):
            with self.subTest(column=column):
                self.assertIn('data-i18n="%s">%s</th>' % (column, column), section)


class TestVaultMarkup(unittest.TestCase):
    def setUp(self):
        self.html = _read("index.html")
        start = self.html.index('id="account-screen"')
        self.screen = self.html[start:self.html.index("<!-- /account-screen -->", start)]
        self.panel = self.screen[self.screen.index('id="account-panel-vault"'):self.screen.index('id="account-panel-security"')]

    def test_vault_section_lives_in_the_account_screen_vault_tab(self):
        self.assertIn('id="account-tab-vault"', self.screen)
        self.assertIn('id="account-vault-content"', self.panel)
        self.assertRegex(self.screen, r'<button type="button"[^>]*id="account-tab-vault"')
        self.assertRegex(self.panel, r'<div id="account-vault-content"[^>]*>')
        self.assertRegex(self.panel, r'<h2[^>]*data-i18n="Account vault"')

    def test_vault_section_is_after_character_list(self):
        self.assertGreater(self.screen.index('id="account-panel-vault"'), self.screen.index('id="account-characters"'))
        self.assertGreater(self.screen.index('id="account-tab-vault"'), self.screen.index('id="account-tab-characters"'))

    def test_vault_tab_label_is_distinct_english(self):
        self.assertRegex(self.screen, r'(?s)id="account-tab-vault"[^>]*>.*?<span data-i18n="Vault">Vault</span>')


class TestMarketAndVaultScript(unittest.TestCase):
    def setUp(self):
        self.js = _read("admin.js")

    def test_calls_market_endpoint_with_filters(self):
        body = _function_body(self.js, "loadMarket")
        self.assertIn("/api/admin/market", body)
        for param in ("'status'", "'q'", "'page'", "'page_size'"):
            with self.subTest(param=param):
                self.assertIn(param, body)

    def test_calls_vault_endpoint_with_encoded_account(self):
        body = _function_body(self.js, "loadAccountVault")
        self.assertRegex(body, r"/api/admin/accounts/'\s*\+\s*encodeURIComponent\(")
        self.assertIn("/vault?", body)
        self.assertIn("page_size", body)

    def test_views_are_read_only_get_requests(self):
        for name in ("loadMarket", "loadAccountVault"):
            with self.subTest(name=name):
                body = _function_body(self.js, name)
                self.assertTrue(body, "function %s not found" % name)
                self.assertNotRegex(body, r"method:\s*'(POST|PUT|PATCH|DELETE)'")
        for name in ("renderMarketTable", "renderAccountVault"):
            with self.subTest(name=name):
                body = _function_body(self.js, name)
                self.assertTrue(body, "function %s not found" % name)
                self.assertNotRegex(body, r"btn-(cancel|remove|delete|create)")

    def test_tab_switch_loads_market(self):
        body = _function_body(self.js, "switchTab")
        self.assertIn("tabViewMarket", body)
        self.assertIn("tabId === 'market'", body)
        self.assertIn("loadMarket()", body)

    def test_market_pager_wiring(self):
        self.assertRegex(self.js, r"renderPager\(els\.marketPager, els\.marketPagerInfo, els\.marketPagerPrev, els\.marketPagerNext,[^;]*'records'\)")
        for element_id in ("market-pager", "market-pager-prev", "market-pager-next", "market-pager-info"):
            with self.subTest(element_id=element_id):
                self.assertIn("getElementById('%s')" % element_id, self.js)
        self.assertIn("goToMarketPage(", self.js)
        # A page past the end falls back to the last page, like loadAuditLog.
        self.assertRegex(_function_body(self.js, "loadMarket"), r"market\.page\s*=\s*market\.pages")

    def test_market_filter_wiring(self):
        for needle in (
            "market-filter-form",
            "market-clear",
            "applyMarketFilters",
            "resetMarketFilters",
        ):
            with self.subTest(needle=needle):
                self.assertIn(needle, self.js)
        self.assertRegex(_function_body(self.js, "applyMarketFilters"), r"state\.market\.page\s*=\s*1")

    def test_vault_tab_and_pager_wiring(self):
        self.assertIn("getElementById('account-vault-content')", self.js)
        self.assertIn("btn-vault-page", self.js)
        self.assertIn("state.vault", self.js)
        self.assertIn("goToVaultPage(", self.js)
        # Opening a different account starts from a clean vault.
        self.assertIn("resetAccountVault(", _function_body(self.js, "openAccountScreen"))
        # The vault is fetched for the account that is open, and its tab renders the result.
        self.assertIn("loadAccountVault(", _function_body(self.js, "setAccountTab"))
        self.assertIn("loadAccountVault(", _function_body(self.js, "loadAccountScreen"))

    def test_server_text_is_escaped(self):
        market = _function_body(self.js, "renderMarketTable")
        # The item name is escaped by the shared chip.
        self.assertIn("itemChipHtml(l", market)
        self.assertRegex(_function_body(self.js, "itemChipHtml"), r"escapeHtml\(named \? item\.name")
        for field in ("seller_account", "seller_role_name", "buyer_account", "buyer_role_name"):
            with self.subTest(field=field):
                self.assertIn("l.%s" % field, market)
        party = _function_body(self.js, "marketPartyCell")
        self.assertIn("escapeHtml(account)", party)
        self.assertIn("escapeHtml(character)", party)
        vault = _function_body(self.js, "renderAccountVault")
        self.assertIn("itemChipHtml(item)", vault)
        for field in ("pack_name", "deposited_by_name", "reason"):
            with self.subTest(field=field):
                self.assertRegex(vault, r"escapeHtml\([^;]*\b%s\b" % field)

    def test_market_notice_uses_server_reason(self):
        body = _function_body(self.js, "loadMarket")
        self.assertIn("data.reason", body)
        self.assertIn("marketUnavailable", body)

    def test_status_badges_use_literal_keys(self):
        body = _function_body(self.js, "marketStatusBadge")
        for needle in ("badge-active", "badge-admin", "badge-banned", "t('Active')", "t('Sold')", "t('Cancelled')"):
            with self.subTest(needle=needle):
                self.assertIn(needle, body)

    def test_no_console_calls(self):
        self.assertNotRegex(self.js, r"\bconsole\.")

    def test_no_new_hardcoded_hex_in_new_functions(self):
        for name in (
            "loadMarket",
            "renderMarketTable",
            "marketStatusBadge",
            "renderMarketSummary",
            "loadAccountVault",
            "renderAccountVault",
            "renderVaultPanel",
        ):
            with self.subTest(name=name):
                self.assertEqual(HEX_COLOR_RE.findall(_function_body(self.js, name)), [])


class TestMarketAndVaultStyles(unittest.TestCase):
    def test_new_css_rules_use_tokens_only(self):
        css = _read("admin.css")
        marker = css.find("/* Account vault and web market (read-only) */")
        if marker == -1:
            return  # no dedicated CSS block needed
        block = css[marker:]
        self.assertEqual(HEX_COLOR_RE.findall(block), [])


class TestMarketAndVaultLocale(unittest.TestCase):
    EXPECTED_KEYS = (
        "Market",
        "Web Market",
        "Vault",
        "Account vault",
        "Not VIP",
        "VIP (note)",
        "Sold",
        "Cancelled",
        "Active listings",
        "Zeny in active listings",
        "Zeny pending to claim",
        "Deposited by",
        "Price (Zeny)",
    )

    def setUp(self):
        with open(os.path.join(PUBLIC, "locales", "es.json"), encoding="utf-8") as f:
            self.es = json.load(f)
        self.js = _read("admin.js")
        self.html = _read("index.html")

    def test_expected_keys_translated(self):
        for key in self.EXPECTED_KEYS:
            with self.subTest(key=key):
                self.assertIn(key, self.es)
                self.assertTrue(self.es[key].strip())

    def test_every_t_key_in_new_functions_is_translated(self):
        names = (
            "loadMarket",
            "renderMarketTable",
            "marketStatusBadge",
            "renderMarketSummary",
            "loadAccountVault",
            "renderAccountVault",
            "vaultVipBadge",
            "renderVaultPanel",
        )
        for name in names:
            body = _function_body(self.js, name)
            with self.subTest(name=name):
                self.assertTrue(body, "function %s not found" % name)
                for key in T_CALL_RE.findall(body):
                    self.assertIn(key.replace("\\'", "'"), self.es)

    def test_market_markup_i18n_values_translated(self):
        section = self.html[self.html.index('id="tab-view-market"'):]
        section = section[:section.index("</section>")]
        for value in re.findall(r'data-i18n(?:-[a-z-]+)?="([^"]*)"', section):
            with self.subTest(value=value):
                self.assertIn(value, self.es)


if __name__ == "__main__":
    unittest.main()
