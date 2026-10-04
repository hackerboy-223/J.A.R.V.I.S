from __future__ import annotations

import faulthandler
import logging
from logging.handlers import RotatingFileHandler
import shutil
import sqlite3
import sys
import threading
import traceback
from pathlib import Path
from typing import Any, Callable

from jarvis.config import DATA_DIR, settings


_LOGGER_NAME = "jarvis"


def configure_logging() -> logging.Logger:
    logger = logging.getLogger(_LOGGER_NAME)
    if logger.handlers:
        return logger

    log_dir = DATA_DIR / "logs"
    log_dir.mkdir(parents=True, exist_ok=True)
    handler = RotatingFileHandler(
        log_dir / "jarvis.log",
        maxBytes=2_000_000,
        backupCount=5,
        encoding="utf-8",
    )
    handler.setFormatter(
        logging.Formatter("%(asctime)s | %(levelname)s | %(threadName)s | %(message)s")
    )
    logger.setLevel(logging.INFO)
    logger.addHandler(handler)
    logger.propagate = False
    return logger


def install_crash_hooks() -> logging.Logger:
    logger = configure_logging()
    try:
        crash_path = DATA_DIR / "logs" / "native-crash.log"
        crash_file = crash_path.open("a", encoding="utf-8")
        faulthandler.enable(file=crash_file, all_threads=True)
    except Exception:
        pass

    old_hook = sys.excepthook

    def excepthook(exc_type, exc, tb) -> None:
        logger.critical(
            "Unhandled exception\n%s",
            "".join(traceback.format_exception(exc_type, exc, tb)),
        )
        old_hook(exc_type, exc, tb)

    sys.excepthook = excepthook

    if hasattr(threading, "excepthook"):
        old_thread_hook = threading.excepthook

        def thread_hook(args) -> None:
            logger.error(
                "Unhandled thread exception in %s\n%s",
                getattr(args.thread, "name", "thread"),
                "".join(
                    traceback.format_exception(
                        args.exc_type,
                        args.exc_value,
                        args.exc_traceback,
                    )
                ),
            )
            old_thread_hook(args)

        threading.excepthook = thread_hook

    return logger


def health_snapshot(
    *,
    scheduler_running: bool | None = None,
    extra_checks: dict[str, Callable[[], Any]] | None = None,
) -> dict[str, Any]:
    checks: dict[str, dict[str, Any]] = {}

    try:
        with sqlite3.connect(settings.database_path, timeout=5) as db:
            value = db.execute("PRAGMA quick_check").fetchone()
        ok = bool(value and value[0] == "ok")
        checks["sqlite"] = {"ok": ok, "detail": value[0] if value else "no result"}
    except Exception as exc:
        checks["sqlite"] = {"ok": False, "detail": str(exc)}

    try:
        usage = shutil.disk_usage(DATA_DIR)
        checks["disk"] = {
            "ok": usage.free > 256 * 1024 * 1024,
            "free_bytes": usage.free,
            "total_bytes": usage.total,
        }
    except Exception as exc:
        checks["disk"] = {"ok": False, "detail": str(exc)}

    checks["workspace"] = {
        "ok": settings.workspace_root.exists() and settings.workspace_root.is_dir(),
        "path": str(settings.workspace_root),
    }
    checks["scheduler"] = {
        "ok": scheduler_running is not False,
        "running": scheduler_running,
    }

    for name, fn in (extra_checks or {}).items():
        try:
            detail = fn()
            checks[name] = {"ok": True, "detail": detail}
        except Exception as exc:
            checks[name] = {"ok": False, "detail": str(exc)}

    overall = all(bool(item.get("ok")) for item in checks.values())
    return {"ok": overall, "checks": checks, "data_dir": str(DATA_DIR)}
