from __future__ import annotations

import json
from typing import Any, Callable

from jarvis.config import settings
from jarvis.core.llm import LLMClient
from jarvis.core.memory import MemoryStore
from jarvis.core.tools import Tool, ToolRegistry
from jarvis.profile import OWNER_PROFILE
from jarvis.tools.pc import pc_control
from jarvis.tools.system import system_status


SYSTEM_PROMPT = f"""
You are J.A.R.V.I.S., H@CKERBOY's local desktop AI agent.

{OWNER_PROFILE}

Operating rules:
- Speak French by default unless H@CKERBOY uses another language.
- Be concise in voice mode and practical in desktop mode.
- Never claim a PC action succeeded unless a tool returned success.
- Use system_status for real machine telemetry.
- Use pc_control only for explicitly requested allowlisted local actions.
- Never invent access to files, apps, sensors, accounts, or hardware.
- For actions that could modify or delete user data, require explicit confirmation
  and only use tools that are specifically designed for that operation.
""".strip()


class JarvisAgent:
    def __init__(self, confirm: Callable[[str], bool] | None = None) -> None:
        self.memory = MemoryStore(settings.database_path)
        self.llm = LLMClient()
        self.confirm = confirm or (lambda _: False)
        self.tools = ToolRegistry()
        self.tools.register(
            Tool(
                name="system_status",
                description="Read CPU, memory, platform and runtime status of the local PC.",
                fn=system_status,
            )
        )
        self.tools.register(
            Tool(
                name="pc_control",
                description=(
                    "Open an allowlisted local app, known folder, or http/https URL. "
                    "Arguments: action=open_app|open_folder|open_url, target=..."
                ),
                fn=pc_control,
                requires_confirmation=True,
            )
        )

    def _messages(self, user_text: str) -> list[dict[str, Any]]:
        facts = self.memory.facts()
        memory_context = json.dumps(facts, ensure_ascii=False)
        messages = [
            {
                "role": "system",
                "content": f"{SYSTEM_PROMPT}\nKnown memory facts: {memory_context}",
            }
        ]
        messages.extend(self.memory.recent_messages(limit=20))
        messages.append({"role": "user", "content": user_text})
        return messages

    def ask(self, user_text: str) -> str:
        clean = user_text.strip()
        if not clean:
            return ""

        self.memory.add_message("user", clean)
        messages = self._messages(clean)

        for _ in range(6):
            result = self.llm.complete(messages, self.tools.definitions())
            message = result.get("message") or {}
            calls = message.get("tool_calls") or []

            if not calls:
                answer = str(message.get("content") or "").strip()
                self.memory.add_message("assistant", answer)
                return answer

            messages.append(message)

            for call in calls:
                function = call.get("function") or {}
                name = str(function.get("name") or "")
                raw_args = function.get("arguments") or "{}"
                try:
                    args = json.loads(raw_args) if isinstance(raw_args, str) else dict(raw_args)
                except (json.JSONDecodeError, TypeError, ValueError):
                    args = {}

                tool = self.tools.get(name)

                if tool.requires_confirmation:
                    summary = f"Autoriser J.A.R.V.I.S. à exécuter {name} avec {args} ?"
                    if not self.confirm(summary):
                        tool_result = {"ok": False, "error": "Action refused by user"}
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

        fallback = "J'ai atteint ma limite d'actions pour ce tour, H@CKERBOY."
        self.memory.add_message("assistant", fallback)
        return fallback
