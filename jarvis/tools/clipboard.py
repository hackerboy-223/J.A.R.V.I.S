from __future__ import annotations

from typing import Any


def clipboard_read(_: dict[str, Any] | None = None) -> dict[str, Any]:
    try:
        import win32clipboard  # type: ignore
    except Exception as exc:
        raise RuntimeError("pywin32 est requis pour le presse-papiers Windows.") from exc

    win32clipboard.OpenClipboard()
    try:
        if not win32clipboard.IsClipboardFormatAvailable(win32clipboard.CF_UNICODETEXT):
            return {"text": "", "available": False}
        text = win32clipboard.GetClipboardData(win32clipboard.CF_UNICODETEXT)
        return {"text": str(text)[:100_000], "available": True}
    finally:
        win32clipboard.CloseClipboard()


def clipboard_write(args: dict[str, Any]) -> dict[str, Any]:
    try:
        import win32clipboard  # type: ignore
    except Exception as exc:
        raise RuntimeError("pywin32 est requis pour le presse-papiers Windows.") from exc

    text = str(args.get("text", ""))
    if len(text) > 100_000:
        raise ValueError("Texte trop volumineux pour le presse-papiers.")
    win32clipboard.OpenClipboard()
    try:
        win32clipboard.EmptyClipboard()
        win32clipboard.SetClipboardText(text, win32clipboard.CF_UNICODETEXT)
    finally:
        win32clipboard.CloseClipboard()
    return {"written": True, "chars": len(text)}
