import os
import re
import unittest

CSS_PATH = os.path.join(os.path.dirname(__file__), "..", "public", "admin.css")


def rule_body(css, selector):
    match = re.search(r"(?m)^" + re.escape(selector) + r"\s*\{([^}]*)\}", css)
    assert match, "rule %s not found" % selector
    return match.group(1)


class TestBarsAlignWithContent(unittest.TestCase):
    """The header and tab bar stay full width, but their content must start and end where the page content does."""

    @classmethod
    def setUpClass(cls):
        with open(CSS_PATH, encoding="utf-8") as f:
            cls.css = f.read()

    def test_content_width_is_one_shared_variable(self):
        self.assertRegex(self.css, r"--content-max:\s*1400px")
        self.assertIn("max-width: var(--content-max)", rule_body(self.css, ".main-content"))

    def test_bars_pad_their_content_into_the_content_box(self):
        inline = re.search(r"--bar-inline:\s*([^;]+);", self.css)
        self.assertIsNotNone(inline, "--bar-inline is not defined")
        self.assertIn("var(--content-max)", inline.group(1))
        self.assertIn("var(--page-gutter)", inline.group(1))
        for selector in (".admin-header", ".subnav-tabs"):
            with self.subTest(selector=selector):
                self.assertIn("padding: 0 var(--bar-inline)", rule_body(self.css, selector))

    def test_content_keeps_the_same_gutter(self):
        self.assertIn("padding: var(--page-gutter)", rule_body(self.css, ".main-content"))


class TestShellFitsNarrowScreens(unittest.TestCase):
    """On a phone the header wraps and the top tab bar scrolls inside itself; the page never scrolls sideways."""

    @classmethod
    def setUpClass(cls):
        with open(CSS_PATH, encoding="utf-8") as f:
            cls.css = f.read()

    def test_the_tab_bar_scrolls_inside_itself(self):
        body = rule_body(self.css, ".subnav-tabs")
        self.assertRegex(body, r"overflow-x:\s*auto")
        self.assertRegex(body, r"overflow-y:\s*hidden")

    def test_tabs_keep_their_size_instead_of_shrinking(self):
        body = rule_body(self.css, ".tab-btn")
        self.assertRegex(body, r"flex-shrink:\s*0")
        self.assertRegex(body, r"white-space:\s*nowrap")

    def test_the_header_wraps_instead_of_overflowing(self):
        body = rule_body(self.css, ".admin-header")
        self.assertRegex(body, r"flex-wrap:\s*wrap")
        self.assertRegex(body, r"min-height:\s*64px")
        self.assertNotRegex(body, r"(?m)^\s*height:\s*64px")

    def test_the_status_area_wraps_and_stays_on_the_right(self):
        body = rule_body(self.css, ".header-status-area")
        self.assertRegex(body, r"flex-wrap:\s*wrap")


if __name__ == "__main__":
    unittest.main()
