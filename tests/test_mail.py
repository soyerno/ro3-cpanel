"""HTTP-level tests for the read-only character mailbox view (issue #9, part B).

The mailbox fixtures follow RO3Emu's persisted shape: MailService.Mailbox serialized with
System.Text.Json default options (PascalCase property names, UTF-8 bytes) into role.mailbox.
"""

import contextlib
import json
import os
import sqlite3
import sys
import tempfile
import threading
import unittest
import urllib.error
import urllib.parse
import urllib.request
from http.server import ThreadingHTTPServer
from unittest import mock

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
import server

ADMIN_USER = "boss"
ADMIN_PASS = "Pw-123456"


def letter(mail_id, created, **overrides):
    """One MailService.Letter as System.Text.Json writes it (default options)."""
    data = {
        "Id": mail_id,
        "Category": 1,
        "CreatedTime": created,
        "RemoveTime": 0,
        "Title": "Title " + mail_id,
        "Content": "Content " + mail_id,
        "Abstract": "Abstract " + mail_id,
        "Sender": "RO3",
        "SenderId": "0",
        "TemplateId": 0,
        "ImportantType": 0,
        "DeliveryKey": "delivery/" + mail_id,
        "ContentParams": None,
        "Read": False,
        "Claimed": False,
        "Attachments": [],
        "Items": [],
        "Currency": {},
    }
    data.update(overrides)
    return data


def mailbox_bytes(letters, next_id=0):
    return json.dumps({"NextId": next_id, "Letters": letters}, ensure_ascii=False).encode("utf-8")


RICH_LETTER = letter(
    "m-rich", 1700000300,
    Title="Recompensa", Sender="Kafra", SenderId="42", TemplateId=7, ImportantType=1, Read=True,
    Category=2, RemoveTime=1800000000,
    ContentParams="AAECAw==",
    Attachments=[{"Entry": 501, "Count": 3, "Bind": 1}, {"Entry": 100, "Count": 50, "Bind": 0}],
    Items=[{"Guid": 9001, "Entry": 1201, "Stack": 1, "Pack": 0, "Sort": 0, "Grid": 0, "IsLocked": False,
            "Attrs": {"30": 5}, "StringAttrs": None, "BindType": 0, "BindExpire": 0,
            "ExpireTimeStamp": 0, "Enchantments": {}}],
    Currency={"2": 1000, "1": 5},
)

# role name -> (deleted_time, mailbox blob)
ROLES = {
    "Rich": (0, mailbox_bytes([
        letter("m-old", 1700000100),
        RICH_LETTER,
        letter("m-mid", 1700000200),
    ], next_id=3)),
    "Paged": (0, mailbox_bytes([letter("p%02d" % i, 1700000000 + i) for i in range(25)])),
    "SameTime": (0, mailbox_bytes([letter("a", 1700000000), letter("c", 1700000000), letter("b", 1700000000)])),
    "NullBox": (0, None),
    "EmptyBlob": (0, b""),
    "NoLetters": (0, mailbox_bytes([])),
    "BadUtf8": (0, b"\xff\xfe\x00garbage"),
    "BadJson": (0, b"{\"NextId\": 1, \"Letters\": ["),
    "NotObject": (0, b"[1, 2, 3]"),
    "BadLetters": (0, b"{\"NextId\": 1, \"Letters\": \"nope\"}"),
    "Deleted": (1700000000, mailbox_bytes([letter("gone", 1700000000)])),
}


class MailViewTest(unittest.TestCase):
    def setUp(self):
        # Restore module globals BEFORE mutating them.
        self.addCleanup(setattr, server, "DB_PATH", server.DB_PATH)
        self.addCleanup(setattr, server, "CONFIG", server.CONFIG)
        self.addCleanup(setattr, server, "ACTIVE_SESSIONS", server.ACTIVE_SESSIONS)

        tmp = tempfile.TemporaryDirectory(ignore_cleanup_errors=True)
        self.addCleanup(tmp.cleanup)
        self.db_path = os.path.join(tmp.name, "ro3emu.db")

        with contextlib.closing(sqlite3.connect(self.db_path)) as con:
            con.execute("CREATE TABLE account (name TEXT PRIMARY KEY, password_hash BLOB, salt BLOB, created_utc TEXT)")
            con.execute("CREATE TABLE auth_token (token TEXT, kind TEXT, account TEXT, expires_utc TEXT)")
            con.execute(
                """CREATE TABLE role (
                    id INTEGER PRIMARY KEY AUTOINCREMENT, account TEXT, name TEXT, sex INTEGER,
                    career INTEGER, level INTEGER, job_level INTEGER, last_login_time INTEGER,
                    create_time INTEGER, currency TEXT, stats TEXT, scene_entry INTEGER,
                    pos_x REAL, pos_y REAL, pos_z REAL, deleted_time INTEGER DEFAULT 0, mailbox BLOB)"""
            )
            con.execute("INSERT INTO account (name, password_hash, salt, created_utc) VALUES ('owner', x'00', x'00', '2024-01-01T00:00:00Z')")
            con.execute("INSERT INTO auth_token VALUES ('tok-owner', 'session', 'owner', '2099-01-01')")
            self.role_ids = {}
            for name, (deleted, blob) in ROLES.items():
                cur = con.execute(
                    "INSERT INTO role (account, name, sex, career, level, job_level, last_login_time, create_time,"
                    " currency, stats, scene_entry, pos_x, pos_y, pos_z, deleted_time, mailbox)"
                    " VALUES ('owner', ?, 1, 1000, 10, 5, 1700000000, 1700000000, '2:100', '1,2,3,4,5,6',"
                    " 10100, 1.0, 2.0, 3.0, ?, ?)",
                    (name, deleted, None if blob is None else sqlite3.Binary(blob)),
                )
                self.role_ids[name] = cur.lastrowid
            con.commit()

        server.DB_PATH = self.db_path
        server.CONFIG = dict(server.CONFIG)
        server.CONFIG["admin_users"] = [{"username": ADMIN_USER, "password": ADMIN_PASS}]
        server.ACTIVE_SESSIONS = {}
        server.init_tables()

        patcher = mock.patch.object(server.CPanelRequestHandler, "log_message", lambda *a, **k: None)
        patcher.start()
        self.addCleanup(patcher.stop)

        self.httpd = ThreadingHTTPServer(("127.0.0.1", 0), server.CPanelRequestHandler)
        thread = threading.Thread(target=self.httpd.serve_forever, daemon=True)
        thread.start()
        self.addCleanup(thread.join, 10)
        self.addCleanup(self.httpd.server_close)
        self.addCleanup(self.httpd.shutdown)
        self.base = "http://127.0.0.1:%d" % self.httpd.server_address[1]
        self.token = self._login()

    def _login(self):
        req = urllib.request.Request(
            self.base + "/api/admin/login",
            data=json.dumps({"username": ADMIN_USER, "password": ADMIN_PASS}).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=10) as resp:
            return json.loads(resp.read().decode("utf-8"))["token"]

    def request(self, path, auth=True, **params):
        url = self.base + path
        if params:
            url += "?" + urllib.parse.urlencode(params)
        headers = {"Authorization": "Bearer " + self.token} if auth else {}
        req = urllib.request.Request(url, headers=headers)
        try:
            with urllib.request.urlopen(req, timeout=10) as resp:
                return resp.status, json.loads(resp.read().decode("utf-8"))
        except urllib.error.HTTPError as err:
            with err:
                return err.code, json.loads(err.read().decode("utf-8"))

    def get_mail(self, role_name, **params):
        status, data = self.request("/api/admin/characters/%d/mail" % self.role_ids[role_name], **params)
        self.assertEqual(status, 200, data)
        return data

    def role_snapshot(self):
        with contextlib.closing(sqlite3.connect(self.db_path)) as con:
            return con.execute("SELECT * FROM role ORDER BY id").fetchall()

    # --- decoding and fields ---

    def test_decodes_mailbox_newest_first_with_verified_fields(self):
        data = self.get_mail("Rich")
        self.assertTrue(data["decodable"])
        self.assertEqual(data["role_id"], self.role_ids["Rich"])
        self.assertEqual(data["role_name"], "Rich")
        self.assertEqual(data["account"], "owner")
        self.assertEqual(data["total"], 3)
        self.assertEqual([m["id"] for m in data["mails"]], ["m-rich", "m-mid", "m-old"])

        rich = data["mails"][0]
        self.assertEqual(rich["title"], "Recompensa")
        self.assertEqual(rich["abstract"], "Abstract m-rich")
        self.assertEqual(rich["content"], "Content m-rich")
        self.assertEqual(rich["sender"], "Kafra")
        self.assertEqual(rich["sender_id"], "42")
        self.assertEqual(rich["category"], 2)
        self.assertEqual(rich["template_id"], 7)
        self.assertEqual(rich["important_type"], 1)
        self.assertEqual(rich["created_at"], "2023-11-14T22:18:20+00:00")
        self.assertEqual(rich["remove_at"], "2027-01-15T08:00:00+00:00")
        self.assertIs(rich["read"], True)
        self.assertIs(rich["claimed"], False)
        self.assertEqual(rich["attachments"], [
            {"entry": 501, "count": 3, "bind": 1},
            {"entry": 100, "count": 50, "bind": 0},
        ])
        self.assertEqual(rich["items"], [{"guid": 9001, "entry": 1201, "stack": 1}])
        self.assertEqual(rich["currency"], [{"entry": 1, "amount": 5}, {"entry": 2, "amount": 1000}])
        # one per attachment, item and currency entry: 2 + 1 + 2
        self.assertEqual(rich["attachment_count"], 5)

        self.assertIsNone(data["mails"][1]["remove_at"])
        self.assertEqual(data["mails"][1]["attachment_count"], 0)

    def test_never_returns_raw_blob_or_internal_keys(self):
        raw = json.dumps(self.get_mail("Rich"))
        for forbidden in ["AAECAw==", "delivery/", "DeliveryKey", "ContentParams", "mailbox", "Attrs"]:
            self.assertNotIn(forbidden, raw)
        keys = set(self.get_mail("Rich")["mails"][0].keys())
        self.assertEqual(keys, {
            "id", "category", "title", "abstract", "content", "sender", "sender_id", "template_id",
            "important_type", "created_at", "remove_at", "read", "claimed", "attachments", "items",
            "currency", "attachment_count",
        })

    def test_same_created_time_breaks_ties_by_id_descending(self):
        self.assertEqual([m["id"] for m in self.get_mail("SameTime")["mails"]], ["c", "b", "a"])

    # --- paging ---

    def test_pagination_defaults_and_slices(self):
        data = self.get_mail("Paged")
        self.assertEqual(data["total"], 25)
        self.assertEqual(data["page"], 1)
        self.assertEqual(data["page_size"], 20)
        self.assertEqual(data["pages"], 2)
        expected = ["p%02d" % i for i in range(24, -1, -1)]
        self.assertEqual([m["id"] for m in data["mails"]], expected[:20])

        collected = []
        for page in range(1, 6):
            chunk = self.get_mail("Paged", page=page, page_size=5)
            self.assertEqual(chunk["pages"], 5)
            collected.extend(m["id"] for m in chunk["mails"])
        self.assertEqual(collected, expected)

        beyond = self.get_mail("Paged", page=9, page_size=5)
        self.assertEqual(beyond["mails"], [])
        self.assertEqual(beyond["total"], 25)

    def test_invalid_paging_params_fall_back_or_clamp(self):
        for params, page, page_size in [
            ({"page": "abc", "page_size": "xyz"}, 1, 20),
            ({"page": "0", "page_size": "0"}, 1, 1),
            ({"page": "-3", "page_size": "100000"}, 1, 100),
        ]:
            with self.subTest(params=params):
                data = self.get_mail("Paged", **params)
                self.assertEqual(data["page"], page)
                self.assertEqual(data["page_size"], page_size)

    # --- empty and undecodable mailboxes ---

    def test_null_empty_and_letterless_mailboxes_are_empty(self):
        for name in ["NullBox", "EmptyBlob", "NoLetters"]:
            with self.subTest(role=name):
                data = self.get_mail(name)
                self.assertTrue(data["decodable"])
                self.assertEqual(data["total"], 0)
                self.assertEqual(data["pages"], 1)
                self.assertEqual(data["mails"], [])

    def test_undecodable_mailbox_returns_200_with_flag(self):
        for name in ["BadUtf8", "BadJson", "NotObject", "BadLetters"]:
            with self.subTest(role=name):
                data = self.get_mail(name)
                self.assertFalse(data["decodable"])
                self.assertEqual(data["total"], 0)
                self.assertEqual(data["mails"], [])
                self.assertTrue(data["message"])

    # --- errors ---

    def test_invalid_role_id_returns_400(self):
        for raw in ["abc", "0", "-1", "1.5", "+1", "%201"]:
            with self.subTest(raw=raw):
                status, data = self.request("/api/admin/characters/%s/mail" % raw)
                self.assertEqual(status, 400)
                self.assertEqual(data["error"], "Invalid character ID")

    def test_unknown_or_deleted_role_returns_404(self):
        for role_id in [999999, self.role_ids["Deleted"]]:
            with self.subTest(role_id=role_id):
                status, data = self.request("/api/admin/characters/%d/mail" % role_id)
                self.assertEqual(status, 404)
                self.assertEqual(data["error"], "Character not found")

    def test_requires_authentication(self):
        status, data = self.request("/api/admin/characters/%d/mail" % self.role_ids["Rich"], auth=False)
        self.assertEqual(status, 401)
        self.assertNotIn("mails", data)

    # --- read-only ---

    def test_requests_do_not_modify_role_table(self):
        before = self.role_snapshot()
        for name in ROLES:
            self.request("/api/admin/characters/%d/mail" % self.role_ids[name], page=2, page_size=3)
        self.request("/api/admin/characters/abc/mail")
        self.assertEqual(self.role_snapshot(), before)

    def test_read_path_runs_with_query_only(self):
        original_get_db = server.get_db
        seen = []

        @contextlib.contextmanager
        def spying_get_db():
            with original_get_db() as con:
                yield con
                seen.append(con.execute("PRAGMA query_only").fetchone()[0])

        with mock.patch.object(server, "get_db", spying_get_db):
            self.get_mail("Rich")
        # Session validation may open its own connection first; the mail read is the last one.
        self.assertTrue(seen)
        self.assertEqual(seen[-1], 1)


if __name__ == "__main__":
    unittest.main()
