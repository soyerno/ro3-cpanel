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

    def test_names_match_the_game_job_data(self):
        # job_id -> job_name of the game's own skill trees (konsor-ro3 data/ro3base/skill_trees.json). The tier
        # decides which id is which: 1300 and 4300 are the transcended second jobs, 1400 and 4400 the third jobs.
        # aethai/ro3emu-server CombatTableRulesTests.cs calls 1400 "Lord Knight" and 4400 "High Priest" in comments,
        # but the same test asserts every resonance job (1400, 4400, 2400) has job rank 5, like the Warlock.
        self.assertEqual(server.career_name(1300), "Lord Knight")
        self.assertEqual(server.career_name(1310), "Paladin")
        self.assertEqual(server.career_name(1400), "Rune Knight")
        self.assertEqual(server.career_name(2400), "Warlock")
        self.assertEqual(server.career_name(4300), "High Priest")
        self.assertEqual(server.career_name(4400), "Arch Bishop")
        self.assertEqual(server.career_name(6100), "Merchant")
        # tests/Ro3Emu.Tests/DungeonTests.Return.cs:534 (const long izlude = 10101)
        self.assertEqual(server.scene_name(10101), "Izlude")

    def test_every_job_of_the_game_data_has_a_name(self):
        game_jobs = (1000, 1100, 1200, 1210, 1300, 1310, 1400, 1410, 2100, 2200, 2300, 2400, 3100, 3200, 3300, 3400,
                     4100, 4200, 4300, 4400, 5100, 5200, 5300, 6100, 6200, 6300, 6400)
        for job in game_jobs:
            with self.subTest(job=job):
                self.assertFalse(server.career_name(job).startswith("Class "), job)

    def test_town_and_field_scenes_follow_the_game_map_data(self):
        # id -> name_en of the game's scene data (konsor-ro3 data/ro3base/maps.json)
        expected = {10100: "Prontera", 10102: "Byalan Island", 10103: "Inn", 10104: "Library", 10201: "Archer Village",
                    10220: "Payon Forest", 10514: "Sograt Desert", 10600: "Alberta", 10610: "Sunken Ship",
                    10700: "Glast Heim the Ancient City", 30399: "Producer's Lair", 101: "Garden of Time"}
        for scene, name in expected.items():
            with self.subTest(scene=scene):
                self.assertEqual(server.scene_name(scene), name)

    def test_guessed_scene_names_the_game_data_contradicts_are_gone(self):
        # These were unverified guesses (Prontera West, Morroc Field, Al De Baran...). The ids are other maps or none.
        for scene in (10301, 10400, 10401, 10800):
            with self.subTest(scene=scene):
                self.assertEqual(server.scene_name(scene), "Map %d" % scene)

    def test_the_whole_map_list_is_there(self):
        towns = [s for s in server.SCENE_MAP if s < 1000000]
        self.assertGreaterEqual(len(towns), 72)

    def test_unknown_career_falls_back(self):
        self.assertEqual(server.career_name(987654), "Class 987654")

    def test_unknown_scene_falls_back(self):
        self.assertEqual(server.scene_name(0), "Map 0")
        self.assertEqual(server.scene_name(424242), "Map 424242")

    def test_non_integer_id_falls_back_without_raising(self):
        self.assertEqual(server.career_name(None), "Class None")
        self.assertEqual(server.scene_name("abc"), "Map abc")

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
