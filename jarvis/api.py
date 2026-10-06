from __future__ import annotations

from contextlib import asynccontextmanager
import asyncio
import json
import secrets
import time
import uuid
from typing import Any

from fastapi import FastAPI, Header, HTTPException, WebSocket, WebSocketDisconnect
from fastapi.responses import StreamingResponse

from jarvis.config import settings
from jarvis.core.agent import JarvisAgent
from jarvis.core.logging_setup import _redact
from jarvis.version import __version__


_MAX_API_MESSAGES = 64
_MAX_API_MESSAGE_PARTS = 64
_MAX_API_USER_CHARS = 32_000
_MAX_API_TOTAL_TEXT_CHARS = 128_000
_MAX_API_MODEL_CHARS = 120
_MAX_API_JOB_PROMPT_CHARS = 32_000


def _validate_chat_messages(messages: object) -> list[dict[str, Any]]:
    if not isinstance(messages, list):
        raise HTTPException(status_code=400, detail="messages doit être une liste.")
    if not messages:
        raise HTTPException(status_code=400, detail="messages ne peut pas être vide.")
    if len(messages) > _MAX_API_MESSAGES:
        raise HTTPException(
            status_code=413,
            detail=f"Trop de messages ({_MAX_API_MESSAGES} max).",
        )

    normalized: list[dict[str, Any]] = []
    total_chars = 0

    for raw in messages:
        if not isinstance(raw, dict):
            raise HTTPException(status_code=400, detail="Message API invalide.")
        role = str(raw.get("role", "")).strip()
        if role not in {"system", "user", "assistant", "tool"}:
            raise HTTPException(status_code=400, detail="Rôle de message invalide.")

        content = raw.get("content", "")
        if isinstance(content, str):
            total_chars += len(content)
        elif isinstance(content, list):
            if len(content) > _MAX_API_MESSAGE_PARTS:
                raise HTTPException(status_code=413, detail="Trop de parties dans un message.")
            for part in content:
                if not isinstance(part, dict):
                    raise HTTPException(status_code=400, detail="Partie de message invalide.")
                text = part.get("text")
                if isinstance(text, str):
                    total_chars += len(text)
        elif content is not None:
            raise HTTPException(status_code=400, detail="Contenu de message invalide.")

        if total_chars > _MAX_API_TOTAL_TEXT_CHARS:
            raise HTTPException(
                status_code=413,
                detail="Conversation trop volumineuse pour l'API locale.",
            )
        normalized.append(raw)

    return normalized


def create_app(agent: JarvisAgent | None = None) -> FastAPI:
    jarvis = agent or JarvisAgent(confirm=lambda _: False)

    @asynccontextmanager
    async def lifespan(_: FastAPI):
        jarvis.events.publish("core.started", {"source": "fastapi"})
        yield
        jarvis.shutdown()

    app = FastAPI(
        title="J.A.R.V.I.S. API",
        version=__version__,
        lifespan=lifespan,
    )

    def valid_token(raw: str | None) -> bool:
        if not settings.api_token:
            return True
        if not raw:
            return False
        token = raw[len("Bearer "):] if raw.startswith("Bearer ") else raw
        return secrets.compare_digest(token, settings.api_token)

    def require_auth(authorization: str | None) -> None:
        if not valid_token(authorization):
            raise HTTPException(status_code=401, detail="Bearer token requis ou invalide.")

    @app.get("/health")
    async def health(authorization: str | None = Header(default=None)) -> dict[str, Any]:
        require_auth(authorization)
        snapshot = jarvis.health.snapshot()
        return {
            "status": "ok" if snapshot["healthy"] else "degraded",
            "service": "jarvis",
            "provider": settings.llm_provider,
            "model": settings.llm_model,
            **snapshot,
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

    @app.get("/v1/platform/health")
    async def platform_health(
        authorization: str | None = Header(default=None),
    ) -> dict[str, Any]:
        require_auth(authorization)
        return jarvis.health.snapshot()

    @app.get("/v1/platform/activity")
    async def activity(
        limit: int = 100,
        authorization: str | None = Header(default=None),
    ) -> dict[str, Any]:
        require_auth(authorization)
        return {"events": jarvis.platform.activity(limit)}

    @app.get("/v1/platform/events")
    async def recent_events(
        limit: int = 100,
        authorization: str | None = Header(default=None),
    ) -> dict[str, Any]:
        require_auth(authorization)
        return {"events": jarvis.events.recent(limit)}

    @app.get("/v1/platform/permissions")
    async def permissions(
        authorization: str | None = Header(default=None),
    ) -> dict[str, Any]:
        require_auth(authorization)
        return {"permissions": jarvis.permissions.list()}

    @app.put("/v1/platform/permissions/{capability:path}")
    async def set_permission(
        capability: str,
        payload: dict[str, Any],
        authorization: str | None = Header(default=None),
    ) -> dict[str, Any]:
        require_auth(authorization)
        result = jarvis.permissions.set(
            capability,
            str(payload.get("decision", "ask")),
            scope=str(payload.get("scope", "always")),
        )
        jarvis.platform.log(
            "permission",
            "changed",
            {
                "capability": result.capability,
                "decision": result.decision.value,
                "source": result.source,
            },
        )
        jarvis.events.publish(
            "permission.changed",
            {
                "capability": result.capability,
                "decision": result.decision.value,
                "source": result.source,
            },
        )
        return {
            "capability": result.capability,
            "decision": result.decision.value,
            "source": result.source,
        }

    @app.get("/v1/platform/jobs")
    async def jobs(
        limit: int = 100,
        authorization: str | None = Header(default=None),
    ) -> dict[str, Any]:
        require_auth(authorization)
        return {"jobs": jarvis.jobs.list(limit)}

    @app.post("/v1/platform/jobs/{job_id}/cancel")
    async def cancel_job(
        job_id: str,
        authorization: str | None = Header(default=None),
    ) -> dict[str, Any]:
        require_auth(authorization)
        return {"cancelled": jarvis.jobs.cancel(job_id), "job_id": job_id}

    @app.post("/v1/platform/jobs/cancel-all")
    async def cancel_all_jobs(
        authorization: str | None = Header(default=None),
    ) -> dict[str, Any]:
        require_auth(authorization)
        count = jarvis.jobs.cancel_all()
        jarvis.events.publish("core.stop_requested", {"jobs": count})
        return {"cancelled": count}

    @app.get("/v1/platform/workspaces")
    async def workspaces(
        authorization: str | None = Header(default=None),
    ) -> dict[str, Any]:
        require_auth(authorization)
        return {"workspaces": jarvis.platform.workspaces()}

    @app.post("/v1/platform/workspaces")
    async def add_workspace(
        payload: dict[str, Any],
        authorization: str | None = Header(default=None),
    ) -> dict[str, Any]:
        require_auth(authorization)
        workspace = jarvis.platform.add_workspace(
            str(payload.get("name", "")),
            str(payload.get("root_path", "")),
            bool(payload.get("favorite", False)),
        )
        jarvis.events.publish("workspace.updated", workspace)
        return workspace

    @app.get("/v1/platform/missions")
    async def missions(
        status: str | None = None,
        authorization: str | None = Header(default=None),
    ) -> dict[str, Any]:
        require_auth(authorization)
        return {"missions": jarvis.platform.missions(status)}

    @app.post("/v1/platform/missions")
    async def create_mission(
        payload: dict[str, Any],
        authorization: str | None = Header(default=None),
    ) -> dict[str, Any]:
        require_auth(authorization)
        mission = jarvis.platform.create_mission(
            str(payload.get("title", "")),
            str(payload.get("workspace_id")) if payload.get("workspace_id") else None,
            str(payload.get("mode", "standard")),
        )
        jarvis.events.publish("mission.created", mission)
        return mission

    @app.post("/v1/platform/missions/{mission_id}/checkpoint")
    async def checkpoint_mission(
        mission_id: str,
        payload: dict[str, Any],
        authorization: str | None = Header(default=None),
    ) -> dict[str, Any]:
        require_auth(authorization)
        state = payload.get("state")
        if not isinstance(state, dict):
            raise HTTPException(status_code=400, detail="state doit être un objet.")
        jarvis.platform.checkpoint(mission_id, state)
        jarvis.events.publish("mission.checkpoint", {"mission_id": mission_id})
        return {"ok": True, "mission_id": mission_id}

    @app.get("/v1/platform/missions/{mission_id}/checkpoint")
    async def latest_checkpoint(
        mission_id: str,
        authorization: str | None = Header(default=None),
    ) -> dict[str, Any]:
        require_auth(authorization)
        return jarvis.platform.latest_checkpoint(mission_id)

    @app.post("/v1/chat/jobs")
    async def chat_job(
        payload: dict[str, Any],
        authorization: str | None = Header(default=None),
    ) -> dict[str, Any]:
        require_auth(authorization)
        prompt = str(payload.get("prompt", "")).strip()
        if not prompt:
            raise HTTPException(status_code=400, detail="prompt est requis.")
        if len(prompt) > _MAX_API_JOB_PROMPT_CHARS:
            raise HTTPException(status_code=413, detail="prompt trop volumineux.")
        mode = str(payload.get("mode", "standard")).strip().lower()
        operator_id = str(payload.get("operator_id", "api-job")).strip()[:120] or "api-job"

        def run(ctx):
            def progress(message: str) -> None:
                ctx.progress(0.5, message)
                ctx.checkpoint()
            return jarvis.ask(prompt, mode=mode, progress=progress, operator_id=operator_id)

        job_id = jarvis.jobs.submit(prompt[:120], run)
        return {"job_id": job_id}

    @app.websocket("/ws/events")
    async def event_socket(websocket: WebSocket) -> None:
        token = websocket.query_params.get("token") or websocket.headers.get("authorization")
        if not valid_token(token):
            await websocket.close(code=4401)
            return

        await websocket.accept()
        loop = asyncio.get_running_loop()
        queue: asyncio.Queue[dict[str, Any]] = asyncio.Queue(maxsize=256)

        def on_event(event) -> None:
            payload = event.to_dict()

            def push() -> None:
                if queue.full():
                    try:
                        queue.get_nowait()
                    except asyncio.QueueEmpty:
                        pass
                try:
                    queue.put_nowait(payload)
                except asyncio.QueueFull:
                    pass

            loop.call_soon_threadsafe(push)

        subscription = jarvis.events.subscribe(on_event)
        try:
            await websocket.send_json({"type": "connected", "service": "jarvis"})
            while True:
                event = await queue.get()
                await websocket.send_json(event)
        except WebSocketDisconnect:
            pass
        finally:
            jarvis.events.unsubscribe(subscription)

    @app.post("/v1/chat/completions")
    async def chat_completions(
        payload: dict[str, Any],
        authorization: str | None = Header(default=None),
    ):
        require_auth(authorization)

        messages = _validate_chat_messages(payload.get("messages"))

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
        if len(user_text) > _MAX_API_USER_CHARS:
            raise HTTPException(
                status_code=413,
                detail=f"Message utilisateur trop long ({_MAX_API_USER_CHARS} caractères max).",
            )

        metadata = payload.get("metadata")
        if not isinstance(metadata, dict):
            metadata = {}

        mode = str(metadata.get("mode", "standard")).strip().lower()
        if mode not in {"standard", "parallel", "sequential", "debate", "research", "operative"}:
            mode = "standard"
        operator_id = str(metadata.get("operator_id", "api")).strip()[:120] or "api"

        completion_id = f"chatcmpl-{uuid.uuid4().hex}"
        created = int(time.time())
        model = str(payload.get("model") or settings.llm_model).strip()[:_MAX_API_MODEL_CHARS]

        if bool(payload.get("stream", False)):
            queue: asyncio.Queue[tuple[str, str]] = asyncio.Queue(maxsize=128)
            loop = asyncio.get_running_loop()

            def push(kind: str, value: str) -> None:
                future = asyncio.run_coroutine_threadsafe(
                    queue.put((kind, value)),
                    loop,
                )
                future.result(timeout=30)

            def progress(message: str) -> None:
                push("progress", str(message)[:1000])

            def stream_worker() -> None:
                try:
                    for delta in jarvis.stream(
                        user_text,
                        mode=mode,
                        progress=progress,
                        operator_id=operator_id,
                    ):
                        push("delta", str(delta))
                except Exception as exc:
                    try:
                        push("error", _redact(str(exc))[:2000])
                    except Exception:
                        pass
                finally:
                    try:
                        push("done", "")
                    except Exception:
                        pass

            asyncio.create_task(asyncio.to_thread(stream_worker))

            async def event_stream():
                first_delta = True
                while True:
                    kind, value = await queue.get()
                    if kind == "progress":
                        event = {
                            "id": completion_id,
                            "object": "chat.completion.chunk",
                            "created": created,
                            "model": model,
                            "choices": [{"index": 0, "delta": {}, "finish_reason": None}],
                            "jarvis": {"event": "progress", "message": value},
                        }
                        yield "data: " + json.dumps(event, ensure_ascii=False) + "\n\n"
                        continue

                    if kind == "delta":
                        event = {
                            "id": completion_id,
                            "object": "chat.completion.chunk",
                            "created": created,
                            "model": model,
                            "choices": [
                                {
                                    "index": 0,
                                    "delta": {
                                        **({"role": "assistant"} if first_delta else {}),
                                        "content": value,
                                    },
                                    "finish_reason": None,
                                }
                            ],
                        }
                        first_delta = False
                        yield "data: " + json.dumps(event, ensure_ascii=False) + "\n\n"
                        continue

                    if kind == "error":
                        event = {
                            "id": completion_id,
                            "object": "chat.completion.chunk",
                            "created": created,
                            "model": model,
                            "choices": [
                                {
                                    "index": 0,
                                    "delta": {"content": f"Erreur streaming : {value}"},
                                    "finish_reason": None,
                                }
                            ],
                        }
                        yield "data: " + json.dumps(event, ensure_ascii=False) + "\n\n"
                        continue

                    final = {
                        "id": completion_id,
                        "object": "chat.completion.chunk",
                        "created": created,
                        "model": model,
                        "choices": [{"index": 0, "delta": {}, "finish_reason": "stop"}],
                    }
                    yield "data: " + json.dumps(final, ensure_ascii=False) + "\n\n"
                    yield "data: [DONE]\n\n"
                    break

            return StreamingResponse(
                event_stream(),
                media_type="text/event-stream",
                headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
            )

        answer = await asyncio.to_thread(
            jarvis.ask,
            user_text,
            mode,
            None,
            operator_id,
        )

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
