"""Accessibility, UX and CSP polish of the admin panel: static checks.

These tests only read public/index.html, public/admin.js, public/admin.css and
public/locales/es.json; they do not start the server. The pure helpers of the
`// ui-helpers:begin ... // ui-helpers:end` block of admin.js are also executed with
node when it is installed (the check is skipped otherwise).

Groups follow the polish pass:
  P0 CSP (no inline styles or handlers), P1 modals, P2 live regions,
  P3 contrast and focus (measured from the :root tokens), P4 resilience and responsive polish.
"""

import json
import os
import re
import shutil
import subprocess
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PUBLIC = os.path.join(ROOT, "public")

SURFACES = ("bg-dark", "bg-card", "bg-card-hover", "bg-modal")
EMOJI_RE = re.compile("[\U0001F000-\U0001FFFF\u2600-\u27BF\u2B00-\u2BFF\ufe0f]")
NAV_TABS = ("accounts", "dashboard", "rankings", "guilds", "auctions", "audit", "economy", "giftcodes", "market")
MODALS = ("modal-guild", "modal-password", "modal-create", "modal-ban", "modal-delete", "modal-giftcode")

# Every loader that fills a table from the API, with the key its Retry button carries.
LOADERS = (
    ("loadAccounts", "accounts"),
    ("loadAuditLog", "audit"),
    ("loadEconomy", "economy"),
    ("loadRankings", "rankings"),
    ("loadGuilds", "guilds"),
    ("loadAuctions", "auctions"),
    ("loadGiftCodes", "giftcodes"),
    ("loadMarket", "market"),
)

# Handlers that send a request from a form or a button and must lock it while it is in flight.
SUBMIT_HANDLERS = (
    "handleUpdatePassword",
    "handleCreateAccount",
    "handleBanAccount",
    "handleDeleteAccount",
    "handleCreateGiftCode",
    "handleUnbanAccount",
    "sendGmCommand",
)

# Classes that replace the inline styles: each must be styled and actually used.
REPLACEMENT_CLASSES = (
    "table-state", "w-10", "w-18", "text-gold", "card-title", "muted-note", "modal-dialog-sm", "modal-title-danger",
    "login-error", "btn-block", "row-actions", "info-list", "dash-grid", "search-icon", "is-leaving",
)


def _read(*parts):
    with open(os.path.join(PUBLIC, *parts), encoding="utf-8") as f:
        return f.read()


def _function_body(js, name):
    """Source of `function name(...) { ... }` up to the next function / section comment."""
    match = re.search(r"\n  function %s\(.*?(?=\n  function |\n  // ---|\Z)" % re.escape(name), js, re.S)
    return match.group(0) if match else ""


def _root_tokens(css):
    root = re.search(r":root\s*\{(.*?)\n\}", css, re.S).group(1)
    return dict(re.findall(r"--([\w-]+):\s*(#[0-9a-fA-F]{6})\s*;", root))


def _luminance(hex_color):
    def channel(value):
        value /= 255
        return value / 12.92 if value <= 0.03928 else ((value + 0.055) / 1.055) ** 2.4

    r, g, b = (int(hex_color[i:i + 2], 16) for i in (1, 3, 5))
    return 0.2126 * channel(r) + 0.7152 * channel(g) + 0.0722 * channel(b)


def _ratio(a, b):
    high, low = sorted((_luminance(a), _luminance(b)), reverse=True)
    return (high + 0.05) / (low + 0.05)


def _rule_body(css, selector):
    match = re.search(r"(?m)^" + re.escape(selector) + r"\s*\{([^}]*)\}", css)
    assert match, "rule %s not found" % selector
    return match.group(1)


def _open_tags(html, tag):
    return re.findall(r"<%s\b[^>]*>" % tag, html)


class TestP0NoInlineStyles(unittest.TestCase):
    """A strict `style-src 'self'` policy drops every style attribute, so none may remain."""

    @classmethod
    def setUpClass(cls):
        cls.html = _read("index.html")
        cls.js = _read("admin.js")
        cls.css = _read("admin.css")

    def test_index_html_has_no_style_attributes(self):
        self.assertNotRegex(self.html, r"\bstyle\s*=")

    def test_admin_js_builds_no_style_attributes(self):
        self.assertNotIn('style="', self.js)
        self.assertNotIn('style=\\"', self.js)
        self.assertNotIn("style='", self.js)
        self.assertNotRegex(self.js, r"setAttribute\(\s*['\"]style['\"]")

    def test_there_are_no_inline_event_handler_attributes(self):
        self.assertNotRegex(self.html, r"\son[a-z]+\s*=")
        self.assertNotRegex(self.js, r"\son[a-z]+\s*=\s*[\"'\\]")

    def test_the_browse_accounts_button_is_wired_from_the_script(self):
        self.assertRegex(self.html, r'<button[^>]*id="btn-browse-accounts"')
        self.assertIn("getElementById('btn-browse-accounts')", self.js)

    def test_replacement_classes_are_styled_and_used(self):
        for name in REPLACEMENT_CLASSES:
            with self.subTest(name=name):
                self.assertRegex(self.css, r"\.%s\b" % re.escape(name))
                self.assertRegex(self.html + self.js, r"\b%s\b" % re.escape(name))

    def test_replacement_css_adds_no_raw_hex_colours(self):
        marker = self.css.index("/* Panel polish:")
        self.assertEqual(re.findall(r"#[0-9a-fA-F]{3,8}\b", self.css[marker:]), [])


class TestP1Modals(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.html = _read("index.html")
        cls.js = _read("admin.js")

    def _modal_tags(self):
        return re.findall(r'<div id="(modal-[\w-]+)" class="modal-backdrop"([^>]*)>', self.html)

    def test_every_modal_is_a_labelled_modal_dialog(self):
        tags = self._modal_tags()
        self.assertEqual(sorted(t[0] for t in tags), sorted(MODALS))
        # One chunk per modal: from its opening tag to the next modal (or the toast container).
        chunks = re.split(r'(?=<div id="modal-[\w-]+" class="modal-backdrop")', self.html)[1:]
        for (modal_id, attrs), chunk in zip(tags, chunks):
            with self.subTest(modal=modal_id):
                self.assertIn('role="dialog"', attrs)
                self.assertIn('aria-modal="true"', attrs)
                labelled = re.search(r'aria-labelledby="([^"]+)"', attrs)
                self.assertIsNotNone(labelled)
                self.assertIn('id="%s"' % labelled.group(1), chunk)

    def test_every_modal_close_button_has_an_accessible_name(self):
        closers = re.findall(r'<button[^>]*class="modal-close"[^>]*>', self.html)
        self.assertEqual(len(closers), len(MODALS))
        for tag in closers:
            with self.subTest(tag=tag):
                self.assertIn('type="button"', tag)
                self.assertIn('aria-label="Close"', tag)
                self.assertIn('data-i18n-aria-label="Close"', tag)

    def test_close_label_is_translated(self):
        self.assertIn("Close", json.loads(_read("locales", "es.json")))

    def test_the_dialog_can_take_focus_when_it_has_no_field(self):
        self.assertEqual(len(re.findall(r'<div class="modal-dialog[^"]*" tabindex="-1">', self.html)), len(MODALS))

    def test_focus_is_trapped_while_a_modal_is_open(self):
        self.assertIn("function focusTrapTarget(", self.js)
        keydown = _function_body(self.js, "handleModalKeydown")
        self.assertIn("'Tab'", keydown)
        self.assertIn("focusTrapTarget(", keydown)
        self.assertIn("shiftKey", keydown)
        self.assertRegex(self.js, r"addEventListener\('keydown',\s*handleModalKeydown\)")

    def test_escape_closes_the_top_modal(self):
        keydown = _function_body(self.js, "handleModalKeydown")
        self.assertIn("'Escape'", keydown)
        self.assertIn("preventDefault()", keydown)
        self.assertRegex(keydown, r"closeModal\(modalStack\[modalStack\.length - 1\]\)")

    def test_the_account_screen_escape_rule_ignores_presses_while_a_modal_is_open(self):
        body = _function_body(self.js, "handleAccountEscape")
        self.assertIn("e.defaultPrevented", body)
        self.assertIn(".modal-backdrop:not([hidden])", body)

    def test_focus_returns_to_the_opener_and_the_background_is_inert_while_open(self):
        open_body = _function_body(self.js, "openModal")
        close_body = _function_body(self.js, "closeModal")
        self.assertIn("modalReturnFocus.set(", open_body)
        self.assertIn("setBackgroundInert(true)", open_body)
        self.assertIn("opener.focus()", close_body)
        self.assertIn("setBackgroundInert(false)", close_body)
        inert = _function_body(self.js, "setBackgroundInert")
        self.assertIn("inert", inert)
        self.assertIn("toast-container", inert)
        # The opener is released from inert before it gets focus back.
        self.assertLess(close_body.index("setBackgroundInert(false)"), close_body.index("opener.focus()"))

    def test_focus_trap_helper_wraps_at_both_ends_when_run_with_node(self):
        node = shutil.which("node")
        if not node:
            self.skipTest("node is not installed")
        block = re.search(r"// ui-helpers:begin(.*?)// ui-helpers:end", self.js, re.S)
        self.assertIsNotNone(block, "ui-helpers block missing")
        script = (
            "const vm = require('node:vm'); const assert = require('node:assert/strict');"
            "const ui = vm.runInNewContext(process.argv[1] + '; ({ focusTrapTarget, actionLabel, toastRole })', {});"
            "const a = {}, b = {}, c = {}, outside = {};"
            "assert.equal(ui.focusTrapTarget([a, b, c], c, false), a);"
            "assert.equal(ui.focusTrapTarget([a, b, c], a, true), c);"
            "assert.equal(ui.focusTrapTarget([a, b, c], b, false), null);"
            "assert.equal(ui.focusTrapTarget([a, b, c], b, true), null);"
            "assert.equal(ui.focusTrapTarget([a, b], outside, false), a);"
            "assert.equal(ui.focusTrapTarget([a, b], outside, true), b);"
            "assert.equal(ui.focusTrapTarget([], outside, false), null);"
            "assert.equal(ui.actionLabel('Manage', 'alice'), 'Manage: alice');"
            "assert.equal(ui.actionLabel('Manage', ''), 'Manage');"
            "assert.equal(ui.toastRole('error'), 'alert');"
            "assert.equal(ui.toastRole('success'), 'status');"
            "assert.equal(ui.toastRole('info'), 'status');"
        )
        result = subprocess.run([node, "-e", script, block.group(1)], capture_output=True, text=True, timeout=30)
        self.assertEqual(result.returncode, 0, result.stderr)


class TestP2LiveRegions(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.html = _read("index.html")
        cls.js = _read("admin.js")

    def test_toast_container_is_a_polite_live_region(self):
        self.assertRegex(self.html, r'<div id="toast-container"[^>]*aria-live="polite"')

    def test_errors_are_announced_as_alerts_and_the_rest_as_status(self):
        toast = _function_body(self.js, "showToast")
        self.assertIn("setAttribute('role', toastRole(type))", toast)
        helper = _function_body(self.js, "toastRole")
        self.assertIn("'error'", helper)
        self.assertIn("'alert'", helper)
        self.assertIn("'status'", helper)

    def test_login_error_is_an_alert(self):
        self.assertRegex(self.html, r'<div id="login-error"[^>]*role="alert"')

    def test_loading_regions_announce_busy_state(self):
        self.assertGreaterEqual(len(re.findall(r'<tbody id="[\w-]+"[^>]*aria-busy="true"', self.html)), 6)
        helper = _function_body(self.js, "trackBusy")
        self.assertIn("aria-busy", helper)
        for name, _ in LOADERS:
            with self.subTest(loader=name):
                self.assertIn("trackBusy(", _function_body(self.js, name))


class TestP3ContrastAndFocus(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.html = _read("index.html")
        cls.js = _read("admin.js")
        cls.css = _read("admin.css")
        cls.tokens = _root_tokens(cls.css)

    def assertContrast(self, foreground, background, minimum):
        value = _ratio(self.tokens[foreground], self.tokens[background])
        self.assertGreaterEqual(value, minimum, "--%s on --%s is %.2f:1" % (foreground, background, value))

    def test_body_and_muted_text_reach_aa_on_every_surface(self):
        for name in ("text-main", "text-muted", "text-dim"):
            for surface in SURFACES:
                with self.subTest(text=name, surface=surface):
                    self.assertContrast(name, surface, 4.5)

    def test_accent_text_reaches_aa_on_every_surface(self):
        for name in ("gold", "danger", "success", "info"):
            for surface in SURFACES:
                with self.subTest(text=name, surface=surface):
                    self.assertContrast(name, surface, 4.5)

    def test_form_control_borders_reach_3_to_1(self):
        for surface in SURFACES:
            with self.subTest(surface=surface):
                self.assertContrast("border-input", surface, 3.0)

    def test_form_controls_use_the_input_border_token(self):
        for selector in (".form-input, .form-textarea", ".select-filter", ".search-box"):
            with self.subTest(selector=selector):
                self.assertIn("var(--border-input)", _rule_body(self.css, selector))

    def test_danger_button_hover_text_reaches_aa(self):
        body = _rule_body(self.css, ".btn-danger:hover")
        background = re.search(r"background:\s*var\(--([\w-]+)\)", body).group(1)
        text = re.search(r"(?<![\w-])color:\s*var\(--([\w-]+)\)", body).group(1)
        self.assertContrast(background, text, 4.5)

    def test_no_text_is_smaller_than_12px(self):
        sizes = [int(v) for v in re.findall(r"font-size:\s*(\d+)px", self.css)]
        self.assertGreater(len(sizes), 20)
        self.assertEqual([s for s in sizes if s < 12], [])

    def test_one_focus_ring_for_every_interactive_element(self):
        css = re.sub(r"/\*.*?\*/", "", self.css, flags=re.S)
        rings = re.findall(r"([^{}]*:focus-visible[^{}]*)\{([^{}]*\boutline:[^{}]*)\}", css)
        self.assertEqual(len(rings), 1, [r[0].strip() for r in rings])
        selector, body = rings[0]
        self.assertEqual(selector.strip(), ":focus-visible")
        self.assertRegex(body, r"outline:\s*2px solid var\(--border-focus\)")
        self.assertRegex(body, r"outline-offset:\s*2px")

    def test_no_rule_removes_the_outline(self):
        self.assertNotRegex(self.css, r"outline:\s*(none|0)\b")

    def test_every_control_has_an_accessible_name(self):
        labelled = set(re.findall(r'<label[^>]*\bfor="([^"]+)"', self.html))
        for tag in _open_tags(self.html, "input") + _open_tags(self.html, "select") + _open_tags(self.html, "textarea"):
            if re.search(r'type="(hidden|submit|button)"', tag):
                continue
            element_id = re.search(r'\bid="([^"]+)"', tag)
            with self.subTest(tag=tag):
                self.assertTrue(
                    'aria-label="' in tag or (element_id and element_id.group(1) in labelled),
                    "control without a label or aria-label",
                )

    def test_search_inputs_and_filters_are_named(self):
        for element_id, key in (
            ("search-input", "Search accounts"),
            ("status-select", "Filter accounts by status"),
            ("sort-select", "Sort accounts"),
            ("guild-search-input", "Search guild by name"),
        ):
            with self.subTest(element_id=element_id):
                tag = re.search(r'<(?:input|select)[^>]*id="%s"[^>]*>' % element_id, self.html).group(0)
                self.assertIn('data-i18n-aria-label="%s"' % key, tag)
                self.assertIn("aria-label=", tag)
                self.assertIn(key, json.loads(_read("locales", "es.json")))

    def test_the_tab_bar_is_a_named_navigation_landmark(self):
        self.assertRegex(self.html, r'<nav id="app-subnav"[^>]*aria-label="Panel sections"[^>]*data-i18n-aria-label="Panel sections"')

    def test_the_active_tab_is_exposed_to_assistive_technology(self):
        self.assertIn("aria-current", _function_body(self.js, "switchTab"))

    def test_row_action_buttons_are_named_with_their_text_and_the_account(self):
        helper = _function_body(self.js, "actionLabel")
        self.assertIn("': '", helper)
        rows = _function_body(self.js, "renderAccountsTable")
        for css_class, text in (
            ("btn-view-detail", "t('Manage')"),
            ("btn-change-pw", "t('Pass')"),
            ("btn-unban", "t('Unban')"),
            ("btn-ban", "t('Ban')"),
            ("btn-delete", "t('Delete account')"),
        ):
            with self.subTest(button=css_class):
                button = re.search(r'%s" data-account=.*?</button>' % css_class, rows, re.S)
                self.assertIsNotNone(button)
                self.assertIn("aria-label=", button.group(0))
                self.assertIn("actionLabel(" + text, button.group(0))

    def test_decorative_glyphs_are_hidden_from_assistive_technology(self):
        for tag in re.findall(r'<span[^>]*>([^<]*)</span>', self.html):
            if EMOJI_RE.search(tag) and len(tag.strip()) <= 2:
                self.assertRegex(self.html, r'<span[^>]*aria-hidden="true"[^>]*>%s</span>' % re.escape(tag))
        for tag in re.findall(r'<div class="stat-icon[^"]*"[^>]*>', self.html):
            self.assertIn('aria-hidden="true"', tag)


class TestP4Resilience(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.html = _read("index.html")
        cls.js = _read("admin.js")
        cls.css = _read("admin.css")
        cls.es = json.loads(_read("locales", "es.json"))

    def test_error_row_helper_offers_a_retry(self):
        helper = _function_body(self.js, "errorRowHtml")
        self.assertIn("colspan", helper)
        self.assertIn("data-retry=", helper)
        self.assertIn("t('Retry')", helper)
        self.assertIn('role="alert"', helper)

    def test_each_table_loader_shows_an_error_row_and_can_be_retried(self):
        retry_map = re.search(r"var RETRY_LOADERS = \{(.*?)\};", self.js, re.S)
        self.assertIsNotNone(retry_map)
        for name, key in LOADERS:
            with self.subTest(loader=name):
                body = _function_body(self.js, name)
                self.assertIn("errorRowHtml(", body)
                self.assertRegex(retry_map.group(1), r"\b%s:\s*%s\b" % (key, name))
                self.assertIn("'%s'" % key, body)

    def test_retry_buttons_are_wired_from_the_main_container(self):
        self.assertRegex(self.js, r"els\.mainContent\.addEventListener\('click'")
        self.assertIn("RETRY_LOADERS[", self.js)

    def test_character_mail_failure_can_be_retried(self):
        body = _function_body(self.js, "loadCharacterMail")
        self.assertIn("t('Retry')", body)
        self.assertIn("btn-mail-page", body)

    def test_the_initial_loading_rows_have_no_inline_styles_and_use_the_state_class(self):
        for text in ("Loading account list...", "Loading rankings...", "Loading guilds...", "Loading auctions...",
                     "Loading records...", "Loading movements...", "Loading gift codes...", "Loading listings..."):
            with self.subTest(text=text):
                self.assertRegex(self.html, r'<td[^>]*class="table-state"[^>]*data-i18n="%s"' % re.escape(text))

    def test_submit_buttons_are_disabled_while_the_request_is_in_flight(self):
        helper = _function_body(self.js, "setSubmitting")
        self.assertIn("disabled = busy", helper)
        self.assertIn("is-loading", helper)
        for name in SUBMIT_HANDLERS:
            with self.subTest(handler=name):
                body = _function_body(self.js, name)
                self.assertTrue(body, "function %s not found" % name)
                self.assertIn("setSubmitting(", body)
                self.assertIn("finally", body)

    def test_accounts_render_as_stacked_cards_on_narrow_screens(self):
        self.assertRegex(self.html, r'<table class="data-table data-table--stack">\s*<thead>\s*<tr>\s*<th[^>]*data-i18n="Account"')
        rows = _function_body(self.js, "renderAccountsTable")
        for key in ("Account", "Status", "Associated Characters", "Registration Date", "Last Login", "Actions"):
            with self.subTest(label=key):
                self.assertIn('data-label="\' + escapeHtml(t(\'%s\'))' % key, rows)
        media = re.search(r"@media \(max-width: 640px\)\s*\{(.*?)\n\}", self.css, re.S)
        self.assertIsNotNone(media)
        for needle in (".data-table--stack tr", ".data-table--stack td::before", "attr(data-label)", "display: block"):
            with self.subTest(needle=needle):
                self.assertIn(needle, media.group(1))

    def test_touch_targets_are_44px_on_coarse_pointers(self):
        coarse = re.search(r"@media \(pointer: coarse\)\s*\{(.*?)\n\}", self.css, re.S)
        self.assertIsNotNone(coarse)
        self.assertIn("min-height: 44px", coarse.group(1))
        self.assertIn("min-width: 44px", coarse.group(1))
        for selector in (".btn", ".tab-btn", ".modal-close", ".select-filter", ".lang-btn"):
            with self.subTest(selector=selector):
                self.assertIn(selector, coarse.group(1))

    def test_nav_icons_are_inline_svg_and_the_labels_are_plain_text(self):
        for tab in NAV_TABS:
            with self.subTest(tab=tab):
                button = re.search(r'<button class="tab-btn[^"]*" data-tab="%s"[^>]*>(.*?)</button>' % tab, self.html, re.S)
                self.assertIsNotNone(button)
                self.assertRegex(button.group(1), r'<svg\b[^>]*aria-hidden="true"[^>]*focusable="false"')
                self.assertNotRegex(button.group(1), EMOJI_RE.pattern)
                label = re.search(r'<span data-i18n="([^"]+)">([^<]+)</span>', button.group(1))
                self.assertIsNotNone(label)
                self.assertEqual(label.group(1), label.group(2))
                self.assertIn(label.group(1), self.es)
                self.assertNotRegex(label.group(1), EMOJI_RE.pattern)

    def test_the_nav_translation_keys_no_longer_carry_an_emoji(self):
        for key in ("👥 Accounts", "📊 Dashboard", "🏆 Rankings", "🛡️ Guilds", "💰 Auctions", "📜 Audit Log",
                    "💰 Economy", "🎁 Gift Codes", "🏪 Market"):
            with self.subTest(key=key):
                self.assertNotIn(key, self.es)
        self.assertEqual(self.es["Dashboard"], "Dashboard")
        self.assertEqual(self.es["Market"], "Mercado")

    def test_toasts_have_no_coloured_side_stripe(self):
        for rule in re.findall(r"\.toast[^{}]*\{([^{}]*)\}", self.css):
            self.assertNotRegex(rule, r"border-(left|right)")
        self.assertNotRegex(self.css, r"border-(left|right):\s*[2-9]\d*px")

    def test_reduced_motion_turns_every_animation_and_transition_off(self):
        media = re.search(r"@media \(prefers-reduced-motion: reduce\)\s*\{(.*?)\n\}", self.css, re.S)
        self.assertIsNotNone(media)
        body = media.group(1)
        self.assertRegex(body, r"(?m)^\s*\*,\s*$")
        self.assertIn("animation: none !important", body)
        self.assertIn("transition: none !important", body)

    def test_toast_fade_out_is_a_class_not_an_inline_style(self):
        toast = _function_body(self.js, "showToast")
        self.assertIn("classList.add('is-leaving')", toast)
        self.assertNotIn(".style.", toast)

    def test_new_strings_have_spanish_translations_and_dead_keys_are_gone(self):
        for key in ("Dashboard", "Rankings", "Guilds", "Auctions", "Audit Log", "Economy", "Market", "Panel sections",
                    "Search accounts", "Filter accounts by status", "Sort accounts"):
            with self.subTest(key=key):
                self.assertIn(key, self.es)
        self.assertNotIn("Manage account {name}", self.es)


if __name__ == "__main__":
    unittest.main()
