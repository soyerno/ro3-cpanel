"""Each panel tab has its own URL: switching tabs writes <base><slug> to the address bar, back/forward switch tabs, and
window.CPANEL_ROUTES lets an overlay add routes (aliases, preferred slugs, an onShow hook).

Static checks over public/admin.js and public/index.html, plus the pure path helpers run under Node when available.
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

SLUGS = ("dashboard", "accounts", "rankings", "guilds", "economy", "auctions", "giftcodes", "market", "audit",
         "mercado")


class TabRouteScriptTest(unittest.TestCase):
    def setUp(self):
        self.js = read("public", "admin.js")

    def test_switch_tab_writes_the_tab_url(self):
        body = function_body(self.js, "switchTab")
        self.assertIn("writeTabUrl(", body)
        writer = function_body(self.js, "writeTabUrl")
        self.assertIn("history.pushState(", writer)
        self.assertIn("history.replaceState(", writer)

    def test_only_the_accounts_tab_keeps_the_account_hash(self):
        body = function_body(self.js, "tabUrl")
        self.assertIn("tabId === 'accounts'", body)
        self.assertIn("loc.hash", body)

    def test_back_and_forward_switch_tabs_without_pushing(self):
        self.assertRegex(self.js, r"addEventListener\('popstate', handleTabPopState\)")
        body = function_body(self.js, "handleTabPopState")
        self.assertIn("switchTab(tab, { history: 'replace' })", body)

    def test_login_opens_the_tab_named_by_the_url(self):
        body = function_body(self.js, "setAuthenticated")
        self.assertIn("history: 'replace'", body)
        self.assertIn("tabFromLocation()", body)

    def test_routes_hook_is_exposed_for_overlays(self):
        self.assertIn("globalThis.CPANEL_ROUTES = {", self.js)
        for name in ("registerRoute", "setPreferredSlug", "setBase", "tabForSlug", "slugForTab", "base", "refresh"):
            with self.subTest(name=name):
                self.assertRegex(self.js, r"\n    %s: " % name)

    def test_switch_tab_hides_overlay_views_and_runs_on_show_hooks(self):
        body = function_body(self.js, "switchTab")
        self.assertIn("syncExtraTabViews(tabId)", body)
        self.assertIn("runRouteShowHooks(tabId)", body)


class TabRouteCspTest(unittest.TestCase):
    def test_index_has_no_inline_handlers_or_styles(self):
        html = read("public", "index.html")
        self.assertIsNone(re.search(r"\son[a-z]+\s*=", html))
        self.assertIsNone(re.search(r"\sstyle\s*=", html))

    def test_assets_load_relative_to_the_panel_base_and_fetches_are_absolute(self):
        html = read("public", "index.html")
        self.assertIn('<script src="admin.js"></script>', html)
        self.assertIn('href="admin.css"', html)
        js = read("public", "admin.js")
        self.assertIn("var LOCALE_URL = '/locales/es.json';", js)


@unittest.skipUnless(shutil.which("node"), "node is not installed")
class TabRoutePathHelpersTest(unittest.TestCase):
    """detectRouteBase / routeSlugFromPath are pure: run them under Node with a fixed slug list."""

    def run_helpers(self, calls):
        js = read("public", "admin.js")
        source = "\n".join(function_body(js, name) for name in ("decodeRouteSegment", "detectRouteBase", "routeSlugFromPath"))
        script = source + """
var slugs = %s;
function isSlug(s) { return slugs.indexOf(String(s).toLowerCase()) !== -1; }
var calls = %s;
process.stdout.write(JSON.stringify(calls.map(function (c) {
  return c[0] === 'base' ? detectRouteBase(c[1], isSlug) : routeSlugFromPath(c[1], c[2]);
})));
""" % (json.dumps(SLUGS), json.dumps(calls))
        out = subprocess.run(["node", "-e", script], capture_output=True, text=True, encoding="utf-8", timeout=30, check=True)
        return json.loads(out.stdout)

    def test_base_is_the_prefix_before_a_known_slug(self):
        cases = [
            ("/", "/"), ("/market", "/"), ("/accounts", "/"),
            ("/admin/", "/admin/"), ("/admin/market", "/admin/"), ("/admin/market/", "/admin/"),
            ("/admin/mercado", "/admin/"), ("/admin/index.html", "/admin/"), ("/admin/unknown", "/admin/"),
            ("/index.html", "/"), ("/admin", "/"),
        ]
        got = self.run_helpers([["base", path] for path, _ in cases])
        self.assertEqual(got, [want for _, want in cases])

    def test_slug_is_the_single_segment_after_the_base(self):
        cases = [
            ("/admin/market", "/admin/", "market"), ("/admin/market/", "/admin/", "market"),
            ("/market", "/", "market"), ("/admin/", "/admin/", ""), ("/admin", "/admin/", ""),
            ("/admin/a/b", "/admin/", None), ("/other/market", "/admin/", None),
            ("/admin/Auditor%C3%ADa", "/admin/", "Auditoría"),
        ]
        got = self.run_helpers([["slug", path, base] for path, base, _ in cases])
        self.assertEqual(got, [want for _, _, want in cases])


if __name__ == "__main__":
    unittest.main()
