import os
import sqlite3
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
import server


class TestGetDb(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        db_path = os.path.join(self.tmp.name, "ro3emu.db")
        con = sqlite3.connect(db_path)
        con.execute("CREATE TABLE t (v INTEGER)")
        con.commit()
        con.close()
        saved = server.DB_PATH
        server.DB_PATH = db_path
        self.addCleanup(setattr, server, "DB_PATH", saved)

    def _count(self):
        with server.get_db() as con:
            return con.execute("SELECT COUNT(*) FROM t").fetchone()[0]

    def test_connection_is_closed_when_the_block_exits(self):
        # An open handle keeps the file locked on Windows.
        with server.get_db() as con:
            con.execute("SELECT 1")
        with self.assertRaises(sqlite3.ProgrammingError):
            con.execute("SELECT 1")

    def test_changes_are_committed_when_the_block_succeeds(self):
        with server.get_db() as con:
            con.execute("INSERT INTO t VALUES (1)")
        self.assertEqual(self._count(), 1)

    def test_changes_are_rolled_back_when_the_block_raises(self):
        with self.assertRaises(RuntimeError):
            with server.get_db() as con:
                con.execute("INSERT INTO t VALUES (1)")
                raise RuntimeError("boom")
        self.assertEqual(self._count(), 0)

    def test_rows_are_accessible_by_column_name(self):
        with server.get_db() as con:
            con.execute("INSERT INTO t VALUES (7)")
            self.assertEqual(con.execute("SELECT v FROM t").fetchone()["v"], 7)


if __name__ == "__main__":
    unittest.main()
