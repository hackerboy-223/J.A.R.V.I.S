from __future__ import annotations

import argparse
import ipaddress

from jarvis.config import settings


def _serve(host: str, port: int) -> int:
    try:
        address = ipaddress.ip_address(host)
        loopback = address.is_loopback
    except ValueError:
        loopback = host.lower() == "localhost"

    if not loopback and not settings.api_token:
        print(
            "Refus de démarrer JARVIS sur une interface réseau sans JARVIS_API_TOKEN."
        )
        return 2

    import uvicorn
    from jarvis.api import create_app

    uvicorn.run(
        create_app(),
        host=host,
        port=port,
        log_level="info",
    )
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(prog="jarvis")
    sub = parser.add_subparsers(dest="command")

    serve = sub.add_parser("serve", help="Lancer l'API locale OpenAI-compatible.")
    serve.add_argument("--host", default=settings.api_host)
    serve.add_argument("--port", type=int, default=settings.api_port)

    args = parser.parse_args()
    if args.command == "serve":
        return _serve(args.host, args.port)

    from jarvis.ui.main_window import run_app
    return run_app()


if __name__ == "__main__":
    raise SystemExit(main())
