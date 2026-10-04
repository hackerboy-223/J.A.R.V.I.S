<div align="center">

# ⚡ J.A.R.V.I.S.

### Just A Rather Very Intelligent System

<img
  src="https://readme-typing-svg.demolab.com?font=Fira+Code&weight=600&size=22&pause=900&color=00D4FF&center=true&vCenter=true&width=900&lines=Local+AI+Desktop+Agent;Voice+%2B+Memory+%2B+Tools+%2B+Automation;Python+%2B+Next.js+Hybrid+Architecture;Built+for+Windows;A+personal+AI+operating+layer"
  alt="J.A.R.V.I.S. animated typing banner"
/>

<br/>

![Python](https://img.shields.io/badge/Python-3.11%2B-3776AB?logo=python&logoColor=white)
![PySide6](https://img.shields.io/badge/PySide6-Qt%20Desktop-41CD52?logo=qt&logoColor=white)
![FastAPI](https://img.shields.io/badge/FastAPI-Local%20API-009688?logo=fastapi&logoColor=white)
![Next.js](https://img.shields.io/badge/Next.js-16-000000?logo=nextdotjs&logoColor=white)
![TypeScript](https://img.shields.io/badge/TypeScript-5-3178C6?logo=typescript&logoColor=white)
![Bun](https://img.shields.io/badge/Bun-Runtime-000000?logo=bun&logoColor=white)
![SQLite](https://img.shields.io/badge/SQLite-Memory-003B57?logo=sqlite&logoColor=white)
![Windows](https://img.shields.io/badge/Windows-Primary%20Target-0078D4?logo=windows11&logoColor=white)

**Un assistant personnel local, vocal, outillé et extensible — avec interface desktop native, interface web, mémoire persistante, recherche, automatisation contrôlée et API locale.**

</div>

---

## ✨ Vision

J.A.R.V.I.S. n'est pas pensé comme un simple chatbot.

Le projet vise une **couche d'assistance personnelle** capable de :

- comprendre des instructions naturelles ;
- conserver un contexte utile dans le temps ;
- travailler sur des fichiers et projets locaux ;
- utiliser des outils vérifiables plutôt que d'inventer des actions ;
- fonctionner à la voix ;
- lancer des tâches persistantes ;
- exposer un cœur local utilisable par plusieurs interfaces ;
- contrôler certaines actions Windows avec des permissions explicites ;
- évoluer vers un assistant de bureau réellement autonome, sans devenir un shell aveugle.

> Le principe central : **plus de capacités, mais toujours avec visibilité, permissions et traçabilité.**

---

# 🧠 Architecture actuelle

J.A.R.V.I.S. possède aujourd'hui deux interfaces complémentaires autour d'un socle en cours d'unification.

```mermaid
flowchart TB
    U[H@CKERBOY] --> D[PySide6 Desktop]
    U --> W[Next.js Web UI]

    D --> C[Python JARVIS Core]
    W --> WA[Web Agent / API Layer]

    C --> M[(SQLite Memory)]
    C --> K[Knowledge Base / RAG]
    C --> T[Tool Registry]
    C --> S[Scheduler]
    C --> SK[Skills]
    C --> MCP[MCP]
    C --> V[Voice Pipeline]
    C --> API[FastAPI Local API]

    T --> PC[Safe PC Control]
    T --> FILES[Workspace Files]
    T --> WEB[Exa / Public Web]
    T --> PY[Restricted Python Sandbox]

    WA --> P[(Prisma + SQLite)]
    WA --> CTRL[Control Center]
    WA --> VOICE[Browser / Server Voice]

    API -. future unified transport .-> W
```

### Direction cible

```text
                    J.A.R.V.I.S. CORE
                         Python
                           │
         ┌─────────────────┼─────────────────┐
         │                 │                 │
      Memory            Tools            Scheduler
         │                 │                 │
         └─────────────────┼─────────────────┘
                           │
                 FastAPI / WebSocket
                           │
              ┌────────────┴────────────┐
              │                         │
        PySide6 Desktop             Next.js UI
```

L'objectif final est simple : **un seul cerveau, une seule mémoire, les mêmes permissions et outils, deux interfaces.**

---

# ✅ État du projet

| Domaine | État |
|---|---|
| Desktop natif PySide6 | ✅ Actif |
| Web UI Next.js | ✅ Actif |
| Mémoire SQLite | ✅ Actif |
| Knowledge Base / BM25 | ✅ Actif |
| Embeddings hybrides | 🟡 Optionnel |
| Scheduler persistant | ✅ Actif |
| Modes multi-agents | ✅ Actif |
| Skills | ✅ Actif |
| MCP | ✅ Actif |
| API locale FastAPI | ✅ Actif |
| Sandbox Python restreint | ✅ Actif |
| Contrôle PC allowlisté | ✅ Actif |
| Voix mains libres | ✅ Actif |
| Wake word / interruption | ✅ Présent |
| Exa web search | ✅ Intégré |
| Control Center Web | ✅ Actif |
| Diagnostic plateforme | ✅ 12 sous-systèmes |
| Capture écran multi-moniteurs | ✅ Actif |
| Compréhension vision par modèle | 🟡 Côté IA à brancher plus tard |
| Window manager Windows | ✅ Actif |
| Automatisation UI sûre | ✅ Option Windows (`.[windows]`) |
| Permissions Center natif | ✅ Actif |
| Missions persistantes UI | ✅ Actif |
| Installer / updater | 🟡 Inno Setup + GitHub Releases ; signature à fournir |
| Core Python ↔ Web unifié | 🟡 Bridge streaming opt-in actif |

---

# 🚀 Fonctionnalités

## 🧠 Agent principal

Le cœur Python utilise une boucle d'agent avec outils et contexte persistant.

Capacités :

- conversations avec historique ;
- tool calling ;
- mémoire locale ;
- connaissances indexées ;
- modes de raisonnement spécialisés ;
- fallback local pour certaines commandes ;
- API OpenAI-compatible locale ;
- exécution de tâches programmées ;
- contexte par opérateur / mission.

---

## 🤖 Modes agent

L'interface desktop expose plusieurs modes :

| Mode | Usage |
|---|---|
| **STANDARD** | Agent général avec outils |
| **PARALLEL AGENTS** | Plusieurs rôles travaillent en parallèle puis synthèse |
| **SEQUENTIAL CHAIN** | Plan → construction → revue |
| **AI DEBATE** | Positions concurrentes puis synthèse |
| **DEEP RESEARCH** | Recherche web multi-requêtes et synthèse |
| **OPERATIVE** | Travail persistant avec état sauvegardé |

---

## 🧠 Mémoire

J.A.R.V.I.S. utilise SQLite pour plusieurs types de mémoire :

- messages récents ;
- faits explicitement mémorisés ;
- journal d'actions ;
- résultats d'agents ;
- état persistant des opérateurs ;
- historique d'exécution ;
- tâches programmées ;
- base de connaissances locale.

Les connexions SQLite sont fermées explicitement pour éviter les handles verrouillés sous Windows.

---

## 📚 Knowledge Base / RAG

J.A.R.V.I.S. peut indexer des fichiers texte et code localement.

Formats pris en charge :

```text
.txt  .md  .csv  .json
.py   .js  .ts   .tsx  .jsx
.html .xml .log  .yaml .yml
.sql  .ps1
```

Fonctionnement :

```text
Document
   ↓
Chunking local
   ↓
SQLite
   ↓
BM25
   ↓
Embeddings optionnels
   ↓
Contexte injecté dans l'agent
```

BM25 fonctionne sans API externe.

Les embeddings sont optionnels via un endpoint OpenAI-compatible.

---

## 🛠️ Outils Python

Le registre d'outils comprend notamment :

| Outil | Rôle |
|---|---|
| `system_status` | CPU, RAM, plateforme et runtime |
| `pc_control` | Actions Windows allowlistées |
| `web_search` | Recherche publique via Exa |
| `read_page` | Lecture protégée de pages publiques |
| `knowledge_search` | Recherche dans la base locale |
| `file_read` | Lecture dans le workspace autorisé |
| `file_write` | Écriture contrôlée |
| `file_patch` | Patch textuel exact |
| `python_sandbox` | Calcul Python restreint |
| `use_skill` | Chargement d'un Skill |
| `mcp_servers` | Liste des serveurs MCP |
| `mcp_list_tools` | Outils MCP disponibles |
| `mcp_call` | Appel d'un outil MCP configuré |
| scheduler tools | Créer, lister, pause, reprise, annulation |
| operative state | État persistant par opérateur |

### Sécurité fichiers

Les outils fichiers :

- restent dans `JARVIS_WORKSPACE_ROOT` ;
- bloquent les chemins secrets ;
- refusent l'évasion du workspace ;
- n'exposent pas `.env`, `.git`, `.ssh` ou les credentials.

---

# 🖥️ Contrôle PC

Le contrôle local est **désactivable** et limité à une liste explicite.

Actions actuellement prévues dans la couche de contrôle :

- ouvrir Calculatrice ;
- ouvrir Bloc-notes ;
- ouvrir l'Explorateur ;
- ouvrir Bureau ;
- ouvrir Documents ;
- ouvrir Téléchargements ;
- ouvrir le projet ;
- ouvrir une URL HTTP/HTTPS.

Activation :

```env
JARVIS_ALLOW_PC_CONTROL="true"
```

Aucun shell arbitraire n'est donné au modèle.

---

# 🎙️ Voix

J.A.R.V.I.S. possède une pile vocale hybride.

### Pipeline

```text
Microphone
   ↓
Vosk live
   ↓
partial captions / wake word
   ↓
Final utterance
   ↓
Groq Whisper (si configuré)
   ↓ fallback
Vosk / faster-whisper local
   ↓
Agent
   ↓
TTS local
```

### Fonctions

- transcription live ;
- mains libres ;
- wake word « Jarvis » ;
- interruption pendant la parole ;
- fallback local ;
- TTS nettoyé des URLs, blocs de code et bruit Markdown ;
- réaction audio du Neural HUD.

Configuration basse consommation recommandée :

```env
JARVIS_STT_PROVIDER="hybrid"
JARVIS_WHISPER_MODEL="tiny"
JARVIS_WHISPER_COMPUTE="int8"
JARVIS_WHISPER_CPU_THREADS="2"
JARVIS_WHISPER_PARTIAL_TRANSCRIPTS="false"
```

---

# 🌐 Recherche Web

La recherche Python utilise Exa comme moteur de retrieval.

```env
EXA_API_KEY=""
JARVIS_EXA_SNIPPET_CHARS="1800"
```

Le système :

- recherche ;
- récupère des highlights ;
- compacte le contexte ;
- retire les doublons ;
- protège contre les accès localhost / réseaux privés lors de la lecture de pages ;
- conserve les métadonnées utiles au diagnostic.

---

# 🧩 Skills

Les Skills sont des instructions réutilisables chargées à la demande.

Structure :

```text
skills/
└── mon-skill/
    ├── SKILL.md
    └── skill.toml
```

Un exemple est disponible dans :

```text
skills.example/code-review/
```

J.A.R.V.I.S. ne lance pas automatiquement des scripts arbitraires fournis par un Skill.

---

# 🔌 MCP

J.A.R.V.I.S. peut se connecter à des serveurs MCP explicitement configurés.

Fichier :

```text
mcp.json
```

Exemple fourni :

```text
mcp.example.json
```

Variables :

```env
JARVIS_MCP_CONFIG=""
```

Principes :

- serveurs préconfigurés uniquement ;
- stdio ou Streamable HTTP sécurisé ;
- pas de commande inventée par le modèle ;
- variables d'environnement explicitement transmises uniquement.

---

# ⏰ Scheduler

J.A.R.V.I.S. embarque un scheduler SQLite persistant.

Types :

- `once`
- `interval`
- `cron`

Outils :

- `schedule_task`
- `list_scheduled_tasks`
- `pause_scheduled_task`
- `resume_scheduled_task`
- `cancel_scheduled_task`

Le processus desktop ou API doit être actif pour exécuter les tâches arrivées à échéance.

---

# 🧪 Sandbox Python

Le sandbox permet de petits calculs Python contrôlés.

Restrictions principales :

- timeout court ;
- imports allowlistés ;
- builtins restreints ;
- aucun `open()` ;
- pas de réseau ;
- pas de subprocess exposé ;
- répertoire temporaire isolé.

> Ce mécanisme réduit la surface d'action, mais n'est pas présenté comme une frontière de sécurité OS absolue.

---

# 🖼️ Desktop natif — PySide6

L'application desktop comprend :

- HUD Neural Core natif Qt ;
- réseau neuronal animé ;
- scanner ;
- particules ;
- états visuels idle/listening/thinking/speaking/error ;
- chat local ;
- typewriter ;
- sélection du mode agent ;
- mains libres ;
- diagnostic microphone ;
- test voix ;
- import Knowledge Base ;
- Profile Memory ;
- Agent Memory ;
- confirmations d'actions.

### Lancement

```powershell
python -m jarvis
```

### Diagnostic UI

```powershell
python -m jarvis doctor
```

Le mode doctor affiche des checkpoints de démarrage Qt et active `faulthandler` afin de rendre les crashs natifs Windows plus faciles à diagnostiquer.

---

# 🌐 Interface Web — Next.js

La version web reste disponible comme interface moderne et PWA.

Fonctions :

- conversations ;
- streaming agent ;
- sidebar ;
- recherche de conversations ;
- voix ;
- HUD ;
- télémétrie ;
- thème ;
- Control Center ;
- palette `Ctrl/Cmd + K` ;
- permissions navigateur ;
- actions locales allowlistées ;
- notifications de fin ;
- login production.

### Stack Web

| Couche | Technologie |
|---|---|
| Framework | Next.js 16 App Router |
| Langage | TypeScript |
| UI | React 19 + Tailwind CSS 4 |
| Components | Radix / shadcn style |
| Runtime | Bun |
| ORM | Prisma |
| Database | SQLite |
| Validation / state | Zod / Zustand |
| Animations | Framer Motion |

---

# 🔐 Sécurité

J.A.R.V.I.S. est conçu comme assistant personnel single-user.

## Web

En production :

```env
JARVIS_ACCESS_PASSWORD=""
JARVIS_SESSION_SECRET=""
JARVIS_ENCRYPTION_KEY=""
JARVIS_ALLOW_RUN_JS="false"
JARVIS_ALLOW_PC_CONTROL="false"
```

Protections présentes :

- cookie HttpOnly ;
- SameSite strict ;
- signature serveur ;
- routes privées ;
- rate limiting ;
- chiffrement de secrets persistés lorsque configuré ;
- outils dangereux désactivés par défaut ;
- health-check public minimal.

Voir [SECURITY.md](./SECURITY.md).

## Python

Principes :

- pas de shell illimité ;
- workspace contraint ;
- secrets bloqués ;
- actions mutantes confirmables ;
- MCP préconfiguré uniquement ;
- API locale par défaut ;
- token obligatoire pour exposition réseau non-loopback ;
- action log SQLite ;
- sandbox restreint.

---

# ⚙️ Installation Desktop

## Prérequis

- Windows 10/11 recommandé ;
- Python 3.11+ ;
- microphone optionnel ;
- connexion Internet seulement pour les fournisseurs et recherches distantes.

## Installation

```powershell
git clone https://github.com/hackerboy-223/J.A.R.V.I.S.git
cd J.A.R.V.I.S

python -m venv .venv
.\.venv\Scripts\Activate.ps1

python -m pip install --upgrade pip
python -m pip install -e .

Copy-Item .env.python.example .env
```

Puis configurez les fournisseurs souhaités dans `.env`.

Lancement :

```powershell
python -m jarvis
```

---

# ⚙️ Installation Web

Prérequis :

- Bun ;
- Node compatible avec Next.js 16.

```powershell
git clone https://github.com/hackerboy-223/J.A.R.V.I.S.git
cd J.A.R.V.I.S

bun install
Copy-Item .env.example .env

bun run db:push
bun run dev
```

Puis :

```text
http://localhost:3000
```

---

# 🧪 Vérification

## Web

```powershell
bun run check
```

Cette commande exécute :

```text
ESLint
  ↓
Prisma generate
  ↓
TypeScript
  ↓
Next.js production build
```

## Python

```powershell
python -m jarvis selftest
```

Le self-test offline vérifie actuellement :

1. Scheduler ;
2. Operative state ;
3. Knowledge memory ;
4. Skills ;
5. Python sandbox ;
6. MCP ;
7. FastAPI.

---

# 🌐 API locale OpenAI-compatible

Démarrage :

```powershell
python -m jarvis serve
```

Valeur par défaut :

```text
http://127.0.0.1:8000
```

Routes :

```text
GET  /health
GET  /v1/models
POST /v1/chat/completions
```

Exemple :

```json
{
  "model": "jarvis",
  "messages": [
    {
      "role": "user",
      "content": "Continue l'audit du projet"
    }
  ],
  "metadata": {
    "mode": "operative",
    "operator_id": "project-audit"
  }
}
```

Exposition réseau :

```env
JARVIS_API_HOST="127.0.0.1"
JARVIS_API_PORT="8000"
JARVIS_API_TOKEN=""
```

J.A.R.V.I.S. refuse un bind non-loopback sans token API.

---

# 🧠 Fournisseurs IA

Le cœur Python possède une couche de provider configurable.

Exemples actuels :

### OpenRouter

```env
JARVIS_LLM_PROVIDER="openrouter"
JARVIS_LLM_BASE_URL="https://openrouter.ai/api/v1"
OPENROUTER_API_KEY=""
JARVIS_LLM_MODEL="openrouter/free"
```

### Hugging Face

```env
JARVIS_LLM_PROVIDER="huggingface"
HF_TOKEN=""
JARVIS_HF_MODEL="zai-org/GLM-5.3-Flash"
JARVIS_HF_PROVIDER="auto"
```

### Ollama local

```env
JARVIS_OLLAMA_BASE_URL="http://127.0.0.1:11434/v1"
JARVIS_OLLAMA_MODEL="qwen2.5:1.5b"
```

> La stratégie long terme est de pouvoir fonctionner avec un modèle téléchargé/local sans dépendre d'un quota API.

---

# 📂 Structure principale

```text
J.A.R.V.I.S/
│
├── jarvis/                     # Cœur desktop Python
│   ├── __main__.py             # CLI : desktop / serve / selftest / doctor
│   ├── api.py                  # API FastAPI locale
│   ├── config.py               # Configuration runtime
│   ├── knowledge.py            # Knowledge Base / RAG
│   ├── profile.py              # Profil principal
│   ├── selftest.py             # Smoke tests plateforme
│   │
│   ├── core/
│   │   ├── agent.py            # Boucle agent
│   │   ├── llm.py              # Providers LLM
│   │   ├── memory.py           # SQLite memory
│   │   ├── scheduler.py        # Scheduler persistant
│   │   ├── skills.py           # Skills
│   │   ├── mcp_bridge.py       # MCP
│   │   ├── tools.py            # Registry
│   │   └── ...
│   │
│   ├── tools/
│   │   ├── files.py
│   │   ├── pc.py
│   │   ├── sandbox.py
│   │   ├── system.py
│   │   └── web.py
│   │
│   ├── ui/
│   │   ├── main_window.py
│   │   └── neural_widget.py
│   │
│   └── voice/
│       ├── stt.py
│       ├── tts.py
│       └── vosk_stt.py
│
├── src/                        # Interface Web Next.js
│   ├── app/
│   ├── components/
│   ├── hooks/
│   └── lib/
│
├── prisma/                     # Schéma SQLite web
├── tests/                      # Tests Python
├── packaging/                  # Build Windows
├── scripts/                    # Scripts Web/build
├── skills.example/             # Exemple de Skill
├── mcp.example.json
├── pyproject.toml
├── package.json
├── README_PYTHON.md
├── SECURITY.md
└── README.md
```

---

# 🗺️ Roadmap

## Phase A — Core professionnel

- [x] PermissionEngine unifié
- [x] JobManager
- [x] EventBus
- [x] STOP global coopératif
- [x] Health Center UI
- [x] crash logs persistants
- [x] Settings UI native
- [x] secrets Windows Credential Manager

## Phase B — Assistant de bureau

- [x] System tray
- [x] notifications Windows
- [x] Task Center
- [x] Activity Center
- [x] clipboard contrôlé
- [x] file index / search
- [x] workspaces favoris
- [x] window manager

## Phase C — Capacités avancées

- [x] capture écran
- [ ] compréhension visuelle par un modèle multimodal (côté IA)
- [x] capture multi-moniteurs
- [x] safe UI automation
- [x] missions persistantes
- [x] restauration après reboot
- [x] undo / redo
- [x] diff viewer
- [x] vrai streaming API

## Phase D — Unification

- [x] Python Core exposé comme surface temps réel
- [ ] suppression finale du moteur Web historique après validation
- [x] WebSocket event stream
- [x] Next.js peut devenir client du Python Core via `JARVIS_CORE_URL`
- [ ] mémoire unique après migration/validation du bridge
- [ ] permissions Web redirigées entièrement vers le Core
- [x] scheduler Python unique pour les tâches agent

## Phase E — Produit Windows

- [x] first-run wizard
- [x] couverture pytest / pytest-qt
- [x] migration Prisma → Python
- [x] installer Windows
- [x] auto-update GitHub Releases
- [ ] signature si distribution publique (certificat/signing externe requis)

---

# 📦 Build Windows

Le projet contient déjà une recette PyInstaller.

```powershell
python -m pip install -e ".[build,windows,dev]"
python -m unittest discover -s tests -v
python -m jarvis selftest
.\packaging\build-windows.ps1
```

Sortie prévue :

```text
dist/JARVIS-Windows-x64.zip
```

Le build est volontairement en dossier plutôt qu'en exécutable one-file afin de réduire les problèmes liés aux bibliothèques natives Qt/audio.

---

# 🔎 Diagnostic

Quelques commandes utiles :

```powershell
# Vérification Python
python -m jarvis selftest

# Diagnostic fenêtre Qt
python -m jarvis doctor

# Lancer le desktop
python -m jarvis

# API locale
python -m jarvis serve

# Vérification Web complète
bun run check
```

---

# 🛡️ Philosophie de sécurité

J.A.R.V.I.S. suit quatre règles :

### 1. Observe avant d'agir

Une réponse ne doit jamais prétendre qu'une action a réussi sans résultat réel d'un outil.

### 2. Limite les pouvoirs

Une capacité locale doit être explicitement définie et scoped.

### 3. Confirme les modifications

Écriture, patch, automatisation ou appel externe sensible doivent rester contrôlables.

### 4. Garde une trace

Les actions importantes doivent pouvoir être auditées.

---

# 🧭 Principes de conception

- **Local-first**
- **Windows-first**
- **Low-dependency**
- **Observable**
- **Permission-based**
- **Recoverable**
- **Extensible**
- **Voice-ready**
- **API-ready**
- **Model-agnostic**

---

# 🤝 Contribution

Le projet évolue vite.

Avant une modification importante :

```powershell
git switch main
git pull
git switch -c feat/ma-feature
```

Validation recommandée :

```powershell
python -m jarvis selftest
bun run check
```

Pour les modifications touchant permissions, fichiers, MCP, sandbox ou exposition réseau, documenter le modèle de sécurité associé.

---

# 📜 Licence

Le dépôt est actuellement présenté comme **projet personnel à usage libre**, mais aucune licence Open Source formelle n'est encore publiée dans un fichier `LICENSE`.

Si le projet doit devenir réellement Open Source ou distribué publiquement, ajouter une licence explicite avant une release majeure.

---

# 👤 Auteur

**H@CKERBOY**

Projet personnel autour de :

- intelligence artificielle ;
- agents ;
- développement web ;
- développement desktop ;
- automatisation ;
- cybersécurité défensive ;
- assistants vocaux.

---

<div align="center">

### ⚡ J.A.R.V.I.S.

**Local. Vocal. Persistant. Outillé. Contrôlable.**

<img
  src="https://readme-typing-svg.demolab.com?font=Fira+Code&size=17&pause=1200&color=FFC864&center=true&vCenter=true&width=800&lines=System+online.;Memory+online.;Tools+online.;Awaiting+your+command."
  alt="J.A.R.V.I.S. system status animation"
/>

*« À votre service. »*

</div>
