from __future__ import annotations

from contextlib import asynccontextmanager
import asyncio
import json
import queue
import secrets
import time
import uuid
from typing import Any

from fastapi import FastAPI, Header, HTTPException, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse

from jarvis.config import settings
from jarvis.core.agent import JarvisAgent
from jarvis.core.diagnostics import health_snapshot


_TERMINAL_JOB_STATES = {"completed", "failed", "cancelled"}


def create_app(agent: JarvisAgent | None = None) -> FastAPI:
    jarvis = agent or JarvisAgent(confirm=lambda _: False)

    @asynccontextmanager
    async def lifespan(_: FastAPI):
        yield
        jarvis.shutdown()

    app = FastAPI(
        title="J.A.R.V.I.S. API",
        version="0.3.0",
        lifespan=lifespan,
    )
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["http://127.0.0.1:3000", "http://localhost:3000"],
        allow_credentials=False,
        allow_methods=["GET", "POST", "PATCH", "DELETE"],
        allow_headers=["Authorization", "Content-Type"],
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

    def websocket_authorized(websocket: WebSocket) -> bool:
        if not settings.api_token:
            return True
        token = websocket.query_params.get("token") or ""
        return secrets.compare_digest(token, settings.api_token)

    def parse_chat(payload: dict[str, Any]) -> tuple[str, str, str]:
        messages = payload.get("messages")
        if not isinstance(messages, list):
            raise HTTPException(status_code=400, detail="messages doit être une liste.")

        user_text = ""
        for message in reversed(messages):
            if not isinstance(message, dict) or message.get("role") != "user":
                continue
            body = message.get("content", "")
            if isinstance(body, str):
                user_text = body.strip()
            elif isinstance(body, list):
                parts = [
                    str(part.get("text", ""))
                    for part in body
                    if isinstance(part, dict) and part.get("type") == "text"
                ]
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
        return user_text, mode, operator_id

    async def wait_for_job(job_id: str) -> dict[str, Any]:
        while True:
            job = jarvis.runtime.jobs.get(job_id)
            if job is None:
                raise HTTPException(status_code=404, detail="Job introuvable.")
            if job.get("status") in _TERMINAL_JOB_STATES:
                return job
            await asyncio.sleep(0.05)

    @app.get("/health")
    async def health(authorization: str | None = Header(default=None)) -> dict[str, Any]:
        require_auth(authorization)
        return {
            "status": "ok",
            "service": "jarvis",
            "provider": settings.llm_provider,
            "model": settings.llm_model,
        }

    @app.get("/health/full")
    async def health_full(authorization: str | None = Header(default=None)) -> dict[str, Any]:
        require_auth(authorization)
        scheduler_running = bool(
            jarvis.scheduler._thread is not None and jarvis.scheduler._thread.is_alive()
        )
        return health_snapshot(
            scheduler_running=scheduler_running,
            extra_checks={
                "skills": lambda: len(jarvis.skills.list()),
                "mcp": lambda: len(jarvis.mcp.list_servers()),
            },
        )

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
        user_text, mode, operator_id = parse_chat(payload)
        completion_id = f"chatcmpl-{uuid.uuid4().hex}"
        created = int(time.time())
        model = str(payload.get("model") or settings.llm_model)

        if bool(payload.get("stream", False)):
            async def event_stream():
                deltas: queue.Queue[str] = queue.Queue()
                job_id = jarvis.submit(
                    user_text,
                    mode=mode,
                    operator_id=operator_id,
                    on_delta=lambda text: deltas.put(str(text)),
                )

                role_chunk = {
                    "id": completion_id,
                    "object": "chat.completion.chunk",
                    "created": created,
                    "model": model,
                    "choices": [
                        {
                            "index": 0,
                            "delta": {"role": "assistant"},
                            "finish_reason": None,
                        }
                    ],
                }
                yield "data: " + json.dumps(role_chunk, ensure_ascii=False) + "\n\n"

                try:
                    while True:
                        try:
                            text = await asyncio.to_thread(deltas.get, True, 0.15)
                        except queue.Empty:
                            text = ""

                        if text:
                            chunk = {
                                "id": completion_id,
                                "object": "chat.completion.chunk",
                                "created": created,
                                "model": model,
                                "choices": [
                                    {
                                        "index": 0,
                                        "delta": {"content": text},
                                        "finish_reason": None,
                                    }
                                ],
                            }
                            yield "data: " + json.dumps(chunk, ensure_ascii=False) + "\n\n"

                        job = jarvis.runtime.jobs.get(job_id)
                        if job is not None and job.get("status") in _TERMINAL_JOB_STATES:
                            while not deltas.empty():
                                tail = deltas.get_nowait()
                                chunk = {
                                    "id": completion_id,
                                    "object": "chat.completion.chunk",
                                    "created": created,
                                    "model": model,
                                    "choices": [
                                        {
                                            "index": 0,
                                            "delta": {"content": tail},
                                            "finish_reason": None,
                                        }
                                    ],
                                }
                                yield "data: " + json.dumps(chunk, ensure_ascii=False) + "\n\n"
                            break
                finally:
                    job = jarvis.runtime.jobs.get(job_id)
                    if job and job.get("status") not in _TERMINAL_JOB_STATES:
                        jarvis.runtime.jobs.cancel(job_id)

                job = jarvis.runtime.jobs.get(job_id) or {}
                if job.get("status") == "failed":
                    error_chunk = {
                        "id": completion_id,
                        "object": "chat.completion.chunk",
                        "created": created,
                        "model": model,
                        "choices": [
                            {
                                "index": 0,
                                "delta": {"content": f"\nErreur agent : {job.get('error', 'inconnue')}"},
                                "finish_reason": "stop",
                            }
                        ],
                    }
                    yield "data: " + json.dumps(error_chunk, ensure_ascii=False) + "\n\n"
                else:
                    end_chunk = {
                        "id": completion_id,
                        "object": "chat.completion.chunk",
                        "created": created,
                        "model": model,
                        "choices": [
                            {
                                "index": 0,
                                "delta": {},
                                "finish_reason": "stop",
                            }
                        ],
                    }
                    yield "data: " + json.dumps(end_chunk, ensure_ascii=False) + "\n\n"
                yield "data: [DONE]\n\n"

            return StreamingResponse(
                event_stream(),
                media_type="text/event-stream",
                headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
            )

        job_id = jarvis.submit(user_text, mode=mode, operator_id=operator_id)
        job = await wait_for_job(job_id)
        if job.get("status") != "completed":
            raise HTTPException(
                status_code=500,
                detail=job.get("error") or f"Job terminé avec l'état {job.get('status')}",
            )
        result = job.get("result") or {}
        answer = str(result.get("answer") or "")

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
            "jarvis_job_id": job_id,
        }

    @app.get("/v1/jobs")
    async def jobs(
        limit: int = 100,
        authorization: str | None = Header(default=None),
    ) -> dict[str, Any]:
        require_auth(authorization)
        return {"jobs": jarvis.runtime.jobs.list(limit)}

    @app.get("/v1/jobs/{job_id}")
    async def job(
        job_id: str,
        authorization: str | None = Header(default=None),
    ) -> dict[str, Any]:
        require_auth(authorization)
        item = jarvis.runtime.jobs.get(job_id)
        if item is None:
            raise HTTPException(status_code=404, detail="Job introuvable.")
        return item

    @app.post("/v1/jobs/{job_id}/cancel")
    async def cancel_job(
        job_id: str,
        authorization: str | None = Header(default=None),
    ) -> dict[str, Any]:
        require_auth(authorization)
        return {"cancel_requested": jarvis.runtime.jobs.cancel(job_id), "job_id": job_id}

    @app.post("/v1/stop")
    async def stop_all(authorization: str | None = Header(default=None)) -> dict[str, Any]:
        require_auth(authorization)
        return {"cancel_requested": jarvis.stop_all()}

    @app.get("/v1/activity")
    async def activity(
        limit: int = 100,
        authorization: str | None = Header(default=None),
    ) -> dict[str, Any]:
        require_auth(authorization)
        return {"events": jarvis.runtime.activity.recent(limit)}

    @app.get("/v1/permissions")
    async def permissions(authorization: str | None = Header(default=None)) -> dict[str, Any]:
        require_auth(authorization)
        return {"permissions": jarvis.runtime.permissions.effective()}

    @app.post("/v1/permissions/{capability}")
    async def set_permission(
        capability: str,
        payload: dict[str, Any],
        authorization: str | None = Header(default=None),
    ) -> dict[str, Any]:
        require_auth(authorization)
        decision = str(payload.get("decision", "ask")).lower()
        scope = str(payload.get("scope", "always")).lower()
        if decision not in {"allow", "ask", "deny"}:
            raise HTTPException(status_code=400, detail="decision invalide.")
        if scope not in {"once", "session", "always"}:
            raise HTTPException(status_code=400, detail="scope invalide.")
        jarvis.runtime.permissions.set(capability, decision, scope)  # type: ignore[arg-type]
        jarvis.runtime.events.emit(
            "permission.changed",
            {"capability": capability, "decision": decision, "scope": scope},
        )
        return {"capability": capability, "decision": decision, "scope": scope}

    @app.get("/v1/workspaces")
    async def workspaces(authorization: str | None = Header(default=None)) -> dict[str, Any]:
        require_auth(authorization)
        return {"workspaces": jarvis.runtime.workspaces.list()}

    @app.post("/v1/workspaces")
    async def create_workspace(
        payload: dict[str, Any],
        authorization: str | None = Header(default=None),
    ) -> dict[str, Any]:
        require_auth(authorization)
        return jarvis.runtime.workspaces.add(
            str(payload.get("name", "")),
            str(payload.get("path", "")),
            bool(payload.get("favorite", False)),
        )

    @app.post("/v1/workspaces/{workspace_id}/index")
    async def index_workspace(
        workspace_id: str,
        payload: dict[str, Any] | None = None,
        authorization: str | None = Header(default=None),
    ) -> dict[str, Any]:
        require_auth(authorization)
        item = jarvis.runtime.workspaces.get(workspace_id)
        if item is None:
            raise HTTPException(status_code=404, detail="Workspace introuvable.")
        body = payload or {}
        return await asyncio.to_thread(
            jarvis.runtime.file_index.index_workspace,
            workspace_id,
            item["root_path"],
            max_files=int(body.get("max_files", 50000) or 50000),
        )

    @app.get("/v1/files/search")
    async def file_search(
        q: str,
        workspace_id: str | None = None,
        limit: int = 50,
        authorization: str | None = Header(default=None),
    ) -> dict[str, Any]:
        require_auth(authorization)
        return {
            "results": jarvis.runtime.file_index.search(
                q,
                workspace_id=workspace_id,
                limit=limit,
            )
        }

    @app.get("/v1/missions")
    async def missions(authorization: str | None = Header(default=None)) -> dict[str, Any]:
        require_auth(authorization)
        return {"missions": jarvis.runtime.missions.list()}

    @app.post("/v1/missions")
    async def create_mission(
        payload: dict[str, Any],
        authorization: str | None = Header(default=None),
    ) -> dict[str, Any]:
        require_auth(authorization)
        return jarvis.runtime.missions.create(
            str(payload.get("title", "")),
            workspace_id=str(payload.get("workspace_id", "")).strip() or None,
            mode=str(payload.get("mode", "operative") or "operative"),
        )

    @app.get("/v1/missions/{mission_id}")
    async def mission(
        mission_id: str,
        authorization: str | None = Header(default=None),
    ) -> dict[str, Any]:
        require_auth(authorization)
        item = jarvis.runtime.missions.get(mission_id)
        if item is None:
            raise HTTPException(status_code=404, detail="Mission introuvable.")
        return item

    @app.websocket("/ws/events")
    async def event_socket(websocket: WebSocket) -> None:
        if not websocket_authorized(websocket):
            await websocket.close(code=4401)
            return

        await websocket.accept()
        subscription = jarvis.runtime.events.subscribe()
        try:
            while True:
                try:
                    event = await asyncio.to_thread(subscription.get, 1.0)
                except queue.Empty:
                    await websocket.send_json({"type": "ping", "time": time.time()})
                    continue
                await websocket.send_json(event.as_dict())
        except WebSocketDisconnect:
            pass
        finally:
            subscription.close()

    return app
