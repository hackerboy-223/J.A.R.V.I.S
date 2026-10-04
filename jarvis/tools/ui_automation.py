from __future__ import annotations

from typing import Any


def _desktop():
    try:
        from pywinauto import Desktop
    except Exception as exc:
        raise RuntimeError(
            "Automatisation UI optionnelle indisponible. Installe le groupe [windows]."
        ) from exc
    return Desktop(backend="uia")


def inspect_controls(args: dict[str, Any]) -> dict[str, Any]:
    title = str(args.get("window_title", "")).strip()
    if not title:
        raise ValueError("window_title est requis.")
    window = _desktop().window(title=title)
    window.wait("exists enabled visible", timeout=5)
    controls = []
    for child in window.descendants()[:200]:
        info = child.element_info
        controls.append(
            {
                "name": str(info.name or ""),
                "control_type": str(info.control_type or ""),
                "automation_id": str(info.automation_id or ""),
            }
        )
    return {"window": title, "controls": controls}


def ui_action(args: dict[str, Any]) -> dict[str, Any]:
    title = str(args.get("window_title", "")).strip()
    action = str(args.get("action", "")).strip().lower()
    automation_id = str(args.get("automation_id", "")).strip()
    control_title = str(args.get("control_title", "")).strip()
    value = str(args.get("value", ""))

    if not title:
        raise ValueError("window_title est requis.")
    if not automation_id and not control_title:
        raise ValueError("automation_id ou control_title est requis.")

    window = _desktop().window(title=title)
    window.wait("exists enabled visible", timeout=5)
    control = (
        window.child_window(auto_id=automation_id)
        if automation_id
        else window.child_window(title=control_title)
    )
    control.wait("exists enabled visible", timeout=5)

    if action == "click":
        control.click_input()
    elif action == "type":
        if len(value) > 10000:
            raise ValueError("Texte trop long pour l'automatisation UI.")
        # Never pass model text through pywinauto's SendKeys grammar:
        # sequences such as {ENTER}, ^A or %F4 would be interpreted as keys.
        setter = getattr(control, "set_edit_text", None)
        if not callable(setter):
            raise ValueError(
                "La saisie est autorisée uniquement sur un contrôle éditable "
                "supportant set_edit_text."
            )
        control.set_focus()
        setter(value)
    else:
        raise ValueError("Actions autorisées : click, type.")

    return {"ok": True, "action": action, "window": title}
