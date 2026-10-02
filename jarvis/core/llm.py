from __future__ import annotations

import json
from typing import Any

import httpx
from huggingface_hub import InferenceClient

from jarvis.config import settings


def _tool_call_to_dict(call: Any) -> dict[str, Any]:
    function = getattr(call, "function", None)
    name = getattr(function, "name", "") if function is not None else ""
    arguments = getattr(function, "arguments", "{}") if function is not None else "{}"

    if isinstance(arguments, dict):
        arguments = json.dumps(arguments, ensure_ascii=False)
    elif not isinstance(arguments, str):
        arguments = "{}"

    return {
        "id": str(getattr(call, "id", "") or ""),
        "type": "function",
        "function": {
            "name": str(name or ""),
            "arguments": arguments,
        },
    }


class LLMClient:
    def __init__(self) -> None:
        self.provider = settings.llm_provider
        self.base_url = settings.llm_base_url.rstrip("/")
        self.api_key = settings.llm_api_key
        self.model = settings.llm_model
        self.hf_token = settings.hf_token
        self.hf_model = settings.hf_model
        self.hf_provider = settings.hf_provider

    def _is_local(self) -> bool:
        return "localhost" in self.base_url or "127.0.0.1" in self.base_url

    def _complete_huggingface(
        self,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]] | None,
    ) -> dict[str, Any]:
        if not self.hf_token:
            return {
                "message": {
                    "role": "assistant",
                    "content": (
                        "Le moteur Hugging Face est sélectionné, mais HF_TOKEN n'est pas configuré. "
                        "Ajoute ton token Hugging Face dans le fichier .env."
                    ),
                }
            }

        kwargs: dict[str, Any] = {"api_key": self.hf_token}
        if self.hf_provider and self.hf_provider != "auto":
            kwargs["provider"] = self.hf_provider

        client = InferenceClient(**kwargs)

        request: dict[str, Any] = {
            "model": self.hf_model,
            "messages": messages,
            "temperature": 0.4,
            "max_tokens": 1536,
        }
        if tools:
            request["tools"] = tools
            request["tool_choice"] = "auto"

        completion = client.chat_completion(**request)
        message = completion.choices[0].message

        result: dict[str, Any] = {
            "role": "assistant",
            "content": str(getattr(message, "content", "") or ""),
        }

        raw_calls = getattr(message, "tool_calls", None) or []
        if raw_calls:
            result["tool_calls"] = [_tool_call_to_dict(call) for call in raw_calls]

        return {"message": result}

    def _complete_openai_compatible(
        self,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]] | None,
    ) -> dict[str, Any]:
        if not self.api_key and not self._is_local():
            return {
                "message": {
                    "role": "assistant",
                    "content": (
                        "Aucun endpoint LLM compatible n'est configuré. "
                        "Renseigne JARVIS_LLM_API_KEY, JARVIS_LLM_BASE_URL et JARVIS_LLM_MODEL."
                    ),
                }
            }

        payload: dict[str, Any] = {
            "model": self.model,
            "messages": messages,
            "temperature": 0.4,
            "max_tokens": 1536,
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
        return {"message": data["choices"][0]["message"]}

    def complete(
        self,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]] | None = None,
    ) -> dict[str, Any]:
        if self.provider in {"huggingface", "hf"}:
            return self._complete_huggingface(messages, tools)

        return self._complete_openai_compatible(messages, tools)
