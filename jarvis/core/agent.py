from __future__ import annotations

import json
from typing import Any, Callable

from jarvis.config import settings
from jarvis.core.llm import LLMClient
from jarvis.core.memory import MemoryStore
from jarvis.core.tools import Tool, ToolRegistry
from jarvis.knowledge import KnowledgeBase
from jarvis.profile import OWNER_PROFILE
from jarvis.tools.pc import pc_control
from jarvis.tools.system import system_status
from jarvis.tools.web import read_page, web_search
from jarvis.workflows import WorkflowEngine


ProgressFn = Callable[[str], None]


SYSTEM_PROMPT = f"""
You are J.A.R.V.I.S., H@CKERBOY's local desktop AI agent.

{OWNER_PROFILE}

Operating rules:
- Speak French by default unless H@CKERBOY uses another language.
- Be concise in voice mode and practical in desktop mode.
- Never claim a PC action succeeded unless a tool returned success.
- Use system_status for real machine telemetry.
- Use pc_control only for explicitly requested allowlisted local actions.
- Use web_search/read_page when current public information is genuinely needed.
- Use knowledge_search when the user's local documents may contain the answer.
- Use remember_fact only when the user explicitly asks you to remember a personal fact or preference.
- Never invent access to files, apps, sensors, accounts, or hardware.
- For actions that could modify or delete user data, require explicit confirmation
  and only use tools specifically designed for that operation.
""".strip()


class JarvisAgent:
    def __init__(self, confirm: Callable[[str], bool] | None = None) -> None:
        self.memory = MemoryStore(settings.database_path)
        self.knowledge = KnowledgeBase(settings.database_path)
        self.llm = LLMClient()
        self.workflows = WorkflowEngine(self.llm)
        self.confirm = confirm or (lambda _: False)
        self.tools = ToolRegistry()
        self._register_tools()

    def _register_tools(self) -> None:
        self.tools.register(
            Tool(
                name="system_status",
                description="Read CPU, memory, platform and runtime status of the local PC.",
                fn=system_status,
                parameters={
                    "type": "object",
                    "properties": {},
                    "additionalProperties": False,
                },
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
                requires_confirmation=True,
            )
        )

        self.tools.register(
            Tool(
                name="web_search",
                description="Search the public web for recent information through Serper.",
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
                description="Read text from a public http/https webpage with local-network protection.",
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
                description="Search H@CKERBOY's local indexed documents and return relevant chunks.",
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

    def _messages(self, user_text: str) -> list[dict[str, Any]]:
        facts = self.memory.facts()
        memory_context = json.dumps(facts, ensure_ascii=False)
        rag_context = self.knowledge.context_for(user_text, top_k=5)
        prior_context = self._prior_work_context()

        system_sections = [
            SYSTEM_PROMPT,
            f"Known memory facts: {memory_context}",
        ]
        if prior_context:
            system_sections.append(prior_context)
        if rag_context:
            system_sections.append(rag_context)

        messages: list[dict[str, Any]] = [
            {
                "role": "system",
                "content": "\n\n".join(system_sections),
            }
        ]
        recent = self.memory.recent_messages(limit=20)
        messages.extend(recent)
        if not recent or recent[-1].get("role") != "user" or recent[-1].get("content") != user_text:
            messages.append({"role": "user", "content": user_text})
        return messages

    def _run_standard(self, clean: str, progress: ProgressFn) -> str:
        messages = self._messages(clean)

        for step in range(1, 7):
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
                    args = json.loads(raw_args) if isinstance(raw_args, str) else dict(raw_args)
                except (json.JSONDecodeError, TypeError, ValueError):
                    args = {}

                try:
                    tool = self.tools.get(name)
                except ValueError as exc:
                    tool_result = {"ok": False, "error": str(exc)}
                else:
                    progress(f"TOOL · {name.upper()}")
                    if tool.requires_confirmation:
                        summary = f"Autoriser J.A.R.V.I.S. à exécuter {name} avec {args} ?"
                        if not self.confirm(summary):
                            tool_result = {"ok": False, "error": "Action refusée par l'utilisateur"}
                        else:
                            try:
                                tool_result = {"ok": True, "data": self.tools.execute(name, args)}
                            except Exception as exc:
                                tool_result = {"ok": False, "error": str(exc)}
                    else:
                        try:
                            tool_result = {"ok": True, "data": self.tools.execute(name, args)}
                        except Exception as exc:
                            tool_result = {"ok": False, "error": str(exc)}

                self.memory.log_action(name, args, tool_result)
                messages.append(
                    {
                        "role": "tool",
                        "tool_call_id": str(call.get("id") or ""),
                        "name": name,
                        "content": json.dumps(tool_result, ensure_ascii=False),
                    }
                )

        return "J'ai atteint ma limite d'actions pour ce tour, H@CKERBOY."

    def ask(
        self,
        user_text: str,
        mode: str = "standard",
        progress: ProgressFn | None = None,
    ) -> str:
        clean = user_text.strip()
        if not clean:
            return ""

        progress = progress or (lambda _: None)
        normalized_mode = mode.strip().lower()
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
            else:
                answer = self._run_standard(clean, progress)
        except Exception as exc:
            answer = f"Erreur agent : {exc}"

        self.memory.add_message("assistant", answer)
        return answer
