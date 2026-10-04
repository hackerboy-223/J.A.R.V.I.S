from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from jarvis.config import DATA_DIR


def capture_screen(args: dict[str, Any]) -> dict[str, Any]:
    try:
        import mss  # type: ignore
        import mss.tools  # type: ignore
    except Exception as exc:
        raise RuntimeError("Le package mss est requis pour la capture écran.") from exc

    monitor_index = int(args.get("monitor", 1) or 1)
    output_dir = (DATA_DIR / "captures").resolve()
    output_dir.mkdir(parents=True, exist_ok=True)

    with mss.mss() as grabber:
        monitors = grabber.monitors
        if monitor_index < 0 or monitor_index >= len(monitors):
            raise ValueError(f"monitor doit être entre 0 et {len(monitors) - 1}.")
        monitor = monitors[monitor_index]
        shot = grabber.grab(monitor)
        stamp = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S-%f")
        path = output_dir / f"screen-{stamp}.png"
        mss.tools.to_png(shot.rgb, shot.size, output=str(path))

    return {
        "captured": True,
        "path": str(path),
        "monitor": monitor_index,
        "width": int(shot.width),
        "height": int(shot.height),
    }


def list_monitors(_: dict[str, Any] | None = None) -> dict[str, Any]:
    try:
        import mss  # type: ignore
    except Exception as exc:
        raise RuntimeError("Le package mss est requis pour la capture écran.") from exc

    with mss.mss() as grabber:
        monitors = [
            {
                "index": index,
                "left": int(item["left"]),
                "top": int(item["top"]),
                "width": int(item["width"]),
                "height": int(item["height"]),
            }
            for index, item in enumerate(grabber.monitors)
        ]
    return {"monitors": monitors}
