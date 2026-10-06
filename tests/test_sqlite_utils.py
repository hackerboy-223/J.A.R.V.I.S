from __future__ import annotations

from contextlib import closing
import tempfile
import unittest
from pathlib import Path

from jarvis.core.sqlite_utils import open_sqlite, prepare_sqlite


class SqliteUtilsTests(unittest.TestCase):
    def test_wal_and_connection_pragmas_are_enabled(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "jarvis.db"
            self.assertEqual(prepare_sqlite(path), "wal")

            with closing(open_sqlite(path)) as db:
                journal = str(db.execute("PRAGMA journal_mode").fetchone()[0]).lower()
                foreign_keys = int(db.execute("PRAGMA foreign_keys").fetchone()[0])
                busy_timeout = int(db.execute("PRAGMA busy_timeout").fetchone()[0])
                synchronous = int(db.execute("PRAGMA synchronous").fetchone()[0])

            self.assertEqual(journal, "wal")
            self.assertEqual(foreign_keys, 1)
            self.assertGreaterEqual(busy_timeout, 10_000)
            # SQLite: 1 = NORMAL
            self.assertEqual(synchronous, 1)


if __name__ == "__main__":
    unittest.main()
