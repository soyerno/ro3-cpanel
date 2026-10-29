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


if __name__ == "__main__":
    unittest.main()
