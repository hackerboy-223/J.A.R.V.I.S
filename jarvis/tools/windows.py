from __future__ import annotations

import ctypes
from ctypes import wintypes
import os
from typing import Any


if os.name == "nt":
    user32 = ctypes.windll.user32
else:
    user32 = None


def _require_windows() -> None:
    if user32 is None:
        raise RuntimeError("Cette fonction est disponible uniquement sous Windows.")


def list_windows(args: dict[str, Any] | None = None) -> dict[str, Any]:
    _require_windows()
    limit = max(1, min(int((args or {}).get("limit", 80)), 200))
    windows: list[dict[str, Any]] = []

    EnumWindowsProc = ctypes.WINFUNCTYPE(ctypes.c_bool, wintypes.HWND, wintypes.LPARAM)

    def callback(hwnd, _lparam) -> bool:
        if len(windows) >= limit:
            return False
        if not user32.IsWindowVisible(hwnd):
            return True
        length = user32.GetWindowTextLengthW(hwnd)
        if length <= 0:
            return True
        buffer = ctypes.create_unicode_buffer(length + 1)
        user32.GetWindowTextW(hwnd, buffer, length + 1)
        title = buffer.value.strip()
        if title:
            windows.append({"handle": int(hwnd), "title": title})
        return True

    user32.EnumWindows(EnumWindowsProc(callback), 0)
    foreground = int(user32.GetForegroundWindow() or 0)
    return {"foreground": foreground, "windows": windows}


def window_action(args: dict[str, Any]) -> dict[str, Any]:
    _require_windows()
    action = str(args.get("action", "")).strip().lower()
    handle = int(args.get("handle", 0) or 0)
    if handle <= 0 or not user32.IsWindow(handle):
        raise ValueError("Handle de fenêtre invalide.")

    if action == "focus":
        user32.ShowWindow(handle, 9)  # SW_RESTORE
        ok = bool(user32.SetForegroundWindow(handle))
    elif action == "minimize":
        ok = bool(user32.ShowWindow(handle, 6))  # SW_MINIMIZE
    elif action == "maximize":
        ok = bool(user32.ShowWindow(handle, 3))  # SW_MAXIMIZE
    elif action == "restore":
        ok = bool(user32.ShowWindow(handle, 9))
    else:
        raise ValueError("Actions autorisées : focus, minimize, maximize, restore.")

    return {"ok": ok, "action": action, "handle": handle}
