"""Every player name the panel shows links to that player's account screen (#/accounts/<name>)."""

import os
import re
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from test_character_card_ui import run_js  # noqa: E402
from test_confirm_ui import function_body, read  # noqa: E402

LINK_FUNCTIONS = ("escapeHtml", "accountRouteHash", "accountLinkHtml")


class AccountLinkHelperTest(unittest.TestCase):
    def test_a_name_links_to_the_account_screen(self):
        run_js(self, """
          assert.equal(accountLinkHtml('alpha', 'HeroAlpha'), '<a class="player-link" href="#/accounts/alpha">HeroAlpha</a>');
          assert.equal(accountLinkHtml('alpha'), '<a class="player-link" href="#/accounts/alpha">alpha</a>');
        """, LINK_FUNCTIONS)

    def test_the_account_is_percent_encoded_so_slashes_and_unicode_reach_the_route_intact(self):
        run_js(self, """
          assert.match(accountLinkHtml('a/b', 'x'), /href="#\/accounts\/a%2Fb"/);
          assert.match(accountLinkHtml('\u00d1and\u00fa', 'x'), /href="#\/accounts\/%C3%91and%C3%BA"/);
          assert.match(accountLinkHtml('a b', 'x'), /href="#\/accounts\/a%20b"/);
        """, LINK_FUNCTIONS)

    def test_hostile_names_are_escaped_in_the_text_and_the_url(self):
        run_js(self, """
          const html = accountLinkHtml('"><script>alert(1)</script>', '<img src=x onerror=alert(1)>');
          assert.doesNotMatch(html, /<script|<img/);
          assert.doesNotMatch(html, /href="#\/accounts\/[^"]*[<>]/);
          assert.match(html, /^<a class="player-link" href="#\/accounts\/[^"<>]*">/);
          assert.equal((html.match(/<a /g) || []).length, 1);
        """, LINK_FUNCTIONS)

    def test_no_account_means_plain_text_not_a_dead_link(self):
        run_js(self, """
          for (const none of [null, undefined, '']) {
            assert.equal(accountLinkHtml(none, 'Ghost'), 'Ghost');
          }
          assert.equal(accountLinkHtml(null), '');
        """, LINK_FUNCTIONS)


class AuditTargetTest(unittest.TestCase):
    FUNCTIONS = LINK_FUNCTIONS + ("auditTargetHtml",)

    def test_targets_of_account_actions_link_to_the_account(self):
        run_js(self, """
          for (const action of ['create_account', 'update_password', 'ban_account', 'unban_account', 'gm_command']) {
            const html = auditTargetHtml({action: action, target: 'alpha'});
            assert.match(html, /<a class="player-link" href="#\/accounts\/alpha"/, action);
          }
        """, self.FUNCTIONS)

    def test_targets_that_are_not_accounts_or_no_longer_exist_stay_plain(self):
        run_js(self, """
          for (const action of ['delete_account', 'gift_code_create', 'feature_toggle', 'delete_character', 'login_failed']) {
            const html = auditTargetHtml({action: action, target: 'SOMETHING'});
            assert.doesNotMatch(html, /<a /, action);
            assert.match(html, /audit-target/);
          }
          assert.equal(auditTargetHtml({action: 'update_password', target: ''}), '\u2014');
        """, self.FUNCTIONS)

    def test_a_long_target_is_cut_for_display_but_links_and_titles_with_the_full_name(self):
        run_js(self, """
          const name = 'a_really_long_account_name_here';
          const html = auditTargetHtml({action: 'ban_account', target: name});
          assert.match(html, new RegExp('href="#/accounts/' + name + '"'));
          assert.match(html, /title="a_really_long_account_name_here"/);
          assert.match(html, />a_really_long_accoun\u2026</);
        """, self.FUNCTIONS)


class WiringTest(unittest.TestCase):
    def setUp(self):
        self.js = read("public", "admin.js")

    def test_every_list_that_names_a_player_links_it(self):
        for name in ("renderAccountsTable", "renderOnlinePlayers", "renderEconomyTable", "marketPartyCell",
                     "showGuildDetail", "loadRankings", "renderAuctionsTable", "describeEconomyOwner"):
            with self.subTest(function=name):
                self.assertIn("accountLinkHtml(", function_body(self.js, name))

    def test_the_audit_log_uses_the_target_helper(self):
        self.assertIn("auditTargetHtml(l)", function_body(self.js, "loadAuditLog"))

    def test_account_list_links_both_the_account_and_each_of_its_characters(self):
        body = function_body(self.js, "renderAccountsTable")
        self.assertIn("accountLinkHtml(acc.name", body)
        self.assertIn("accountLinkHtml(acc.name, c.name)", body)

    def test_rankings_link_the_character_and_the_account_but_not_guild_names(self):
        body = function_body(self.js, "loadRankings")
        self.assertIn("accountLinkHtml(r.account, r.name)", body)
        self.assertIn("accountLinkHtml(r.account)", body)

    def test_market_parties_link_the_account_and_the_character_to_the_same_account(self):
        body = function_body(self.js, "marketPartyCell")
        self.assertIn("accountLinkHtml(account)", body)
        self.assertIn("accountLinkHtml(account, character)", body)

    def test_a_player_link_works_from_any_tab_because_the_route_opens_the_account_screen(self):
        # The existing hashchange handler does the navigation; the links need no click handler of their own.
        self.assertNotIn("player-link').addEventListener", self.js)
        self.assertRegex(self.js, r"addEventListener\('hashchange', handleRouteChange\)")


class CssTest(unittest.TestCase):
    def test_the_link_looks_like_text_until_hovered_and_keeps_the_shared_focus_ring(self):
        css = read("public", "admin.css")
        body = re.search(r"\.player-link \{([^}]*)\}", css).group(1)
        self.assertIn("color: inherit", body)
        self.assertRegex(css, r"\.player-link:hover \{[^}]*text-decoration:\s*underline")
        self.assertNotRegex(css, r"\.player-link:focus[^{]*\{[^}]*outline:")


if __name__ == "__main__":
    unittest.main()
