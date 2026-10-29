"""Client-side i18n: English is the key and the default text, Spanish lives in public/locales/es.json.

These are static checks over public/index.html, public/admin.js and public/locales/es.json.
"""

import html as html_lib
import json
import os
import re
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PUBLIC = os.path.join(ROOT, "public")

PLACEHOLDER_RE = re.compile(r"\{(\w+)\}")
# Spanish-only characters: accented vowels, enye, dieresis and inverted marks.
SPANISH_CHARS_RE = re.compile("[áéíóúñüÁÉÍÓÚÑÜ¿¡]")

# Files whose default text must be English. Nothing needs an exception today; if one is ever
# unavoidable, add "<file>": ["literal"] here with a comment explaining why.
SPANISH_ALLOWLIST = {}

# data-i18n, data-i18n-placeholder, data-i18n-title, data-i18n-aria-label (any quote style).
DATA_I18N_RE = re.compile(r"""data-i18n(?:-[a-z-]+)?=(?:"([^"]*)"|'([^']*)')""")
# t('...') / t("...") with simple escapes; \b keeps it from matching split( / format( / etc.
T_CALL_RE = re.compile(r"""(?<![\w.$])t\(\s*(?:'((?:[^'\\\n]|\\.)*)'|"((?:[^"\\\n]|\\.)*)")""")
# Any t( call whose first argument is not a string literal (dynamic keys cannot be verified).
T_DYNAMIC_RE = re.compile(r"""(?<![\w.$])(?<!function )t\(\s*(?!['"\s])""")


def _read(*parts):
    with open(os.path.join(PUBLIC, *parts), encoding="utf-8") as f:
        return f.read()


def _unescape_js(raw):
    simple = {"n": "\n", "t": "\t", "r": "\r", "'": "'", '"': '"', "\\": "\\"}

    def repl(match):
        ch = match.group(1)
        if ch in simple:
            return simple[ch]
        if ch.startswith("u") and len(ch) == 5:
            return chr(int(ch[1:], 16))
        return ch

    return re.sub(r"\\(u[0-9a-fA-F]{4}|.)", repl, raw)


def _t_keys(js):
    keys = set()
    for match in T_CALL_RE.finditer(js):
        raw = match.group(1) if match.group(1) is not None else match.group(2)
        keys.add(_unescape_js(raw))
    return keys


def _data_i18n_values(text, unescape_html=False):
    values = set()
    for match in DATA_I18N_RE.finditer(text):
        raw = match.group(1) if match.group(1) is not None else match.group(2)
        values.add(html_lib.unescape(raw) if unescape_html else raw)
    return values


class TestLocaleFile(unittest.TestCase):
    def setUp(self):
        with open(os.path.join(PUBLIC, "locales", "es.json"), encoding="utf-8") as f:
            self.es = json.load(f)

    def test_es_json_is_flat_object_of_nonempty_strings(self):
        self.assertIsInstance(self.es, dict)
        self.assertGreater(len(self.es), 0)
        for key, value in self.es.items():
            with self.subTest(key=key):
                self.assertIsInstance(key, str)
                self.assertTrue(key.strip(), "empty key")
                self.assertIsInstance(value, str)
                self.assertTrue(value.strip(), "empty translation")

    def test_placeholders_match_between_key_and_value(self):
        for key, value in self.es.items():
            with self.subTest(key=key):
                self.assertEqual(sorted(PLACEHOLDER_RE.findall(key)), sorted(PLACEHOLDER_RE.findall(value)))

    def test_every_t_key_in_admin_js_exists_in_es_json(self):
        keys = _t_keys(_read("admin.js"))
        self.assertGreater(len(keys), 50, "expected admin.js to use t() for its dynamic strings")
        missing = sorted(k for k in keys if k not in self.es)
        self.assertEqual(missing, [])

    def test_admin_js_has_no_dynamic_t_keys(self):
        # applyI18n() is the only place that legitimately translates a key read from the DOM.
        lines = [line for line in _read("admin.js").splitlines() if "getAttribute(" not in line]
        self.assertEqual(T_DYNAMIC_RE.findall("\n".join(lines)), [])

    def test_every_es_json_key_is_used(self):
        used = _t_keys(_read("admin.js")) | _data_i18n_values(_read("admin.js"))
        used |= _data_i18n_values(_read("index.html"), unescape_html=True)
        self.assertEqual(sorted(k for k in self.es if k not in used), [])

    def test_data_i18n_values_built_by_admin_js_exist_in_es_json(self):
        values = _data_i18n_values(_read("admin.js"))
        missing = sorted(v for v in values if v not in self.es)
        self.assertEqual(missing, [])

    def test_every_data_i18n_value_in_index_html_exists_in_es_json(self):
        values = _data_i18n_values(_read("index.html"), unescape_html=True)
        self.assertGreater(len(values), 50, "expected index.html to be annotated with data-i18n*")
        missing = sorted(v for v in values if v not in self.es)
        self.assertEqual(missing, [])


class TestDefaultTextIsEnglish(unittest.TestCase):
    def _assert_no_spanish(self, filename):
        text = _read(filename)
        allowed = SPANISH_ALLOWLIST.get(filename, [])
        offenders = []
        for lineno, line in enumerate(text.splitlines(), 1):
            if SPANISH_CHARS_RE.search(line) and not any(a in line for a in allowed):
                offenders.append("%s:%d: %s" % (filename, lineno, line.strip()[:100]))
        self.assertEqual(offenders, [])

    def test_index_html_has_no_spanish_default_text(self):
        self._assert_no_spanish("index.html")

    def test_admin_js_has_no_spanish_default_text(self):
        self._assert_no_spanish("admin.js")


class TestIndexMarkup(unittest.TestCase):
    def setUp(self):
        self.html = _read("index.html")

    def test_html_lang_is_english(self):
        self.assertRegex(self.html, r"<html[^>]*\blang=\"en\"")

    def test_language_selector_present_on_login_and_in_app(self):
        for element_id in ("lang-switch-login", "lang-switch-app"):
            with self.subTest(element_id=element_id):
                self.assertIn('id="%s"' % element_id, self.html)
        self.assertEqual(self.html.count('data-lang="en"'), 2)
        self.assertEqual(self.html.count('data-lang="es"'), 2)


class TestRuntimeContract(unittest.TestCase):
    def setUp(self):
        self.js = _read("admin.js")

    def test_runtime_pieces_exist(self):
        for needle in (
            "function t(",
            "function applyI18n(",
            "panel_lang",
            "default_language",
            "/locales/es.json",
            "X-Panel-Lang",
        ):
            with self.subTest(needle=needle):
                self.assertIn(needle, self.js)

    def test_panel_lang_header_is_set_in_api_helper(self):
        helper = re.search(r"function apiFetch\(.*?\n  \}\n", self.js, re.S)
        self.assertIsNotNone(helper)
        self.assertIn("X-Panel-Lang", helper.group(0))

    def test_no_console_calls(self):
        self.assertNotRegex(self.js, r"\bconsole\.(log|error|warn)\b")


if __name__ == "__main__":
    unittest.main()
