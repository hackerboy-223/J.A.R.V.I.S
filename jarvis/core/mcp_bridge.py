from __future__ import annotations

import asyncio
import json
import os
from pathlib import Path
import re
from typing import Any

from jarvis.config import settings
from jarvis.core.network import validate_service_base_url


_ENV_REF = re.compile(r"^\$\{([A-Za-z_][A-Za-z0-9_]*)\}$")


class MCPManager:
    """Explicit-config MCP client. No arbitrary server command can be supplied by the model."""

    def __init__(self, config_path: Path | None = None) -> None:
        self.config_path = (config_path or settings.mcp_config_path).expanduser().resolve()

    def _config(self) -> dict[str, Any]:
        if not self.config_path.exists():
            return {"servers": {}}
        data = json.loads(self.config_path.read_text(encoding="utf-8"))
        if not isinstance(data, dict):
            raise ValueError("Configuration MCP invalide.")
        servers = data.get("servers", {})
        if not isinstance(servers, dict):
            raise ValueError("mcp.json doit contenir un objet servers.")
        return {"servers": servers}

    def list_servers(self) -> list[dict[str, str]]:
        result = []
        for name, cfg in self._config()["servers"].items():
            if not isinstance(cfg, dict):
                continue
            transport = str(cfg.get("transport", "stdio")).lower()
            result.append({"name": str(name), "transport": transport})
        return result

    def _server(self, name: str) -> dict[str, Any]:
        cfg = self._config()["servers"].get(name)
        if not isinstance(cfg, dict):
            raise ValueError(f"Serveur MCP non configuré : {name}")
        return cfg

    @staticmethod
    def _expand_env(values: dict[str, Any]) -> dict[str, str]:
        env: dict[str, str] = {}
        for key, raw in values.items():
            text = str(raw)
            match = _ENV_REF.fullmatch(text)
            if match:
                value = os.getenv(match.group(1))
                if value is None:
                    raise RuntimeError(f"Variable d'environnement MCP absente : {match.group(1)}")
                env[str(key)] = value
            else:
                env[str(key)] = text
        return env

    def _client_for(self, name: str):
        from mcp import Client, StdioServerParameters

        cfg = self._server(name)
        transport = str(cfg.get("transport", "stdio")).lower()
        if transport in {"http", "streamable_http"}:
            url = validate_service_base_url(
                str(cfg.get("url", "")).strip(),
                label="MCP",
            )
            return Client(url)

        if transport == "stdio":
            command = str(cfg.get("command", "")).strip()
            if not command:
                raise ValueError("command est requis pour un serveur MCP stdio.")
            args = [str(v) for v in cfg.get("args", [])]
            env = self._expand_env(cfg.get("env", {}))
            cwd_raw = cfg.get("cwd")
            cwd = str(Path(cwd_raw).expanduser().resolve()) if cwd_raw else None
            return Client(StdioServerParameters(command=command, args=args, env=env, cwd=cwd))

        raise ValueError(f"Transport MCP non supporté : {transport}")

    async def _list_tools_async(self, server: str) -> dict[str, Any]:
        client_cm = self._client_for(server)
        async with client_cm as client:
            page = await client.list_tools()
            tools = []
            for tool in page.tools:
                tools.append(
                    {
                        "name": tool.name,
                        "description": tool.description or "",
                        "input_schema": tool.input_schema,
                    }
                )
            return {"server": server, "tools": tools}

    async def _call_async(
        self,
        server: str,
        tool: str,
        arguments: dict[str, Any],
    ) -> dict[str, Any]:
        client_cm = self._client_for(server)
        async with client_cm as client:
            result = await client.call_tool(tool, arguments)
            texts = []
            for part in getattr(result, "content", []) or []:
                text = getattr(part, "text", None)
                if text:
                    texts.append(str(text))
            return {
                "server": server,
                "tool": tool,
                "is_error": bool(getattr(result, "is_error", False)),
                "content": "\n".join(texts)[:30000],
                "structured_content": getattr(result, "structured_content", None),
            }

    @staticmethod
    def _run(coro):
        try:
            asyncio.get_running_loop()
        except RuntimeError:
            return asyncio.run(coro)

        result: list[Any] = []
        error: list[BaseException] = []

        def runner() -> None:
            try:
                result.append(asyncio.run(coro))
            except BaseException as exc:
                error.append(exc)

        import threading
        thread = threading.Thread(target=runner, daemon=True)
        thread.start()
        thread.join()
        if error:
            raise error[0]
        return result[0]

    def list_tools(self, server: str) -> dict[str, Any]:
        return self._run(self._list_tools_async(server))

    def call_tool(
        self,
        server: str,
        tool: str,
        arguments: dict[str, Any],
    ) -> dict[str, Any]:
        return self._run(self._call_async(server, tool, arguments))
