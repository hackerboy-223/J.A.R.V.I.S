from __future__ import annotations

import ipaddress
from urllib.parse import urlparse


def is_loopback_url(raw: str) -> bool:
    try:
        parsed = urlparse(str(raw or "").strip())
    except Exception:
        return False

    host = (parsed.hostname or "").strip().lower()
    if host == "localhost":
        return True
    try:
        return ipaddress.ip_address(host).is_loopback
    except ValueError:
        return False


def validate_service_base_url(raw: str, *, label: str = "service") -> str:
    value = str(raw or "").strip().rstrip("/")
    parsed = urlparse(value)

    if parsed.scheme not in {"http", "https"} or not parsed.hostname:
        raise ValueError(f"URL {label} invalide.")

    if parsed.username or parsed.password:
        raise ValueError(
            f"Les credentials intégrés dans l'URL {label} sont interdits."
        )

    if parsed.scheme == "http" and not is_loopback_url(value):
        raise ValueError(
            f"{label} distant doit utiliser HTTPS. "
            "HTTP est autorisé uniquement sur localhost/loopback."
        )

    return value


def service_endpoint(raw: str, path: str, *, label: str = "service") -> str:
    base = validate_service_base_url(raw, label=label)
    suffix = "/" + str(path or "").lstrip("/")
    return base + suffix
