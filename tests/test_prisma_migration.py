from __future__ import annotations

import sqlite3
import tempfile
import unittest
from pathlib import Path

from jarvis.core.migration import PrismaImporter


class PrismaMigrationTests(unittest.TestCase):
    def test_import_is_idempotent(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            source = Path(temp_dir) / "legacy.db"
            target = Path(temp_dir) / "jarvis.db"
            db = sqlite3.connect(source)
            db.executescript(
                """
                CREATE TABLE Conversation(
                    id TEXT PRIMARY KEY,
                    title TEXT,
                    model TEXT,
                    engine TEXT,
                    createdAt TEXT,
                    updatedAt TEXT
                );
                CREATE TABLE Message(
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
                INSERT INTO Conversation VALUES('c1','Demo','jarvis','auto','2026','2026');
                INSERT INTO Message VALUES('m1','user','Bonjour',NULL,NULL,NULL,0,NULL,'c1','2026');
                """
            )
            db.commit()
            db.close()

            importer = PrismaImporter()
            first = importer.import_into(source, target)
            second = importer.import_into(source, target)
            self.assertEqual(first["conversations_seen"], 1)
            self.assertEqual(first["messages_seen"], 1)
            self.assertEqual(first["conversations_imported"], 1)
            self.assertEqual(first["messages_imported"], 1)
            self.assertEqual(second["conversations_imported"], 0)
            self.assertEqual(second["messages_imported"], 0)


if __name__ == "__main__":
    unittest.main()
