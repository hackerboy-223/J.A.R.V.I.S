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
        self.openrouter_referer = settings.openrouter_referer
        self.openrouter_title = settings.openrouter_title
        self.ollama_base_url = settings.ollama_base_url.rstrip("/")
        self.ollama_model = settings.ollama_model

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

    def _complete_openrouter(
        self,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]] | None,
    ) -> dict[str, Any]:
        if not self.api_key:
            raise RuntimeError(
                "Clé OpenRouter absente. Configure OPENROUTER_API_KEY "
                "ou JARVIS_LLM_API_KEY dans .env."
            )

        payload: dict[str, Any] = {
            "model": self.model or "openrouter/free",
            "messages": messages,
            "temperature": 0.4,
            "max_tokens": 1536,
        }
        if tools:
            payload["tools"] = tools
            payload["tool_choice"] = "auto"

        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
            "X-Title": self.openrouter_title or "J.A.R.V.I.S.",
        }
        if self.openrouter_referer:
            headers["HTTP-Referer"] = self.openrouter_referer

        response = httpx.post(
            "https://openrouter.ai/api/v1/chat/completions",
            headers=headers,
            json=payload,
            timeout=90,
        )

        if response.status_code == 401:
            raise RuntimeError("Clé OpenRouter invalide ou non autorisée.")
        if response.status_code == 402:
            raise RuntimeError("OpenRouter demande des crédits pour cette requête.")
        if response.status_code == 429:
            raise RuntimeError(
                "Limite OpenRouter atteinte. Le quota gratuit peut être temporairement épuisé."
            )

        response.raise_for_status()
        data = response.json()

        if not data.get("choices"):
            error = data.get("error") or {}
            message = error.get("message") if isinstance(error, dict) else str(error)
            raise RuntimeError(message or "Réponse OpenRouter vide.")

        return {"message": data["choices"][0]["message"]}

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

    def _complete_ollama(
        self,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]] | None,
    ) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "model": self.ollama_model,
            "messages": messages,
            "temperature": 0.4,
        }
        if tools:
            payload["tools"] = tools
            payload["tool_choice"] = "auto"

        response = httpx.post(
            f"{self.ollama_base_url}/chat/completions",
            headers={"Content-Type": "application/json"},
            json=payload,
            timeout=90,
        )
        response.raise_for_status()
        data = response.json()
        return {"message": data["choices"][0]["message"]}

    @staticmethod
    def _stream_openai_endpoint(
        url: str,
        headers: dict[str, str],
        payload: dict[str, Any],
        on_delta,
    ) -> dict[str, Any]:
        request = dict(payload)
        request["stream"] = True
        content_parts: list[str] = []
        tool_calls: dict[int, dict[str, Any]] = {}

        with httpx.stream(
            "POST",
            url,
            headers=headers,
            json=request,
            timeout=90,
        ) as response:
            response.raise_for_status()
            for line in response.iter_lines():
                if not line or not line.startswith("data:"):
                    continue
                raw = line[5:].strip()
                if not raw or raw == "[DONE]":
                    continue
                try:
                    chunk = json.loads(raw)
                except json.JSONDecodeError:
                    continue
                choices = chunk.get("choices") or []
                if not choices:
                    continue
                delta = choices[0].get("delta") or {}
                text = delta.get("content")
                if isinstance(text, str) and text:
                    content_parts.append(text)
                    if on_delta is not None:
                        on_delta(text)

                for call in delta.get("tool_calls") or []:
                    if not isinstance(call, dict):
                        continue
                    index = int(call.get("index", 0) or 0)
                    current = tool_calls.setdefault(
                        index,
                        {
                            "id": "",
                            "type": "function",
                            "function": {"name": "", "arguments": ""},
                        },
                    )
                    if call.get("id"):
                        current["id"] = str(call["id"])
                    if call.get("type"):
                        current["type"] = str(call["type"])
                    function = call.get("function") or {}
                    if function.get("name"):
                        current["function"]["name"] += str(function["name"])
                    if function.get("arguments"):
                        current["function"]["arguments"] += str(function["arguments"])

        message: dict[str, Any] = {
            "role": "assistant",
            "content": "".join(content_parts),
        }
        if tool_calls:
            message["tool_calls"] = [tool_calls[key] for key in sorted(tool_calls)]
        return {"message": message}

    def stream_complete(
        self,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]] | None = None,
        on_delta=None,
    ) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "model": self.model,
            "messages": messages,
            "temperature": 0.4,
            "max_tokens": 1536,
        }
        if tools:
            payload["tools"] = tools
            payload["tool_choice"] = "auto"

        if self.provider in {"openrouter", "open_router"} or "openrouter.ai" in self.base_url:
            if not self.api_key:
                raise RuntimeError("Clé OpenRouter absente.")
            headers = {
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json",
                "X-Title": self.openrouter_title or "J.A.R.V.I.S.",
            }
            if self.openrouter_referer:
                headers["HTTP-Referer"] = self.openrouter_referer
            try:
                return self._stream_openai_endpoint(
                    "https://openrouter.ai/api/v1/chat/completions",
                    headers,
                    payload,
                    on_delta,
                )
            except Exception as openrouter_exc:
                fallback = dict(payload)
                fallback["model"] = self.ollama_model
                try:
                    return self._stream_openai_endpoint(
                        f"{self.ollama_base_url}/chat/completions",
                        {"Content-Type": "application/json"},
                        fallback,
                        on_delta,
                    )
                except Exception as ollama_exc:
                    raise RuntimeError(
                        f"Streaming indisponible. OpenRouter: {openrouter_exc} | Ollama: {ollama_exc}"
                    ) from openrouter_exc

        if self.provider in {"ollama", "local"}:
            payload["model"] = self.ollama_model
            return self._stream_openai_endpoint(
                f"{self.ollama_base_url}/chat/completions",
                {"Content-Type": "application/json"},
                payload,
                on_delta,
            )

        if self.provider in {"huggingface", "hf"}:
            # Hugging Face providers do not expose a uniform OpenAI SSE surface.
            # Preserve correctness and emit the final text as one delta.
            result = self._complete_huggingface(messages, tools)
            text = str((result.get("message") or {}).get("content") or "")
            if text and on_delta is not None:
                on_delta(text)
            return result

        headers = {"Content-Type": "application/json"}
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"
        if not self.api_key and not self._is_local():
            result = self._complete_openai_compatible(messages, tools)
            text = str((result.get("message") or {}).get("content") or "")
            if text and on_delta is not None:
                on_delta(text)
            return result
        return self._stream_openai_endpoint(
            f"{self.base_url}/chat/completions",
            headers,
            payload,
            on_delta,
        )

    def complete(
        self,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]] | None = None,
    ) -> dict[str, Any]:
        if self.provider in {"openrouter", "open_router"}:
            try:
                return self._complete_openrouter(messages, tools)
            except Exception as openrouter_exc:
                try:
                    return self._complete_ollama(messages, tools)
                except Exception as ollama_exc:
                    raise RuntimeError(
                        "OpenRouter est indisponible et aucun Ollama local utilisable "
                        "n'a été détecté. "
                        f"OpenRouter: {openrouter_exc} | Ollama: {ollama_exc}"
                    ) from openrouter_exc

        if self.provider in {"huggingface", "hf"}:
            try:
                return self._complete_huggingface(messages, tools)
            except Exception as hf_exc:
                try:
                    return self._complete_ollama(messages, tools)
                except Exception as ollama_exc:
                    raise RuntimeError(
                        "Hugging Face est indisponible (quota/crédits ou provider) "
                        "et aucun Ollama local utilisable n'a été détecté. "
                        f"HF: {hf_exc} | Ollama: {ollama_exc}"
                    ) from hf_exc

        if self.provider in {"ollama", "local"}:
            return self._complete_ollama(messages, tools)

        # Backward compatibility: an OpenRouter base URL also gets OpenRouter headers.
        if "openrouter.ai" in self.base_url:
            return self._complete_openrouter(messages, tools)

        return self._complete_openai_compatible(messages, tools)
