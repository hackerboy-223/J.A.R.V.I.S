from __future__ import annotations

import argparse
import ipaddress
import sys


def _serve(host: str | None, port: int | None) -> int:
    from jarvis.config import settings

    host = host or settings.api_host
    port = settings.api_port if port is None else port
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
    argv = sys.argv[1:]
    if argv and argv[0] == "--jarvis-sandbox-runner":
        if len(argv) != 1:
            print("Usage interne invalide pour le sandbox JARVIS.")
            return 2
        from jarvis.sandbox_runner import run_sandbox_runner

        return run_sandbox_runner()

    parser = argparse.ArgumentParser(prog="jarvis")
    sub = parser.add_subparsers(dest="command")

    serve = sub.add_parser("serve", help="Lancer l'API locale OpenAI-compatible.")
    serve.add_argument("--host")
    serve.add_argument("--port", type=int)
    sub.add_parser("selftest", help="Tester les nouveaux sous-systèmes sans API externe.")

    args = parser.parse_args(argv)
    if args.command == "serve":
        return _serve(args.host, args.port)
    if args.command == "selftest":
        from jarvis.selftest import run as run_selftest
        return run_selftest()

    from jarvis.ui.main_window import run_app
    return run_app()


if __name__ == "__main__":
    raise SystemExit(main())
