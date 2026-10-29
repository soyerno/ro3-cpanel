import json
import os
import re
import unittest

PUBLIC = os.path.join(os.path.dirname(__file__), "..", "public")


def read(*parts):
    with open(os.path.join(PUBLIC, *parts), encoding="utf-8") as f:
        return f.read()


class TestAuditLogPagerUi(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.html = read("index.html")
        cls.js = read("admin.js")
        cls.es = json.loads(read("locales", "es.json"))

    def audit_section(self):
        match = re.search(r'<section id="tab-view-audit".*?</section>', self.html, re.S)
        self.assertIsNotNone(match)
        return match.group(0)

    def test_audit_tab_has_an_accessible_pager(self):
        section = self.audit_section()
        for element_id in ("audit-pager", "audit-pager-prev", "audit-pager-info", "audit-pager-next"):
            with self.subTest(element_id=element_id):
                self.assertIn('id="%s"' % element_id, section)
        self.assertIn('data-i18n-aria-label="Audit log pagination"', section)
        self.assertIn("Audit log pagination", self.es)

    def test_loader_requests_the_current_page_and_renders_the_pager(self):
        self.assertRegex(self.js, r"/api/admin/audit-log\?")
        self.assertIn("state.auditPage", self.js)
        self.assertRegex(
            self.js,
            r"renderPager\(els\.auditPager, els\.auditPagerInfo, els\.auditPagerPrev, els\.auditPagerNext,\s*"
            r"state\.auditPage, state\.auditPages, state\.auditTotal, 'records'\)",
        )

    def test_prev_and_next_move_one_page_within_bounds(self):
        self.assertRegex(self.js, r"function goToAuditPage\(page\)")
        self.assertIn("goToAuditPage(state.auditPage - 1)", self.js)
        self.assertIn("goToAuditPage(state.auditPage + 1)", self.js)
        self.assertRegex(self.js, r"page > state\.auditPages")

    def test_entering_the_tab_starts_on_the_first_page_but_a_language_reload_keeps_the_page(self):
        match = re.search(r"function switchTab\(tabId\) \{(.*?)\n  \}\n", self.js, re.S)
        self.assertIsNotNone(match)
        body = match.group(1)
        self.assertRegex(body, r"var previousTab = state\.activeTab;\s*state\.activeTab = tabId;")
        self.assertRegex(body, r"previousTab !== 'audit'\)\s*state\.auditPage = 1")

    def test_page_past_the_end_falls_back_to_the_last_page(self):
        self.assertRegex(self.js, r"state\.auditPage = state\.auditPages;\s*return loadAuditLog\(\)")


if __name__ == "__main__":
    unittest.main()
