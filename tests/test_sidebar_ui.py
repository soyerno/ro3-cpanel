"""The panel menu is a collapsible sidebar with grouped sub-sections instead of a horizontally scrolling tab bar.

Static checks over public/index.html, public/admin.css and public/admin.js. The behaviour is also checked in a
real browser when the change ships (see the PR).
"""

import os
import re
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from test_confirm_ui import function_body, read  # noqa: E402

TABS = ("dashboard", "accounts", "rankings", "guilds", "economy", "auctions", "giftcodes", "market", "audit")
GROUPS = {"players": ("accounts", "rankings", "guilds"),
          "trade": ("economy", "auctions", "giftcodes", "market"),
          "system": ("audit",)}


def rule(css, selector):
    match = re.search(r"(?m)^" + re.escape(selector) + r"\s*\{([^}]*)\}", css)
    assert match, "rule %s not found" % selector
    return match.group(1)


class SidebarMarkupTest(unittest.TestCase):
    def setUp(self):
        self.html = read("public", "index.html")
        match = re.search(r'<nav id="app-subnav".*?</nav>', self.html, re.S)
        self.assertIsNotNone(match)
        self.nav = match.group(0)

    def test_the_nav_is_a_labelled_sidebar_between_the_header_and_the_content_inside_one_shell(self):
        self.assertRegex(self.nav, r'<nav id="app-subnav" class="sidebar"[^>]*aria-label="Panel sections"[^>]*data-i18n-aria-label="Panel sections"')
        shell = self.html.index('id="app-shell"')
        self.assertLess(self.html.index('id="app-header"'), shell)
        self.assertLess(shell, self.html.index('id="app-subnav"'))
        self.assertLess(self.html.index('id="app-subnav"'), self.html.index('id="main-content"'))
        self.assertLess(self.html.index('id="main-content"'), self.html.index("</main>"))
        after_main = self.html[self.html.index("</main>"):]
        self.assertRegex(after_main, r"</main>\s*</div>")

    def test_every_section_is_still_one_tab_button_with_its_data_tab(self):
        for tab in TABS:
            with self.subTest(tab=tab):
                self.assertEqual(self.nav.count('data-tab="%s"' % tab), 1)
                self.assertRegex(self.nav, r'<button class="tab-btn[^"]*" data-tab="%s" type="button"' % tab)

    def test_sections_are_grouped_under_collapsible_headings(self):
        for group, tabs in GROUPS.items():
            with self.subTest(group=group):
                block = re.search(r'<div class="sidebar-group[^"]*" data-group="%s">(.*?)\n    </div>\n' % group, self.nav, re.S)
                self.assertIsNotNone(block, group)
                for tab in tabs:
                    self.assertIn('data-tab="%s"' % tab, block.group(1))
                toggle = re.search(r'<button type="button" class="sidebar-group-toggle" id="sidebar-toggle-%s" aria-expanded="true" aria-controls="(sidebar-items-%s)"' % (group, group), block.group(1))
                self.assertIsNotNone(toggle)
                self.assertIn('id="%s"' % toggle.group(1), block.group(1))

    def test_dashboard_is_a_top_level_entry_before_the_groups(self):
        self.assertLess(self.nav.index('data-tab="dashboard"'), self.nav.index('data-group="players"'))
        self.assertLess(self.nav.index('data-group="players"'), self.nav.index('data-group="trade"'))
        self.assertLess(self.nav.index('data-group="trade"'), self.nav.index('data-group="system"'))

    def test_the_original_tab_order_constraints_still_hold(self):
        for earlier, later in (("economy", "giftcodes"), ("giftcodes", "market")):
            self.assertLess(self.nav.index('data-tab="%s"' % earlier), self.nav.index('data-tab="%s"' % later))

    def test_the_accounts_counter_stays_inside_the_accounts_button(self):
        button = re.search(r'<button class="tab-btn[^"]*" data-tab="accounts".*?</button>', self.nav, re.S).group(0)
        self.assertIn('id="tab-accounts-count"', button)

    def test_collapse_button_announces_its_state_and_has_a_name(self):
        self.assertRegex(self.nav, r'<button type="button" id="sidebar-collapse" class="sidebar-collapse" aria-pressed="false" aria-label="Collapse menu" data-i18n-aria-label="Collapse menu"')

    def test_header_hamburger_controls_the_sidebar(self):
        header = re.search(r'<header id="app-header".*?</header>', self.html, re.S).group(0)
        self.assertRegex(header, r'<button type="button" id="sidebar-open" class="sidebar-open" aria-controls="app-subnav" aria-expanded="false" aria-label="Open menu" data-i18n-aria-label="Open menu"')

    def test_the_drawer_has_a_close_button_and_a_backdrop(self):
        self.assertRegex(self.nav, r'<button type="button" id="sidebar-close" class="sidebar-close" aria-label="Close menu" data-i18n-aria-label="Close menu"')
        self.assertRegex(self.html, r'<div id="sidebar-backdrop" class="sidebar-backdrop" hidden></div>')

    def test_decorative_svgs_are_hidden_from_assistive_tech(self):
        for svg in re.findall(r"<svg\b[^>]*>", self.nav):
            self.assertIn('aria-hidden="true"', svg)
            self.assertIn('focusable="false"', svg)

    def test_no_inline_style_or_handler_attributes_in_the_shell(self):
        shell = self.html[self.html.index('<header id="app-header"'):self.html.index("</nav>")]
        self.assertNotRegex(shell, r"\sstyle\s*=")
        self.assertNotRegex(shell, r"\son[a-z]+\s*=")


class SidebarCssTest(unittest.TestCase):
    def setUp(self):
        self.css = read("public", "admin.css")

    def test_the_menu_never_scrolls_sideways(self):
        body = rule(self.css, ".sidebar")
        self.assertRegex(body, r"overflow-x:\s*hidden")
        self.assertRegex(body, r"overflow-y:\s*auto")
        self.assertNotRegex(self.css, r"\.subnav-tabs")

    def test_the_shell_lays_the_sidebar_and_the_content_side_by_side_and_lets_the_content_shrink(self):
        self.assertRegex(rule(self.css, ".app-shell"), r"display:\s*flex")
        self.assertRegex(rule(self.css, ".main-content"), r"min-width:\s*0")

    def test_the_desktop_sidebar_stays_in_view_below_the_header(self):
        body = rule(self.css, ".sidebar")
        self.assertRegex(body, r"position:\s*sticky")
        self.assertIn("top: var(--header-height)", body)

    def test_a_collapsed_sidebar_is_an_icon_rail_with_hidden_labels(self):
        self.assertIn(".app-shell.is-collapsed .sidebar", self.css)
        self.assertRegex(self.css, r"\.app-shell\.is-collapsed [^{]*\.tab-btn > span[^{]*\{[^}]*display:\s*none")

    def test_groups_fold_and_the_chevron_turns(self):
        self.assertIn(".sidebar-group:not(.is-open) .sidebar-items", self.css)
        self.assertRegex(self.css, r"\.sidebar-group\.is-open [^{]*\.sidebar-chevron[^{]*\{[^}]*rotate")

    def test_the_active_item_has_a_visible_non_colour_indicator(self):
        body = rule(self.css, ".tab-btn.active")
        self.assertRegex(body, r"box-shadow:\s*inset")
        self.assertNotRegex(body, r"border-(left|right)")

    def test_on_a_phone_the_sidebar_is_an_off_canvas_drawer_hidden_from_everyone_until_opened(self):
        mobile = re.search(r"@media \(max-width: 860px\)\s*\{(.*?)\n\}", self.css, re.S)
        self.assertIsNotNone(mobile)
        text = mobile.group(1)
        self.assertRegex(text, r"\.sidebar \{[^}]*position:\s*fixed")
        self.assertRegex(text, r"\.sidebar \{[^}]*transform:\s*translateX\(-100%\)")
        self.assertRegex(text, r"\.sidebar \{[^}]*visibility:\s*hidden")
        self.assertRegex(text, r"\.sidebar\.is-open \{[^}]*visibility:\s*visible")
        self.assertIn(".sidebar-open", text)
        self.assertIn(".sidebar-close", text)

    def test_drawer_controls_only_exist_on_the_matching_screen_size(self):
        bodies = re.findall(r"(?m)^\.sidebar-open,\s*\.sidebar-close \{([^}]*)\}", self.css)
        self.assertTrue(any(re.search(r"display:\s*none", b) for b in bodies), "hidden by default outside the drawer breakpoint")

    def test_the_backdrop_sits_between_the_page_and_the_drawer(self):
        backdrop = int(re.search(r"z-index:\s*(\d+)", rule(self.css, ".sidebar-backdrop")).group(1))
        mobile = re.search(r"@media \(max-width: 860px\)\s*\{(.*?)\n\}", self.css, re.S).group(1)
        drawer = re.search(r"\.sidebar \{[^}]*z-index:\s*(\d+)", mobile)
        self.assertIsNotNone(drawer)
        self.assertLess(backdrop, int(drawer.group(1)))
        self.assertGreater(backdrop, 100)

    def test_motion_is_switched_off_for_people_who_ask_for_less(self):
        reduced = re.search(r"@media \(prefers-reduced-motion: reduce\)\s*\{(.*?)\n\}", self.css, re.S).group(1)
        self.assertRegex(reduced, r"transition:\s*none\s*!important")

    def test_items_are_big_enough_to_touch(self):
        coarse = re.search(r"@media \(pointer: coarse\)\s*\{(.*?)\n\}", self.css, re.S).group(1)
        self.assertIn(".sidebar-group-toggle", coarse)
        self.assertIn(".sidebar-collapse", coarse)
        self.assertIn(".sidebar-open", coarse)


class SidebarScriptTest(unittest.TestCase):
    def setUp(self):
        self.js = read("public", "admin.js")

    def test_preferences_survive_reloads_but_never_break_when_storage_is_blocked(self):
        for name in ("readSidebarPrefs", "saveSidebarPrefs"):
            self.assertIn("try {", function_body(self.js, name), name)
            self.assertIn("catch", function_body(self.js, name), name)

    def test_collapsing_updates_the_pressed_state_the_label_and_the_rail_tooltips(self):
        body = function_body(self.js, "setSidebarCollapsed")
        self.assertIn("is-collapsed", body)
        self.assertIn("aria-pressed", body)
        self.assertIn("syncSidebarTitles()", body)

    def test_a_group_toggle_keeps_aria_expanded_in_sync(self):
        body = function_body(self.js, "toggleSidebarGroup")
        self.assertIn("aria-expanded", body)
        self.assertIn("is-open", body)

    def test_opening_a_section_opens_its_group(self):
        self.assertIn("openSidebarGroupOf(tabId)", function_body(self.js, "switchTab"))

    def test_picking_any_menu_item_closes_the_drawer_even_one_another_script_adds(self):
        # A delegated listener on the nav sees every .tab-btn, including ones that this file does not handle
        # (the Konsor build injects its own section button).
        init = function_body(self.js, "initSidebar")
        self.assertIn("els.subnav.addEventListener('click'", init)
        self.assertIn("if (e.target.closest('.tab-btn')) closeSidebarDrawer();", init)

    def test_the_drawer_closes_with_escape_the_backdrop_and_the_close_button(self):
        self.assertIn("'Escape'", function_body(self.js, "handleSidebarKeydown"))
        init = function_body(self.js, "initSidebar")
        for el in ("sidebarBackdrop", "sidebarClose", "sidebarOpen", "sidebarCollapse"):
            self.assertIn("els.%s" % el, init)

    def test_while_the_drawer_is_open_the_page_behind_it_is_inert_and_focus_comes_back(self):
        open_body = function_body(self.js, "openSidebarDrawer")
        self.assertIn("inert = true", open_body)
        close_body = function_body(self.js, "closeSidebarDrawer")
        self.assertIn("inert = false", close_body)
        self.assertIn("sidebarOpen.focus()", close_body)

    def test_leaving_phone_width_closes_the_drawer(self):
        self.assertIn("matchMedia('(max-width: 860px)')", function_body(self.js, "initSidebar"))

    def test_the_sidebar_is_initialised_with_the_other_listeners(self):
        self.assertRegex(self.js, r"\binitSidebar\(\);")


if __name__ == "__main__":
    unittest.main()
