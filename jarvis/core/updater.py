from __future__ import annotations

import hashlib
from pathlib import Path
from typing import Any

import httpx


RELEASES_URL = "https://api.github.com/repos/hackerboy-223/J.A.R.V.I.S/releases/latest"


class UpdateService:
    def latest(self) -> dict[str, Any]:
        response = httpx.get(
            RELEASES_URL,
            headers={"Accept": "application/vnd.github+json"},
            timeout=15,
        )
        if response.status_code == 404:
            return {"available": False, "reason": "Aucune release publiée."}
        response.raise_for_status()
        data = response.json()
        return {
            "available": True,
            "tag": data.get("tag_name"),
            "name": data.get("name"),
            "published_at": data.get("published_at"),
            "html_url": data.get("html_url"),
            "assets": [
                {
                    "name": item.get("name"),
                    "url": item.get("browser_download_url"),
                    "size": item.get("size"),
                    "digest": item.get("digest"),
                }
                for item in data.get("assets", [])
                if isinstance(item, dict)
            ],
        }

    def download(self, url: str, destination: Path, sha256: str | None = None) -> Path:
        if not url.startswith("https://github.com/"):
            raise ValueError("Seuls les assets GitHub HTTPS sont autorisés.")
        destination.parent.mkdir(parents=True, exist_ok=True)
        with httpx.stream("GET", url, follow_redirects=True, timeout=120) as response:
            response.raise_for_status()
            with destination.open("wb") as handle:
                for chunk in response.iter_bytes():
                    handle.write(chunk)
        if sha256:
            digest = hashlib.sha256(destination.read_bytes()).hexdigest()
            if digest.lower() != sha256.lower():
                destination.unlink(missing_ok=True)
                raise RuntimeError("Le SHA-256 de la mise à jour ne correspond pas.")
        return destination
