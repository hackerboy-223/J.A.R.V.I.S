from __future__ import annotations

import json
import math
import re
import sqlite3
import threading
import uuid
from pathlib import Path
from typing import Any

from jarvis.config import settings
from jarvis.core.embeddings import EmbeddingClient, cosine_similarity


_TOKEN_RE = re.compile(r"[\wÀ-ÿ'-]{3,}", re.UNICODE)


def _tokens(text: str) -> list[str]:
    return [t.lower() for t in _TOKEN_RE.findall(text)]


class KnowledgeBase:
    """Local text knowledge base with lightweight BM25 retrieval."""

    def __init__(self, db_path: Path) -> None:
        self.db_path = db_path
        self._lock = threading.RLock()
        self.embedding_client = EmbeddingClient()
        self._init_db()

    def _connect(self) -> sqlite3.Connection:
        db = sqlite3.connect(self.db_path)
        db.row_factory = sqlite3.Row
        return db

    def _init_db(self) -> None:
        with self._lock, self._connect() as db:
            db.executescript(
                """
                CREATE TABLE IF NOT EXISTS knowledge_documents (
                    id TEXT PRIMARY KEY,
                    name TEXT NOT NULL,
                    source_path TEXT,
                    size_chars INTEGER NOT NULL,
                    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
                );

                CREATE TABLE IF NOT EXISTS knowledge_chunks (
                    id TEXT PRIMARY KEY,
                    document_id TEXT NOT NULL,
                    chunk_index INTEGER NOT NULL,
                    text TEXT NOT NULL,
                    FOREIGN KEY(document_id) REFERENCES knowledge_documents(id)
                );

                CREATE INDEX IF NOT EXISTS idx_knowledge_chunks_doc
                ON knowledge_chunks(document_id);
                """
            )
            columns = {
                str(row["name"])
                for row in db.execute("PRAGMA table_info(knowledge_chunks)").fetchall()
            }
            if "embedding_json" not in columns:
                db.execute("ALTER TABLE knowledge_chunks ADD COLUMN embedding_json TEXT")
            db.commit()

    @staticmethod
    def chunk_text(text: str, chunk_words: int = 650, overlap_words: int = 120) -> list[str]:
        words = text.split()
        if not words:
            return []

        step = max(1, chunk_words - overlap_words)
        chunks: list[str] = []
        for start in range(0, len(words), step):
            piece = " ".join(words[start : start + chunk_words]).strip()
            if len(piece) >= 40:
                chunks.append(piece)
            if start + chunk_words >= len(words):
                break
        return chunks

    def add_text(self, name: str, text: str, source_path: str | None = None) -> dict[str, Any]:
        clean = text.strip()
        if len(clean) < 10:
            raise ValueError("Le document est vide ou trop court.")

        doc_id = uuid.uuid4().hex
        chunks = self.chunk_text(clean)
        if not chunks:
            raise ValueError("Impossible de découper ce document.")

        vectors: list[list[float]] = []
        if self.embedding_client.enabled:
            try:
                vectors = self.embedding_client.embed_many(chunks)
            except Exception:
                vectors = []

        with self._lock, self._connect() as db:
            db.execute(
                """
                INSERT INTO knowledge_documents(id, name, source_path, size_chars)
                VALUES (?, ?, ?, ?)
                """,
                (doc_id, name[:240], source_path, len(clean)),
            )
            db.executemany(
                """
                INSERT INTO knowledge_chunks(
                    id, document_id, chunk_index, text, embedding_json
                )
                VALUES (?, ?, ?, ?, ?)
                """,
                [
                    (
                        f"{doc_id}:{index}",
                        doc_id,
                        index,
                        chunk,
                        (
                            json.dumps(vectors[index])
                            if index < len(vectors)
                            else None
                        ),
                    )
                    for index, chunk in enumerate(chunks)
                ],
            )
            db.commit()

        return {
            "id": doc_id,
            "name": name,
            "chunks": len(chunks),
            "size_chars": len(clean),
        }

    def add_file(self, path: Path) -> dict[str, Any]:
        allowed = {
            ".txt", ".md", ".csv", ".json", ".py", ".js", ".ts", ".tsx",
            ".jsx", ".html", ".xml", ".log", ".yaml", ".yml", ".sql", ".ps1",
        }
        suffix = path.suffix.lower()
        if suffix not in allowed:
            raise ValueError(f"Type de fichier non pris en charge : {suffix or '(aucune extension)'}")

        if path.stat().st_size > 10 * 1024 * 1024:
            raise ValueError("Document trop volumineux (10 Mo max).")

        text = path.read_text(encoding="utf-8", errors="replace")
        return self.add_text(path.name, text, str(path))

    def list_documents(self) -> list[dict[str, Any]]:
        with self._lock, self._connect() as db:
            rows = db.execute(
                """
                SELECT d.id, d.name, d.source_path, d.size_chars, d.created_at,
                       COUNT(c.id) AS chunks
                FROM knowledge_documents d
                LEFT JOIN knowledge_chunks c ON c.document_id = d.id
                GROUP BY d.id
                ORDER BY d.created_at DESC
                """
            ).fetchall()
        return [dict(row) for row in rows]

    def remove_document(self, doc_id: str) -> None:
        with self._lock, self._connect() as db:
            db.execute("DELETE FROM knowledge_chunks WHERE document_id = ?", (doc_id,))
            db.execute("DELETE FROM knowledge_documents WHERE id = ?", (doc_id,))
            db.commit()

    def search(self, query: str, top_k: int = 5) -> list[dict[str, Any]]:
        q_tokens = _tokens(query)
        if not q_tokens:
            return []

        with self._lock, self._connect() as db:
            rows = db.execute(
                """
                SELECT c.id, c.document_id, c.chunk_index, c.text,
                       c.embedding_json, d.name
                FROM knowledge_chunks c
                JOIN knowledge_documents d ON d.id = c.document_id
                """
            ).fetchall()

        if not rows:
            return []

        docs = []
        for row in rows:
            text = str(row["text"])
            tokens = _tokens(text)
            docs.append((row, tokens))

        n_docs = len(docs)
        avg_len = sum(len(tokens) for _, tokens in docs) / max(1, n_docs)
        k1 = 1.5
        b = 0.75

        doc_freq: dict[str, int] = {}
        for token in set(q_tokens):
            doc_freq[token] = sum(1 for _, tokens in docs if token in set(tokens))

        query_vector: list[float] | None = None
        if self.embedding_client.enabled:
            try:
                query_vector = self.embedding_client.embed(query)
            except Exception:
                query_vector = None

        lexical_rows: list[tuple[float, float, sqlite3.Row]] = []
        for row, tokens in docs:
            if not tokens:
                continue
            score = 0.0
            dl = len(tokens)
            counts: dict[str, int] = {}
            for token in tokens:
                counts[token] = counts.get(token, 0) + 1

            for token in q_tokens:
                tf = counts.get(token, 0)
                if tf <= 0:
                    continue
                df = doc_freq.get(token, 0)
                idf = math.log(1.0 + (n_docs - df + 0.5) / (df + 0.5))
                denom = tf + k1 * (1.0 - b + b * dl / max(1.0, avg_len))
                score += idf * (tf * (k1 + 1.0) / denom)

            dense = 0.0
            raw_embedding = row["embedding_json"]
            if query_vector is not None and raw_embedding:
                try:
                    vector = json.loads(str(raw_embedding))
                    if isinstance(vector, list):
                        dense = max(0.0, cosine_similarity(query_vector, vector))
                except (json.JSONDecodeError, TypeError, ValueError):
                    dense = 0.0

            if score > 0 or dense > 0:
                lexical_rows.append((score, dense, row))

        max_bm25 = max((item[0] for item in lexical_rows), default=0.0)
        dense_weight = settings.hybrid_dense_weight if query_vector is not None else 0.0
        combined: list[tuple[float, float, float, sqlite3.Row]] = []
        for bm25, dense, row in lexical_rows:
            bm25_norm = bm25 / max_bm25 if max_bm25 > 0 else 0.0
            hybrid = (1.0 - dense_weight) * bm25_norm + dense_weight * dense
            combined.append((hybrid, bm25, dense, row))

        combined.sort(key=lambda item: item[0], reverse=True)

        return [
            {
                "score": round(hybrid, 4),
                "bm25_score": round(bm25, 4),
                "dense_score": round(dense, 4),
                "retrieval": "hybrid" if dense_weight > 0 else "bm25",
                "document_id": row["document_id"],
                "document": row["name"],
                "chunk_index": row["chunk_index"],
                "text": str(row["text"])[:2200],
            }
            for hybrid, bm25, dense, row
            in combined[: max(1, min(top_k, 12))]
        ]

    def context_for(self, query: str, top_k: int = 5) -> str:
        results = self.search(query, top_k=top_k)
        if not results:
            return ""

        parts = ["=== KNOWLEDGE BASE ==="]
        for item in results:
            parts.append(
                f"[Document: {item['document']}]\n{item['text']}"
            )
        parts.append(
            "Use this local knowledge when relevant. Mention the document name when relying on it."
        )
        return "\n\n".join(parts)
