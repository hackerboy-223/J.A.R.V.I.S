from __future__ import annotations

import os
from pathlib import Path
import subprocess
import webbrowser

from jarvis.config import settings


_ALLOWED_APPS = {
    "calculator": ["calc.exe"],
    "notepad": ["notepad.exe"],
    "explorer": ["explorer.exe"],
}

_ALLOWED_FOLDERS = {
    "desktop": lambda: Path.home() / "Desktop",
    "documents": lambda: Path.home() / "Documents",
    "downloads": lambda: Path.home() / "Downloads",
    "project": lambda: Path.cwd(),
}


def pc_control(args: dict) -> dict:
    if not settings.allow_pc_control:
        raise PermissionError("PC control is disabled. Set JARVIS_ALLOW_PC_CONTROL=true.")

    action = str(args.get("action", "")).strip().lower()
    target = str(args.get("target", "")).strip()

    if action == "open_app":
        cmd = _ALLOWED_APPS.get(target.lower())
        if not cmd:
            raise ValueError("Allowed apps: calculator, notepad, explorer")
        subprocess.Popen(cmd, close_fds=True)
        return {"status": "opened", "kind": "app", "target": target.lower()}

    if action == "open_folder":
        factory = _ALLOWED_FOLDERS.get(target.lower())
        if not factory:
            raise ValueError("Allowed folders: desktop, documents, downloads, project")
        folder = factory().resolve()
        os.startfile(folder)
        return {"status": "opened", "kind": "folder", "target": str(folder)}

    if action == "open_url":
        if not target.lower().startswith(("http://", "https://")):
            raise ValueError("Only http:// and https:// URLs are allowed")
        webbrowser.open(target, new=2)
        return {"status": "opened", "kind": "url", "target": target}

    raise ValueError("Allowed actions: open_app, open_folder, open_url")
