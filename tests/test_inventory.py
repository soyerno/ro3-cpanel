"""HTTP-level tests for the read-only character inventory endpoint.

GET /api/admin/characters/<role_id>/items
"""

import contextlib
import io
import json
import os
import sqlite3
import sys
import tempfile
import threading
import unittest
import urllib.error
import urllib.request
from http.server import ThreadingHTTPServer

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
import server

ADMIN_USER = "boss"
ADMIN_PASS = "Pw-123456"

# Mirrors aethai/ro3emu-server src/Ro3Emu.Server/Accounts/Persistence/CoreSchemaPlans.cs
# (ItemSchemaPlan: base CREATE TABLE plus the columns it adds with ALTER TABLE).
ITEM_TABLE_SQL = """
    CREATE TABLE item (
        guid    INTEGER PRIMARY KEY AUTOINCREMENT,
        role_id INTEGER NOT NULL,
        entry   INTEGER NOT NULL,
        stack   INTEGER NOT NULL,
        pack    INTEGER NOT NULL,
        sort    INTEGER NOT NULL,
        grid    INTEGER NOT NULL DEFAULT 0,
        attrs TEXT,
        enchantments TEXT,
        is_locked INTEGER NOT NULL DEFAULT 0,
        str_attrs TEXT,
        bind_type INTEGER NOT NULL DEFAULT 0,
        bind_expire INTEGER NOT NULL DEFAULT 0
    )
"""

ITEM_ROWS = [
    # guid, role_id, entry, stack, pack, sort, grid, is_locked, bind_type
    (1000001, 1, 100001, 5, 1, 1, 0, 0, 0),
    (1000002, 1, 200002, 1, 2, 1, 0, 1, 1),
    (1000003, 1, 999999, 1, 3, 1, 0, 0, 0),
    (1000004, 2, 100001, 9, 1, 1, 0, 0, 0),
    (1000005, 3, 100001, 7, 1, 1, 0, 0, 0),
    (1000006, 2, 300003, 1, 2, 2, 5, 0, 0),
]


class _QuietHandler(server.CPanelRequestHandler):
    def log_message(self, format, *args):
        pass


class InventoryEndpointTests(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory(ignore_cleanup_errors=True)
        self.addCleanup(tmp.cleanup)
        self.tmpdir = tmp.name
        self.db_path = os.path.join(self.tmpdir, "ro3emu.db")

        # Register restores BEFORE mutating module globals.
        self.addCleanup(setattr, server, "DB_PATH", server.DB_PATH)
        self.addCleanup(setattr, server, "CONFIG", server.CONFIG)
        self.addCleanup(setattr, server, "ACTIVE_SESSIONS", server.ACTIVE_SESSIONS)
        names_state = getattr(server, "ITEM_NAMES_STATE", None)
        if names_state is not None:
            snapshot = {k: (set(v) if isinstance(v, set) else v) for k, v in names_state.items()}

            def restore_names_state():
                names_state.clear()
                names_state.update(snapshot)

            self.addCleanup(restore_names_state)
            names_state.update({"key": None, "names": None, "warned": set()})

        server.DB_PATH = self.db_path
        server.CONFIG = dict(server.CONFIG)
        server.CONFIG["admin_users"] = [{"username": ADMIN_USER, "password": ADMIN_PASS}]
        server.CONFIG["item_names_file"] = ""
        server.ACTIVE_SESSIONS = {}

        self._create_db(with_items=True)
        server.init_tables()

        self.httpd = ThreadingHTTPServer(("127.0.0.1", 0), _QuietHandler)
        thread = threading.Thread(target=self.httpd.serve_forever, daemon=True)
        thread.start()

        def stop_server():
            self.httpd.shutdown()
            self.httpd.server_close()
            thread.join(timeout=10)

        self.addCleanup(stop_server)
        self.base_url = "http://127.0.0.1:%d" % self.httpd.server_address[1]
        self.token = self._login()

    # --- fixtures -------------------------------------------------------

    def _create_db(self, with_items):
        with contextlib.closing(sqlite3.connect(self.db_path)) as con:
            con.execute("CREATE TABLE account (name TEXT PRIMARY KEY, password_hash BLOB, salt BLOB, created_utc TEXT)")
            con.execute("CREATE TABLE auth_token (token TEXT PRIMARY KEY, kind TEXT, expires_utc TEXT, account TEXT)")
            con.execute(
                "CREATE TABLE role (id INTEGER PRIMARY KEY, account TEXT, name TEXT, sex INTEGER, career INTEGER, "
                "level INTEGER, job_level INTEGER, last_login_time INTEGER, create_time INTEGER, currency TEXT, "
                "stats TEXT, scene_entry INTEGER, pos_x REAL, pos_y REAL, pos_z REAL, deleted_time INTEGER DEFAULT 0)"
            )
            con.execute("INSERT INTO account (name, created_utc) VALUES ('alice', '2026-01-01T00:00:00Z')")
            con.execute("INSERT INTO account (name, created_utc) VALUES ('bob', '2026-01-01T00:00:00Z')")
            con.execute("INSERT INTO role (id, account, name, deleted_time) VALUES (1, 'alice', 'Aria', 0)")
            con.execute("INSERT INTO role (id, account, name, deleted_time) VALUES (2, 'bob', 'Bram', 0)")
            con.execute("INSERT INTO role (id, account, name, deleted_time) VALUES (3, 'alice', 'Gone', 1790000000)")
            if with_items:
                con.execute(ITEM_TABLE_SQL)
                con.executemany(
                    "INSERT INTO item (guid, role_id, entry, stack, pack, sort, grid, is_locked, bind_type) "
                    "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
                    ITEM_ROWS,
                )
            con.commit()

    def _item_snapshot(self):
        with contextlib.closing(sqlite3.connect(self.db_path)) as con:
            return con.execute("SELECT * FROM item ORDER BY guid").fetchall()

    def _write_names_file(self, content):
        path = os.path.join(self.tmpdir, "item_names.json")
        with open(path, "w", encoding="utf-8") as f:
            f.write(content)
        server.CONFIG["item_names_file"] = path
        return path

    # --- HTTP helpers ---------------------------------------------------

    def _request(self, path, method="GET", body=None, token=None):
        headers = {}
        data = None
        if body is not None:
            data = json.dumps(body).encode("utf-8")
            headers["Content-Type"] = "application/json"
        if token:
            headers["Authorization"] = "Bearer " + token
        req = urllib.request.Request(self.base_url + path, data=data, headers=headers, method=method)
        try:
            with urllib.request.urlopen(req, timeout=10) as resp:
                return resp.status, json.loads(resp.read().decode("utf-8"))
        except urllib.error.HTTPError as err:
            with err:
                return err.code, json.loads(err.read().decode("utf-8"))

    def _login(self):
        status, data = self._request(
            "/api/admin/login", method="POST", body={"username": ADMIN_USER, "password": ADMIN_PASS}
        )
        self.assertEqual(status, 200, data)
        return data["token"]

    def _get_items(self, role_id):
        return self._request("/api/admin/characters/%s/items" % role_id, token=self.token)

    # --- tests ----------------------------------------------------------

    def test_lists_only_items_of_requested_role(self):
        status, data = self._get_items(1)
        self.assertEqual(status, 200, data)
        self.assertEqual(data["character"], {"id": 1, "name": "Aria", "account": "alice"})
        self.assertTrue(data["available"])
        self.assertEqual(data["total"], 3)
        self.assertEqual(sorted(i["guid"] for i in data["items"]), [1000001, 1000002, 1000003])
        by_guid = {i["guid"]: i for i in data["items"]}
        self.assertEqual(by_guid[1000001]["entry"], 100001)
        self.assertEqual(by_guid[1000001]["stack"], 5)
        self.assertEqual(by_guid[1000001]["pack"], 1)
        self.assertEqual(by_guid[1000001]["pack_name"], "Objetos")
        self.assertFalse(by_guid[1000001]["locked"])
        self.assertTrue(by_guid[1000002]["locked"])
        self.assertEqual(by_guid[1000002]["bind_type"], 1)
        self.assertEqual(by_guid[1000002]["pack_name"], "Equipo")
        self.assertEqual(by_guid[1000003]["pack_name"], "Cartas")

    def test_equipped_flag_follows_grid_and_unknown_pack_has_null_name(self):
        with contextlib.closing(sqlite3.connect(self.db_path)) as con:
            con.execute(
                "INSERT INTO item (guid, role_id, entry, stack, pack, sort, grid) VALUES (1000007, 2, 1, 1, 77, 1, 0)"
            )
            con.commit()
        status, data = self._get_items(2)
        self.assertEqual(status, 200, data)
        by_guid = {i["guid"]: i for i in data["items"]}
        self.assertEqual(data["total"], 3)
        self.assertFalse(by_guid[1000004]["equipped"])
        self.assertTrue(by_guid[1000006]["equipped"])
        self.assertEqual(by_guid[1000007]["pack"], 77)
        self.assertIsNone(by_guid[1000007]["pack_name"])

    def test_names_null_when_no_names_file_configured(self):
        status, data = self._get_items(1)
        self.assertEqual(status, 200, data)
        self.assertTrue(all(i["name"] is None for i in data["items"]))

    def test_names_resolved_from_names_file_and_unknown_entry_is_null(self):
        self._write_names_file(json.dumps({"100001": "Poción Roja", "200002": "Espada <b>"}))
        status, data = self._get_items(1)
        self.assertEqual(status, 200, data)
        by_entry = {i["entry"]: i for i in data["items"]}
        self.assertEqual(by_entry[100001]["name"], "Poción Roja")
        self.assertEqual(by_entry[200002]["name"], "Espada <b>")
        self.assertIsNone(by_entry[999999]["name"])

    def test_malformed_names_file_falls_back_to_null_with_single_warning(self):
        self._write_names_file("{not valid json")
        stderr = io.StringIO()
        with contextlib.redirect_stderr(stderr):
            first_status, first = self._get_items(1)
            second_status, second = self._get_items(1)
        self.assertEqual(first_status, 200, first)
        self.assertEqual(second_status, 200, second)
        self.assertTrue(all(i["name"] is None for i in first["items"] + second["items"]))
        self.assertEqual(stderr.getvalue().count("item_names_file"), 1, stderr.getvalue())

    def test_names_file_that_is_not_an_object_is_ignored(self):
        self._write_names_file(json.dumps(["Poción Roja"]))
        with contextlib.redirect_stderr(io.StringIO()):
            status, data = self._get_items(1)
        self.assertEqual(status, 200, data)
        self.assertTrue(all(i["name"] is None for i in data["items"]))

    def test_missing_names_file_falls_back_to_null(self):
        server.CONFIG["item_names_file"] = os.path.join(self.tmpdir, "does-not-exist.json")
        with contextlib.redirect_stderr(io.StringIO()):
            status, data = self._get_items(1)
        self.assertEqual(status, 200, data)
        self.assertTrue(all(i["name"] is None for i in data["items"]))

    def test_invalid_role_id_returns_400(self):
        for bad in ["abc", "0", "-1", "1.5", "99999999999999999999999"]:
            with self.subTest(role_id=bad):
                status, data = self._get_items(bad)
                self.assertEqual(status, 400, data)
                self.assertIn("error", data)
                self.assertIn("personaje", data["error"].lower())

    def test_unknown_role_returns_404(self):
        status, data = self._get_items(4242)
        self.assertEqual(status, 404, data)
        self.assertEqual(data["error"], "Personaje no encontrado")

    def test_deleted_role_returns_404(self):
        status, data = self._get_items(3)
        self.assertEqual(status, 404, data)
        self.assertEqual(data["error"], "Personaje no encontrado")

    def test_missing_item_table_reports_unavailable(self):
        with contextlib.closing(sqlite3.connect(self.db_path)) as con:
            con.execute("DROP TABLE item")
            con.commit()
        status, data = self._get_items(1)
        self.assertEqual(status, 200, data)
        self.assertEqual(data["items"], [])
        self.assertEqual(data["total"], 0)
        self.assertFalse(data["available"])
        self.assertEqual(data["character"]["id"], 1)

    def test_unauthenticated_request_returns_401(self):
        status, data = self._request("/api/admin/characters/1/items")
        self.assertEqual(status, 401, data)
        self.assertIn("error", data)

    def test_item_table_is_unchanged_after_requests(self):
        before = self._item_snapshot()
        self._write_names_file(json.dumps({"100001": "Poción Roja"}))
        for role_id in ["1", "2", "3", "abc", "4242"]:
            self._get_items(role_id)
        self.assertEqual(self._item_snapshot(), before)

    def test_existing_account_detail_still_works(self):
        status, data = self._request("/api/admin/accounts/alice", token=self.token)
        self.assertEqual(status, 200, data)
        self.assertEqual(sorted(c["id"] for c in data["characters"]), [1])


if __name__ == "__main__":
    unittest.main()
