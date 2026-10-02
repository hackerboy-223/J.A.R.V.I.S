from __future__ import annotations

from typing import Any

import httpx

from jarvis.config import settings


class LLMClient:
    def __init__(self) -> None:
        self.base_url = settings.llm_base_url.rstrip("/")
        self.api_key = settings.llm_api_key
        self.model = settings.llm_model

    def _is_local(self) -> bool:
        return "localhost" in self.base_url or "127.0.0.1" in self.base_url

    def complete(
        self,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]] | None = None,
    ) -> dict[str, Any]:
        if not self.api_key and not self._is_local():
            return {
                "message": {
                    "role": "assistant",
                    "content": (
                        "Le noyau Python est opérationnel, mais aucun cerveau LLM n'est configuré. "
                        "Ajoute JARVIS_LLM_API_KEY, JARVIS_LLM_BASE_URL et JARVIS_LLM_MODEL."
                    ),
                }
            }

        payload: dict[str, Any] = {
            "model": self.model,
            "messages": messages,
            "temperature": 0.4,
        }
        if tools:
            payload["tools"] = tools
            payload["tool_choice"] = "auto"

        headers = {"Content-Type": "application/json"}
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"

        response = httpx.post(
            f"{self.base_url}/chat/completions",
            headers=headers,
            json=payload,
            timeout=90,
        )
        response.raise_for_status()
        data = response.json()
        message = data["choices"][0]["message"]
        return {"message": message}
