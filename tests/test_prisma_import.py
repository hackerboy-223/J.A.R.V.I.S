from __future__ import annotations

from contextlib import closing
from pathlib import Path
import sqlite3
from types import SimpleNamespace
import tempfile
import unittest

import jarvis.migrations.prisma_import as prisma_import


class PrismaImportTests(unittest.TestCase):
    def test_import_is_idempotent_and_backed_up(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            source = root / "old.db"
            target = root / "new.db"
            data = root / "data"

            with closing(sqlite3.connect(source)) as db:
                db.executescript(
                    """
                    CREATE TABLE Conversation (
                        id TEXT PRIMARY KEY,
                        title TEXT,
                        model TEXT,
                        engine TEXT,
                        createdAt TEXT,
                        updatedAt TEXT
                    );
                    CREATE TABLE Message (
                        id TEXT PRIMARY KEY,
                        role TEXT,
                        content TEXT,
                        toolName TEXT,
                        toolArgs TEXT,
                        toolResult TEXT,
                        step INTEGER,
                        durationMs INTEGER,
                        conversationId TEXT,
                        createdAt TEXT
                    );
                    """
                )
                db.execute(
                    "INSERT INTO Conversation VALUES (?,?,?,?,?,?)",
                    ("c1", "Demo", "m", "core", "a", "b"),
                )
                db.execute(
                    "INSERT INTO Message VALUES (?,?,?,?,?,?,?,?,?,?)",
                    ("m1", "user", "hello", None, None, None, 0, None, "c1", "a"),
                )
                db.commit()

            old_settings = prisma_import.settings
            old_data_dir = prisma_import.DATA_DIR
            try:
                prisma_import.settings = SimpleNamespace(database_path=target)
                prisma_import.DATA_DIR = data
                first = prisma_import.import_prisma_database(source)
                second = prisma_import.import_prisma_database(source)
            finally:
                prisma_import.settings = old_settings
                prisma_import.DATA_DIR = old_data_dir

            self.assertEqual(first["conversations"], 1)
            self.assertEqual(second["messages"], 1)
            self.assertTrue(Path(first["backup"]).exists())

            with closing(sqlite3.connect(target)) as db:
                conversations = db.execute(
                    "SELECT COUNT(*) FROM imported_conversations"
                ).fetchone()[0]
                messages = db.execute(
                    "SELECT COUNT(*) FROM imported_messages"
                ).fetchone()[0]
            self.assertEqual(conversations, 1)
            self.assertEqual(messages, 1)


if __name__ == "__main__":
    unittest.main()
