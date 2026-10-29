import ast
import json
import os
import re
import sys
import threading
import unittest
import urllib.error
import urllib.request
from http.server import ThreadingHTTPServer
from unittest import mock

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
import server

SERVER_PY = os.path.join(os.path.dirname(server.__file__), "server.py")
SPANISH_MARKS = re.compile("[áéíóúñ¿¡ÁÉÍÓÚÑ]")
PLACEHOLDER = re.compile(r"\{(\w+)\}")


class TestTranslate(unittest.TestCase):
    def tearDown(self):
        server.set_language(None)

    def test_english_is_the_default(self):
        with mock.patch.dict(server.CONFIG, {"default_language": "en"}):
            server.set_language(None)
            self.assertEqual(server.tr("Account not found"), "Account not found")

    def test_spanish_translation_with_params(self):
        server.set_language("es")
        self.assertEqual(server.tr("Account '{username}' does not exist", username="bob"), "La cuenta 'bob' no existe")

    def test_english_params_are_interpolated(self):
        server.set_language("en")
        self.assertEqual(server.tr("Account '{username}' does not exist", username="bob"), "Account 'bob' does not exist")

    def test_unknown_key_falls_back_to_english(self):
        server.set_language("es")
        self.assertEqual(server.tr("Not in the dictionary {x}", x=1), "Not in the dictionary 1")

    def test_normalize_language(self):
        self.assertEqual(server.normalize_language("es"), "es")
        self.assertEqual(server.normalize_language("EN"), "en")
        self.assertEqual(server.normalize_language("fr"), "en")
        self.assertEqual(server.normalize_language(None), "en")

    def test_name_fallbacks_follow_the_language(self):
        server.set_language("en")
        self.assertEqual(server.career_name(987654), "Class 987654")
        self.assertEqual(server.scene_name(987654), "Map 987654")
        server.set_language("es")
        self.assertEqual(server.career_name(987654), "Clase 987654")
        self.assertEqual(server.scene_name(987654), "Mapa 987654")


class TestApiLanguage(unittest.TestCase):
    def setUp(self):
        patcher = mock.patch.object(server.CPanelRequestHandler, "log_message", lambda *a, **k: None)
        patcher.start()
        self.addCleanup(patcher.stop)
        conf = mock.patch.dict(server.CONFIG, {"default_language": "en"})
        conf.start()
        self.addCleanup(conf.stop)
        self.httpd = ThreadingHTTPServer(("127.0.0.1", 0), server.CPanelRequestHandler)
        threading.Thread(target=self.httpd.serve_forever, daemon=True).start()
        self.addCleanup(self.httpd.server_close)
        self.addCleanup(self.httpd.shutdown)
        self.base = "http://127.0.0.1:%d" % self.httpd.server_address[1]

    def request(self, path, method="GET", lang=None, body=None):
        headers = {"Content-Type": "application/json"}
        if lang is not None:
            headers["X-Panel-Lang"] = lang
        data = json.dumps(body).encode() if body is not None else None
        req = urllib.request.Request(self.base + path, data=data, method=method, headers=headers)
        try:
            with urllib.request.urlopen(req, timeout=10) as resp:
                return resp.status, json.loads(resp.read().decode("utf-8")), resp.headers
        except urllib.error.HTTPError as e:
            return e.code, json.loads(e.read().decode("utf-8")), e.headers

    def test_public_config_exposes_default_language(self):
        status, body, _ = self.request("/api/admin/config")
        self.assertEqual(status, 200)
        self.assertEqual(body["default_language"], "en")

    def test_public_config_normalizes_an_invalid_default_language(self):
        with mock.patch.dict(server.CONFIG, {"default_language": "fr"}):
            _, body, _ = self.request("/api/admin/config")
        self.assertEqual(body["default_language"], "en")

    def test_error_is_english_without_header(self):
        status, body, _ = self.request("/api/admin/login", "POST", body={"username": "", "password": ""})
        self.assertEqual(status, 400)
        self.assertEqual(body["error"], "Enter a username and password")

    def test_error_is_spanish_with_header(self):
        status, body, _ = self.request("/api/admin/login", "POST", lang="es", body={"username": "", "password": ""})
        self.assertEqual(status, 400)
        self.assertEqual(body["error"], "Debe ingresar usuario y contraseña")

    def test_unauthorized_follows_the_header(self):
        _, en, _ = self.request("/api/admin/stats", lang="en")
        _, es, _ = self.request("/api/admin/stats", lang="es")
        self.assertEqual(en["error"], "Unauthorized. Sign in as an administrator.")
        self.assertEqual(es["error"], "No autorizado. Inicie sesión como administrador.")

    def test_configured_default_applies_when_header_missing_or_invalid(self):
        with mock.patch.dict(server.CONFIG, {"default_language": "es"}):
            _, none_hdr, _ = self.request("/api/admin/stats")
            _, bad_hdr, _ = self.request("/api/admin/stats", lang="xx")
        self.assertEqual(none_hdr["error"], "No autorizado. Inicie sesión como administrador.")
        self.assertEqual(bad_hdr["error"], "No autorizado. Inicie sesión como administrador.")

    def test_language_does_not_leak_between_requests(self):
        self.request("/api/admin/stats", lang="es")
        _, body, _ = self.request("/api/admin/stats")
        self.assertEqual(body["error"], "Unauthorized. Sign in as an administrator.")

    def test_spanish_dictionary_is_served_without_cache(self):
        req = urllib.request.Request(self.base + "/locales/es.json")
        with urllib.request.urlopen(req, timeout=10) as resp:
            self.assertEqual(resp.status, 200)
            self.assertEqual(resp.headers.get("Cache-Control"), "no-cache")
            self.assertIn("application/json", resp.headers.get("Content-Type"))
            self.assertIsInstance(json.loads(resp.read().decode("utf-8")), dict)


class TestDictionaryCompleteness(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        with open(SERVER_PY, encoding="utf-8") as f:
            cls.tree = ast.parse(f.read())

    def tr_keys(self):
        keys = set()
        for node in ast.walk(self.tree):
            if (
                isinstance(node, ast.Call)
                and isinstance(node.func, ast.Name)
                and node.func.id == "tr"
                and node.args
                and isinstance(node.args[0], ast.Constant)
                and isinstance(node.args[0].value, str)
            ):
                keys.add(node.args[0].value)
        return keys

    def test_every_tr_key_has_a_spanish_translation(self):
        missing = sorted(k for k in self.tr_keys() if k not in server.ES_MESSAGES)
        self.assertEqual(missing, [])

    def test_dynamic_labels_and_audit_details_are_translated(self):
        labels = list(server.PACK_NAMES.values()) + list(server.ECONOMY_OWNER_KIND_LABELS.values())
        labels += list(server.ECONOMY_ASSET_KIND_LABELS.values())
        stored = [
            "Invalid credentials", "Administrative sign-in", "Account created by admin",
            "Password changed by admin", "Suspension lifted by admin", "Account deleted by admin",
            "Rule violation / Admin action",
        ]
        self.assertEqual(sorted(k for k in labels + stored if k not in server.ES_MESSAGES), [])

    def test_audit_details_translate_on_read(self):
        server.set_language("es")
        self.addCleanup(server.set_language, None)
        self.assertEqual(server.localize_audit_details("Reason: spam"), "Motivo: spam")
        self.assertEqual(server.localize_audit_details("Retry in 30s"), "Reintentar en 30s")
        self.assertEqual(server.localize_audit_details("!warp 1 -> sent (done)"), "!warp 1 -> enviado (done)")
        self.assertEqual(server.localize_audit_details("Account created by admin"), "Cuenta creada por admin")
        self.assertEqual(server.localize_audit_details("unknown text"), "unknown text")
        server.set_language("en")
        self.assertEqual(server.localize_audit_details("Reason: spam"), "Reason: spam")

    def test_translations_keep_their_placeholders(self):
        for key, value in server.ES_MESSAGES.items():
            with self.subTest(key=key):
                self.assertTrue(value.strip())
                self.assertEqual(set(PLACEHOLDER.findall(key)), set(PLACEHOLDER.findall(value)))

    def test_no_untranslated_spanish_literals_remain(self):
        dict_nodes = set()
        for node in ast.walk(self.tree):
            if isinstance(node, ast.Assign) and any(
                isinstance(t, ast.Name) and t.id == "ES_MESSAGES" for t in node.targets
            ):
                dict_nodes = {id(n) for n in ast.walk(node)}
        docstrings = set()
        for node in ast.walk(self.tree):
            if isinstance(node, (ast.Module, ast.FunctionDef, ast.ClassDef)) and node.body:
                first = node.body[0]
                if isinstance(first, ast.Expr) and isinstance(first.value, ast.Constant):
                    docstrings.add(id(first.value))
        leftovers = [
            (n.lineno, n.value)
            for n in ast.walk(self.tree)
            if isinstance(n, ast.Constant)
            and isinstance(n.value, str)
            and id(n) not in dict_nodes
            and id(n) not in docstrings
            and SPANISH_MARKS.search(n.value)
        ]
        self.assertEqual(leftovers, [])


if __name__ == "__main__":
    unittest.main()
