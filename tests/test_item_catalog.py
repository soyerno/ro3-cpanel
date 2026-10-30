"""Item names, icons and quality from an optional catalog file (config 'item_catalog_file').

The catalog is a JSON list of rows like {"id": 5001, "n": "Red Potion", "ic": "item_5001.png", "q": "Common"}
(the shape Konsor's items-catalog.json has). Names from 'item_names_file' still win when both are set. Icons are
only ever file names that pass a strict pattern: the panel builds the URL from 'item_icons_url' on the client.
"""

import contextlib
import io
import json
import os
import sys
import tempfile
import unittest
import urllib.parse

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import server  # noqa: E402
import test_vault_market as tvm  # noqa: E402

CATALOG = [
    {"id": 5001, "n": "Red Potion", "nz": "红药水", "ic": "item_5001.png", "q": "Common", "qc": "#94a3b8", "cat": "i"},
    {"id": 5002, "n": "Blue Gem", "ic": "gem_blue.webp", "q": "Mythic"},
    {"id": 7001, "n": "Mystery", "ic": "", "q": ""},
]


class CatalogCase(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(ignore_cleanup_errors=True)
        self.addCleanup(self.tmp.cleanup)
        self._saved = (dict(server.CONFIG), dict(server.ITEM_NAMES_STATE), dict(server.ITEM_CATALOG_STATE))
        self.addCleanup(self._restore)
        server.CONFIG["item_names_file"] = ""
        server.CONFIG.pop("item_catalog_file", None)
        server.ITEM_NAMES_STATE.update({"key": None, "names": None, "warned": set()})
        server.ITEM_CATALOG_STATE.update({"key": None, "catalog": None, "warned": set()})

    def _restore(self):
        server.CONFIG.clear()
        server.CONFIG.update(self._saved[0])
        for state, saved in ((server.ITEM_NAMES_STATE, self._saved[1]), (server.ITEM_CATALOG_STATE, self._saved[2])):
            state.clear()
            state.update(saved)

    def write_catalog(self, content, name="catalog.json"):
        path = os.path.join(self.tmp.name, name)
        with open(path, "w", encoding="utf-8") as fh:
            fh.write(content if isinstance(content, str) else json.dumps(content))
        server.CONFIG["item_catalog_file"] = path
        return path


class LoadCatalogTest(CatalogCase):
    def test_no_catalog_configured_means_no_catalog_and_no_warning(self):
        err = io.StringIO()
        with contextlib.redirect_stderr(err):
            self.assertIsNone(server.load_item_catalog())
        self.assertEqual(err.getvalue(), "")

    def test_reads_name_icon_and_lowercase_quality(self):
        self.write_catalog(CATALOG)
        catalog = server.load_item_catalog()
        self.assertEqual(catalog["5001"], {"name": "Red Potion", "icon": "item_5001.png", "quality": "common"})
        self.assertEqual(catalog["5002"], {"name": "Blue Gem", "icon": "gem_blue.webp", "quality": "mythic"})
        self.assertEqual(catalog["7001"], {"name": "Mystery", "icon": None, "quality": None})

    def test_hostile_icon_names_are_dropped_but_the_name_is_kept(self):
        hostile = ["../x.png", "a/b.png", "a\\b.png", "x.gif", ".png", "x.PNG", "x.png/", "javascript:alert(1).png",
                   "x.png?y=1", "x y.png", "<img>.png", "a" * 200 + ".png", "x.png\n", "%2e%2e.png", "http://e/x.png"]
        self.write_catalog([{"id": i, "n": "n%d" % i, "ic": ic, "q": "rare"} for i, ic in enumerate(hostile, start=1)])
        catalog = server.load_item_catalog()
        for i in range(1, len(hostile) + 1):
            self.assertEqual(catalog[str(i)]["name"], "n%d" % i)
            self.assertIsNone(catalog[str(i)]["icon"], hostile[i - 1])

    def test_an_unknown_quality_is_dropped_so_it_can_never_become_a_css_class(self):
        self.write_catalog([{"id": 1, "n": "x", "q": "common legendary"}, {"id": 2, "n": "y", "q": '"><script>'}])
        catalog = server.load_item_catalog()
        self.assertIsNone(catalog["1"]["quality"])
        self.assertIsNone(catalog["2"]["quality"])

    def test_bad_rows_are_skipped_not_fatal(self):
        self.write_catalog([5, "x", None, [], {"n": "no id"}, {"id": True, "n": "bool"}, {"id": 1.5, "n": "float"},
                            {"id": -3, "n": "negative"}, {"id": 4, "n": 12}, {"id": "9", "n": "digits as text"},
                            {"id": 8, "n": "ok"}])
        catalog = server.load_item_catalog()
        self.assertEqual(sorted(catalog), ["8", "9"])

    def test_long_names_are_cut(self):
        self.write_catalog([{"id": 1, "n": "x" * 500}])
        self.assertEqual(len(server.load_item_catalog()["1"]["name"]), 120)

    def test_the_first_row_of_an_id_wins(self):
        self.write_catalog([{"id": 1, "n": "first"}, {"id": 1, "n": "second"}])
        self.assertEqual(server.load_item_catalog()["1"]["name"], "first")

    def test_a_missing_or_broken_file_warns_once_and_disables_the_catalog(self):
        for content in (None, "{not json", json.dumps({"id": 1}), json.dumps("text")):
            server.ITEM_CATALOG_STATE.update({"key": None, "catalog": None, "warned": set()})
            if content is None:
                server.CONFIG["item_catalog_file"] = os.path.join(self.tmp.name, "nope.json")
            else:
                self.write_catalog(content)
            err = io.StringIO()
            with contextlib.redirect_stderr(err):
                self.assertIsNone(server.load_item_catalog())
                self.assertIsNone(server.load_item_catalog())
            self.assertEqual(err.getvalue().count("item_catalog_file"), 1, err.getvalue())

    def test_a_file_over_the_size_cap_is_refused(self):
        self.write_catalog(CATALOG)
        original = server.ITEM_CATALOG_MAX_BYTES
        server.ITEM_CATALOG_MAX_BYTES = 10
        self.addCleanup(setattr, server, "ITEM_CATALOG_MAX_BYTES", original)
        err = io.StringIO()
        with contextlib.redirect_stderr(err):
            self.assertIsNone(server.load_item_catalog())
        self.assertIn("item_catalog_file", err.getvalue())

    def test_an_edited_file_is_reloaded(self):
        path = self.write_catalog([{"id": 1, "n": "old"}])
        self.assertEqual(server.load_item_catalog()["1"]["name"], "old")
        with open(path, "w", encoding="utf-8") as fh:
            json.dump([{"id": 1, "n": "newer name"}], fh)
        os.utime(path, (os.path.getmtime(path) + 5, os.path.getmtime(path) + 5))
        self.assertEqual(server.load_item_catalog()["1"]["name"], "newer name")


class ItemInfoTest(CatalogCase):
    def test_without_any_source_an_item_is_all_none(self):
        self.assertEqual(server.item_info(5001), {"name": None, "icon": None, "quality": None})

    def test_catalog_fills_name_icon_and_quality_for_int_and_text_ids(self):
        self.write_catalog(CATALOG)
        expected = {"name": "Red Potion", "icon": "item_5001.png", "quality": "common"}
        self.assertEqual(server.item_info(5001), expected)
        self.assertEqual(server.item_info("5001"), expected)

    def test_an_unknown_id_is_all_none(self):
        self.write_catalog(CATALOG)
        self.assertEqual(server.item_info(424242), {"name": None, "icon": None, "quality": None})

    def test_the_names_file_still_wins_over_the_catalog_name(self):
        self.write_catalog(CATALOG)
        names = os.path.join(self.tmp.name, "names.json")
        with open(names, "w", encoding="utf-8") as fh:
            json.dump({"5001": "Poción roja"}, fh)
        server.CONFIG["item_names_file"] = names
        info = server.item_info(5001)
        self.assertEqual(info["name"], "Poción roja")
        self.assertEqual(info["icon"], "item_5001.png")

    def test_load_item_names_merges_the_catalog_under_the_names_file(self):
        self.write_catalog(CATALOG)
        names = os.path.join(self.tmp.name, "names.json")
        with open(names, "w", encoding="utf-8") as fh:
            json.dump({"5001": "Poción roja", "9": "Only in file"}, fh)
        server.CONFIG["item_names_file"] = names
        merged = server.load_item_names()
        self.assertEqual((merged["5001"], merged["5002"], merged["9"]), ("Poción roja", "Blue Gem", "Only in file"))

    def test_a_weird_entry_never_raises(self):
        self.write_catalog(CATALOG)
        for entry in (None, "", "abc", -1, 1.5, True, [], {}, 2 ** 80):
            self.assertEqual(server.item_info(entry), {"name": None, "icon": None, "quality": None}, repr(entry))


class MailAndGiftCodeItemsTest(CatalogCase):
    def test_mail_attachments_and_items_carry_name_icon_and_quality(self):
        self.write_catalog(CATALOG)
        mail = server.format_mail({
            "Id": "m", "Attachments": [{"Entry": 5001, "Count": 3, "Bind": 1}, {"Entry": 999, "Count": 1, "Bind": 0}],
            "Items": [{"Guid": 1, "Entry": 5002, "Stack": 2}],
        })
        first, second = mail["attachments"]
        self.assertEqual((first["entry"], first["count"], first["bind"]), (5001, 3, 1))
        self.assertEqual((first["name"], first["icon"], first["quality"]), ("Red Potion", "item_5001.png", "common"))
        self.assertEqual((second["name"], second["icon"], second["quality"]), (None, None, None))
        (item,) = mail["items"]
        self.assertEqual((item["entry"], item["stack"], item["guid"]), (5002, 2, 1))
        self.assertEqual((item["name"], item["icon"], item["quality"]), ("Blue Gem", "gem_blue.webp", "mythic"))

    def test_mail_without_a_catalog_keeps_its_fields_and_has_empty_name_icon_quality(self):
        mail = server.format_mail({"Id": "m", "Attachments": [{"Entry": 5001, "Count": 3, "Bind": 1}]})
        self.assertEqual(mail["attachments"], [{"entry": 5001, "count": 3, "bind": 1, "name": None, "icon": None, "quality": None}])

    def test_gift_code_rewards_carry_the_icon_too(self):
        self.write_catalog(CATALOG)
        (reward,) = server.parse_gift_items(json.dumps([[5002, 4]]))
        self.assertEqual(reward, {"entry": 5002, "count": 4, "name": "Blue Gem", "icon": "gem_blue.webp", "quality": "mythic"})


class VaultMarketCatalogTest(tvm.VaultMarketTestCase):
    def setUp(self):
        super().setUp()
        path = os.path.join(self.tmp.name, "catalog.json")
        with open(path, "w", encoding="utf-8") as fh:
            json.dump(CATALOG + [{"id": 6001, "n": "Catalog Only Sword", "ic": "sword.png", "q": "Rare"}], fh)
        server.CONFIG["item_catalog_file"] = path
        self._catalog_saved = dict(server.ITEM_CATALOG_STATE)
        server.ITEM_CATALOG_STATE.update({"key": None, "catalog": None, "warned": set()})
        self.addCleanup(self._restore_catalog)

    def _restore_catalog(self):
        server.ITEM_CATALOG_STATE.clear()
        server.ITEM_CATALOG_STATE.update(self._catalog_saved)

    def test_vault_items_carry_icon_and_quality(self):
        self.sql("INSERT INTO account_vault (account, entry, stack, pack, is_locked, deposited_by_role_id, deposited_by_name, deposited_utc)"
                 " VALUES (?, ?, ?, ?, ?, 7, ?, ?)", *tvm.vault_row("alice", 5002))
        _, body = self.call("/api/admin/accounts/alice/vault")
        item = body["items"][0]
        self.assertEqual((item["name"], item["icon"], item["quality"]), ("Blue Gem", "gem_blue.webp", "mythic"))

    def test_market_listings_carry_icon_and_quality_and_search_finds_catalog_names(self):
        self.sql(
            "INSERT INTO web_market (seller_account, seller_role_id, seller_role_name, entry, stack, pack, price_zeny, is_locked,"
            " status, buyer_account, buyer_role_name, created_utc, updated_utc) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)",
            *tvm.listing("alice", 6001, 500, created="2026-10-29 09:00:01"),
        )
        _, body = self.call("/api/admin/market")
        listing = body["listings"][0]
        self.assertEqual((listing["name"], listing["icon"], listing["quality"]), ("Catalog Only Sword", "sword.png", "rare"))
        _, found = self.call("/api/admin/market?status=all&q=" + urllib.parse.quote("only sword"))
        self.assertEqual([l["entry"] for l in found["listings"]], [6001])


class IconBaseUrlConfigTest(tvm.VaultMarketTestCase):
    """item_icons_url is the only way an icon URL reaches the page, so it must be a same-site path."""

    def icons_url(self, value):
        server.CONFIG["item_icons_url"] = value
        status, body = self.call("/api/admin/config", token=False)
        self.assertEqual(status, 200)
        return body["item_icons_url"]

    def test_default_is_empty(self):
        server.CONFIG.pop("item_icons_url", None)
        self.assertEqual(self.call("/api/admin/config", token=False)[1]["item_icons_url"], "")

    def test_same_site_paths_are_kept_and_get_a_trailing_slash(self):
        self.assertEqual(self.icons_url("item-icons/"), "item-icons/")
        self.assertEqual(self.icons_url("/admin/item-icons"), "/admin/item-icons/")
        self.assertEqual(self.icons_url("  /icons/v1/  "), "/icons/v1/")

    def test_anything_that_could_leave_the_site_or_run_script_is_dropped(self):
        for bad in ("https://evil.example/icons/", "http://evil.example/", "//evil.example/icons/", "javascript:alert(1)",
                    "data:image/png;base64,AAAA", "../icons/", "/a/../../b/", "/a b/", "/a\"onerror=x/", "/a'/", "/<x>/",
                    "\\\\evil\\x\\", "/a?b=1", "/a#frag", 5, ["x"], None, True, "x" * 400):
            self.assertEqual(self.icons_url(bad), "", repr(bad))


if __name__ == "__main__":
    unittest.main()
