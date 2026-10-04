from __future__ import annotations

from contextlib import closing
from datetime import datetime, timezone
from pathlib import Path
import shutil
import sqlite3
from typing import Any

from jarvis.config import DATA_DIR, settings


def _table_exists(db: sqlite3.Connection, name: str) -> bool:
    row = db.execute(
        "SELECT 1 FROM sqlite_master WHERE type='table' AND name=?",
        (name,),
    ).fetchone()
    return row is not None


def import_prisma_database(source_path: str | Path) -> dict[str, Any]:
    source = Path(source_path).expanduser().resolve()
    if not source.exists() or not source.is_file():
        raise FileNotFoundError("Base Prisma source introuvable.")
    if source == settings.database_path.resolve():
        raise ValueError("La base source ne peut pas être la base Python active.")

    backups = DATA_DIR / "backups"
    backups.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    backup = backups / f"prisma-before-import-{stamp}.db"
    shutil.copy2(source, backup)

    with closing(sqlite3.connect(source)) as old:
        old.row_factory = sqlite3.Row
        if not _table_exists(old, "Conversation") or not _table_exists(old, "Message"):
            raise ValueError(
                "La base ne contient pas les tables Prisma Conversation et Message attendues."
            )
        conversations = [
            dict(row)
            for row in old.execute("SELECT * FROM Conversation ORDER BY createdAt").fetchall()
        ]
        messages = [
            dict(row)
            for row in old.execute("SELECT * FROM Message ORDER BY createdAt").fetchall()
        ]

    with closing(sqlite3.connect(settings.database_path, timeout=10)) as db:
        db.executescript(
            """
            CREATE TABLE IF NOT EXISTS imported_conversations (
                source_id TEXT PRIMARY KEY,
                title TEXT,
                model TEXT,
                engine TEXT,
                created_at TEXT,
                updated_at TEXT,
                imported_at DATETIME DEFAULT CURRENT_TIMESTAMP
            );
            CREATE TABLE IF NOT EXISTS imported_messages (
                source_id TEXT PRIMARY KEY,
                conversation_source_id TEXT,
                role TEXT,
                content TEXT,
                tool_name TEXT,
                tool_args TEXT,
                tool_result TEXT,
                step INTEGER,
                duration_ms INTEGER,
                created_at TEXT,
                imported_at DATETIME DEFAULT CURRENT_TIMESTAMP
            );
            CREATE TABLE IF NOT EXISTS migration_runs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                source_path TEXT NOT NULL,
                source_backup TEXT NOT NULL,
                conversations INTEGER NOT NULL,
                messages INTEGER NOT NULL,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP
            );
            """
        )

        for item in conversations:
            db.execute(
                """
                INSERT OR IGNORE INTO imported_conversations(
                    source_id, title, model, engine, created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    item.get("id"),
                    item.get("title"),
                    item.get("model"),
                    item.get("engine"),
                    item.get("createdAt"),
                    item.get("updatedAt"),
                ),
            )

        for item in messages:
            db.execute(
                """
                INSERT OR IGNORE INTO imported_messages(
                    source_id, conversation_source_id, role, content,
                    tool_name, tool_args, tool_result, step, duration_ms, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    item.get("id"),
                    item.get("conversationId"),
                    item.get("role"),
                    item.get("content"),
                    item.get("toolName"),
                    item.get("toolArgs"),
                    item.get("toolResult"),
                    item.get("step"),
                    item.get("durationMs"),
                    item.get("createdAt"),
                ),
            )

        db.execute(
            """
            INSERT INTO migration_runs(
                source_path, source_backup, conversations, messages
            ) VALUES (?, ?, ?, ?)
            """,
            (str(source), str(backup), len(conversations), len(messages)),
        )
        db.commit()

    return {
        "source": str(source),
        "backup": str(backup),
        "conversations": len(conversations),
        "messages": len(messages),
        "idempotent": True,
    }
