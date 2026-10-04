from __future__ import annotations

from typing import Any


def _win32():
    try:
        import win32con  # type: ignore
        import win32gui  # type: ignore
        import win32process  # type: ignore
    except Exception as exc:
        raise RuntimeError("pywin32 est requis pour la gestion des fenêtres Windows.") from exc
    return win32con, win32gui, win32process


def list_windows(_: dict[str, Any] | None = None) -> dict[str, Any]:
    _, win32gui, win32process = _win32()
    items: list[dict[str, Any]] = []

    def callback(hwnd: int, __: object) -> None:
        if not win32gui.IsWindowVisible(hwnd):
            return
        title = str(win32gui.GetWindowText(hwnd) or "").strip()
        if not title:
            return
        try:
            _, pid = win32process.GetWindowThreadProcessId(hwnd)
            rect = tuple(int(value) for value in win32gui.GetWindowRect(hwnd))
        except Exception:
            return
        items.append({"hwnd": int(hwnd), "pid": int(pid), "title": title[:300], "rect": rect})

    win32gui.EnumWindows(callback, None)
    return {"windows": items[:200]}


def active_window(_: dict[str, Any] | None = None) -> dict[str, Any]:
    _, win32gui, win32process = _win32()
    hwnd = int(win32gui.GetForegroundWindow())
    if not hwnd:
        return {"active": None}
    _, pid = win32process.GetWindowThreadProcessId(hwnd)
    return {
        "active": {
            "hwnd": hwnd,
            "pid": int(pid),
            "title": str(win32gui.GetWindowText(hwnd) or "")[:300],
            "rect": tuple(int(value) for value in win32gui.GetWindowRect(hwnd)),
        }
    }


def focus_window(args: dict[str, Any]) -> dict[str, Any]:
    win32con, win32gui, _ = _win32()
    requested = str(args.get("title", "")).strip().lower()
    if not requested:
        raise ValueError("title est requis.")

    matches = list_windows({})["windows"]
    match = next((item for item in matches if requested in item["title"].lower()), None)
    if match is None:
        raise ValueError("Fenêtre introuvable.")

    hwnd = int(match["hwnd"])
    if win32gui.IsIconic(hwnd):
        win32gui.ShowWindow(hwnd, win32con.SW_RESTORE)
    win32gui.SetForegroundWindow(hwnd)
    return {"focused": True, "title": match["title"], "hwnd": hwnd}
