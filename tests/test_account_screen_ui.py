"""Account management screen (replaces the account detail modal): static checks.

These tests only read public/index.html, public/admin.js, public/admin.css and
public/locales/es.json; they do not start the server.
"""

import json
import os
import re
import shutil
import subprocess
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PUBLIC = os.path.join(ROOT, "public")

HEX_COLOR_RE = re.compile(r"#[0-9a-fA-F]{3,8}\b")
TABS = ("characters", "vault", "security")
SCREEN_START = "// --- Account management screen"
SCREEN_END = "// --- Character Mail (read-only)"
CSS_MARKER = "/* Account management screen */"


def _read(*parts):
    with open(os.path.join(PUBLIC, *parts), encoding="utf-8") as f:
        return f.read()


def _function_body(js, name):
    """Source of `function name(...) { ... }` up to the next function / section comment."""
    match = re.search(r"\n  function %s\(.*?(?=\n  function |\n  // ---|\Z)" % re.escape(name), js, re.S)
    return match.group(0) if match else ""


def _screen_html(html):
    start = html.index('id="account-screen"')
    return html[start:html.index("<!-- /account-screen -->", start)]


def _screen_js(js):
    start = js.index(SCREEN_START)
    return js[start:js.index(SCREEN_END, start)]


class TestScreenMarkup(unittest.TestCase):
    def setUp(self):
        self.html = _read("index.html")
        self.screen = _screen_html(self.html)

    def test_section_is_hidden_by_default_and_lives_in_main_after_the_list(self):
        self.assertRegex(self.html, r'<section id="account-screen"[^>]*\bhidden\b')
        main_end = self.html.index("</main>")
        self.assertGreater(self.html.index('id="account-screen"'), self.html.index('id="tab-view-accounts"'))
        self.assertLess(self.html.index('id="account-screen"'), main_end)

    def test_the_list_stays_in_the_dom_and_the_screen_is_not_a_top_tab(self):
        self.assertIn('<section id="tab-view-accounts">', self.html)
        self.assertIn('id="accounts-tbody"', self.html)
        self.assertNotRegex(self.html, r'data-tab="account[^s"]')
        self.assertEqual(self.html.count('data-tab="accounts"'), 1)

    def test_breadcrumb_landmark_with_current_page(self):
        self.assertRegex(self.screen, r'<nav[^>]*aria-label="Breadcrumb"[^>]*data-i18n-aria-label="Breadcrumb"')
        self.assertRegex(self.screen, r'aria-current="page"')
        self.assertRegex(self.screen, r'<a[^>]*href="#/accounts"')

    def test_back_link_returns_to_the_list(self):
        self.assertRegex(self.screen, r'<a id="account-back"[^>]*href="#/accounts"')

    def test_h1_is_programmatically_focusable_and_h2_label_the_sections(self):
        self.assertRegex(self.html, r'<h1 id="account-title"[^>]*tabindex="-1"')
        self.assertEqual(self.screen.count("<h1"), 1)
        self.assertGreaterEqual(self.screen.count("<h2"), 4)

    def test_tablist_tabs_and_panels_are_wired(self):
        self.assertRegex(self.screen, r'role="tablist"[^>]*aria-label="[^"]+"')
        self.assertEqual(len(re.findall(r'role="tab"', self.screen)), 3)
        self.assertEqual(len(re.findall(r'role="tabpanel"', self.screen)), 3)
        for index, tab in enumerate(TABS):
            with self.subTest(tab=tab):
                button = re.search(r'<button[^>]*id="account-tab-%s"[^>]*>' % tab, self.screen)
                self.assertIsNotNone(button)
                tag = button.group(0)
                self.assertIn('role="tab"', tag)
                self.assertIn('aria-controls="account-panel-%s"' % tab, tag)
                self.assertIn('aria-selected="%s"' % ("true" if index == 0 else "false"), tag)
                self.assertIn('tabindex="%s"' % ("0" if index == 0 else "-1"), tag)
                self.assertIn('type="button"', tag)
                panel = re.search(r'<div[^>]*id="account-panel-%s"[^>]*>' % tab, self.screen)
                self.assertIsNotNone(panel)
                self.assertIn('role="tabpanel"', panel.group(0))
                self.assertIn('aria-labelledby="account-tab-%s"' % tab, panel.group(0))
                if index:
                    self.assertRegex(panel.group(0), r"\bhidden\b")

    def test_panels_hold_characters_gm_tools_vault_and_security(self):
        characters = self.screen[self.screen.index('id="account-panel-characters"'):self.screen.index('id="account-panel-vault"')]
        self.assertIn('id="account-characters"', characters)
        self.assertIn('id="account-gm-slot"', characters)
        vault = self.screen[self.screen.index('id="account-panel-vault"'):self.screen.index('id="account-panel-security"')]
        self.assertIn('id="account-vault-content"', vault)
        security = self.screen[self.screen.index('id="account-panel-security"'):]
        for element_id in ("account-btn-password", "account-btn-ban", "account-btn-unban", "account-btn-delete"):
            with self.subTest(element_id=element_id):
                self.assertIn('id="%s"' % element_id, security)

    def test_danger_zone_is_the_last_block_of_the_security_panel_and_holds_delete(self):
        panel = self.screen[self.screen.index('id="account-panel-security"'):]
        zone = panel.index('id="account-danger-zone"')
        self.assertIn('id="account-btn-delete"', panel[zone:])
        self.assertNotIn('id="account-btn-delete"', panel[:zone])
        self.assertRegex(panel[zone - 80:zone + 80], r'<section[^>]*account-danger-zone')
        tail = panel[panel.index("</section>", zone) + len("</section>"):]
        self.assertNotRegex(tail, r"<(section|article|h2|h3|button|form|a)\b")
        self.assertNotIn("account-card", tail)
        # The zone carries a short warning and is labelled by its own heading.
        self.assertRegex(panel[zone:], r'<h3[^>]*id="account-danger-title"')
        self.assertRegex(panel[zone:], r'aria-labelledby="account-danger-title"|id="account-danger-title"')

    def test_delete_uses_the_danger_style_and_is_separated_from_other_actions(self):
        self.assertRegex(self.screen, r'<button[^>]*id="account-btn-delete"[^>]*class="btn btn-danger"|<button[^>]*class="btn btn-danger"[^>]*id="account-btn-delete"')
        self.assertRegex(self.screen, r'<button[^>]*id="account-btn-ban"[^>]*btn-danger|<button[^>]*btn-danger[^>]*id="account-btn-ban"')

    def test_save_notes_is_the_only_primary_button(self):
        self.assertEqual(len(re.findall(r"\bbtn-primary\b", self.screen)), 1)
        self.assertRegex(self.screen, r'<button[^>]*id="account-save-notes"[^>]*btn-primary|<button[^>]*btn-primary[^>]*id="account-save-notes"')

    def test_notes_field_has_a_visible_label_and_a_polite_status_region(self):
        self.assertRegex(self.screen, r'<label[^>]*for="account-notes"')
        self.assertRegex(self.screen, r'<textarea id="account-notes"')
        self.assertRegex(self.screen, r'id="account-notes-status"[^>]*aria-live="polite"|aria-live="polite"[^>]*id="account-notes-status"')

    def test_structural_icons_are_inline_svg_and_hidden_from_assistive_tech(self):
        svgs = re.findall(r"<svg\b[^>]*>", self.screen)
        self.assertGreaterEqual(len(svgs), 4)  # back arrow + three tab icons
        for tag in svgs:
            with self.subTest(tag=tag):
                self.assertIn('aria-hidden="true"', tag)
                self.assertIn('focusable="false"', tag)

    def test_no_inline_styles_or_hardcoded_colors_in_the_screen_markup(self):
        self.assertNotIn("style=", self.screen)
        self.assertEqual(HEX_COLOR_RE.findall(self.screen), [])

    def test_state_region_offers_a_way_back_to_the_list(self):
        self.assertIn('id="account-state"', self.screen)


class TestModalIsGone(unittest.TestCase):
    def setUp(self):
        self.html = _read("index.html")
        self.js = _read("admin.js")

    def test_modal_detail_markup_and_ids_are_removed(self):
        for needle in ('id="modal-detail"', 'id="detail-acc-', 'id="detail-chars-list"', 'id="detail-vault"',
                       'id="btn-view-vault"', 'id="btn-save-notes"', "Account Record"):
            with self.subTest(needle=needle):
                self.assertNotIn(needle, self.html)

    def test_script_no_longer_opens_the_detail_modal(self):
        self.assertNotIn("modalDetail", self.js)
        self.assertNotIn("modal-detail", self.js)
        self.assertNotIn("detail-acc-", self.js)
        self.assertNotIn("detail-chars-list", self.js)
        body = _function_body(self.js, "showAccountDetail")
        if body:
            self.assertNotIn("openModal(els.modalDetail)", body)

    def test_confirmation_modals_are_kept(self):
        for modal in ("modal-password", "modal-ban", "modal-delete"):
            with self.subTest(modal=modal):
                self.assertIn('id="%s"' % modal, self.html)


class TestRouter(unittest.TestCase):
    def setUp(self):
        self.js = _read("admin.js")
        self.screen_js = _screen_js(self.js)

    def test_hash_route_is_encoded_and_decoded(self):
        self.assertIn("'#/accounts/'", self.js)
        self.assertIn("encodeURIComponent(name)", _function_body(self.js, "accountRouteHash"))
        parse = _function_body(self.js, "parseAccountRoute")
        self.assertIn("decodeURIComponent(", parse)
        self.assertIn("catch", parse)  # a malformed escape must not throw

    def test_hashchange_drives_the_screen(self):
        self.assertIn("addEventListener('hashchange'", self.js)
        self.assertRegex(self.js, r"addEventListener\('hashchange',\s*handleRouteChange\)")
        handler = _function_body(self.js, "handleRouteChange")
        self.assertIn("parseAccountRoute(", handler)
        self.assertIn("openAccountScreen(", handler)
        self.assertIn("closeAccountScreen(", handler)

    def test_direct_url_opens_the_screen_after_login(self):
        self.assertIn("handleRouteChange()", _function_body(self.js, "setAuthenticated"))

    def test_row_button_navigates_by_hash_instead_of_opening_a_modal(self):
        self.assertRegex(self.js, r"classList\.contains\('btn-view-detail'\)\)\s*\{\s*navigateToAccount\(acc\)")
        self.assertIn("location.hash = accountRouteHash(", _function_body(self.js, "navigateToAccount"))

    def test_row_button_is_labelled_manage(self):
        self.assertIn("t('Manage')", self.js)
        row_button = re.search(r"btn-view-detail\" data-account=.*?</button>", self.js)
        self.assertIsNotNone(row_button)
        self.assertNotIn("t('Record')", row_button.group(0))
        self.assertIn("aria-label=", row_button.group(0))

    def test_unknown_account_gets_a_not_found_state(self):
        load = _function_body(self.js, "loadAccountScreen")
        self.assertIn("404", load)
        self.assertIn("renderAccountNotFound(", load)
        self.assertIn("#/accounts", _function_body(self.js, "renderAccountNotFound"))

    def test_back_and_escape_return_to_the_list(self):
        self.assertIn("goToAccountList", self.js)
        key = _function_body(self.js, "handleAccountEscape")
        self.assertIn("'Escape'", key)
        for needle in ("INPUT", "TEXTAREA", "SELECT", ".modal-backdrop"):
            with self.subTest(needle=needle):
                self.assertIn(needle, key)
        self.assertIn("goToAccountList()", key)
        self.assertRegex(self.js, r"addEventListener\('keydown',\s*handleAccountEscape\)")

    def test_switching_tabs_or_language_keeps_the_screen_working(self):
        switch = _function_body(self.js, "switchTab")
        self.assertIn("renderAccountsViews()", switch)
        self.assertIn("resetAccountScreen()", switch)
        relocalize = _function_body(self.js, "relocalize")
        self.assertIn("isAccountScreenOpen()", relocalize)

    def test_returning_to_the_list_preserves_scroll_and_does_not_refetch(self):
        close = _function_body(self.js, "closeAccountScreen")
        self.assertIn("scrollTo(", close)
        self.assertIn("focusAccountOpener(", close)
        self.assertNotIn("loadAccounts()", close)
        self.assertIn("listScroll", _function_body(self.js, "openAccountScreen"))


class TestFocusAndTabs(unittest.TestCase):
    def setUp(self):
        self.js = _read("admin.js")

    def test_focus_moves_to_the_heading_on_route_change(self):
        self.assertIn("els.accountTitle.focus(", _function_body(self.js, "openAccountScreen"))

    def test_focus_returns_to_the_row_button_that_opened_the_screen(self):
        body = _function_body(self.js, "focusAccountOpener")
        self.assertIn("btn-view-detail", body)
        self.assertIn(".focus(", body)

    def test_tab_keyboard_support(self):
        body = _function_body(self.js, "handleAccountTabKeydown")
        for key in ("ArrowLeft", "ArrowRight", "Home", "End"):
            with self.subTest(key=key):
                self.assertIn("'%s'" % key, body)
        self.assertRegex(self.js, r"addEventListener\('keydown',\s*handleAccountTabKeydown\)")

    def test_tabs_use_aria_selected_and_roving_tabindex(self):
        body = _function_body(self.js, "setAccountTab")
        self.assertIn("aria-selected", body)
        self.assertIn("tabindex", body)
        self.assertIn("hidden", body)

    def test_active_tab_is_kept_in_the_url(self):
        self.assertIn("replaceState(", _function_body(self.js, "setAccountTab"))

    def test_lazy_loading_uses_skeletons_and_a_retry_button(self):
        self.assertIn("skeleton", self.js)
        self.assertIn("data-retry", self.js)
        self.assertIn("t('Retry')", self.js)
        self.assertIn("loadAccountVault(", _function_body(self.js, "setAccountTab"))


class TestFormsAndFeedback(unittest.TestCase):
    def setUp(self):
        self.js = _read("admin.js")

    def test_save_notes_shows_progress_and_inline_status(self):
        body = _function_body(self.js, "handleSaveNotes")
        self.assertIn("disabled = true", body)
        self.assertIn("is-loading", body)
        self.assertIn("setNotesStatus(", body)
        self.assertIn("finally", body)

    def test_unsaved_notes_are_confirmed_before_leaving(self):
        body = _function_body(self.js, "confirmDiscardNotes")
        self.assertIn("confirm(", body)
        self.assertIn("t('You have unsaved notes. Leave without saving?')", body)
        self.assertIn("beforeunload", self.js)

    def test_modals_are_reused_from_the_screen(self):
        for needle in ("showChangePassword(", "showBanAccount(", "handleUnbanAccount(", "showDeleteAccount("):
            with self.subTest(needle=needle):
                self.assertGreaterEqual(self.js.count(needle), 2)  # definition + the screen call
        for element_id in ("account-btn-password", "account-btn-ban", "account-btn-unban", "account-btn-delete"):
            with self.subTest(element_id=element_id):
                self.assertIn("getElementById('%s')" % element_id, self.js)

    def test_mutations_refresh_the_screen_and_delete_returns_to_the_list(self):
        self.assertIn("goToAccountList()", _function_body(self.js, "handleDeleteAccount"))
        for name in ("handleUpdatePassword", "handleBanAccount", "handleUnbanAccount"):
            with self.subTest(name=name):
                self.assertIn("refreshOpenAccount(", _function_body(self.js, name))

    def test_admin_accounts_hide_ban_and_delete_like_the_list(self):
        body = _function_body(self.js, "renderAccountSecurity")
        self.assertIn("is_admin", body)
        self.assertIn("accountDangerZone", body)

    def test_server_text_is_escaped(self):
        card = _function_body(self.js, "renderCharacterCard")
        for needle in ("escapeHtml(c.name)", "escapeHtml(c.career_name)", "escapeHtml(c.scene_name)"):
            with self.subTest(needle=needle):
                self.assertIn(needle, card)
        badges = _function_body(self.js, "renderAccountBadges")
        self.assertIn("escapeHtml(", badges)
        self.assertIn("textContent", _function_body(self.js, "renderAccountHeader"))

    def test_gm_tools_live_in_the_characters_panel(self):
        body = _function_body(self.js, "buildGmPanel")
        self.assertIn("els.accountGmSlot", body)
        self.assertNotIn("modal-body", body)

    def test_no_console_calls(self):
        self.assertNotRegex(self.js, r"\bconsole\.")

    def test_new_script_has_no_hex_colors_and_no_inline_styles(self):
        block = _screen_js(self.js)
        self.assertEqual(HEX_COLOR_RE.findall(block), [])
        self.assertNotIn("style=", block)
        self.assertNotIn(".style.", block)


class TestStyles(unittest.TestCase):
    def setUp(self):
        self.css = _read("admin.css")
        self.marker = self.css.index(CSS_MARKER)
        self.block = self.css[self.marker:]

    def test_added_css_uses_tokens_only(self):
        root = re.search(r":root\s*\{(.*?)\n\}", self.css, re.S).group(1)
        tokens = {c.lower() for c in HEX_COLOR_RE.findall(root)}
        added = {c.lower() for c in HEX_COLOR_RE.findall(self.block)}
        self.assertEqual(sorted(added - tokens), [])
        self.assertEqual(sorted(added), [])  # tokens are used through var(), never re-typed

    def test_reduced_motion_is_respected(self):
        match = re.search(r"@media \(prefers-reduced-motion: reduce\)\s*\{(.*?)\n\}", self.block, re.S)
        self.assertIsNotNone(match)
        self.assertIn("animation: none", match.group(1))
        self.assertIn("transition: none", match.group(1))

    def test_motion_only_animates_transform_and_opacity(self):
        for value in re.findall(r"transition:\s*([^;]+);", self.block):
            if value.startswith("none"):
                continue  # the reduced-motion reset
            with self.subTest(value=value):
                self.assertNotIn("all", value)
                self.assertRegex(value, r"^(transform|opacity)\b")

    def test_responsive_rules_exist_and_the_layout_is_mobile_first(self):
        self.assertRegex(self.block, r"@media \(min-width: 1024px\)\s*\{[^@]*\.account-layout")
        self.assertIn("position: sticky", self.block)
        base = self.block[:self.block.index("@media (min-width: 1024px)")]
        self.assertRegex(base, r"\.account-layout\s*\{[^}]*display:\s*flex")
        self.assertNotIn("overflow-x: scroll", base)

    def test_tabs_scroll_with_snapping_on_small_screens(self):
        self.assertRegex(self.block, r"\.account-tabs\s*\{[^}]*overflow-x:\s*auto")
        self.assertIn("scroll-snap-type: x", self.block)
        self.assertIn("scroll-snap-align", self.block)

    def test_touch_targets_and_focus_rings(self):
        self.assertIn("min-height: 44px", self.block)
        self.assertRegex(self.block, r"\.account-tab:focus-visible")
        # Buttons, links and fields of the screen get the one global 2px ring (pinned in
        # tests/test_admin_polish_ui.py); no rule may take it away from them.
        self.assertRegex(self.css, r"(?m)^:focus-visible\s*\{[^}]*outline:\s*2px solid var\(--border-focus\)")
        self.assertNotRegex(self.css, r"outline:\s*(none|0)\b")
        self.assertRegex(self.block, r'\.account-tab\[aria-selected="true"\]')

    def test_screen_uses_the_shared_page_width_tokens(self):
        self.assertNotIn("max-width: 1400px", self.block)
        self.assertNotRegex(self.block, r"padding:\s*\d+px\s+24px")

    def test_skeleton_and_danger_zone_styles_exist(self):
        for selector in (".skeleton", ".account-danger-zone", ".btn.is-loading", ".sr-only"):
            with self.subTest(selector=selector):
                self.assertIn(selector, self.block)

    def test_no_horizontal_page_scroll_guards(self):
        self.assertRegex(self.block, r"\.account-main\s*\{[^}]*min-width:\s*0")


class TestLocale(unittest.TestCase):
    def setUp(self):
        self.es = json.loads(_read("locales", "es.json"))

    def test_row_button_label_is_manage(self):
        self.assertEqual(self.es["Manage"], "Gestionar")

    def test_modal_only_keys_are_gone(self):
        for key in ("📋 Account Record:", "Hide vault", "View the shared account vault (read-only)",
                    "Error loading record: {message}"):
            with self.subTest(key=key):
                self.assertNotIn(key, self.es)

    def test_new_screen_strings_are_translated(self):
        for key in ("Security & moderation", "Danger zone", "Characters", "Retry", "Saving…",
                    "You have unsaved notes. Leave without saving?", "Back to accounts", "Notes"):
            with self.subTest(key=key):
                self.assertIn(key, self.es)


class TestGmAfkTools(unittest.TestCase):
    """GM Tools: the WildAFK auto mode / Bonus Time form (afkunlock, afkmode, afktime)."""

    def setUp(self):
        self.js = _read("admin.js")
        self.panel = _function_body(self.js, "buildGmPanel")
        self.es = json.loads(_read("locales", "es.json"))

    def test_form_is_built_inside_the_gm_tools_panel(self):
        self.assertIn('id="gm-afk-form"', self.panel)
        self.assertIn('id="gm-afk-minutes"', self.panel)
        self.assertIn('data-i18n="Auto mode / Bonus Time"', self.panel)

    def test_admin_js_parses(self):
        # The other checks read admin.js as text; only a parser catches a broken string literal.
        node = shutil.which("node")
        if node is None:
            self.skipTest("node is not installed")
        result = subprocess.run([node, "--check", os.path.join(PUBLIC, "admin.js")], capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stderr)

    def test_note_says_the_character_must_be_online_and_the_result_is_in_game_chat(self):
        note = re.search(r'id="gm-afk-note"[^>]*data-i18n="([^"]+)"', self.panel)
        self.assertIsNotNone(note)
        text = note.group(1)
        self.assertIn("online", text)
        self.assertIn("game chat", text)
        self.assertIn("gm_allowed_commands", text)

    def test_buttons_send_each_afk_command_with_validated_args(self):
        for snippet in ("sendGmCommand('afkunlock', { state: 'on' })", "sendGmCommand('afkunlock', { state: 'off' })",
                        "sendGmCommand('afkmode', { state: 'on' })", "sendGmCommand('afkmode', { state: 'off' })",
                        "sendGmCommand('afktime', { action: 'info' })"):
            with self.subTest(snippet=snippet):
                self.assertIn(snippet, self.panel)
        handler = _function_body(self.js, "handleGmAfkTime")
        self.assertIn("parseGmInt('gm-afk-minutes')", handler)
        self.assertIn("sendGmCommand('afktime', { action: action, minutes: minutes })", handler)
        self.assertIn("100000", handler)

    def test_minutes_input_is_cleared_with_the_panel(self):
        self.assertIn("'gm-afk-minutes'", _function_body(self.js, "resetGmPanel"))

    def test_afk_strings_are_translated(self):
        for key in ("Auto mode / Bonus Time", "Unlock auto mode", "Lock auto mode", "Bonus Time on", "Bonus Time off",
                    "Minutes", "Show Bonus Time", "Set minutes", "Add minutes"):
            with self.subTest(key=key):
                self.assertIn(key, self.es)


if __name__ == "__main__":
    unittest.main()
