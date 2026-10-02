<div align="center">

# ⚡ J.A.R.V.I.S.

**Just A Rather Very Intelligent System**

Assistant IA vocal façon Iron Man — propulsé par les modèles **GLM de Z.ai** et **Hugging Face**.

</div>

---

## 🎯 Description

J.A.R.V.I.S. est un agent conversationnel **vocal** avec une interface holographique HUD inspirée de l'univers Iron Man. Il **écoute**, **réfléchit**, **agit sur la machine** et **répond à voix haute**, avec une animation neuronale plein écran qui réagit à votre voix et à la sienne.

- 🧠 **Moteur GLM via Z.ai** — disponible quand l’environnement Z.ai est correctement configuré
- 🤗 **Hugging Face en option** — Llama 3.3, Qwen 2.5/3, Mistral, GLM 4.5/5.3 via Inference Providers (token HF)
- 🎙️ **Agent vocal complet** — reconnaissance vocale (STT) + synthèse vocale (TTS) en streaming par phrases
- 🇫🇷 **Voix françaises** — voix natives du navigateur (instantanées, hors ligne) ou voix serveur classées d'après un test réel de diction française
- 🛠️ **7 outils embarqués** — recherche web, lecture de page, calculatrice, exécution JavaScript, date/heure, diagnostic système, effets HUD
- 🌐 **Lien neural plein écran** — réseau de neurones animé (canvas 2D, projection 3D) qui vibre à l'écoute et pulse pendant l'élocution
- 📱 **PWA** — installable, thème HUD ambré, responsive mobile/desktop

## 🖼️ Interface

- **Réacteur Arc** animé (canvas) avec états : veille / écoute / réflexion / élocution
- **Boot sequence** cinéma au lancement — « NOYAU : GLM 4.6 — MOTEUR STARK INTÉGRÉ »
- **HUD corners, radar sweep, telemetry panel**, scanlines et grille holographique
- **Lien neural** : canal vocal plein écran avec typewriter synchro voix

## 🛠️ Stack technique

| Couche | Technologie |
|---|---|
| Framework | **Next.js 16** (App Router) + TypeScript |
| Runtime / packages | **Bun** |
| UI | **Tailwind CSS 4** + shadcn/ui (style New York) + Lucide |
| Base de données | **Prisma ORM** + SQLite |
| LLM | GLM 4.6 / 4.5-Air / 4.5-Flash (Z.ai) · Hugging Face Inference Providers |
| Voix | STT serveur (whisper) · TTS serveur 7 voix · Web Speech API navigateur |

## 🚀 Démarrage rapide

```bash
# 1. Installer les dépendances
bun install

# 2. Configurer l'environnement
cp .env.example .env

# 3. Créer la base de données
bun run db:push

# 4. Lancer J.A.R.V.I.S.
bun run dev
```

Ouvrez <http://localhost:3000>. En développement local, l’authentification peut rester désactivée si aucune variable de sécurité n’est définie. Le moteur Z.ai dépend de la configuration disponible dans votre environnement.

> 💡 **Pour la voix** : le navigateur exige une page **HTTPS** ou `localhost` pour le micro. Si l'app est intégrée dans un aperçu (iframe), ouvrez-la dans un onglet dédié — J.A.R.V.I.S. vous le proposera automatiquement.

## 🔐 Sécurité et production

En production, J.A.R.V.I.S. se verrouille automatiquement. Définissez au minimum :

```env
JARVIS_ACCESS_PASSWORD="un-mot-de-passe-fort"
JARVIS_SESSION_SECRET="une-longue-valeur-aleatoire-d-au-moins-32-caracteres"
JARVIS_ENCRYPTION_KEY="une-autre-longue-valeur-aleatoire"
JARVIS_ALLOW_RUN_JS="false"
```

- Les sessions utilisent un cookie **HttpOnly**, `SameSite=Strict` et signé côté serveur.
- Le token Hugging Face est chiffré en **AES-256-GCM** quand `JARVIS_ENCRYPTION_KEY` est défini.
- Les routes chat, conversations, réglages, voix et télémétrie nécessitent une session valide.
- Les endpoints coûteux sont limités en fréquence.
- `run_js` est **désactivé par défaut en production**. Ne l’activez que dans un environnement réellement isolé.
- Le health-check public `/api` ne révèle plus le nom d’hôte, le CPU, la RAM ou la version du système.

> **Important — dépendances :** avant tout déploiement public, utilisez une version Next.js corrigée par les dernières publications de sécurité et régénérez `bun.lock` avec Bun. Le lockfile ne doit jamais être modifié à la main.

Voir également [SECURITY.md](./SECURITY.md).

## 🧰 Outils de l'agent

| Outil | Description |
|---|---|
| `web_search` | Recherche web en temps réel |
| `read_page` | Lit et résume n'importe quelle page web |
| `calculator` | Calculs de précision |
| `run_js` | Exécute du JavaScript côté serveur (sandbox) |
| `get_datetime` | Date et heure du système |
| `system_status` | Diagnostic complet de la machine (CPU, RAM, réseau…) |
| `hud_action` | Déclenche des effets HUD en direct (balayage radar, alertes…) |

L'agent choisit ses outils **autonomement** selon votre demande — les résultats s'affichent dans des cartes dédiées, avec statut et durée.

## ⚙️ Configuration

Tout se règle dans l'interface (**⚙ Réglages**) :

- **Modèle** : GLM via l’environnement Z.ai configuré, ou modèles Hugging Face (token requis)
- **Voix** : moteur navigateur (voix françaises natives) ou moteur serveur (tongtong ★, xiaochen ★ recommandées en français)
- **Température, étapes max, prompt système**

## 📁 Structure du projet

```
src/
├── app/
│   ├── api/
│   │   ├── chat/          # Route SSE de l'agent (streaming + outils)
│   │   ├── voice/asr/     # Reconnaissance vocale
│   │   ├── voice/tts/     # Synthèse vocale (découpage par phrases)
│   │   ├── conversations/ # CRUD des conversations
│   │   ├── settings/      # Réglages + test de connexion
│   │   └── system-status/ # Diagnostic machine
│   ├── layout.tsx / page.tsx
│   └── manifest.ts        # PWA
├── components/
│   ├── chat/              # Composer, messages, réglages, sidebar…
│   └── jarvis/            # Réacteur Arc, lien neural, HUD, boot…
├── hooks/
│   ├── use-jarvis-voice.tsx  # Agent vocal (micro, STT, file TTS streaming)
│   └── use-hugging-agent.ts  # Orchestration SSE de l'agent
└── lib/
    ├── agent/             # Moteurs (Z.ai / HF), parsing d'outils, prompt
    ├── server/            # Settings serveur
    └── types.ts           # Modèles, voix, outils
prisma/schema.prisma       # Conversations, messages, réglages
```

## 📜 Licence

Projet personnel — usage libre.

---

<div align="center">

*« À votre service, Monsieur. »* — J.A.R.V.I.S.

</div>
