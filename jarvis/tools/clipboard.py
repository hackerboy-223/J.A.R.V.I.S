from __future__ import annotations

from typing import Any

try:
    import win32clipboard
except Exception:
    win32clipboard = None


def _require_clipboard() -> None:
    if win32clipboard is None:
        raise RuntimeError("Clipboard Windows indisponible (pywin32 requis).")


def clipboard_read(_: dict[str, Any] | None = None) -> dict[str, Any]:
    _require_clipboard()
    win32clipboard.OpenClipboard()
    try:
        if not win32clipboard.IsClipboardFormatAvailable(win32clipboard.CF_UNICODETEXT):
            return {"text": "", "available": False}
        text = win32clipboard.GetClipboardData(win32clipboard.CF_UNICODETEXT)
        return {"text": str(text)[:100000], "available": True}
    finally:
        win32clipboard.CloseClipboard()


def clipboard_write(args: dict[str, Any]) -> dict[str, Any]:
    _require_clipboard()
    text = str(args.get("text", ""))
    if len(text) > 100000:
        raise ValueError("Texte clipboard trop volumineux.")
    win32clipboard.OpenClipboard()
    try:
        win32clipboard.EmptyClipboard()
        win32clipboard.SetClipboardText(text, win32clipboard.CF_UNICODETEXT)
    finally:
        win32clipboard.CloseClipboard()
    return {"written": True, "chars": len(text)}
