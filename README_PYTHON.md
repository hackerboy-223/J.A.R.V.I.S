# J.A.R.V.I.S. — Python Core & Desktop

Le cœur Python est désormais le runtime local principal de J.A.R.V.I.S. Il fournit l'agent, la mémoire, les permissions, les jobs, les outils Windows, la voix, le scheduler, MCP, les Skills et une API temps réel utilisable par le Desktop Qt et, de façon opt-in, par l'interface Next.js.

## Démarrage Windows

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -e ".[windows,dev]"
Copy-Item .env.python.example .env
python -m jarvis selftest
python -m jarvis doctor
python -m jarvis
```

L'extra `windows` installe l'automatisation UI optionnelle. Les capacités sensibles restent soumises au PermissionEngine.

## Core runtime

```text
JarvisAgent
   │
   ├── JarvisRuntime
   │    ├── EventBus
   │    ├── PermissionEngine
   │    ├── JobManager
   │    ├── ActivityStore
   │    ├── WorkspaceStore
   │    ├── MissionStore
   │    ├── RecentFileStore
   │    ├── FileIndex (SQLite FTS5)
   │    └── ChangeJournal (diff / undo)
   │
   ├── MemoryStore
   ├── KnowledgeBase
   ├── TaskScheduler
   ├── SkillManager
   ├── MCPManager
   └── ToolRegistry
```

## Capacités système

Implémenté :

- PermissionEngine `allow / ask / deny`, scopes once/session/always ;
- JobManager persistant et annulation coopérative ;
- EventBus partagé ;
- Activity Center ;
- Health Center et bundles diagnostics sans secrets ;
- Settings natifs via QSettings ;
- secrets via Windows Credential Manager/keyring ;
- system tray + mode arrière-plan ;
- notifications de jobs ;
- Task Center scheduler ;
- clipboard contrôlé ;
- liste/focus/minimize/maximize/restore des fenêtres Windows ;
- capture multi-moniteurs via MSS ;
- UI Automation ciblée via pywinauto (extra optionnel) ;
- workspace registry ;
- index de fichiers SQLite FTS5 ;
- fichiers récents ;
- missions persistantes et reprise au démarrage ;
- écritures fichiers atomiques ;
- diff avant patch et ChangeJournal ;
- undo protégé contre l'écrasement de modifications plus récentes ;
- streaming LLM pour endpoints OpenAI-compatible ;
- API SSE + WebSocket ;
- bridge Next.js → Python Core ;
- import idempotent Prisma → Python avec backup ;
- updater GitHub Releases ;
- installateur Inno Setup lorsqu'il est disponible.

La **capture écran** est implémentée, mais l'interprétation sémantique de l'image dépendra du futur choix de modèle multimodal : ce côté IA est volontairement laissé pour plus tard.

## Sécurité

J.A.R.V.I.S. ne reçoit pas de shell système général.

- Les fichiers sont limités au workspace configuré.
- Les chemins secrets sont bloqués.
- L'automatisation UI n'accepte pas de coordonnées arbitraires.
- La saisie UI utilise uniquement des contrôles éditables, sans grammaire SendKeys.
- Les captures écran et lectures du clipboard sont permissionnées.
- Les actions mutantes et externes peuvent être mises sur ASK ou DENY.
- Les actions sont journalisées.
- L'API bind sur localhost par défaut et exige un token pour un bind non-loopback.
- L'updater demande confirmation avant téléchargement puis avant installation.

## API locale

```powershell
python -m jarvis serve
```

Par défaut : `http://127.0.0.1:8000`.

Routes principales :

```text
GET  /health
GET  /health/full
GET  /v1/models
POST /v1/chat/completions
GET  /v1/jobs
POST /v1/jobs/{id}/cancel
POST /v1/stop
GET  /v1/activity
GET  /v1/permissions
POST /v1/permissions/{capability}
GET/POST /v1/workspaces
POST /v1/workspaces/{id}/index
GET  /v1/files/search
GET/POST /v1/missions
GET  /v1/missions/{id}
WS   /ws/events
```

## Next.js comme client du Core

Dans l'environnement Web :

```env
JARVIS_CORE_URL="http://127.0.0.1:8000"
JARVIS_CORE_TOKEN=""
```

Quand `JARVIS_CORE_URL` est défini, `/api/chat` conserve l'historique Prisma de l'interface mais envoie le raisonnement au Core Python et retransmet son streaming. Quand la variable est vide, le moteur Web historique reste disponible comme fallback de migration.

## Migration de l'ancienne DB Prisma

```powershell
python -m jarvis migrate-prisma .\db\custom.db
```

L'import :

- sauvegarde la source ;
- vérifie les tables attendues ;
- importe conversations et messages dans des tables dédiées ;
- utilise `INSERT OR IGNORE` pour rester idempotent ;
- conserve un journal de migration.

## Vérification

```powershell
python -m compileall -q jarvis tests
python -m unittest discover -s tests -v
python -m jarvis selftest
```

Le selftest offline couvre désormais 12 domaines : scheduler, operative state, knowledge, Skills, sandbox, MCP, FastAPI, permissions, EventBus, JobManager, index FTS5 et missions/workspaces.

## Build Windows

```powershell
python -m pip install -e ".[build,windows,dev]"
python -m unittest discover -s tests -v
python -m jarvis selftest
.\packaging\build-windows.ps1
```

Sorties :

```text
dist/JARVIS-Windows-x64.zip
dist/JARVIS-Setup-x64.exe   # si Inno Setup 6 est installé
```

La signature Authenticode n'est pas générée automatiquement : elle nécessite un certificat ou un service de signature éligible.

## Ce qui reste volontairement à finaliser

- choix/installation du futur modèle IA local ;
- compréhension visuelle multimodale des captures ;
- migration définitive de toute l'UI Web vers les permissions/mémoire du Core ;
- suppression du moteur Web historique après validation ;
- signature Windows pour distribution publique ;
- validation du packaging sur plusieurs machines Windows.
