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
    sub.add_parser("doctor", help="Diagnostiquer le démarrage de l\'interface desktop Qt.")
    sub.add_parser("health", help="Afficher l'état de santé local de J.A.R.V.I.S.")

    index = sub.add_parser("index", help="Indexer les fichiers du workspace local.")
    index.add_argument("--root")
    index.add_argument("--workspace-id", default="default")

    migrate = sub.add_parser("migrate-prisma", help="Importer l'ancienne base Prisma SQLite.")
    migrate.add_argument("source")

    sub.add_parser("update-check", help="Vérifier la dernière GitHub Release disponible.")

    args = parser.parse_args(argv)
    if args.command == "serve":
        return _serve(args.host, args.port)
    if args.command == "selftest":
        from jarvis.selftest import run as run_selftest
        return run_selftest()
    if args.command == "doctor":
        from jarvis.ui.main_window import run_app
        return run_app(diagnostic_seconds=2.0)
    if args.command == "health":
        import json
        from jarvis.core.health import HealthService
        from jarvis.core.platform_store import PlatformStore
        from jarvis.config import settings
        service = HealthService(PlatformStore(settings.database_path))
        print(json.dumps(service.snapshot(), ensure_ascii=False, indent=2))
        return 0
    if args.command == "index":
        import json
        from pathlib import Path
        from jarvis.config import settings
        from jarvis.core.file_index import FileIndex
        root = Path(args.root).expanduser() if args.root else settings.workspace_root
        result = FileIndex(settings.database_path).rebuild(
            root,
            workspace_id=str(args.workspace_id or "default"),
        )
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 0
    if args.command == "migrate-prisma":
        import json
        from pathlib import Path
        from jarvis.config import settings
        from jarvis.core.migration import PrismaImporter
        result = PrismaImporter().import_into(Path(args.source), settings.database_path)
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 0
    if args.command == "update-check":
        import json
        from jarvis.core.updater import UpdateService
        print(json.dumps(UpdateService().latest(), ensure_ascii=False, indent=2))
        return 0

    from jarvis.ui.main_window import run_app
    return run_app()


if __name__ == "__main__":
    raise SystemExit(main())
