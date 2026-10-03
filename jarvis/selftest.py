from __future__ import annotations

import json
from pathlib import Path
import tempfile


def run() -> int:
    checks: list[tuple[str, bool, str]] = []

    def check(name: str, fn) -> None:
        try:
            detail = fn()
            checks.append((name, True, str(detail or "OK")))
        except Exception as exc:
            checks.append((name, False, f"{type(exc).__name__}: {exc}"))

    def scheduler_check() -> str:
        from jarvis.core.scheduler import TaskScheduler
        with tempfile.TemporaryDirectory() as tmp:
            db = Path(tmp) / "test.db"
            scheduler = TaskScheduler(db, callback=lambda _: None)
            task = scheduler.create("test", "interval", "60", "operative")
            assert task["enabled"] == 1
            assert scheduler.list()
            scheduler.pause(task["id"])
            scheduler.resume(task["id"])
            scheduler.cancel(task["id"])
            scheduler.stop()
        return "once/interval/cron engine import + SQLite CRUD OK"

    def operative_check() -> str:
        from jarvis.core.memory import MemoryStore
        with tempfile.TemporaryDirectory() as tmp:
            store = MemoryStore(Path(tmp) / "memory.db")
            store.set_operative_state("selftest", {"step": 2})
            assert store.get_operative_state("selftest")["step"] == 2
            store.add_operative_run("selftest", "hello", "world")
            assert store.recent_operative_runs("selftest")
        return "persistent state/history OK"

    def knowledge_check() -> str:
        from jarvis.knowledge import KnowledgeBase
        with tempfile.TemporaryDirectory() as tmp:
            kb = KnowledgeBase(Path(tmp) / "knowledge.db")

            class _OfflineEmbeddings:
                enabled = False

            kb.embedding_client = _OfflineEmbeddings()
            kb.add_text(
                "demo.txt",
                "Python est un langage de programmation. "
                "JARVIS utilise une base de connaissances locale pour retrouver des informations.",
            )
            results = kb.search("langage Python", top_k=3)
            assert results and results[0]["document"] == "demo.txt"
        return "BM25 fallback OK"

    def skills_check() -> str:
        from jarvis.core.skills import SkillManager
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "skills"
            directory = root / "demo"
            directory.mkdir(parents=True)
            (directory / "SKILL.md").write_text(
                "# Demo skill\n\nUse this skill only for the self-test.",
                encoding="utf-8",
            )
            manager = SkillManager(root)
            assert manager.list()[0]["name"] == "demo"
            loaded = manager.load("demo")
            assert "self-test" in loaded["instructions"]
        return "discovery/load OK"

    def sandbox_check() -> str:
        from jarvis.tools.sandbox import python_sandbox
        result = python_sandbox(
            {
                "code": "import math\nprint(math.sqrt(81))",
                "timeout_seconds": 3,
            }
        )
        assert result["returncode"] == 0
        assert "9.0" in result["stdout"]
        return "restricted Python subprocess OK"

    def mcp_check() -> str:
        from jarvis.core.mcp_bridge import MCPManager
        with tempfile.TemporaryDirectory() as tmp:
            config = Path(tmp) / "mcp.json"
            config.write_text(json.dumps({"servers": {}}), encoding="utf-8")
            manager = MCPManager(config)
            assert manager.list_servers() == []
        return "MCP config/parser OK"

    def api_check() -> str:
        from jarvis.api import create_app
        assert callable(create_app)
        return "FastAPI module/import OK"

    check("Scheduler", scheduler_check)
    check("Operative state", operative_check)
    check("Knowledge memory", knowledge_check)
    check("Skills", skills_check)
    check("Python sandbox", sandbox_check)
    check("MCP", mcp_check)
    check("FastAPI", api_check)

    print("\nJ.A.R.V.I.S. PLATFORM SELF-TEST")
    print("=" * 42)
    for name, ok, detail in checks:
        print(f"[{'PASS' if ok else 'FAIL'}] {name}: {detail}")

    failures = [item for item in checks if not item[1]]
    print("=" * 42)
    print(f"{len(checks) - len(failures)}/{len(checks)} checks passed.")
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(run())
