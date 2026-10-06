from __future__ import annotations

import hashlib
from pathlib import Path
import re
import subprocess
from typing import Any
from urllib.parse import urlparse

import httpx

from jarvis.config import DATA_DIR
from jarvis.version import __version__


RELEASES_URL = "https://api.github.com/repos/hackerboy-223/J.A.R.V.I.S/releases/latest"
_RELEASE_PATH_PREFIX = "/hackerboy-223/j.a.r.v.i.s/releases/download/"
_MAX_UPDATE_BYTES = 750 * 1024 * 1024
_VERSION_RE = re.compile(r"^v?(\d+)\.(\d+)\.(\d+)(?:[-+].*)?$", re.IGNORECASE)


def _parse_version(value: str) -> tuple[int, int, int] | None:
    match = _VERSION_RE.fullmatch(str(value or "").strip())
    if not match:
        return None
    return tuple(int(part) for part in match.groups())


def _is_newer(candidate: str, current: str) -> bool:
    candidate_version = _parse_version(candidate)
    current_version = _parse_version(current)
    if candidate_version is None or current_version is None:
        return False
    return candidate_version > current_version


def _trusted_release_url(url: str) -> bool:
    try:
        parsed = urlparse(str(url or "").strip())
    except Exception:
        return False
    return (
        parsed.scheme.lower() == "https"
        and parsed.hostname is not None
        and parsed.hostname.lower() == "github.com"
        and parsed.path.lower().startswith(_RELEASE_PATH_PREFIX)
    )


class UpdateService:
    def latest(self) -> dict[str, Any]:
        response = httpx.get(
            RELEASES_URL,
            headers={
                "Accept": "application/vnd.github+json",
                "X-GitHub-Api-Version": "2026-03-10",
                "User-Agent": f"JARVIS-Desktop/{__version__}",
            },
            timeout=15,
        )
        if response.status_code == 404:
            return {
                "available": False,
                "current_version": __version__,
                "reason": "Aucune release publiée.",
            }
        response.raise_for_status()
        data = response.json()

        tag = str(data.get("tag_name") or "").strip()
        available = _is_newer(tag, __version__)
        result = {
            "available": available,
            "current_version": __version__,
            "tag": tag,
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
        if not available:
            result["reason"] = (
                "J.A.R.V.I.S. est déjà à jour."
                if _parse_version(tag) is not None
                else "La version de la release GitHub est invalide."
            )
        return result

    def download(self, url: str, destination: Path, sha256: str | None = None) -> Path:
        if not _trusted_release_url(url):
            raise ValueError(
                "Seuls les assets HTTPS du dépôt officiel J.A.R.V.I.S. sont autorisés."
            )

        destination = destination.expanduser().resolve()
        destination.parent.mkdir(parents=True, exist_ok=True)
        part = destination.with_name(destination.name + ".part")
        part.unlink(missing_ok=True)

        expected = ""
        if sha256:
            expected = sha256.split(":", 1)[-1].strip().lower()
            if not re.fullmatch(r"[0-9a-f]{64}", expected):
                raise ValueError("Digest SHA-256 de mise à jour invalide.")

        digest = hashlib.sha256()
        written = 0

        try:
            with httpx.stream(
                "GET",
                url,
                headers={"User-Agent": f"JARVIS-Desktop/{__version__}"},
                follow_redirects=True,
                timeout=httpx.Timeout(120, connect=15),
            ) as response:
                response.raise_for_status()

                length_raw = response.headers.get("content-length")
                if length_raw and length_raw.isdigit():
                    declared = int(length_raw)
                    if declared > _MAX_UPDATE_BYTES:
                        raise RuntimeError("La mise à jour dépasse la taille maximale autorisée.")

                with part.open("wb") as handle:
                    for chunk in response.iter_bytes(chunk_size=1024 * 1024):
                        if not chunk:
                            continue
                        written += len(chunk)
                        if written > _MAX_UPDATE_BYTES:
                            raise RuntimeError(
                                "La mise à jour dépasse la taille maximale autorisée."
                            )
                        digest.update(chunk)
                        handle.write(chunk)

            actual = digest.hexdigest().lower()
            if expected and actual != expected:
                raise RuntimeError("Le SHA-256 de la mise à jour ne correspond pas.")

            if written <= 0:
                raise RuntimeError("Le fichier de mise à jour téléchargé est vide.")

            part.replace(destination)
            return destination
        except Exception:
            part.unlink(missing_ok=True)
            raise

    def download_latest_installer(self) -> dict[str, Any]:
        release = self.latest()
        if not release.get("available"):
            return release

        assets = list(release.get("assets") or [])
        installer = next(
            (
                item
                for item in assets
                if str(item.get("name", "")).lower().endswith(".exe")
                and "setup" in str(item.get("name", "")).lower()
            ),
            None,
        )
        if installer is None:
            return {
                **release,
                "downloaded": False,
                "reason": "Aucun installateur Windows .exe dans cette release.",
            }

        digest = str(installer.get("digest") or "").strip()
        if not digest.lower().startswith("sha256:"):
            return {
                **release,
                "downloaded": False,
                "reason": "La release ne fournit pas de digest SHA-256 vérifiable.",
            }

        updates = (DATA_DIR / "updates").resolve()
        destination = updates / str(installer["name"])
        path = self.download(
            str(installer["url"]),
            destination,
            digest,
        )
        return {
            **release,
            "downloaded": True,
            "path": str(path),
            "verified": True,
            "digest": digest,
        }

    @staticmethod
    def launch_installer(path: Path) -> None:
        installer = path.expanduser().resolve()
        updates_root = (DATA_DIR / "updates").resolve()
        try:
            installer.relative_to(updates_root)
        except ValueError as exc:
            raise ValueError(
                "L'installateur doit provenir du dossier de mises à jour J.A.R.V.I.S."
            ) from exc

        if not installer.exists() or not installer.is_file() or installer.suffix.lower() != ".exe":
            raise ValueError("Installateur Windows invalide.")

        subprocess.Popen(
            [str(installer)],
            close_fds=True,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
        )
