from __future__ import annotations

import math
from typing import Any

import httpx

from jarvis.config import settings
from jarvis.core.network import service_endpoint


class EmbeddingClient:
    """Optional OpenAI-compatible embeddings client."""

    @property
    def enabled(self) -> bool:
        return bool(settings.embedding_model and settings.embedding_base_url)

    def embed_many(self, texts: list[str]) -> list[list[float]]:
        if not texts:
            return []
        if not self.enabled:
            return []

        endpoint = service_endpoint(settings.embedding_base_url, "embeddings", label="embeddings")
        headers = {"Content-Type": "application/json"}
        if settings.embedding_api_key:
            headers["Authorization"] = f"Bearer {settings.embedding_api_key}"

        response = httpx.post(
            endpoint,
            headers=headers,
            json={
                "model": settings.embedding_model,
                "input": texts,
            },
            timeout=45,
        )
        response.raise_for_status()
        data = response.json().get("data", [])
        vectors = [item.get("embedding") for item in data]
        if len(vectors) != len(texts) or not all(isinstance(v, list) for v in vectors):
            raise RuntimeError("Réponse embeddings invalide.")
        return [[float(x) for x in vector] for vector in vectors]

    def embed(self, text: str) -> list[float] | None:
        vectors = self.embed_many([text])
        return vectors[0] if vectors else None


def cosine_similarity(a: list[float], b: list[float]) -> float:
    if not a or not b or len(a) != len(b):
        return 0.0
    dot = sum(x * y for x, y in zip(a, b))
    na = math.sqrt(sum(x * x for x in a))
    nb = math.sqrt(sum(y * y for y in b))
    if na <= 0 or nb <= 0:
        return 0.0
    return dot / (na * nb)
