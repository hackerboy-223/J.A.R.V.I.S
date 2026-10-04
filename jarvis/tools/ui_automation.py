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


def control_action(args: dict[str, Any]) -> dict[str, Any]:
    """Controlled UI Automation by window/control name, never raw coordinates."""
    try:
        from pywinauto import Desktop  # type: ignore
    except Exception as exc:
        raise RuntimeError(
            "pywinauto n'est pas installé. Installe l'extra desktop-automation."
        ) from exc

    window_title = str(args.get("window", "")).strip()
    control_title = str(args.get("control", "")).strip()
    action = str(args.get("action", "")).strip().lower()
    value = str(args.get("value", ""))

    if not window_title or not control_title:
        raise ValueError("window et control sont requis.")
    if action not in {"click", "set_text"}:
        raise ValueError("action doit être click ou set_text.")

    desktop = Desktop(backend="uia")
    window = desktop.window(title_re=f".*{window_title}.*")
    control = window.child_window(title=control_title)

    if action == "click":
        control.click_input()
        return {"ok": True, "action": "click", "window": window_title, "control": control_title}

    if len(value) > 5000:
        raise ValueError("Texte trop long pour une action UI.")
    control.set_edit_text(value)
    return {
        "ok": True,
        "action": "set_text",
        "window": window_title,
        "control": control_title,
        "chars": len(value),
    }
