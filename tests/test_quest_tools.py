"""Quest debug tools: the `quest` GM command, the reply passthrough and the quest read endpoints.

Upstream contract (ro3emu-server, ServerHost.cs, loopback only):
- POST /ro3emu/gm answers 200 with a JSON string: the command's reply ("done" when it printed nothing).
- GET /ro3emu/quests -> [{"id", "name"}] sorted by id.
- GET /ro3emu/quests?account=<acct> -> {"account", "role", "quests": [{"id", "name", "status", "progress", "completed"}]},
  400 "not in game" when the account has no character online.
The in-game command is `!quest accept|finish|done|drop <taskId>`.
"""

import json
import os
import re
import sys
import unittest
import urllib.error
import urllib.request

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import test_gm

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
import server

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PUBLIC = os.path.join(ROOT, "public")

CATALOG = [{"id": 10101010, "name": "First steps"}, {"id": 10101020, "name": "The <b>bold</b> road"}]
STATE = {
    "account": "player1",
    "role": "Hero",
    "quests": [{"id": 10101010, "name": "First steps", "status": "running",
                "progress": [{"done": 1, "need": 3}], "completed": 2}],
}


class QuestBase(unittest.TestCase):
    setUp = test_gm.GmEndpointTest.setUp
    _post = test_gm.GmEndpointTest._post
    gm = test_gm.GmEndpointTest.gm
    audit_rows = test_gm.GmEndpointTest.audit_rows
    assert_rejected = test_gm.GmEndpointTest.assert_rejected

    def allow_quest(self):
        server.CONFIG["gm_allowed_commands"] = ["warp", "quest"]

    def _get(self, path, token="default"):
        headers = {}
        if token == "default":
            token = self.token
        if token:
            headers["Authorization"] = "Bearer " + token
        req = urllib.request.Request(self.base + path, headers=headers, method="GET")
        try:
            with urllib.request.urlopen(req, timeout=10) as resp:
                return resp.status, json.loads(resp.read().decode("utf-8"))
        except urllib.error.HTTPError as e:
            with e:
                return e.code, json.loads(e.read().decode("utf-8"))


class QuestCommandTest(QuestBase):
    def test_quest_is_off_unless_it_is_in_the_allowlist(self):
        self.assert_rejected({"account": "player1", "command": "quest", "args": {"action": "accept", "id": 10101010}})

    def test_quest_allowlist_does_not_open_other_commands(self):
        server.CONFIG["gm_allowed_commands"] = ["quest"]
        self.assert_rejected({"account": "player1", "command": "warp", "args": {"scene": 10100}})

    def test_each_action_sends_the_exact_line_and_returns_the_reply(self):
        self.allow_quest()
        for action in ("accept", "finish", "done", "drop"):
            with self.subTest(action=action):
                self.fake.body = json.dumps("Quest %s ok" % action).encode("utf-8")
                code, data = self.gm({"account": "player1", "command": "quest", "args": {"action": action, "id": 10101010}})
                self.assertEqual(code, 200, data)
                self.assertTrue(data["success"])
                self.assertEqual(data["sent"], "!quest %s 10101010" % action)
                self.assertEqual(data["reply"], "Quest %s ok" % action)
                self.assertEqual(self.fake.requests[-1]["body"], "!quest %s 10101010" % action)
        self.assertEqual(len(self.audit_rows()), 4)

    def test_repeat_drops_then_accepts_and_audits_each_line(self):
        self.allow_quest()
        self.fake.replies = [(200, b'"dropped"'), (200, b'"accepted"')]
        code, data = self.gm({"account": "player1", "command": "quest", "args": {"action": "repeat", "id": 7}})
        self.assertEqual(code, 200, data)
        self.assertEqual([r["body"] for r in self.fake.requests], ["!quest drop 7", "!quest accept 7"])
        self.assertEqual(data["sent"], "!quest drop 7\n!quest accept 7")
        self.assertEqual(data["reply"], "dropped\naccepted")
        self.assertEqual(data["replies"], [{"sent": "!quest drop 7", "reply": "dropped"},
                                           {"sent": "!quest accept 7", "reply": "accepted"}])
        rows = self.audit_rows()
        self.assertEqual(len(rows), 2)
        self.assertIn("!quest drop 7", rows[0]["details"])
        self.assertIn("!quest accept 7", rows[1]["details"])

    def test_repeat_stops_when_the_drop_fails(self):
        self.allow_quest()
        self.fake.status, self.fake.body = 400, b'"not in game"'
        code, data = self.gm({"account": "player1", "command": "quest", "args": {"action": "repeat", "id": 7}})
        self.assertEqual(code, 409, data)
        self.assertEqual([r["body"] for r in self.fake.requests], ["!quest drop 7"])
        self.assertEqual(data["sent"], "!quest drop 7")
        rows = self.audit_rows()
        self.assertEqual(len(rows), 1)
        self.assertIn("failed", rows[0]["details"])

    def test_invalid_quest_args_are_rejected(self):
        self.allow_quest()
        bad_args = [
            None,
            {},
            {"action": "accept"},
            {"id": 5},
            {"action": "show", "id": 5},
            {"action": "ACCEPT", "id": 5},
            {"action": "accept", "id": 0},
            {"action": "accept", "id": -5},
            {"action": "accept", "id": "5"},
            {"action": "accept", "id": 5.0},
            {"action": "accept", "id": True},
            {"action": "accept", "id": 2 ** 31},
            {"action": "accept", "id": 5, "extra": 1},
            {"action": "accept\n!zeny 999999", "id": 5},
            {"action": "accept", "id": "5\n!zeny 999999"},
            {"action": "accept 5 !zeny", "id": 5},
            ["accept", 5],
            "accept 5",
        ]
        for args in bad_args:
            with self.subTest(args=args):
                self.assert_rejected({"account": "player1", "command": "quest", "args": args})


class ReplyPassthroughTest(QuestBase):
    def test_warp_returns_the_json_string_reply(self):
        self.fake.body = b'"Warped to 10100"'
        code, data = self.gm({"account": "player1", "command": "warp", "args": {"scene": 10100}})
        self.assertEqual(code, 200, data)
        self.assertEqual(data["sent"], "!warp 10100")
        self.assertEqual(data["reply"], "Warped to 10100")
        self.assertTrue(data["message"])

    def test_non_json_reply_falls_back_to_the_raw_text(self):
        self.fake.body = b"done"
        code, data = self.gm({"account": "player1", "command": "warp", "args": {"scene": 10100}})
        self.assertEqual(code, 200, data)
        self.assertEqual(data["reply"], "done")


class QuestReadEndpointsTest(QuestBase):
    def test_catalog_requires_authentication(self):
        self.allow_quest()
        code, _ = self._get("/api/admin/quests/catalog", token=None)
        self.assertEqual(code, 401)
        code, _ = self._get("/api/admin/quests?account=player1", token=None)
        self.assertEqual(code, 401)
        self.assertEqual(self.fake.requests, [])

    def test_endpoints_are_hidden_when_quest_is_not_allowlisted(self):
        for path in ("/api/admin/quests/catalog", "/api/admin/quests?account=player1"):
            with self.subTest(path=path):
                code, data = self._get(path)
                self.assertEqual(code, 403, data)
                self.assertIn("error", data)
        self.assertEqual(self.fake.requests, [])

    def test_catalog_proxies_the_quest_list(self):
        self.allow_quest()
        self.fake.body = json.dumps(CATALOG).encode("utf-8")
        code, data = self._get("/api/admin/quests/catalog")
        self.assertEqual(code, 200, data)
        self.assertEqual(data["quests"], CATALOG)
        self.assertEqual(self.fake.requests[0]["method"], "GET")
        self.assertEqual(self.fake.requests[0]["path"], "/ro3emu/quests")
        self.assertEqual(self.fake.requests[0]["query"], {})

    def test_character_quests_use_the_canonical_account_name(self):
        self.allow_quest()
        self.fake.body = json.dumps(STATE).encode("utf-8")
        code, data = self._get("/api/admin/quests?account=PLAYER1")
        self.assertEqual(code, 200, data)
        self.assertEqual(data["role"], "Hero")
        self.assertEqual(data["quests"], STATE["quests"])
        self.assertEqual(self.fake.requests[0]["path"], "/ro3emu/quests")
        self.assertEqual(self.fake.requests[0]["query"], {"account": ["player1"]})

    def test_character_quests_not_in_game_maps_to_409(self):
        self.allow_quest()
        self.fake.status, self.fake.body = 400, b'"not in game"'
        code, data = self._get("/api/admin/quests?account=player1")
        self.assertEqual(code, 409, data)
        self.assertIn("not in the game", data["error"])

    def test_character_quests_reject_unknown_or_invalid_accounts(self):
        self.allow_quest()
        self.assertEqual(self._get("/api/admin/quests?account=ghost")[0], 404)
        for bad in ("", "player1%26account%3Dother", "player%201"):
            with self.subTest(account=bad):
                self.assertEqual(self._get("/api/admin/quests?account=" + bad)[0], 400)
        self.assertEqual(self.fake.requests, [])

    def test_non_loopback_base_is_refused(self):
        self.allow_quest()
        server.CONFIG["ro3_base_url"] = "http://10.0.0.5:5380"
        code, data = self._get("/api/admin/quests/catalog")
        self.assertEqual(code, 400, data)
        self.assertIn("same host", data["error"])

    def test_unexpected_payload_is_a_502(self):
        self.allow_quest()
        self.fake.body = b'{"not": "a list"}'
        code, data = self._get("/api/admin/quests/catalog")
        self.assertEqual(code, 502, data)


class QuestToolsUiTest(unittest.TestCase):
    def setUp(self):
        with open(os.path.join(PUBLIC, "admin.js"), encoding="utf-8") as f:
            self.js = f.read()
        start = self.js.index("// --- Quest tools")
        self.section = self.js[start:self.js.index("// --- Sidebar menu", start)]

    def test_section_loads_catalog_and_character_quests(self):
        self.assertIn("/api/admin/quests/catalog", self.section)
        self.assertIn("/api/admin/quests?account=", self.section)
        self.assertIn("encodeURIComponent", self.section)

    def test_all_actions_are_offered(self):
        for action in ("accept", "finish", "done", "drop", "repeat"):
            self.assertRegex(self.section, r"['\"]%s['\"]" % action)
        self.assertIn("sendGmCommand('quest'", self.section)

    def test_server_text_is_never_put_into_inner_html_unescaped(self):
        # Every innerHTML assignment in the section must be static or built through escapeHtml.
        for match in re.finditer(r"innerHTML\s*=\s*([^;]+);", self.section):
            expr = match.group(1)
            self.assertTrue(expr.strip().startswith("'") or "escapeHtml" in expr or expr.strip() == "''", expr)
        self.assertIn("textContent", self.section)

    def test_section_is_hidden_until_the_catalog_answers(self):
        self.assertIn("hidden", self.section)

    def test_reply_is_shown_in_the_result_line(self):
        self.assertIn("data.reply", self.js)


if __name__ == "__main__":
    unittest.main()
