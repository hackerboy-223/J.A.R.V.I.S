from __future__ import annotations

import hashlib
from pathlib import Path
import re
from typing import Any

import httpx

from jarvis.config import DATA_DIR


_VERSION_RE = re.compile(r"\d+")


def _version_tuple(value: str) -> tuple[int, ...]:
    parts = [int(item) for item in _VERSION_RE.findall(value)]
    return tuple(parts or [0])


class UpdateService:
    def __init__(self, repository: str = "hackerboy-223/J.A.R.V.I.S") -> None:
        self.repository = repository

    def latest(self, current_version: str) -> dict[str, Any]:
        response = httpx.get(
            f"https://api.github.com/repos/{self.repository}/releases/latest",
            headers={
                "Accept": "application/vnd.github+json",
                "User-Agent": "JARVIS-Updater",
            },
            timeout=20,
            follow_redirects=True,
        )
        if response.status_code == 404:
            return {"available": False, "reason": "Aucune release publiée."}
        response.raise_for_status()
        data = response.json()
        tag = str(data.get("tag_name") or "")
        assets = []
        for asset in data.get("assets") or []:
            if not isinstance(asset, dict):
                continue
            assets.append(
                {
                    "name": asset.get("name"),
                    "url": asset.get("browser_download_url"),
                    "size": asset.get("size"),
                    "digest": asset.get("digest"),
                }
            )
        return {
            "available": _version_tuple(tag) > _version_tuple(current_version),
            "current": current_version,
            "latest": tag,
            "name": data.get("name"),
            "published_at": data.get("published_at"),
            "notes": data.get("body") or "",
            "assets": assets,
            "page": data.get("html_url"),
        }

    def download(self, asset: dict[str, Any]) -> dict[str, Any]:
        url = str(asset.get("url") or "")
        name = Path(str(asset.get("name") or "JARVIS-update.bin")).name
        if not url.startswith("https://github.com/"):
            raise ValueError("Asset GitHub invalide.")

        target_dir = DATA_DIR / "updates"
        target_dir.mkdir(parents=True, exist_ok=True)
        target = target_dir / name
        digest = hashlib.sha256()

        with httpx.stream("GET", url, follow_redirects=True, timeout=120) as response:
            response.raise_for_status()
            with target.open("wb") as output:
                for chunk in response.iter_bytes():
                    output.write(chunk)
                    digest.update(chunk)

        actual = digest.hexdigest()
        expected_raw = str(asset.get("digest") or "")
        if expected_raw.startswith("sha256:"):
            expected = expected_raw.split(":", 1)[1].lower()
            if actual.lower() != expected:
                target.unlink(missing_ok=True)
                raise RuntimeError("Le SHA-256 de la mise à jour ne correspond pas.")

        return {"path": str(target), "sha256": actual, "verified": bool(expected_raw)}
