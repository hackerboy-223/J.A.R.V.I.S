from __future__ import annotations

from typing import Any

from jarvis.tools.windows import focus_window, list_windows


def inspect_ui(args: dict[str, Any]) -> dict[str, Any]:
    """Read-only UI inspection.

    This first implementation intentionally exposes window-level information
    only. Fine-grained control automation can be added behind the same
    permission boundary without allowing arbitrary pointer coordinates.
    """
    title = str(args.get("title", "")).strip().lower()
    windows = list_windows({})["windows"]
    if title:
        windows = [item for item in windows if title in item["title"].lower()]
    return {"windows": windows[:50], "level": "window"}


def activate_ui(args: dict[str, Any]) -> dict[str, Any]:
    """Safe reversible automation: focus a named visible window only."""
    return focus_window({"title": str(args.get("title", ""))})
