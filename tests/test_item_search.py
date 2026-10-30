"""Item search for the gift code reward rows: GET /api/admin/items?q=<text>&limit=<n>.

It searches the merged item sources (catalog rows plus 'item_names_file' names, which win) by id or name and
returns {"items": [{"entry", "name", "icon", "quality"}]}, best matches first.
"""

import json
import os
import sys
import unittest
import urllib.parse

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import server  # noqa: E402
import test_vault_market as tvm  # noqa: E402

CATALOG = [
    {"id": 5001, "n": "Red Potion", "ic": "item_5001.png", "q": "Common"},
    {"id": 5002, "n": "Blue Gem", "ic": "gem_blue.webp", "q": "Mythic"},
    {"id": 501, "n": "Potion Bag", "ic": "bag.png", "q": "Rare"},
    {"id": 6001, "n": "Sword of Potions", "ic": "sword.png", "q": "Legendary"},
    {"id": 7001, "n": "Apple", "ic": "", "q": ""},
]


class ItemSearchCase(tvm.VaultMarketTestCase):
    """The names file from VaultMarketTestCase has 5001 Red Potion, 5002 Blue Gem and 5003 'Poción 100%'."""

    catalog = CATALOG

    def setUp(self):
        super().setUp()
        self._catalog_saved = dict(server.ITEM_CATALOG_STATE)
        self.addCleanup(self._restore_catalog)
        server.ITEM_CATALOG_STATE.update({"key": None, "catalog": None, "warned": set()})
        if self.catalog is None:
            server.CONFIG.pop("item_catalog_file", None)
        else:
            path = os.path.join(self.tmp.name, "catalog.json")
            with open(path, "w", encoding="utf-8") as fh:
                json.dump(self.catalog, fh)
            server.CONFIG["item_catalog_file"] = path

    def _restore_catalog(self):
        server.ITEM_CATALOG_STATE.clear()
        server.ITEM_CATALOG_STATE.update(self._catalog_saved)

    def search(self, q=None, limit=None, token=None):
        params = {}
        if q is not None:
            params["q"] = q
        if limit is not None:
            params["limit"] = limit
        status, body = self.call("/api/admin/items?" + urllib.parse.urlencode(params), token=token)
        return status, body

    def entries(self, q, limit=None):
        status, body = self.search(q, limit)
        self.assertEqual(status, 200, body)
        return [item["entry"] for item in body["items"]]


class TestItemSearch(ItemSearchCase):
    def test_requires_an_admin_session(self):
        status, _ = self.search("potion", token=False)
        self.assertEqual(status, 401)

    def test_a_row_has_entry_name_icon_and_quality(self):
        _, body = self.search("blue gem")
        self.assertEqual(body["items"], [{"entry": 5002, "name": "Blue Gem", "icon": "gem_blue.webp", "quality": "mythic"}])

    def test_name_search_is_case_insensitive_and_ranks_prefix_before_substring(self):
        # "Potion Bag" starts with the text; the others only contain it (ties ordered by name).
        self.assertEqual(self.entries("POTION"), [501, 5001, 6001])

    def test_names_file_items_without_a_catalog_row_are_found_with_null_icon(self):
        _, body = self.search("poción")
        self.assertEqual(body["items"], [{"entry": 5003, "name": "Poción 100%", "icon": None, "quality": None}])

    def test_numeric_query_finds_the_exact_id_first_then_id_prefixes_by_name(self):
        self.assertEqual(self.entries("501"), [501])
        self.assertEqual(self.entries("5001"), [5001])
        # Blue Gem, Poción 100%, Potion Bag, Red Potion
        self.assertEqual(self.entries("50"), [5002, 5003, 501, 5001])

    def test_a_single_digit_is_enough_for_an_id_search(self):
        self.assertEqual(self.entries("7"), [7001])

    def test_text_shorter_than_two_characters_returns_nothing(self):
        self.assertEqual(self.entries("a"), [])
        self.assertEqual(self.entries(" "), [])
        self.assertEqual(self.entries(""), [])
        _, body = self.search()
        self.assertEqual(body, {"items": []})

    def test_query_is_trimmed(self):
        self.assertEqual(self.entries("  apple  "), [7001])

    def test_unknown_numeric_id_is_an_empty_list(self):
        self.assertEqual(self.entries("999999"), [])

    def test_limit_defaults_to_twenty_and_is_clamped_between_one_and_fifty(self):
        self.assertEqual(self.entries("potion", limit=1), [501])
        self.assertEqual(self.entries("potion", limit=0), [501])
        self.assertEqual(self.entries("potion", limit=-5), [501])
        self.assertEqual(len(self.entries("potion", limit="junk")), 3)

    def test_limit_caps_large_result_sets(self):
        many = [{"id": 10000 + i, "n": "Card %03d" % i} for i in range(80)]
        path = os.path.join(self.tmp.name, "big.json")
        with open(path, "w", encoding="utf-8") as fh:
            json.dump(many, fh)
        server.CONFIG["item_catalog_file"] = path
        self.assertEqual(len(self.entries("card")), 20)
        self.assertEqual(len(self.entries("card", limit=500)), 50)
        self.assertEqual(self.entries("card", limit=3), [10000, 10001, 10002])

    def test_names_file_name_wins_over_the_catalog_name(self):
        _, body = self.search("5001")
        self.assertEqual(body["items"][0]["name"], "Red Potion")


class TestItemSearchWithoutSources(ItemSearchCase):
    catalog = None

    def test_without_a_catalog_or_names_it_is_an_empty_list_not_an_error(self):
        server.CONFIG["item_names_file"] = ""
        server.ITEM_NAMES_STATE.update({"key": None, "names": None, "warned": set()})
        status, body = self.search("potion")
        self.assertEqual((status, body), (200, {"items": []}))


class TestSearchItemsFunction(unittest.TestCase):
    """The ranking itself, without HTTP."""

    def test_ranking_and_tie_break(self):
        names = {"20": "Zeta Dagger", "2": "Dagger", "200": "Dagger", "12": "Dagger Plus", "3": "Old Dagger"}
        result = server.search_items("dagger", 10, names=names, catalog={})
        self.assertEqual([r["entry"] for r in result], [2, 200, 12, 3, 20])

    def test_exact_id_comes_first_even_if_another_name_starts_with_the_digits(self):
        names = {"42": "Zed", "4200": "Bow", "9": "42 Arrows"}
        result = server.search_items("42", 10, names=names, catalog={})
        self.assertEqual([r["entry"] for r in result], [42, 9, 4200])


if __name__ == "__main__":
    unittest.main()
