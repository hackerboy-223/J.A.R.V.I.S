from __future__ import annotations

from html.parser import HTMLParser
import ipaddress
import socket
from urllib.parse import urlparse, urlunparse

import httpx

from jarvis.config import settings


def _compact_snippet(text: str, limit: int) -> str:
    clean = " ".join(str(text or "").split())
    if len(clean) <= limit:
        return clean

    cut = clean[:limit].rstrip()
    last_stop = max(
        cut.rfind(". "),
        cut.rfind("! "),
        cut.rfind("? "),
        cut.rfind("; "),
    )
    if last_stop >= int(limit * 0.55):
        cut = cut[: last_stop + 1].rstrip()
    else:
        last_space = cut.rfind(" ")
        if last_space >= int(limit * 0.7):
            cut = cut[:last_space].rstrip()

    return cut + "…"


def _canonical_result_url(raw: str) -> str:
    value = str(raw or "").strip()
    if not value:
        return ""

    try:
        parsed = urlparse(value)
        if parsed.scheme not in {"http", "https"} or not parsed.netloc:
            return value
        normalized = parsed._replace(
            scheme=parsed.scheme.lower(),
            netloc=parsed.netloc.lower(),
            path=parsed.path.rstrip("/") or "/",
            fragment="",
        )
        return urlunparse(normalized)
    except Exception:
        return value


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
    if not settings.exa_api_key:
        raise RuntimeError(
            "EXA_API_KEY n'est pas configuré. "
            "Ajoute ta clé Exa dans le fichier .env local."
        )

    payload: dict[str, object] = {
        "query": query,
        "type": "auto",
        "contents": {
            "highlights": True,
        },
    }

    requested_count: int | None = None
    if "num" in args and args.get("num") is not None:
        requested_count = max(1, min(int(args.get("num") or 10), 10))
        payload["numResults"] = requested_count

    try:
        response = httpx.post(
            "https://api.exa.ai/search",
            headers={
                "x-api-key": settings.exa_api_key,
                "Content-Type": "application/json",
            },
            json=payload,
            timeout=20,
        )
    except httpx.TimeoutException as exc:
        raise RuntimeError("Exa n'a pas répondu à temps.") from exc
    except httpx.HTTPError as exc:
        raise RuntimeError("Connexion à Exa impossible.") from exc

    if response.status_code == 401:
        raise RuntimeError("Clé Exa invalide ou non autorisée.")
    if response.status_code == 403:
        raise RuntimeError("Accès Exa refusé pour cette clé ou ce compte.")
    if response.status_code == 429:
        raise RuntimeError(
            "Limite Exa atteinte. Réessaie plus tard ou vérifie ton quota."
        )
    if 400 <= response.status_code < 500:
        raise RuntimeError(f"Requête Exa refusée ({response.status_code}).")

    response.raise_for_status()
    data = response.json()

    results = []
    seen_urls: set[str] = set()

    for item in data.get("results", []):
        raw_url = str(item.get("url", "") or "").strip()
        canonical_url = _canonical_result_url(raw_url)
        if not canonical_url or canonical_url in seen_urls:
            continue
        seen_urls.add(canonical_url)

        highlights = item.get("highlights") or []
        if isinstance(highlights, str):
            raw_snippet = highlights
        elif isinstance(highlights, list):
            raw_snippet = "\n".join(
                str(part).strip()
                for part in highlights
                if str(part).strip()
            )
        else:
            raw_snippet = ""

        title = str(item.get("title", "") or "").strip()
        if not title:
            title = urlparse(canonical_url).netloc or canonical_url

        results.append(
            {
                "title": title,
                "url": canonical_url,
                "snippet": _compact_snippet(
                    raw_snippet,
                    settings.exa_snippet_chars,
                ),
                "published_date": item.get("publishedDate"),
                "author": item.get("author"),
            }
        )

        if requested_count is not None and len(results) >= requested_count:
            break

    return {
        "query": query,
        "provider": "exa",
        "request_id": data.get("requestId"),
        "search_time": data.get("searchTime"),
        "cost_dollars": data.get("costDollars"),
        "results": results,
    }


def read_page(args: dict) -> dict:
    url = str(args.get("url", "")).strip()
    if not url:
        raise ValueError("url est requis.")

    target = _safe_public_url(url)
    response = None
    current = target
    for _ in range(4):
        response = httpx.get(
            current,
            headers={"User-Agent": "JARVIS-Desktop/0.2"},
            follow_redirects=False,
            timeout=15,
        )
        if response.status_code not in {301, 302, 303, 307, 308}:
            break
        location = response.headers.get("location")
        if not location:
            break
        current = str(httpx.URL(current).join(location))
        current = _safe_public_url(current)

    if response is None:
        raise RuntimeError("Lecture de page impossible.")
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
