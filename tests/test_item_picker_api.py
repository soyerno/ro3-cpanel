"""Item picker backend: GET /api/admin/items/search, gift-code reward validation and the market 'entry' filter.

All three read the same item list (the catalog and the names file, see server.load_item_names).
"""

import json
import os
import sys
import unittest
import urllib.parse
from contextlib import closing

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import server  # noqa: E402
import test_gift_codes as tgc  # noqa: E402
import test_vault_market as tvm  # noqa: E402

CATALOG = [
    {"id": 1, "n": "Zeta Stone", "ic": "zeta.png", "q": "Rare"},
    {"id": 12, "n": "Apple Sword", "ic": "item_12.png", "q": "Common"},
    {"id": 123, "n": "Sword of Fire", "ic": "item_123.png", "q": "Legendary"},
    {"id": 5001, "n": "Red Potion", "ic": "item_5001.png", "q": "Common"},
    {"id": 5120, "n": "Misc"},
    {"id": 6001, "n": "Potion Pack"},
    {"id": 9001, "n": "Ñandú Feather"},
    {"id": 9002, "n": "<script>alert(1)</script>"},
    {"id": 9003, "n": "100%_off"},
    {"id": 9004, "n": "O'Brien \"Ring\""},
] + [{"id": 20000 + i, "n": "Filler Item %02d" % i} for i in range(1, 61)]


def entries(body):
    return [item["entry"] for item in body["items"]]


class ItemSearchTestCase(tvm.VaultMarketTestCase):
    def setUp(self):
        super().setUp()
        self._saved_catalog = dict(server.ITEM_CATALOG_STATE)
        self.addCleanup(self._restore_catalog)
        path = os.path.join(self.tmp.name, "catalog.json")
        with open(path, "w", encoding="utf-8") as fh:
            json.dump(CATALOG, fh)
        server.CONFIG["item_catalog_file"] = path
        server.ITEM_CATALOG_STATE.update({"key": None, "catalog": None, "warned": set()})

    def _restore_catalog(self):
        server.ITEM_CATALOG_STATE.clear()
        server.ITEM_CATALOG_STATE.update(self._saved_catalog)

    def search(self, q=None, limit=None, **kw):
        parts = []
        if q is not None:
            parts.append("q=" + urllib.parse.quote(q, safe=""))
        if limit is not None:
            parts.append("limit=" + str(limit))
        return self.call("/api/admin/items/search" + ("?" + "&".join(parts) if parts else ""), **kw)


class TestItemSearch(ItemSearchTestCase):
    def test_requires_an_admin_session(self):
        self.assertEqual(self.search("potion", token=False)[0], 401)

    def test_answers_with_the_documented_shape(self):
        status, body = self.search("red potion")
        self.assertEqual(status, 200)
        self.assertEqual(set(body), {"available", "items", "total"})
        self.assertIs(body["available"], True)
        self.assertEqual(body["total"], 1)
        self.assertEqual(body["items"], [{"entry": 5001, "name": "Red Potion", "icon": "item_5001.png", "quality": "common"}])

    def test_an_item_with_no_icon_or_quality_has_nulls(self):
        (item,) = self.search("misc")[1]["items"]
        self.assertEqual(item, {"entry": 5120, "name": "Misc", "icon": None, "quality": None})

    def test_names_from_the_names_file_are_searchable_and_win_over_the_catalog(self):
        with open(self.names_path, "w", encoding="utf-8") as fh:
            json.dump({"5001": "Poción roja", "7777": "Only In Names File"}, fh)
        server.ITEM_NAMES_STATE.update({"key": None, "names": None, "warned": set()})
        self.assertEqual(entries(self.search("only in names")[1]), [7777])
        (renamed,) = self.search("roja")[1]["items"]
        self.assertEqual((renamed["entry"], renamed["name"], renamed["icon"]), (5001, "Poción roja", "item_5001.png"))

    def test_ranking_is_exact_id_then_prefix_then_contains_stable_by_id(self):
        # "12": item 12 is the exact id, 123 starts with it, 5120 and "Filler Item 12" (20012) only contain it.
        self.assertEqual(entries(self.search("12")[1]), [12, 123, 5120, 20012])
        # "pot": "Potion Pack" starts with it, "Red Potion" contains it.
        self.assertEqual(entries(self.search("pot")[1]), [6001, 5001])
        # "sword": "Sword of Fire" starts with it (id 123), "Apple Sword" contains it (id 12).
        self.assertEqual(entries(self.search("sword")[1]), [123, 12])

    def test_equal_rank_results_are_ordered_by_id(self):
        body = self.search("filler", limit=50)[1]
        self.assertEqual(entries(body), sorted(entries(body)))

    def test_matching_ignores_case_including_non_ascii_letters(self):
        self.assertEqual(entries(self.search("RED POTION")[1]), [5001])
        self.assertEqual(entries(self.search("ÑANDÚ")[1]), [9001])
        self.assertEqual(entries(self.search("ñandú")[1]), [9001])

    def test_unicode_queries_work_percent_encoded(self):
        self.assertEqual(entries(self.search("ñand")[1]), [9001])
        self.assertEqual(self.search("日本語")[1]["items"], [])

    def test_a_numeric_query_matches_ids_and_names(self):
        self.assertEqual(entries(self.search("5001")[1]), [5001])
        self.assertEqual(entries(self.search("9003")[1]), [9003])
        self.assertEqual(entries(self.search("100")[1]), [9003, 5003])  # "100%_off" starts with it, "Poción 100%" contains it

    def test_hostile_text_is_matched_literally_and_never_reflected(self):
        self.assertEqual(entries(self.search("%")[1]), [5003, 9003])  # the two names holding a literal percent sign
        self.assertEqual(entries(self.search("_")[1]), [9003])
        self.assertEqual(entries(self.search("'")[1]), [9004])
        self.assertEqual(entries(self.search('"')[1]), [9004])
        self.assertEqual(entries(self.search("<script>")[1]), [9002])
        for hostile in ("'; DROP TABLE account;--", "%' OR '1'='1", "\\", "\x00", "<img src=x onerror=alert(1)>"):
            status, body = self.search(hostile)
            self.assertEqual(status, 200, repr(hostile))
            self.assertEqual(body["items"], [], repr(hostile))
            self.assertNotIn("q", body)
            self.assertNotIn("DROP TABLE", json.dumps(body))

    def test_a_query_is_never_used_as_a_path(self):
        before = dict(server.CONFIG)
        for q in ("../../etc/passwd", "/etc/passwd", "catalog.json", "items.json"):
            self.assertEqual(self.search(q)[1]["items"], [], q)
        self.assertEqual(server.CONFIG, before)

    def test_limit_defaults_to_20_and_is_clamped_to_50(self):
        self.assertEqual(len(self.search("filler")[1]["items"]), 20)
        body = self.search("filler", limit=999)[1]
        self.assertEqual((len(body["items"]), body["total"]), (50, 60))
        self.assertEqual(len(self.search("filler", limit=3)[1]["items"]), 3)

    def test_an_invalid_limit_falls_back_and_a_tiny_one_is_raised_to_one(self):
        for bad in ("abc", "", "1.5"):
            self.assertEqual(len(self.search("filler", limit=bad)[1]["items"]), 20, bad)
        for small in ("0", "-4"):
            self.assertEqual(len(self.search("filler", limit=small)[1]["items"]), 1, small)

    def test_total_counts_every_match_not_just_the_page(self):
        body = self.search("filler", limit=5)[1]
        self.assertEqual((len(body["items"]), body["total"]), (5, 60))

    def test_an_empty_query_returns_the_first_items_by_id(self):
        for body in (self.search("", limit=4)[1], self.search(limit=4)[1], self.search("   ", limit=4)[1]):
            self.assertEqual(entries(body), [1, 12, 123, 5001])
            self.assertEqual(body["total"], len(CATALOG) + 2)  # plus the names-file ids 5002 and 5003

    def test_a_query_of_64_characters_is_fine_and_65_is_refused(self):
        self.assertEqual(self.search("x" * 64)[0], 200)
        status, body = self.search("x" * 65)
        self.assertEqual(status, 400)
        self.assertEqual(body["error"], "The search text can have at most 64 characters")
        _, es = self.search("x" * 65, lang="es")
        self.assertEqual(es["error"], "El texto de búsqueda puede tener como máximo 64 caracteres")

    def test_surrounding_spaces_do_not_count_toward_the_length(self):
        self.assertEqual(entries(self.search("  red potion  ")[1]), [5001])
        self.assertEqual(self.search(" " * 100 + "red")[0], 200)

    def test_without_a_name_source_it_says_unavailable_and_lists_nothing(self):
        server.CONFIG["item_names_file"] = ""
        server.CONFIG.pop("item_catalog_file", None)
        server.ITEM_NAMES_STATE.update({"key": None, "names": None, "warned": set()})
        server.ITEM_CATALOG_STATE.update({"key": None, "catalog": None, "warned": set()})
        status, body = self.search("potion")
        self.assertEqual(status, 200)
        self.assertEqual(body, {"available": False, "items": [], "total": 0})

    def test_it_only_reads(self):
        before = self.snapshot()
        self.search("potion")
        self.search("")
        self.search("x" * 100)
        self.assertEqual(self.snapshot(), before)

    def test_only_get_is_served(self):
        status, _ = self.call("/api/admin/items/search", {"q": "potion"})
        self.assertIn(status, (404, 405))


class TestMarketEntryFilter(ItemSearchTestCase):
    """Reuses the market fixtures of tests/test_vault_market.py; only the new parameter is tested here."""

    add_listing = tvm.TestWebMarket.add_listing
    market = tvm.TestWebMarket.market
    seed = tvm.TestWebMarket.seed

    def listing_entries(self, query):
        status, body = self.market(query)
        self.assertEqual(status, 200, body)
        return sorted(row["entry"] for row in body["listings"])

    def test_entry_narrows_to_that_item_exactly(self):
        self.seed()
        self.assertEqual(self.listing_entries("?entry=5001"), [5001])
        self.assertEqual(self.listing_entries("?entry=5002"), [5002])
        self.assertEqual(self.listing_entries("?entry=424242"), [])

    def test_entry_combines_with_status_and_q(self):
        self.seed()
        self.assertEqual(self.listing_entries("?entry=5001&status=all"), [5001, 5001])
        self.assertEqual(self.listing_entries("?entry=5001&status=sold"), [5001])
        self.assertEqual(self.listing_entries("?entry=5001&status=all&q=bob"), [5001])
        self.assertEqual(self.listing_entries("?entry=5001&q=bob"), [])

    def test_entry_keeps_the_response_shape_and_the_unfiltered_summary(self):
        self.seed()
        status, plain = self.market("")
        status, filtered = self.market("?entry=5001")
        self.assertEqual(set(filtered), set(plain))
        self.assertEqual(filtered["summary"], plain["summary"])
        self.assertEqual(filtered["total"], 1)
        listing = filtered["listings"][0]
        self.assertEqual((listing["entry"], listing["name"]), (5001, "Red Potion"))

    def test_a_blank_entry_means_no_filter(self):
        self.seed()
        self.assertEqual(self.listing_entries("?entry="), self.listing_entries(""))

    def test_a_bad_entry_is_a_400_with_a_translated_message(self):
        self.seed()
        for bad in ("abc", "0", "-5", "1.5", "5001abc", "9" * 30, "%20x"):
            status, body = self.market("?entry=" + bad)
            self.assertEqual(status, 400, bad)
            self.assertEqual(body["error"], "Invalid item ID. It must be a positive whole number", bad)
        _, es = self.market("?entry=abc", lang="es")
        self.assertEqual(es["error"], "ID de objeto inválido. Debe ser un número entero positivo")

    def test_entry_is_checked_after_the_status(self):
        status, body = self.market("?status=bogus&entry=abc")
        self.assertEqual(status, 400)
        self.assertIn("Invalid market status", body["error"])

    def test_entry_filter_does_not_write(self):
        self.seed()
        before = self.snapshot()
        self.market("?entry=5001")
        self.market("?entry=bad")
        self.assertEqual(self.snapshot(), before)


class TestGiftCodeRewardsUseTheList(tgc.GiftCodeTestCase):
    def setUp(self):
        super().setUp()
        with open(self.names_path, "w", encoding="utf-8") as fh:
            json.dump({"10001": "Red Potion", "20003": "Blue Gem"}, fh)
        server.ITEM_NAMES_STATE.update({"key": None, "names": None, "warned": set()})

    def create(self, items, code="PICKED"):
        return self.call("POST", "/api/admin/gift-codes", {"code": code, "items": items})

    def stored(self, code):
        return [row["items"] for row in self.rows("SELECT items FROM gift_code WHERE code = ?", code)]

    def test_a_reward_in_the_list_is_created(self):
        status, body = self.create([{"entry": 10001, "count": 2}, {"entry": 20003, "count": 1}])
        self.assertEqual(status, 200, body)
        self.assertEqual(json.loads(self.stored("PICKED")[0]), [[10001, 2], [20003, 1]])

    def test_a_reward_missing_from_the_list_is_refused_naming_the_id_and_nothing_is_stored(self):
        status, body = self.create([{"entry": 10001, "count": 1}, {"entry": 99999, "count": 1}])
        self.assertEqual(status, 400)
        self.assertEqual(body["error"], "These item IDs are not in the item list: 99999")
        self.assertEqual(self.stored("PICKED"), [])

    def test_every_unknown_id_is_named_up_to_five(self):
        status, body = self.create([{"entry": n, "count": 1} for n in (11, 12, 13, 14, 15, 16, 17)])
        self.assertEqual(status, 400)
        self.assertIn("11, 12, 13, 14, 15", body["error"])
        self.assertNotIn("16", body["error"])

    def test_the_refusal_is_translated(self):
        status, body = self.call("POST", "/api/admin/gift-codes", {"code": "X", "items": [{"entry": 99999, "count": 1}]}, lang="es")
        self.assertEqual(status, 400)
        self.assertEqual(body["error"], "Estos IDs de objeto no están en la lista de objetos: 99999")

    def test_the_catalog_counts_as_the_list_too(self):
        path = os.path.join(self.tmp.name, "catalog.json")
        with open(path, "w", encoding="utf-8") as fh:
            json.dump([{"id": 31337, "n": "Catalog Only"}], fh)
        server.CONFIG["item_catalog_file"] = path
        self.addCleanup(server.CONFIG.pop, "item_catalog_file", None)
        saved = dict(server.ITEM_CATALOG_STATE)
        self.addCleanup(lambda: (server.ITEM_CATALOG_STATE.clear(), server.ITEM_CATALOG_STATE.update(saved)))
        server.ITEM_CATALOG_STATE.update({"key": None, "catalog": None, "warned": set()})
        self.assertEqual(self.create([{"entry": 31337, "count": 1}])[0], 200)
        self.assertEqual(self.create([{"entry": 99999, "count": 1}], code="NOPE")[0], 400)

    def test_without_a_list_any_positive_integer_still_works(self):
        server.CONFIG["item_names_file"] = ""
        server.ITEM_NAMES_STATE.update({"key": None, "names": None, "warned": set()})
        status, body = self.create([{"entry": 99999, "count": 1}])
        self.assertEqual(status, 200, body)

    def test_the_old_shape_errors_still_come_first(self):
        status, body = self.create([{"entry": 0, "count": 1}])
        self.assertEqual(status, 400)
        self.assertIn("positive item ID and count", body["error"])


if __name__ == "__main__":
    unittest.main()
