from __future__ import annotations

from importlib.metadata import PackageNotFoundError, version


DISTRIBUTION_NAME = "jarvis-desktop"
FALLBACK_VERSION = "0.2.0"


def get_version() -> str:
    try:
        return version(DISTRIBUTION_NAME)
    except PackageNotFoundError:
        return FALLBACK_VERSION
    except Exception:
        return FALLBACK_VERSION


__version__ = get_version()
