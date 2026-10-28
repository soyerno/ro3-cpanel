import contextlib
import io
import json
import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
import server


class TestNameLookups(unittest.TestCase):
    def test_known_career_resolves_to_name(self):
        self.assertEqual(server.career_name(1100), "Swordman")
        self.assertEqual(server.career_name(1000), "Novice")

    def test_known_scene_resolves_to_name(self):
        self.assertEqual(server.scene_name(10100), "Prontera")

    def test_upstream_dungeon_scene_resolves_to_name(self):
        # docs/systems/dungeon-inventory.md in aethai/ro3emu-server
        self.assertEqual(server.scene_name(1022001), "Payon Forest")
        self.assertEqual(server.scene_name(1010101), "Izlude")

    def test_names_match_upstream_tests(self):
        # aethai/ro3emu-server tests/Ro3Emu.Tests/CombatTableRulesTests.cs:36-43
        self.assertEqual(server.career_name(1400), "Lord Knight")
        self.assertEqual(server.career_name(4400), "High Priest")
        self.assertEqual(server.career_name(2400), "Warlock")
        # tests/Ro3Emu.Tests/DungeonTests.Return.cs:534 (const long izlude = 10101)
        self.assertEqual(server.scene_name(10101), "Izlude")

    def test_ids_whose_name_upstream_gives_to_another_id_fall_back(self):
        self.assertEqual(server.career_name(1300), "Clase 1300")
        self.assertEqual(server.career_name(4300), "Clase 4300")
        self.assertEqual(server.scene_name(10600), "Mapa 10600")

    def test_unknown_career_falls_back(self):
        self.assertEqual(server.career_name(987654), "Clase 987654")

    def test_unknown_scene_falls_back(self):
        self.assertEqual(server.scene_name(0), "Mapa 0")
        self.assertEqual(server.scene_name(424242), "Mapa 424242")

    def test_non_integer_id_falls_back_without_raising(self):
        self.assertEqual(server.career_name(None), "Clase None")
        self.assertEqual(server.scene_name("abc"), "Mapa abc")

    def test_numeric_string_id_resolves(self):
        self.assertEqual(server.career_name("1100"), "Swordman")


class TestNamesFile(unittest.TestCase):
    def setUp(self):
        # Register restoration before any mutation of the module-level maps.
        saved_careers = dict(server.CAREER_MAP)
        saved_scenes = dict(server.SCENE_MAP)
        self.addCleanup(self._restore, server.CAREER_MAP, saved_careers)
        self.addCleanup(self._restore, server.SCENE_MAP, saved_scenes)
        tmp = tempfile.TemporaryDirectory(ignore_cleanup_errors=True)
        self.addCleanup(tmp.cleanup)
        self.tmp_dir = tmp.name

    @staticmethod
    def _restore(target, saved):
        target.clear()
        target.update(saved)

    def _write(self, name, content):
        path = os.path.join(self.tmp_dir, name)
        with open(path, "w", encoding="utf-8") as f:
            f.write(content)
        return path

    def _apply(self, path):
        err = io.StringIO()
        with contextlib.redirect_stderr(err), contextlib.redirect_stdout(io.StringIO()):
            server.apply_names_file(path)
        return err.getvalue()

    def test_names_file_overrides_and_extends(self):
        path = self._write("names.json", json.dumps({
            "careers": {"1100": "Espadachin", "9001": "Custom Class"},
            "scenes": {"10100": "Capital", "424242": "Custom Map"},
        }))
        self._apply(path)
        self.assertEqual(server.career_name(1100), "Espadachin")
        self.assertEqual(server.career_name(9001), "Custom Class")
        self.assertEqual(server.scene_name(10100), "Capital")
        self.assertEqual(server.scene_name(424242), "Custom Map")
        # Untouched defaults stay.
        self.assertEqual(server.career_name(1000), "Novice")
        self.assertEqual(server.scene_name(10200), "Payon")

    def test_malformed_file_keeps_defaults_and_warns(self):
        path = self._write("broken.json", "{not json")
        before_c, before_s = dict(server.CAREER_MAP), dict(server.SCENE_MAP)
        err = self._apply(path)
        self.assertEqual(server.CAREER_MAP, before_c)
        self.assertEqual(server.SCENE_MAP, before_s)
        self.assertIn("names_file", err)

    def test_missing_file_keeps_defaults_and_warns(self):
        before_c, before_s = dict(server.CAREER_MAP), dict(server.SCENE_MAP)
        err = self._apply(os.path.join(self.tmp_dir, "does-not-exist.json"))
        self.assertEqual(server.CAREER_MAP, before_c)
        self.assertEqual(server.SCENE_MAP, before_s)
        self.assertIn("names_file", err)

    def test_non_object_root_keeps_defaults(self):
        path = self._write("list.json", json.dumps(["careers"]))
        before_c = dict(server.CAREER_MAP)
        err = self._apply(path)
        self.assertEqual(server.CAREER_MAP, before_c)
        self.assertIn("names_file", err)

    def test_non_integer_keys_are_skipped(self):
        path = self._write("keys.json", json.dumps({
            "careers": {"abc": "Bad", "12.5": "Bad", "": "Bad", "1100": "Good"},
            "scenes": {"x1": "Bad", "77777": "Good Map"},
        }))
        self._apply(path)
        self.assertEqual(server.career_name(1100), "Good")
        self.assertEqual(server.scene_name(77777), "Good Map")
        self.assertTrue(all(isinstance(k, int) for k in server.CAREER_MAP))
        self.assertTrue(all(isinstance(k, int) for k in server.SCENE_MAP))
        self.assertNotIn("Bad", server.CAREER_MAP.values())
        self.assertNotIn("Bad", server.SCENE_MAP.values())

    def test_non_string_or_empty_names_are_skipped(self):
        path = self._write("values.json", json.dumps({
            "careers": {"1100": 5, "1000": "  ", "9002": "Ok"},
            "scenes": "not an object",
        }))
        before_s = dict(server.SCENE_MAP)
        self._apply(path)
        self.assertEqual(server.career_name(1100), "Swordman")
        self.assertEqual(server.career_name(1000), "Novice")
        self.assertEqual(server.career_name(9002), "Ok")
        self.assertEqual(server.SCENE_MAP, before_s)

    def test_empty_or_unset_path_is_disabled(self):
        before_c, before_s = dict(server.CAREER_MAP), dict(server.SCENE_MAP)
        for value in ("", "   ", None):
            err = self._apply(value)
            self.assertEqual(err, "")
        self.assertEqual(server.CAREER_MAP, before_c)
        self.assertEqual(server.SCENE_MAP, before_s)


if __name__ == "__main__":
    unittest.main()
