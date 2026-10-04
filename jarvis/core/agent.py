from __future__ import annotations

from datetime import datetime, timezone
import json
import threading
from typing import Any, Callable

from jarvis.config import settings
from jarvis.core.events import EventBus
from jarvis.core.file_index import FileIndex
from jarvis.core.health import HealthService
from jarvis.core.jobs import JobManager
from jarvis.core.llm import LLMClient
from jarvis.core.local_commands import LocalCommandRouter
from jarvis.core.mcp_bridge import MCPManager
from jarvis.core.memory import MemoryStore
from jarvis.core.permissions import PermissionEngine
from jarvis.core.platform_store import PlatformStore
from jarvis.core.scheduler import TaskScheduler
from jarvis.core.skills import SkillManager
from jarvis.core.tools import Tool, ToolRegistry
from jarvis.core.undo import UndoManager
from jarvis.core.updater import UpdateService
from jarvis.knowledge import KnowledgeBase
from jarvis.profile import OWNER_PROFILE
from jarvis.tools.clipboard import clipboard_read, clipboard_write
from jarvis.tools.files import (
    file_patch,
    file_patch_preview,
    file_read,
    file_write,
    workspace_path,
)
from jarvis.tools.pc import pc_control
from jarvis.tools.sandbox import python_sandbox
from jarvis.tools.screen import capture_screen, list_monitors
from jarvis.tools.system import system_status
from jarvis.tools.ui_automation import activate_ui, control_action, inspect_ui
from jarvis.tools.web import read_page, web_search
from jarvis.tools.windows import active_window, focus_window, list_windows, window_action
from jarvis.workflows import WorkflowEngine


ProgressFn = Callable[[str], None]


SYSTEM_PROMPT = f"""
You are J.A.R.V.I.S., H@CKERBOY's local desktop AI agent.

{OWNER_PROFILE}

Operating rules:
- Speak French by default unless H@CKERBOY uses another language.
- Be concise in voice mode and practical in desktop mode.
- Never claim a PC, file, MCP, scheduler, or sandbox action succeeded unless a tool returned success.
- Use system_status for real machine telemetry.
- Use pc_control only for explicitly requested allowlisted local actions.
- Use web_search/read_page when current public information is genuinely needed.
- Use knowledge_search when local indexed documents may contain the answer.
- Use file_read/file_write/file_patch only inside the configured workspace.
- Never request or expose .env files, credentials, private keys, tokens, or hidden secret stores.
- Use python_sandbox only for restricted computation; it is not a general shell.
- Skills are reusable instructions. Load one with use_skill when its catalog description matches the task.
- MCP servers are explicit external integrations. Inspect configured servers/tools before calling one.
- Use remember_fact only when H@CKERBOY explicitly asks you to remember a personal fact or preference.
- Scheduler actions create persistent future work. Never silently schedule work the user did not request.
- In operative mode, use operative_state_get/set to maintain useful persistent task state.
- Never invent access to files, apps, sensors, accounts, hardware, skills, or MCP servers.
- For actions that could modify/delete user data or invoke an external MCP action, require explicit confirmation
  and only use tools specifically designed for that operation.
""".strip()


class JarvisAgent:
    def __init__(self, confirm: Callable[[str], bool] | None = None) -> None:
        self.memory = MemoryStore(settings.database_path)
        self.knowledge = KnowledgeBase(settings.database_path)
        self.events = EventBus()
        self.platform = PlatformStore(settings.database_path)
        self.permissions = PermissionEngine(settings.database_path)
        self.jobs = JobManager(self.events)
        self.health = HealthService(self.platform)
        self.file_index = FileIndex(settings.database_path)
        self.undo = UndoManager()
        self.updater = UpdateService()
        self.llm = LLMClient()
        self.local_router = LocalCommandRouter()
        self.workflows = WorkflowEngine(self.llm)
        self.confirm = confirm or (lambda _: False)
        self.skills = SkillManager()
        self.mcp = MCPManager()
        self._context = threading.local()
        self.tools = ToolRegistry()
        self.scheduler = TaskScheduler(
            settings.database_path,
            callback=self._run_scheduled_task,
        )
        self._register_tools()
        if settings.scheduler_enabled:
            self.scheduler.start()

    def _current_operator_id(self) -> str:
        return str(getattr(self._context, "operator_id", "main") or "main")

    def _register_tools(self) -> None:
        self.tools.register(
            Tool(
                name="system_status",
                description="Read CPU, memory, platform and runtime status of the local PC.",
                fn=system_status,
                parameters={"type": "object", "properties": {}, "additionalProperties": False},
            )
        )

        self.tools.register(
            Tool(
                name="pc_control",
                description=(
                    "Open an allowlisted local app, known folder, or http/https URL. "
                    "Use only when the user explicitly asks for the desktop action."
                ),
                fn=pc_control,
                parameters={
                    "type": "object",
                    "properties": {
                        "action": {
                            "type": "string",
                            "enum": ["open_app", "open_folder", "open_url"],
                        },
                        "target": {"type": "string"},
                    },
                    "required": ["action", "target"],
                    "additionalProperties": False,
                },
                requires_confirmation=settings.confirm_safe_pc_actions,
            )
        )

        self.tools.register(
            Tool(
                name="web_search",
                description=(
                    "Search the public web through Exa semantic search and return "
                    "token-efficient page highlights."
                ),
                fn=web_search,
                parameters={
                    "type": "object",
                    "properties": {
                        "query": {"type": "string"},
                        "num": {"type": "integer", "minimum": 1, "maximum": 10},
                    },
                    "required": ["query"],
                    "additionalProperties": False,
                },
            )
        )

        self.tools.register(
            Tool(
                name="read_page",
                description="Read text from a public http/https webpage with SSRF protection.",
                fn=read_page,
                parameters={
                    "type": "object",
                    "properties": {"url": {"type": "string"}},
                    "required": ["url"],
                    "additionalProperties": False,
                },
            )
        )

        self.tools.register(
            Tool(
                name="knowledge_search",
                description=(
                    "Search indexed local knowledge. Uses BM25 and optional dense embeddings "
                    "when configured."
                ),
                fn=lambda args: {
                    "results": self.knowledge.search(
                        str(args.get("query", "")),
                        top_k=int(args.get("top_k", 5) or 5),
                    )
                },
                parameters={
                    "type": "object",
                    "properties": {
                        "query": {"type": "string"},
                        "top_k": {"type": "integer", "minimum": 1, "maximum": 10},
                    },
                    "required": ["query"],
                    "additionalProperties": False,
                },
            )
        )

        self.tools.register(
            Tool(
                name="file_read",
                description=(
                    "Read a UTF-8 text file inside the configured JARVIS workspace. "
                    "Secret files and paths outside the workspace are blocked."
                ),
                fn=file_read,
                parameters={
                    "type": "object",
                    "properties": {
                        "path": {"type": "string"},
                        "max_chars": {"type": "integer", "minimum": 200, "maximum": 80000},
                    },
                    "required": ["path"],
                    "additionalProperties": False,
                },
            )
        )

        self.tools.register(
            Tool(
                name="file_write",
                description="Create or explicitly overwrite a text file inside the workspace.",
                fn=self._file_write_with_undo,
                parameters={
                    "type": "object",
                    "properties": {
                        "path": {"type": "string"},
                        "content": {"type": "string"},
                        "overwrite": {"type": "boolean"},
                    },
                    "required": ["path", "content"],
                    "additionalProperties": False,
                },
                requires_confirmation=True,
            )
        )

        self.tools.register(
            Tool(
                name="file_patch",
                description=(
                    "Apply an exact text replacement inside a workspace file. "
                    "Use a precise old block and replacement new block."
                ),
                fn=self._file_patch_with_undo,
                parameters={
                    "type": "object",
                    "properties": {
                        "path": {"type": "string"},
                        "old": {"type": "string"},
                        "new": {"type": "string"},
                        "replace_all": {"type": "boolean"},
                    },
                    "required": ["path", "old", "new"],
                    "additionalProperties": False,
                },
                requires_confirmation=True,
            )
        )

        self.tools.register(
            Tool(
                name="file_patch_preview",
                description="Preview an exact file patch as a unified diff without modifying the file.",
                fn=file_patch_preview,
                parameters={
                    "type": "object",
                    "properties": {
                        "path": {"type": "string"},
                        "old": {"type": "string"},
                        "new": {"type": "string"},
                        "replace_all": {"type": "boolean"},
                    },
                    "required": ["path", "old", "new"],
                    "additionalProperties": False,
                },
            )
        )
        self.tools.register(
            Tool(
                name="file_undo",
                description="Undo a JARVIS text-file edit by its returned undo_id.",
                fn=lambda args: self.undo.undo(str(args.get("undo_id", ""))),
                parameters={
                    "type": "object",
                    "properties": {"undo_id": {"type": "string"}},
                    "required": ["undo_id"],
                    "additionalProperties": False,
                },
                requires_confirmation=True,
            )
        )

        self.tools.register(
            Tool(
                name="python_sandbox",
                description=(
                    "Execute restricted Python computation with a short timeout. "
                    "Filesystem, network, subprocess and unsafe builtins are unavailable."
                ),
                fn=python_sandbox,
                parameters={
                    "type": "object",
                    "properties": {
                        "code": {"type": "string"},
                        "timeout_seconds": {"type": "integer", "minimum": 1, "maximum": 10},
                    },
                    "required": ["code"],
                    "additionalProperties": False,
                },
                requires_confirmation=True,
            )
        )

        self.tools.register(
            Tool(
                name="use_skill",
                description="Load an installed JARVIS skill's instructions/pipeline metadata.",
                fn=lambda args: self.skills.load(str(args.get("name", ""))),
                parameters={
                    "type": "object",
                    "properties": {"name": {"type": "string"}},
                    "required": ["name"],
                    "additionalProperties": False,
                },
            )
        )

        self.tools.register(
            Tool(
                name="mcp_servers",
                description="List MCP servers explicitly configured for JARVIS.",
                fn=lambda _: {"servers": self.mcp.list_servers()},
                parameters={"type": "object", "properties": {}, "additionalProperties": False},
            )
        )

        self.tools.register(
            Tool(
                name="mcp_list_tools",
                description="List tools exposed by one configured MCP server.",
                fn=lambda args: self.mcp.list_tools(str(args.get("server", ""))),
                parameters={
                    "type": "object",
                    "properties": {"server": {"type": "string"}},
                    "required": ["server"],
                    "additionalProperties": False,
                },
            )
        )

        self.tools.register(
            Tool(
                name="mcp_call",
                description="Call a tool on an explicitly configured MCP server.",
                fn=lambda args: self.mcp.call_tool(
                    str(args.get("server", "")),
                    str(args.get("tool", "")),
                    dict(args.get("arguments") or {}),
                ),
                parameters={
                    "type": "object",
                    "properties": {
                        "server": {"type": "string"},
                        "tool": {"type": "string"},
                        "arguments": {"type": "object"},
                    },
                    "required": ["server", "tool"],
                    "additionalProperties": False,
                },
                requires_confirmation=True,
            )
        )

        self.tools.register(
            Tool(
                name="schedule_task",
                description=(
                    "Schedule a persistent future agent task. schedule_type is once, interval or cron."
                ),
                fn=lambda args: self.scheduler.create(
                    prompt=str(args.get("prompt", "")),
                    schedule_type=str(args.get("schedule_type", "")),
                    schedule_value=str(args.get("schedule_value", "")),
                    agent_mode=str(args.get("agent_mode", "operative")),
                ),
                parameters={
                    "type": "object",
                    "properties": {
                        "prompt": {"type": "string"},
                        "schedule_type": {
                            "type": "string",
                            "enum": ["once", "interval", "cron"],
                        },
                        "schedule_value": {"type": "string"},
                        "agent_mode": {
                            "type": "string",
                            "enum": ["standard", "operative", "research"],
                        },
                    },
                    "required": ["prompt", "schedule_type", "schedule_value"],
                    "additionalProperties": False,
                },
                requires_confirmation=True,
            )
        )

        self.tools.register(
            Tool(
                name="list_scheduled_tasks",
                description="List persistent JARVIS scheduled tasks and their status.",
                fn=lambda args: {"tasks": self.scheduler.list(int(args.get("limit", 50) or 50))},
                parameters={
                    "type": "object",
                    "properties": {
                        "limit": {"type": "integer", "minimum": 1, "maximum": 100},
                    },
                    "additionalProperties": False,
                },
            )
        )

        for name, description, fn in (
            ("pause_scheduled_task", "Pause a scheduled task.", self.scheduler.pause),
            ("resume_scheduled_task", "Resume and recalculate the next run of a task.", self.scheduler.resume),
            ("cancel_scheduled_task", "Permanently cancel a scheduled task.", self.scheduler.cancel),
        ):
            self.tools.register(
                Tool(
                    name=name,
                    description=description,
                    fn=lambda args, action=fn: action(str(args.get("task_id", ""))),
                    parameters={
                        "type": "object",
                        "properties": {"task_id": {"type": "string"}},
                        "required": ["task_id"],
                        "additionalProperties": False,
                    },
                    requires_confirmation=True,
                )
            )

        self.tools.register(
            Tool(
                name="operative_state_get",
                description="Read persistent state for the current operative agent.",
                fn=lambda _: {
                    "operator_id": self._current_operator_id(),
                    "state": self.memory.get_operative_state(self._current_operator_id()),
                },
                parameters={"type": "object", "properties": {}, "additionalProperties": False},
            )
        )

        self.tools.register(
            Tool(
                name="operative_state_set",
                description=(
                    "Replace persistent state for the current operative agent with a compact JSON object."
                ),
                fn=self._operative_state_set,
                parameters={
                    "type": "object",
                    "properties": {"state": {"type": "object"}},
                    "required": ["state"],
                    "additionalProperties": False,
                },
            )
        )

        self.tools.register(
            Tool(
                name="remember_fact",
                description=(
                    "Store a personal fact or preference only when H@CKERBOY explicitly asks "
                    "J.A.R.V.I.S. to remember it."
                ),
                fn=self._remember_fact,
                parameters={
                    "type": "object",
                    "properties": {
                        "key": {"type": "string"},
                        "value": {"type": "string"},
                    },
                    "required": ["key", "value"],
                    "additionalProperties": False,
                },
            )
        )

        self.tools.register(
            Tool(
                name="clipboard_read",
                description="Read current Windows clipboard text after permission.",
                fn=clipboard_read,
                parameters={"type": "object", "properties": {}, "additionalProperties": False},
                requires_confirmation=True,
            )
        )
        self.tools.register(
            Tool(
                name="clipboard_write",
                description="Copy text to the Windows clipboard.",
                fn=clipboard_write,
                parameters={
                    "type": "object",
                    "properties": {"text": {"type": "string"}},
                    "required": ["text"],
                    "additionalProperties": False,
                },
            )
        )
        self.tools.register(
            Tool(
                name="list_windows",
                description="List visible Windows desktop windows and their bounds.",
                fn=list_windows,
                parameters={"type": "object", "properties": {}, "additionalProperties": False},
            )
        )
        self.tools.register(
            Tool(
                name="active_window",
                description="Read the currently focused Windows window.",
                fn=active_window,
                parameters={"type": "object", "properties": {}, "additionalProperties": False},
            )
        )
        self.tools.register(
            Tool(
                name="focus_window",
                description="Focus or restore a visible window by title.",
                fn=focus_window,
                parameters={
                    "type": "object",
                    "properties": {"title": {"type": "string"}},
                    "required": ["title"],
                    "additionalProperties": False,
                },
                requires_confirmation=True,
            )
        )
        self.tools.register(
            Tool(
                name="list_monitors",
                description="List monitors visible to the local Windows session.",
                fn=list_monitors,
                parameters={"type": "object", "properties": {}, "additionalProperties": False},
            )
        )
        self.tools.register(
            Tool(
                name="capture_screen",
                description="Capture a monitor to a local PNG only when explicitly authorized.",
                fn=capture_screen,
                parameters={
                    "type": "object",
                    "properties": {"monitor": {"type": "integer", "minimum": 0, "maximum": 16}},
                    "additionalProperties": False,
                },
                requires_confirmation=True,
            )
        )
        self.tools.register(
            Tool(
                name="inspect_ui",
                description="Read-only inspection of visible window-level UI information.",
                fn=inspect_ui,
                parameters={
                    "type": "object",
                    "properties": {"title": {"type": "string"}},
                    "additionalProperties": False,
                },
            )
        )
        self.tools.register(
            Tool(
                name="activate_ui",
                description="Safely focus a named visible application window.",
                fn=activate_ui,
                parameters={
                    "type": "object",
                    "properties": {"title": {"type": "string"}},
                    "required": ["title"],
                    "additionalProperties": False,
                },
                requires_confirmation=True,
            )
        )

        self.tools.register(
            Tool(
                name="window_action",
                description="Focus, minimize, maximize or restore a named visible Windows window.",
                fn=window_action,
                parameters={
                    "type": "object",
                    "properties": {
                        "title": {"type": "string"},
                        "action": {
                            "type": "string",
                            "enum": ["focus", "minimize", "maximize", "restore"],
                        },
                    },
                    "required": ["title", "action"],
                    "additionalProperties": False,
                },
                requires_confirmation=True,
            )
        )
        self.tools.register(
            Tool(
                name="ui_control",
                description=(
                    "Interact with a named UI Automation control by semantic name. "
                    "Raw pointer coordinates are intentionally unsupported."
                ),
                fn=control_action,
                parameters={
                    "type": "object",
                    "properties": {
                        "window": {"type": "string"},
                        "control": {"type": "string"},
                        "action": {"type": "string", "enum": ["click", "set_text"]},
                        "value": {"type": "string"},
                    },
                    "required": ["window", "control", "action"],
                    "additionalProperties": False,
                },
                requires_confirmation=True,
            )
        )
        self.tools.register(
            Tool(
                name="search_files",
                description="Search the local indexed workspace by filename/path.",
                fn=lambda args: {
                    "results": self.file_index.search(
                        str(args.get("query", "")),
                        limit=int(args.get("limit", 40) or 40),
                    )
                },
                parameters={
                    "type": "object",
                    "properties": {
                        "query": {"type": "string"},
                        "limit": {"type": "integer", "minimum": 1, "maximum": 100},
                    },
                    "required": ["query"],
                    "additionalProperties": False,
                },
            )
        )
        self.tools.register(
            Tool(
                name="platform_health",
                description="Read JARVIS platform health and local subsystem status.",
                fn=lambda _: self.health.snapshot(),
                parameters={"type": "object", "properties": {}, "additionalProperties": False},
            )
        )

    def _file_write_with_undo(self, args: dict[str, Any]) -> dict[str, Any]:
        path = workspace_path(str(args.get("path", "")))
        before = ""
        if path.exists() and path.is_file():
            before = path.read_text(encoding="utf-8", errors="strict")
        result = file_write(args)
        after = path.read_text(encoding="utf-8", errors="strict")
        undo_id = self.undo.record(path, before, after)
        return {**result, "undo_id": undo_id}

    def _file_patch_with_undo(self, args: dict[str, Any]) -> dict[str, Any]:
        path = workspace_path(str(args.get("path", "")))
        before = path.read_text(encoding="utf-8", errors="strict")
        preview = file_patch_preview(args)
        result = file_patch(args)
        after = path.read_text(encoding="utf-8", errors="strict")
        undo_id = self.undo.record(path, before, after)
        return {
            **result,
            "undo_id": undo_id,
            "diff": preview.get("diff", ""),
        }

    def _operative_state_set(self, args: dict[str, Any]) -> dict[str, Any]:
        state = args.get("state")
        if not isinstance(state, dict):
            raise ValueError("state doit être un objet JSON.")
        operator_id = self._current_operator_id()
        self.memory.set_operative_state(operator_id, state)
        return {"stored": True, "operator_id": operator_id, "state": state}

    def _remember_fact(self, args: dict[str, Any]) -> dict[str, Any]:
        key = str(args.get("key", "")).strip()[:100]
        value = str(args.get("value", "")).strip()[:1000]
        if not key or not value:
            raise ValueError("key et value sont requis.")
        self.memory.set_fact(key, value)
        return {"stored": True, "key": key, "value": value}

    def _prior_work_context(self) -> str:
        results = self.memory.recent_agent_results(limit=8)
        if not results:
            return ""

        lines = ["=== PRIOR WORK MEMORY ==="]
        for item in results:
            lines.append(
                f"[{item['created_at']}] {item['workflow']} · {item['task']}\n"
                f"{item['summary'][:900]}"
            )
        lines.append("Reuse prior work only when relevant to the current request.")
        return "\n\n".join(lines)

    def _messages(
        self,
        user_text: str,
        extra_context: str = "",
        include_recent: bool = True,
    ) -> list[dict[str, Any]]:
        facts = self.memory.facts()
        memory_context = json.dumps(facts, ensure_ascii=False)
        rag_context = self.knowledge.context_for(user_text, top_k=5)
        prior_context = self._prior_work_context()
        skill_catalog = self.skills.catalog()

        system_sections = [
            SYSTEM_PROMPT,
            f"Known memory facts: {memory_context}",
        ]
        if skill_catalog:
            system_sections.append(skill_catalog)
        if prior_context:
            system_sections.append(prior_context)
        if rag_context:
            system_sections.append(rag_context)
        if extra_context:
            system_sections.append(extra_context)

        messages: list[dict[str, Any]] = [
            {"role": "system", "content": "\n\n".join(system_sections)}
        ]
        recent = self.memory.recent_messages(limit=20) if include_recent else []
        messages.extend(recent)
        if (
            not recent
            or recent[-1].get("role") != "user"
            or recent[-1].get("content") != user_text
        ):
            messages.append({"role": "user", "content": user_text})
        return messages

    def _confirm_summary(self, name: str, args: dict[str, Any]) -> str:
        if name in {"file_write", "file_patch"}:
            return f"Autoriser {name} sur {args.get('path', '?')} ?"
        if name == "python_sandbox":
            return "Autoriser l'exécution de ce code dans le sandbox Python restreint ?"
        if name == "mcp_call":
            return (
                f"Autoriser MCP {args.get('server', '?')} · "
                f"{args.get('tool', '?')} ?"
            )
        if name == "schedule_task":
            prompt = str(args.get("prompt", ""))[:160]
            return f"Planifier cette tâche JARVIS : {prompt} ?"
        if name.endswith("_scheduled_task"):
            return f"Autoriser {name} pour la tâche {args.get('task_id', '?')} ?"
        return f"Autoriser J.A.R.V.I.S. à exécuter {name} ?"

    @staticmethod
    def _capability_for_tool(name: str) -> str:
        mapping = {
            "system_status": "system.read",
            "platform_health": "system.read",
            "knowledge_search": "knowledge.read",
            "file_read": "files.read",
            "file_write": "files.write",
            "file_patch": "files.write",
            "file_patch_preview": "files.read",
            "file_undo": "files.write",
            "clipboard_read": "clipboard.read",
            "clipboard_write": "clipboard.write",
            "list_windows": "windows.inspect",
            "active_window": "windows.inspect",
            "focus_window": "windows.focus",
            "inspect_ui": "windows.inspect",
            "activate_ui": "windows.focus",
            "window_action": "windows.focus",
            "ui_control": "ui.click",
            "capture_screen": "screen.read",
            "list_monitors": "screen.read",
            "web_search": "network.web",
            "read_page": "network.web",
            "mcp_call": "mcp.call",
            "python_sandbox": "sandbox.run",
            "schedule_task": "scheduler.write",
            "pause_scheduled_task": "scheduler.write",
            "resume_scheduled_task": "scheduler.write",
            "cancel_scheduled_task": "scheduler.write",
        }
        return mapping.get(name, "system.read")

    def _execute_tool(
        self,
        name: str,
        args: dict[str, Any],
        progress: ProgressFn,
    ) -> dict[str, Any]:
        try:
            tool = self.tools.get(name)
        except ValueError as exc:
            return {"ok": False, "error": str(exc)}

        progress(f"TOOL · {name.upper()}")
        capability = self._capability_for_tool(name)
        permission = self.permissions.get(capability)
        self.events.publish(
            "tool.started",
            {"tool": name, "capability": capability, "permission": permission.decision.value},
        )

        must_confirm = tool.requires_confirmation or permission.decision.value == "ask"
        if permission.decision.value == "deny":
            result = {"ok": False, "error": f"Permission refusée : {capability}"}
            self.platform.log("permission", "denied", {"tool": name, "capability": capability})
            self.events.publish("tool.denied", {"tool": name, "capability": capability})
            return result

        if must_confirm and not self.confirm(self._confirm_summary(name, args)):
            result = {"ok": False, "error": "Action refusée par l'utilisateur"}
            self.platform.log("permission", "rejected", {"tool": name, "capability": capability})
            self.events.publish("tool.denied", {"tool": name, "capability": capability})
            return result

        try:
            result = {"ok": True, "data": self.tools.execute(name, args)}
        except Exception as exc:
            result = {"ok": False, "error": str(exc)}

        self.memory.log_action(name, args, result)
        self.platform.log("tool", name, {"args": args, "result": result})
        self.events.publish("tool.completed", {"tool": name, "result": result})
        return result

    def _run_local_fallback(self, clean: str, progress: ProgressFn) -> str | None:
        routed = self.local_router.parse(clean)
        if routed is None:
            return None

        name, args = routed
        if name == "local_reply":
            return str(args.get("text", "")).strip()

        try:
            tool = self.tools.get(name)
        except ValueError:
            return None

        progress(f"LOCAL · {name.upper()}")
        outcome = self._execute_tool(name, args, progress)
        if not outcome.get("ok"):
            return f"Action locale impossible : {outcome.get('error', 'erreur inconnue')}"

        result = outcome.get("data") or {}
        if name == "system_status":
            return (
                f"CPU {result.get('cpu_percent', '?')} %, "
                f"RAM {result.get('memory_used_percent', '?')} %, "
                f"système {result.get('platform', 'inconnu')}."
            )
        if name == "pc_control":
            return "Action exécutée, H@CKERBOY."
        return json.dumps(result, ensure_ascii=False)

    def _run_standard(
        self,
        clean: str,
        progress: ProgressFn,
        extra_context: str = "",
        include_recent: bool = True,
        max_steps: int = 6,
        local_fallback: bool = True,
    ) -> str:
        if local_fallback:
            local = self._run_local_fallback(clean, progress)
            if local is not None:
                return local

        messages = self._messages(
            clean,
            extra_context=extra_context,
            include_recent=include_recent,
        )

        for step in range(1, max(1, min(max_steps, 20)) + 1):
            progress("THINKING" if step == 1 else f"TOOL LOOP · ÉTAPE {step}")
            try:
                result = self.llm.complete(messages, self.tools.definitions())
            except Exception as exc:
                return f"Erreur du moteur IA : {exc}"

            message = result.get("message") or {}
            calls = message.get("tool_calls") or []
            if not calls:
                return str(message.get("content") or "").strip()

            messages.append(message)
            for call in calls:
                function = call.get("function") or {}
                name = str(function.get("name") or "")
                raw_args = function.get("arguments") or "{}"
                try:
                    args = (
                        json.loads(raw_args)
                        if isinstance(raw_args, str)
                        else dict(raw_args)
                    )
                except (json.JSONDecodeError, TypeError, ValueError):
                    args = {}

                tool_result = self._execute_tool(name, args, progress)
                messages.append(
                    {
                        "role": "tool",
                        "tool_call_id": str(call.get("id") or ""),
                        "name": name,
                        "content": json.dumps(tool_result, ensure_ascii=False),
                    }
                )

        return "J'ai atteint ma limite d'actions pour ce tour, H@CKERBOY."

    def _run_operative(
        self,
        clean: str,
        progress: ProgressFn,
        operator_id: str,
    ) -> str:
        state = self.memory.get_operative_state(operator_id)
        runs = self.memory.recent_operative_runs(operator_id, limit=6)

        history_lines = []
        for item in runs:
            history_lines.append(
                f"[{item['created_at']}] USER: {item['prompt'][:700]}\n"
                f"JARVIS: {item['answer'][:1000]}"
            )

        operative_context = (
            "=== OPERATIVE MODE ===\n"
            f"operator_id: {operator_id}\n"
            "You are a persistent operator. Continue the mission across runs. "
            "Inspect the stored state, update it with operative_state_set when durable "
            "progress, blockers, decisions, or next actions change. Do not invent completed work.\n"
            f"Persistent state: {json.dumps(state, ensure_ascii=False)}"
        )
        if history_lines:
            operative_context += "\n\nRecent operator runs:\n" + "\n\n".join(history_lines)

        progress(f"OPERATIVE · {operator_id}")
        answer = self._run_standard(
            clean,
            progress,
            extra_context=operative_context,
            include_recent=False,
            max_steps=12,
            local_fallback=False,
        )

        latest = self.memory.get_operative_state(operator_id)
        latest["last_prompt"] = clean[:2000]
        latest["last_answer"] = answer[:5000]
        latest["last_run_at"] = datetime.now(timezone.utc).isoformat()
        self.memory.set_operative_state(operator_id, latest)
        self.memory.add_operative_run(operator_id, clean, answer)
        return answer

    def _run_scheduled_task(self, task: dict[str, Any]) -> None:
        task_id = str(task.get("id", "unknown"))
        prompt = str(task.get("prompt", "")).strip()
        mode = str(task.get("agent_mode", "operative")).strip().lower()
        if not prompt:
            return
        self.ask(
            prompt,
            mode=mode,
            progress=lambda _: None,
            operator_id=f"schedule:{task_id}",
        )

    def ask(
        self,
        user_text: str,
        mode: str = "standard",
        progress: ProgressFn | None = None,
        operator_id: str = "main",
    ) -> str:
        clean = user_text.strip()
        if not clean:
            return ""

        progress = progress or (lambda _: None)
        normalized_mode = mode.strip().lower()
        clean_operator_id = operator_id.strip()[:120] or "main"
        self._context.operator_id = clean_operator_id
        self.memory.add_message("user", clean)

        try:
            if normalized_mode == "parallel":
                result = self.workflows.parallel(clean, progress)
                answer = result.answer
                self.memory.add_agent_result(clean, result.mode, answer)
            elif normalized_mode == "sequential":
                result = self.workflows.sequential(clean, progress)
                answer = result.answer
                self.memory.add_agent_result(clean, result.mode, answer)
            elif normalized_mode == "debate":
                result = self.workflows.debate(clean, progress)
                answer = result.answer
                self.memory.add_agent_result(clean, result.mode, answer)
            elif normalized_mode == "research":
                result = self.workflows.research(clean, progress)
                answer = result.answer
                self.memory.add_agent_result(clean, result.mode, answer)
            elif normalized_mode == "operative":
                answer = self._run_operative(clean, progress, clean_operator_id)
            else:
                answer = self._run_standard(clean, progress)
        except Exception as exc:
            answer = f"Erreur agent : {exc}"
        finally:
            self._context.operator_id = "main"

        self.memory.add_message("assistant", answer)
        return answer

    def shutdown(self) -> None:
        self.scheduler.stop()
        self.jobs.shutdown()
        self.permissions.clear_session()
        self.events.publish("core.shutdown", {})
