from __future__ import annotations

import json
from typing import Any

import httpx

from jarvis.config import settings


class LLMClient:
    def __init__(self) -> None:
        self.base_url = settings.llm_base_url.rstrip("/")
        self.api_key = settings.llm_api_key
        self.model = settings.llm_model

    def complete(
        self,
        messages: list[dict[str, str]],
        tools: list[dict[str, Any]] | None = None,
    ) -> dict[str, Any]:
        if not self.api_key:
            return {
                "content": (
                    "Mode local sans clé LLM actif. Configure JARVIS_LLM_API_KEY et "
                    "JARVIS_LLM_BASE_URL pour connecter le cerveau principal."
                ),
                "tool_calls": [],
            }

        payload: dict[str, Any] = {
            "model": self.model,
            "messages": messages,
            "temperature": 0.4,
        }
        if tools:
            payload["tools"] = tools
            payload["tool_choice"] = "auto"

        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }
        response = httpx.post(
            f"{self.base_url}/chat/completions",
            headers=headers,
            json=payload,
            timeout=90,
        )
        response.raise_for_status()
        data = response.json()
        message = data["choices"][0]["message"]

        calls: list[dict[str, Any]] = []
        for call in message.get("tool_calls") or []:
            fn = call.get("function") or {}
            raw_args = fn.get("arguments") or "{}"
            try:
                parsed_args = json.loads(raw_args)
            except json.JSONDecodeError:
                parsed_args = {}
            calls.append(
                {
                    "id": call.get("id", ""),
                    "name": fn.get("name", ""),
                    "arguments": parsed_args,
                }
            )

        return {"content": message.get("content") or "", "tool_calls": calls}
