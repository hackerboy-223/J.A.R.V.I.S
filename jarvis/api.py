from __future__ import annotations

from contextlib import asynccontextmanager
import asyncio
import json
import secrets
import time
import uuid
from typing import Any

from fastapi import FastAPI, Header, HTTPException
from fastapi.responses import StreamingResponse

from jarvis.config import settings
from jarvis.core.agent import JarvisAgent


def create_app(agent: JarvisAgent | None = None) -> FastAPI:
    jarvis = agent or JarvisAgent(confirm=lambda _: False)

    @asynccontextmanager
    async def lifespan(_: FastAPI):
        yield
        jarvis.shutdown()

    app = FastAPI(
        title="J.A.R.V.I.S. API",
        version="0.2.0",
        lifespan=lifespan,
    )

    def require_auth(authorization: str | None) -> None:
        if not settings.api_token:
            return
        prefix = "Bearer "
        if not authorization or not authorization.startswith(prefix):
            raise HTTPException(status_code=401, detail="Bearer token requis.")
        token = authorization[len(prefix):]
        if not secrets.compare_digest(token, settings.api_token):
            raise HTTPException(status_code=401, detail="Token invalide.")

    @app.get("/health")
    async def health(authorization: str | None = Header(default=None)) -> dict[str, Any]:
        require_auth(authorization)
        return {
            "status": "ok",
            "service": "jarvis",
            "provider": settings.llm_provider,
            "model": settings.llm_model,
        }

    @app.get("/v1/models")
    async def models(authorization: str | None = Header(default=None)) -> dict[str, Any]:
        require_auth(authorization)
        return {
            "object": "list",
            "data": [
                {
                    "id": settings.llm_model,
                    "object": "model",
                    "created": 0,
                    "owned_by": "jarvis",
                }
            ],
        }

    @app.post("/v1/chat/completions")
    async def chat_completions(
        payload: dict[str, Any],
        authorization: str | None = Header(default=None),
    ):
        require_auth(authorization)

        messages = payload.get("messages")
        if not isinstance(messages, list):
            raise HTTPException(status_code=400, detail="messages doit être une liste.")

        user_text = ""
        for message in reversed(messages):
            if not isinstance(message, dict) or message.get("role") != "user":
                continue
            content = message.get("content", "")
            if isinstance(content, str):
                user_text = content.strip()
            elif isinstance(content, list):
                parts = []
                for part in content:
                    if isinstance(part, dict) and part.get("type") == "text":
                        parts.append(str(part.get("text", "")))
                user_text = "\n".join(parts).strip()
            break

        if not user_text:
            raise HTTPException(status_code=400, detail="Aucun message utilisateur exploitable.")

        metadata = payload.get("metadata")
        if not isinstance(metadata, dict):
            metadata = {}

        mode = str(metadata.get("mode", "standard")).strip().lower()
        if mode not in {"standard", "parallel", "sequential", "debate", "research", "operative"}:
            mode = "standard"
        operator_id = str(metadata.get("operator_id", "api")).strip()[:120] or "api"

        answer = await asyncio.to_thread(
            jarvis.ask,
            user_text,
            mode,
            None,
            operator_id,
        )

        completion_id = f"chatcmpl-{uuid.uuid4().hex}"
        created = int(time.time())
        model = str(payload.get("model") or settings.llm_model)

        if bool(payload.get("stream", False)):
            async def event_stream():
                chunk = {
                    "id": completion_id,
                    "object": "chat.completion.chunk",
                    "created": created,
                    "model": model,
                    "choices": [
                        {
                            "index": 0,
                            "delta": {"role": "assistant", "content": answer},
                            "finish_reason": "stop",
                        }
                    ],
                }
                yield "data: " + json.dumps(chunk, ensure_ascii=False) + "\n\n"
                yield "data: [DONE]\n\n"

            return StreamingResponse(event_stream(), media_type="text/event-stream")

        return {
            "id": completion_id,
            "object": "chat.completion",
            "created": created,
            "model": model,
            "choices": [
                {
                    "index": 0,
                    "message": {"role": "assistant", "content": answer},
                    "finish_reason": "stop",
                }
            ],
            "usage": {
                "prompt_tokens": 0,
                "completion_tokens": 0,
                "total_tokens": 0,
            },
        }

    return app
