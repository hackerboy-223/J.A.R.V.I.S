from __future__ import annotations

from contextlib import closing
from pathlib import Path
import json
import sqlite3
from typing import Any


class PrismaImporter:
    """Read-only importer for the legacy Prisma SQLite conversation database."""

    def import_into(self, source: Path, target: Path) -> dict[str, Any]:
        source = source.expanduser().resolve()
        target = target.expanduser().resolve()
        if source == target:
            raise ValueError("La source et la destination doivent être différentes.")
        if not source.exists():
            raise FileNotFoundError(source)

        with closing(sqlite3.connect(source)) as old:
            old.row_factory = sqlite3.Row
            tables = {
                str(row[0])
                for row in old.execute(
                    "SELECT name FROM sqlite_master WHERE type='table'"
                ).fetchall()
            }
            if not {"Conversation", "Message"}.issubset(tables):
                raise ValueError("Base Prisma JARVIS non reconnue.")
            conversations = old.execute(
                'SELECT id, title, createdAt, updatedAt FROM "Conversation"'
            ).fetchall()
            messages = old.execute(
                'SELECT role, content, createdAt, conversationId FROM "Message" ORDER BY createdAt'
            ).fetchall()

        with closing(sqlite3.connect(target, timeout=10)) as new:
            new.execute(
                """
                CREATE TABLE IF NOT EXISTS legacy_imports (
                    source_id TEXT PRIMARY KEY,
                    kind TEXT NOT NULL,
                    payload_json TEXT NOT NULL,
                    imported_at DATETIME DEFAULT CURRENT_TIMESTAMP
                )
                """
            )
            for row in conversations:
                new.execute(
                    "INSERT OR IGNORE INTO legacy_imports(source_id, kind, payload_json) VALUES(?,?,?)",
                    (
                        str(row["id"]),
                        "conversation",
                        json.dumps(dict(row), ensure_ascii=False, default=str),
                    ),
                )
            imported_messages = 0
            for index, row in enumerate(messages):
                source_id = f'{row["conversationId"]}:message:{index}:{row["createdAt"]}'
                cur = new.execute(
                    "INSERT OR IGNORE INTO legacy_imports(source_id, kind, payload_json) VALUES(?,?,?)",
                    (
                        source_id,
                        "message",
                        json.dumps(dict(row), ensure_ascii=False, default=str),
                    ),
                )
                imported_messages += int(cur.rowcount > 0)
            new.commit()

        return {
            "conversations_seen": len(conversations),
            "messages_seen": len(messages),
            "messages_imported": imported_messages,
        }
