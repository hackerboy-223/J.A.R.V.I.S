from __future__ import annotations

from datetime import datetime, timezone
from logging.handlers import RotatingFileHandler
import faulthandler
import logging
import os
import re
import sys
import threading
import traceback

from jarvis.config import DATA_DIR


LOG_DIR = (DATA_DIR / "logs").resolve()
CRASH_DIR = (LOG_DIR / "crashes").resolve()
LOG_DIR.mkdir(parents=True, exist_ok=True)
CRASH_DIR.mkdir(parents=True, exist_ok=True)
LOG_FILE = LOG_DIR / "jarvis.log"
_fault_handle = None

_SECRET_NAME_MARKERS = ("TOKEN", "SECRET", "PASSWORD", "API_KEY", "ACCESS_KEY")
_BEARER_RE = re.compile(r"(?i)(\bbearer\s+)[A-Za-z0-9._~+\-/=]{8,}")
_KNOWN_KEY_RE = re.compile(
    r"\b(?:sk-or-v1-|hf_|gsk_|exa_)[A-Za-z0-9._-]{8,}\b",
    re.IGNORECASE,
)
_JSON_SECRET_RE = re.compile(
    r'(?i)(["\']?(?:token|api[_-]?key|secret|password)["\']?\s*[:=]\s*["\']?)'
    r'[^"\'\s,}]{6,}'
)


def _redact(text: object) -> str:
    clean = str(text or "")
    clean = _BEARER_RE.sub(r"\1***REDACTED***", clean)
    clean = _KNOWN_KEY_RE.sub("***REDACTED***", clean)
    clean = _JSON_SECRET_RE.sub(r"\1***REDACTED***", clean)

    # Also redact the exact values of secrets already loaded in the process.
    # This catches providers whose token format is not predictable.
    for name, value in os.environ.items():
        upper = name.upper()
        if not value or len(value) < 6:
            continue
        if any(marker in upper for marker in _SECRET_NAME_MARKERS):
            clean = clean.replace(value, "***REDACTED***")

    return clean


class RedactingFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        return _redact(super().format(record))


def configure_logging() -> logging.Logger:
    logger = logging.getLogger("jarvis")
    if logger.handlers:
        return logger

    logger.setLevel(logging.INFO)
    logger.propagate = False
    formatter = RedactingFormatter(
        "%(asctime)s | %(levelname)s | %(name)s | %(message)s"
    )

    file_handler = RotatingFileHandler(
        LOG_FILE,
        maxBytes=2_000_000,
        backupCount=5,
        encoding="utf-8",
    )
    file_handler.setFormatter(formatter)
    logger.addHandler(file_handler)

    # A frozen --windowed build may not have a usable stderr handle.
    if sys.stderr is not None:
        console = logging.StreamHandler(sys.stderr)
        console.setFormatter(formatter)
        logger.addHandler(console)

    return logger


logger = configure_logging()


def _write_crash(kind: str, exc_type, exc_value, exc_tb) -> None:
    stamp = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S-%f")
    path = CRASH_DIR / f"{kind}-{stamp}.log"
    text = _redact("".join(traceback.format_exception(exc_type, exc_value, exc_tb)))
    path.write_text(text, encoding="utf-8")
    logger.critical("Unhandled %s exception written to %s\n%s", kind, path, text)


def install_crash_hooks() -> None:
    global _fault_handle

    def sys_hook(exc_type, exc_value, exc_tb):
        _write_crash("python", exc_type, exc_value, exc_tb)

    def thread_hook(args: threading.ExceptHookArgs):
        _write_crash("thread", args.exc_type, args.exc_value, args.exc_traceback)

    sys.excepthook = sys_hook
    threading.excepthook = thread_hook

    try:
        native_path = CRASH_DIR / "native-faulthandler.log"
        _fault_handle = native_path.open("a", encoding="utf-8")
        faulthandler.enable(file=_fault_handle, all_threads=True)
    except Exception as exc:
        logger.warning("Impossible d'activer faulthandler persistant: %s", exc)
