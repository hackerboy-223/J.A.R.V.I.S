from __future__ import annotations

from datetime import datetime, timezone
from logging.handlers import RotatingFileHandler
import faulthandler
import logging
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


def configure_logging() -> logging.Logger:
    logger = logging.getLogger("jarvis")
    if logger.handlers:
        return logger
    logger.setLevel(logging.INFO)
    formatter = logging.Formatter(
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

    console = logging.StreamHandler(sys.stderr)
    console.setFormatter(formatter)
    logger.addHandler(console)
    return logger


logger = configure_logging()


def _write_crash(kind: str, exc_type, exc_value, exc_tb) -> None:
    stamp = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S-%f")
    path = CRASH_DIR / f"{kind}-{stamp}.log"
    text = "".join(traceback.format_exception(exc_type, exc_value, exc_tb))
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
