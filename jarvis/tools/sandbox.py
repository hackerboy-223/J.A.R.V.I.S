from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
import threading
from typing import Any

import psutil

from jarvis.config import DATA_DIR
from jarvis.sandbox_runner import validate_sandbox_code


_MAX_MEMORY_BYTES = 256 * 1024 * 1024
_MEMORY_POLL_SECONDS = 0.05


def _terminate_process_tree(process: subprocess.Popen[str]) -> None:
    try:
        root = psutil.Process(process.pid)
    except psutil.Error:
        try:
            process.kill()
        except Exception:
            pass
        return

    try:
        children = root.children(recursive=True)
    except psutil.Error:
        children = []

    for child in reversed(children):
        try:
            child.kill()
        except psutil.Error:
            pass
    try:
        root.kill()
    except psutil.Error:
        pass


def _memory_watch(
    process: subprocess.Popen[str],
    stop: threading.Event,
    exceeded: threading.Event,
) -> None:
    try:
        root = psutil.Process(process.pid)
    except psutil.Error:
        return

    while not stop.wait(_MEMORY_POLL_SECONDS):
        try:
            rss = root.memory_info().rss
            for child in root.children(recursive=True):
                try:
                    rss += child.memory_info().rss
                except psutil.Error:
                    continue
        except psutil.Error:
            return

        if rss > _MAX_MEMORY_BYTES:
            exceeded.set()
            _terminate_process_tree(process)
            return


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

        # Preserve only variables required to start a Windows child process.
        # Provider keys, tokens and the user's full environment are never inherited.
        safe_env = {
            name: os.environ[name]
            for name in ("SYSTEMROOT", "WINDIR", "TEMP", "TMP")
            if os.environ.get(name)
        }
        safe_env["PYTHONIOENCODING"] = "utf-8"

        process = subprocess.Popen(
            command,
            cwd=tmp,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            env=safe_env,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
        )

        stop_monitor = threading.Event()
        memory_exceeded = threading.Event()
        watcher = threading.Thread(
            target=_memory_watch,
            args=(process, stop_monitor, memory_exceeded),
            name="jarvis-sandbox-memory",
            daemon=True,
        )
        watcher.start()

        try:
            stdout, stderr = process.communicate(
                input=json.dumps({"code": code}, ensure_ascii=False),
                timeout=timeout,
            )
        except subprocess.TimeoutExpired as exc:
            _terminate_process_tree(process)
            try:
                process.communicate(timeout=1)
            except Exception:
                pass
            raise RuntimeError(
                f"Sandbox interrompu après {timeout} secondes."
            ) from exc
        finally:
            stop_monitor.set()
            watcher.join(timeout=0.5)

        if memory_exceeded.is_set():
            raise RuntimeError(
                "Sandbox interrompu : limite mémoire de 256 Mo dépassée."
            )

    return {
        "returncode": int(process.returncode or 0),
        "stdout": (stdout or "")[-12000:],
        "stderr": (stderr or "")[-12000:],
        "restricted": True,
        "memory_limit_mb": 256,
    }
