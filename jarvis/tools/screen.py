from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from mss import mss
from mss.tools import to_png

from jarvis.config import DATA_DIR


def screen_monitors(_: dict[str, Any] | None = None) -> dict[str, Any]:
    with mss() as capture:
        monitors = [
            {
                "index": index,
                "left": int(item["left"]),
                "top": int(item["top"]),
                "width": int(item["width"]),
                "height": int(item["height"]),
                "all_monitors": index == 0,
            }
            for index, item in enumerate(capture.monitors)
        ]
    return {"monitors": monitors}


def screen_capture(args: dict[str, Any]) -> dict[str, Any]:
    monitor_index = int(args.get("monitor", 1) or 1)
    persist = bool(args.get("persist", False))

    with mss() as capture:
        monitors = capture.monitors
        if monitor_index < 0 or monitor_index >= len(monitors):
            raise ValueError(f"Écran invalide. Valeurs disponibles : 0..{len(monitors)-1}")
        monitor = monitors[monitor_index]
        shot = capture.grab(monitor)

    target_dir = DATA_DIR / ("captures" if persist else "tmp")
    target_dir.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
    path = target_dir / f"screen-{monitor_index}-{stamp}.png"
    to_png(shot.rgb, shot.size, output=str(path))

    return {
        "path": str(path),
        "monitor": monitor_index,
        "width": shot.width,
        "height": shot.height,
        "persistent": persist,
    }
