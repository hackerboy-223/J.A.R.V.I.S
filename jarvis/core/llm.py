from __future__ import annotations

import json
from typing import Any
from urllib.parse import urlparse

import httpx
from huggingface_hub import InferenceClient

from jarvis.config import settings
from jarvis.core.network import is_loopback_url, service_endpoint


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
        return is_loopback_url(self.base_url)

    def _is_openrouter_url(self) -> bool:
        try:
            return (urlparse(self.base_url).hostname or "").lower() == "openrouter.ai"
        except Exception:
            return False

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

        endpoint = service_endpoint(
            self.base_url,
            "chat/completions",
            label="LLM",
        )
        response = httpx.post(
            endpoint,
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

        endpoint = service_endpoint(
            self.ollama_base_url,
            "chat/completions",
            label="Ollama",
        )
        response = httpx.post(
            endpoint,
            headers={"Content-Type": "application/json"},
            json=payload,
            timeout=90,
        )
        response.raise_for_status()
        data = response.json()
        return {"message": data["choices"][0]["message"]}

    def _stream_openai_http(
        self,
        url: str,
        headers: dict[str, str],
        payload: dict[str, Any],
    ):
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
                if raw == "[DONE]":
                    break
                try:
                    data = json.loads(raw)
                except json.JSONDecodeError:
                    continue
                choices = data.get("choices") or []
                if not choices:
                    continue
                delta = choices[0].get("delta") or {}
                content = delta.get("content")
                if isinstance(content, str) and content:
                    content_parts.append(content)
                    yield {"type": "content", "delta": content}

                for call in delta.get("tool_calls") or []:
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
                    function = call.get("function") or {}
                    if function.get("name"):
                        current["function"]["name"] += str(function["name"])
                    if function.get("arguments"):
                        current["function"]["arguments"] += str(function["arguments"])

        yield {
            "type": "message",
            "message": {
                "role": "assistant",
                "content": "".join(content_parts),
                **(
                    {"tool_calls": [tool_calls[index] for index in sorted(tool_calls)]}
                    if tool_calls
                    else {}
                ),
            },
        }

    def stream(
        self,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]] | None = None,
    ):
        payload: dict[str, Any] = {
            "model": self.model,
            "messages": messages,
            "temperature": 0.4,
            "max_tokens": 1536,
        }
        if tools:
            payload["tools"] = tools
            payload["tool_choice"] = "auto"

        if self.provider in {"huggingface", "hf"}:
            result = self._complete_huggingface(messages, tools)
            message = result["message"]
            content = str(message.get("content") or "")
            if content:
                yield {"type": "content", "delta": content}
            yield {"type": "message", "message": message}
            return

        if self.provider in {"ollama", "local"}:
            payload["model"] = self.ollama_model
            yield from self._stream_openai_http(
                service_endpoint(self.ollama_base_url, "chat/completions", label="Ollama"),
                {"Content-Type": "application/json"},
                payload,
            )
            return

        if self.provider in {"openrouter", "open_router"} or self._is_openrouter_url():
            payload["model"] = self.model or "openrouter/free"
            headers = {
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json",
                "X-Title": self.openrouter_title or "J.A.R.V.I.S.",
            }
            if self.openrouter_referer:
                headers["HTTP-Referer"] = self.openrouter_referer
            try:
                yield from self._stream_openai_http(
                    "https://openrouter.ai/api/v1/chat/completions",
                    headers,
                    payload,
                )
            except Exception as openrouter_exc:
                fallback = dict(payload)
                fallback["model"] = self.ollama_model
                try:
                    yield from self._stream_openai_http(
                        service_endpoint(self.ollama_base_url, "chat/completions", label="Ollama"),
                        {"Content-Type": "application/json"},
                        fallback,
                    )
                except Exception as ollama_exc:
                    raise RuntimeError(
                        "OpenRouter streaming indisponible et fallback Ollama indisponible. "
                        f"OpenRouter: {openrouter_exc} | Ollama: {ollama_exc}"
                    ) from openrouter_exc
            return

        if not self.api_key and not self._is_local():
            result = self._complete_openai_compatible(messages, tools)
            message = result["message"]
            content = str(message.get("content") or "")
            if content:
                yield {"type": "content", "delta": content}
            yield {"type": "message", "message": message}
            return

        headers = {"Content-Type": "application/json"}
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"
        yield from self._stream_openai_http(
            service_endpoint(self.base_url, "chat/completions", label="LLM"),
            headers,
            payload,
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
        if self._is_openrouter_url():
            return self._complete_openrouter(messages, tools)

        return self._complete_openai_compatible(messages, tools)
