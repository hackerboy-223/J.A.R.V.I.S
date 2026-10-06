from __future__ import annotations

from contextlib import closing
from pathlib import Path
import json
import sqlite3
from typing import Any

from jarvis.core.sqlite_utils import open_sqlite, prepare_sqlite


class PrismaImporter:
    """Idempotent importer for the legacy Prisma SQLite conversation database."""

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
                """
                SELECT id, title, model, engine, createdAt, updatedAt
                FROM "Conversation"
                ORDER BY createdAt
                """
            ).fetchall()
            messages = old.execute(
                """
                SELECT id, role, content, toolName, toolArgs, toolResult,
                       step, durationMs, conversationId, createdAt
                FROM "Message"
                ORDER BY createdAt
                """
            ).fetchall()

        prepare_sqlite(target)
        with closing(open_sqlite(target)) as new:
            new.executescript(
                """
                CREATE TABLE IF NOT EXISTS legacy_conversations (
                    source_id TEXT PRIMARY KEY,
                    title TEXT NOT NULL,
                    model TEXT,
                    engine TEXT,
                    created_at TEXT,
                    updated_at TEXT,
                    imported_at DATETIME DEFAULT CURRENT_TIMESTAMP
                );
                CREATE TABLE IF NOT EXISTS legacy_messages (
                    source_id TEXT PRIMARY KEY,
                    conversation_source_id TEXT NOT NULL,
                    role TEXT NOT NULL,
                    content TEXT NOT NULL,
                    tool_name TEXT,
                    tool_args TEXT,
                    tool_result TEXT,
                    step INTEGER,
                    duration_ms INTEGER,
                    created_at TEXT,
                    imported_at DATETIME DEFAULT CURRENT_TIMESTAMP
                );
                CREATE INDEX IF NOT EXISTS idx_legacy_messages_conversation
                ON legacy_messages(conversation_source_id, created_at);
                """
            )

            imported_conversations = 0
            for row in conversations:
                cur = new.execute(
                    """
                    INSERT OR IGNORE INTO legacy_conversations(
                        source_id, title, model, engine, created_at, updated_at
                    ) VALUES(?,?,?,?,?,?)
                    """,
                    (
                        str(row["id"]),
                        str(row["title"] or "Conversation importée"),
                        row["model"],
                        row["engine"],
                        str(row["createdAt"] or ""),
                        str(row["updatedAt"] or ""),
                    ),
                )
                imported_conversations += int(cur.rowcount > 0)

            imported_messages = 0
            for row in messages:
                cur = new.execute(
                    """
                    INSERT OR IGNORE INTO legacy_messages(
                        source_id, conversation_source_id, role, content,
                        tool_name, tool_args, tool_result, step, duration_ms, created_at
                    ) VALUES(?,?,?,?,?,?,?,?,?,?)
                    """,
                    (
                        str(row["id"]),
                        str(row["conversationId"]),
                        str(row["role"] or "assistant"),
                        str(row["content"] or ""),
                        row["toolName"],
                        row["toolArgs"],
                        row["toolResult"],
                        int(row["step"] or 0),
                        row["durationMs"],
                        str(row["createdAt"] or ""),
                    ),
                )
                imported_messages += int(cur.rowcount > 0)

            new.execute(
                """
                CREATE TABLE IF NOT EXISTS migration_runs (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    source_path TEXT NOT NULL,
                    conversations_seen INTEGER NOT NULL,
                    messages_seen INTEGER NOT NULL,
                    imported_conversations INTEGER NOT NULL,
                    imported_messages INTEGER NOT NULL,
                    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
                )
                """
            )
            new.execute(
                """
                INSERT INTO migration_runs(
                    source_path, conversations_seen, messages_seen,
                    imported_conversations, imported_messages
                ) VALUES(?,?,?,?,?)
                """,
                (
                    str(source),
                    len(conversations),
                    len(messages),
                    imported_conversations,
                    imported_messages,
                ),
            )
            new.commit()

        return {
            "source": str(source),
            "conversations_seen": len(conversations),
            "messages_seen": len(messages),
            "conversations_imported": imported_conversations,
            "messages_imported": imported_messages,
        }
