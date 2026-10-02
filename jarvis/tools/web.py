from __future__ import annotations

from html.parser import HTMLParser
import ipaddress
import socket
from urllib.parse import urlparse

import httpx

from jarvis.config import settings


class _TextExtractor(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.parts: list[str] = []
        self._blocked = 0

    def handle_starttag(self, tag: str, attrs) -> None:
        del attrs
        if tag.lower() in {"script", "style", "noscript", "svg"}:
            self._blocked += 1

    def handle_endtag(self, tag: str) -> None:
        if tag.lower() in {"script", "style", "noscript", "svg"} and self._blocked:
            self._blocked -= 1

    def handle_data(self, data: str) -> None:
        if self._blocked:
            return
        text = " ".join(data.split())
        if text:
            self.parts.append(text)


def _safe_public_url(raw: str) -> str:
    target = raw.strip()
    if not target.lower().startswith(("http://", "https://")):
        target = "https://" + target

    parsed = urlparse(target)
    if parsed.scheme not in {"http", "https"} or not parsed.hostname:
        raise ValueError("URL invalide.")

    host = parsed.hostname.lower()
    if host in {"localhost", "127.0.0.1", "::1"}:
        raise ValueError("Les adresses locales ne peuvent pas être lues.")

    try:
        infos = socket.getaddrinfo(host, parsed.port or (443 if parsed.scheme == "https" else 80))
    except socket.gaierror as exc:
        raise ValueError(f"Hôte introuvable : {host}") from exc

    for info in infos:
        ip = ipaddress.ip_address(info[4][0])
        if (
            ip.is_private
            or ip.is_loopback
            or ip.is_link_local
            or ip.is_multicast
            or ip.is_reserved
        ):
            raise ValueError("Cette adresse réseau n'est pas autorisée.")

    return target


def web_search(args: dict) -> dict:
    query = str(args.get("query", "")).strip()
    if not query:
        raise ValueError("query est requis.")
    if not settings.serper_api_key:
        raise RuntimeError("SERPER_API_KEY n'est pas configuré.")

    count = int(args.get("num", 8) or 8)
    count = max(1, min(count, 10))

    response = httpx.post(
        "https://google.serper.dev/search",
        headers={"X-API-KEY": settings.serper_api_key, "Content-Type": "application/json"},
        json={"q": query[:500], "num": count},
        timeout=12,
    )
    response.raise_for_status()
    data = response.json()

    results = []
    for item in data.get("organic", [])[:count]:
        results.append(
            {
                "title": str(item.get("title", "")),
                "url": str(item.get("link", "")),
                "snippet": str(item.get("snippet", "")),
            }
        )

    return {"query": query, "results": results}


def read_page(args: dict) -> dict:
    url = str(args.get("url", "")).strip()
    if not url:
        raise ValueError("url est requis.")

    target = _safe_public_url(url)
    response = httpx.get(
        target,
        headers={"User-Agent": "JARVIS-Desktop/0.2"},
        follow_redirects=True,
        timeout=15,
    )
    response.raise_for_status()

    content_type = response.headers.get("content-type", "")
    if "text" not in content_type and "html" not in content_type and "json" not in content_type:
        raise ValueError(f"Type de contenu non pris en charge : {content_type}")

    text = response.text
    if "html" in content_type:
        parser = _TextExtractor()
        parser.feed(text)
        text = "\n".join(parser.parts)

    clean = " ".join(text.split())
    return {
        "url": str(response.url),
        "status": response.status_code,
        "text": clean[:18000],
    }
