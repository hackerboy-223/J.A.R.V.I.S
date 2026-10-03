from __future__ import annotations

import os
import sys
from collections.abc import Mapping
from pathlib import Path


def resolve_data_dir(
    root: Path,
    environ: Mapping[str, str] | None = None,
    is_frozen: bool | None = None,
    platform_name: str | None = None,
    home: Path | None = None,
) -> Path:
    """Return a writable per-user data directory for this installation."""
    env = os.environ if environ is None else environ
    frozen = bool(getattr(sys, "frozen", False)) if is_frozen is None else is_frozen
    system = sys.platform if platform_name is None else platform_name
    user_home = Path.home() if home is None else home

    override = str(env.get("JARVIS_DATA_DIR", "")).strip()
    if override:
        return Path(override).expanduser()

    # Keep the repository-local layout for development and existing source installs.
    if not frozen:
        return root / "data"

    if system == "win32":
        base = env.get("LOCALAPPDATA") or env.get("APPDATA")
        if base:
            return Path(base) / "JARVIS"
        return user_home / "AppData" / "Local" / "JARVIS"

    if system == "darwin":
        return user_home / "Library" / "Application Support" / "JARVIS"

    xdg_data_home = str(env.get("XDG_DATA_HOME", "")).strip()
    if xdg_data_home:
        return Path(xdg_data_home).expanduser() / "jarvis"
    return user_home / ".local" / "share" / "jarvis"