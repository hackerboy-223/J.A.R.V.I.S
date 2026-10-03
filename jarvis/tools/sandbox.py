from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
from typing import Any

from jarvis.config import DATA_DIR
from jarvis.sandbox_runner import validate_sandbox_code


def python_sandbox(args: dict[str, Any]) -> dict[str, Any]:
    code = str(args.get("code", ""))
    if not code.strip():
        raise ValueError("code est requis.")
    if len(code) > 30000:
        raise ValueError("Code trop volumineux pour le sandbox.")

    validate_sandbox_code(code)

    sandbox_root = DATA_DIR / "sandbox"
    sandbox_root.mkdir(parents=True, exist_ok=True)

    timeout = max(1, min(int(args.get("timeout_seconds", 5) or 5), 10))
    with tempfile.TemporaryDirectory(prefix="run-", dir=sandbox_root) as tmp:
        if getattr(sys, "frozen", False):
            command = [sys.executable, "--jarvis-sandbox-runner"]
        else:
            command = [sys.executable, "-I", "-m", "jarvis.sandbox_runner"]

        # Preserve only Windows variables required to start a child process;
        # do not pass API tokens or the user's full environment into the sandbox.
        safe_env = {
            name: os.environ[name]
            for name in ("SYSTEMROOT", "WINDIR", "TEMP", "TMP")
            if os.environ.get(name)
        }

        try:
            completed = subprocess.run(
                command,
                cwd=tmp,
                capture_output=True,
                text=True,
                input=json.dumps({"code": code}, ensure_ascii=False),
                timeout=timeout,
                env=safe_env,
                creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
            )
        except subprocess.TimeoutExpired as exc:
            raise RuntimeError(f"Sandbox interrompu après {timeout} secondes.") from exc

    return {
        "returncode": completed.returncode,
        "stdout": completed.stdout[-12000:],
        "stderr": completed.stderr[-12000:],
        "restricted": True,
    }
