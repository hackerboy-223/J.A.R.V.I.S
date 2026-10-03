// ============================================================
// Types partagés client / serveur — HuggingAgent
// ============================================================

export type ChatRole = "user" | "assistant" | "tool";

export type EngineMode = "auto" | "hf" | "demo";

/** Moteur réellement utilisé pour une réponse */
export type ActiveEngine = "hf" | "demo";

export interface ToolCallInfo {
  tool: string;
  args: Record<string, unknown>;
}

export interface UiMessage {
  id: string;
  role: ChatRole;
  content: string;
  /** Pour role === "tool" */
  toolName?: string;
  toolArgs?: string; // JSON
  toolResult?: string; // JSON
  step?: number;
  durationMs?: number;
  createdAt?: string;
  /** état local pendant le streaming */
  pending?: boolean;
  error?: string;
}

export interface ConversationSummary {
  id: string;
  title: string;
  model: string | null;
  engine: string;
  createdAt: string;
  updatedAt: string;
  messageCount?: number;
}

export interface ConversationDetail extends ConversationSummary {
  messages: UiMessage[];
}

export interface PublicSettings {
  hasToken: boolean;
  tokenPreview: string | null; // ex: "hf_abc…xyz"
  model: string;
  customModel: string | null;
  engine: EngineMode;
  temperature: number;
  maxSteps: number;
  systemPrompt: string | null;
  // Voix J.A.R.V.I.S.
  voiceEnabled: boolean;
  voiceName: string;
  voiceSpeed: number;
  /** Moteur vocal : "stark" (serveur) ou "browser" (voix natives du navigateur) */
  voiceEngine: VoiceEngine;
  /** URI de la voix navigateur choisie (null = auto : meilleure voix française) */
  browserVoiceUri: string | null;
}

export interface UpdateSettingsPayload {
  hfToken?: string | null; // null => supprimer
  model?: string;
  customModel?: string | null;
  engine?: EngineMode;
  temperature?: number;
  maxSteps?: number;
  systemPrompt?: string | null;
  voiceEnabled?: boolean;
  voiceName?: string;
  voiceSpeed?: number;
  voiceEngine?: VoiceEngine;
  browserVoiceUri?: string | null;
}

// ============================================================
// Statut système (machine) — GET /api/system-status
// ============================================================

export interface SystemStatus {
  hostname: string;
  platform: string;
  arch: string;
  cpuModel: string;
  cpuCount: number;
  loadAvg: [number, number, number];
  totalMem: number; // octets
  freeMem: number; // octets
  usedMemPct: number; // 0-100
  osUptime: number; // secondes
  processUptime: number; // secondes
  nodeVersion: string;
  processMemRss: number; // octets
  timestamp: string;
}

// ============================================================
// Voix J.A.R.V.I.S.
// ============================================================

export interface VoiceInfo {
  name: string;
  label: string;
  description: string;
  /** Langue parlée naturellement par la voix */
  lang: "fr" | "en";
  /** Voix recommandée pour le français */
  recommended?: boolean;
}

/**
 * Voix du moteur vocal Stark (serveur z-ai) — classées d'après un test réel
 * de diction française (aller-retour TTS → ASR) : tongtong ≈ xiaochen >
 * chuichui > luodo > douji > jam > kazi.
 */
export const TTS_VOICES: VoiceInfo[] = [
  {
    name: "tongtong",
    label: "Tongtong (chaleureuse) ★",
    description: "La meilleure diction française du moteur serveur — testée et validée.",
    lang: "fr",
    recommended: true,
  },
  {
    name: "xiaochen",
    label: "Xiaochen (posée)",
    description: "Ton calme et professionnel, bonne diction française.",
    lang: "fr",
    recommended: true,
  },
  {
    name: "chuichui",
    label: "Chuichui (vive)",
    description: "Voix vive et claire, à l'aise en français.",
    lang: "fr",
  },
  {
    name: "luodo",
    label: "Luodo (expressive)",
    description: "Voix expressive et énergique.",
    lang: "fr",
  },
  {
    name: "douji",
    label: "Douji (fluide)",
    description: "Voix naturelle et fluide — meilleure en anglais.",
    lang: "fr",
  },
  {
    name: "jam",
    label: "J.A.M. (gentleman britannique)",
    description: "L’esprit JARVIS originel — parfait en anglais, accent british en français.",
    lang: "en",
  },
  {
    name: "kazi",
    label: "Kazi (neutre)",
    description: "Voix claire et standard — réservée à l'anglais.",
    lang: "en",
  },
];

export const DEFAULT_VOICE = "tongtong";

/** Moteur de la voix J.A.R.V.I.S. */
export type VoiceEngine = "stark" | "browser";

export const DEFAULT_VOICE_ENGINE: VoiceEngine = "browser";

// ============================================================
// Actions HUD déclenchables par l’agent (outil hud_action)
// ============================================================

export type HudAction = "scan" | "alert" | "power_up" | "celebrate" | "ping";

export const HUD_ACTIONS: HudAction[] = ["scan", "alert", "power_up", "celebrate", "ping"];

/** Événement DOM diffusé quand JARVIS déclenche une action HUD : window.dispatchEvent(new CustomEvent<HudAction>("jarvis:hud", { detail })) */
export const HUD_EVENT = "jarvis:hud";

// ============================================================
// Événements SSE de /api/chat
// ============================================================

export type ChatSseEvent =
  | { type: "start"; conversationId: string; userMessageId: string; engine: ActiveEngine; model: string }
  | { type: "status"; step: number; status: string }
  | { type: "tool_start"; step: number; tool: string; args: Record<string, unknown> }
  | { type: "tool_result"; step: number; tool: string; result: unknown; durationMs: number; isError?: boolean }
  | { type: "token"; text: string }
  | { type: "done"; messageId: string; title: string }
  | { type: "error"; message: string };

// ============================================================
// Modèles — moteur Stark intégré (GLM) + Hugging Face (token)
// ============================================================

export interface ModelInfo {
  id: string;
  label: string;
  description: string;
  size: string;
  tags: string[];
  /** "stark" = moteur intégré Z.ai (GLM, sans token) · "hf" = Hugging Face Inference Providers (token requis) */
  family: "stark" | "hf";
}

/**
 * Modèles GLM du moteur Stark INTÉGRÉ (Z.ai SDK, sans token, disponibles immédiatement).
 */
export const STARK_MODELS: ModelInfo[] = [
  {
    id: "glm-4.6",
    label: "GLM 4.6",
    description:
      "Vaisseau amiral Z.ai — agent, raisonnement et code d'élite. Le cerveau de JARVIS.",
    size: "355B MoE",
    tags: ["Z.ai", "GLM", "Agent"],
    family: "stark",
  },
  {
    id: "glm-4.5-air",
    label: "GLM 4.5 Air",
    description: "Version allégée de GLM 4.5 — rapide, efficace, très bon en agent.",
    size: "106B MoE",
    tags: ["Z.ai", "GLM", "Rapide"],
    family: "stark",
  },
  {
    id: "glm-4.5-flash",
    label: "GLM 4.5 Flash",
    description: "Ultra-rapide — réponses éclair pour les tâches courtes.",
    size: "Flash",
    tags: ["Z.ai", "GLM", "Éclair"],
    family: "stark",
  },
  {
    id: "glm-4.5",
    label: "GLM 4.5",
    description: "Génération précédente — agent et écriture solides.",
    size: "355B MoE",
    tags: ["Z.ai", "GLM"],
    family: "stark",
  },
];

/**
 * Modèles Hugging Face (Inference Providers — token requis).
 * GLM y est servi par le provider officiel zai-org.
 */
export const HF_MODELS: ModelInfo[] = [
  {
    id: "zai-org/GLM-5.3",
    label: "GLM 5.3",
    description: "Le tout dernier GLM — pointe du raisonnement, via le provider zai-org.",
    size: "Flagship",
    tags: ["Z.ai", "GLM", "Récent"],
    family: "hf",
  },
  {
    id: "zai-org/GLM-5.3-Flash",
    label: "GLM 5.3 Flash",
    description: "Dernier-né GLM en version éclair, via Hugging Face.",
    size: "Flash",
    tags: ["Z.ai", "GLM", "Rapide"],
    family: "hf",
  },
  {
    id: "zai-org/GLM-4.6",
    label: "GLM 4.6",
    description: "GLM 4.6 via Inference Providers — excellent agent.",
    size: "355B MoE",
    tags: ["Z.ai", "Agent"],
    family: "hf",
  },
  {
    id: "zai-org/GLM-4.5-Air",
    label: "GLM 4.5 Air",
    description: "GLM léger et rapide via Inference Providers.",
    size: "106B MoE",
    tags: ["Z.ai", "Rapide"],
    family: "hf",
  },
  {
    id: "meta-llama/Llama-3.3-70B-Instruct",
    label: "Llama 3.3 70B Instruct",
    description: "Le fleuron open-weights de Meta. Excellent agent généraliste.",
    size: "70B",
    tags: ["Meta", "Chat", "Agent"],
    family: "hf",
  },
  {
    id: "Qwen/Qwen2.5-72B-Instruct",
    label: "Qwen 2.5 72B Instruct",
    description: "Modèle polyvalent d'Alibaba, très fort en raisonnement et multilingue.",
    size: "72B",
    tags: ["Alibaba", "Multilingue", "Code"],
    family: "hf",
  },
  {
    id: "Qwen/Qwen3-32B",
    label: "Qwen 3 32B",
    description: "Dernière génération Qwen avec mode réflexion.",
    size: "32B",
    tags: ["Raisonnement", "Récent"],
    family: "hf",
  },
  {
    id: "mistralai/Mistral-Small-24B-Instruct-2501",
    label: "Mistral Small 24B",
    description: "Rapide et efficace, très bon rapport qualité/vitesse.",
    size: "24B",
    tags: ["Mistral", "Rapide"],
    family: "hf",
  },
];

/** Tous les modèles connus, pour les sélecteurs de l'UI. */
export const ALL_MODELS: ModelInfo[] = [...STARK_MODELS, ...HF_MODELS];

export const DEFAULT_MODEL = "glm-4.6";

/** Un identifiant de la forme « glm-… » désigne un modèle du moteur Stark intégré (sans token). */
export function isStarkModel(id: string): boolean {
  return /^glm-[\d]/i.test(id);
}

export function resolveModel(model?: string | null, customModel?: string | null): string {
  if (model === "__custom__") {
    return (customModel || "").trim() || DEFAULT_MODEL;
  }
  return model || DEFAULT_MODEL;
}

/** Libellé court d'un modèle pour l'UI (badge, boot, bannières). */
export function modelLabel(id: string): string {
  const known = ALL_MODELS.find((m) => m.id === id);
  if (known) return known.label;
  const short = id.split("/").pop() ?? id;
  return short.slice(0, 28);
}

// ============================================================
// Définition des outils de l'agent (pour l'UI et le prompt)
// ============================================================

export interface ToolMeta {
  name: string;
  label: string;
  description: string;
  icon: string; // nom lucide mappé côté UI
}

export const AGENT_TOOLS: ToolMeta[] = [
  {
    name: "web_search",
    label: "Recherche web",
    description: "Recherche sur le web des informations récentes (actualités, docs, faits).",
    icon: "globe",
  },
  {
    name: "read_page",
    label: "Lecture de page",
    description: "Lit une page web et en extrait le contenu (titre, texte).",
    icon: "book-open",
  },
  {
    name: "calculator",
    label: "Calculatrice",
    description: "Évalue une expression mathématique avec précision.",
    icon: "calculator",
  },
  {
    name: "run_js",
    label: "Exécution JS",
    description: "Exécute du code JavaScript dans un bac à sable (console, calculs, transformations).",
    icon: "terminal",
  },
  {
    name: "get_datetime",
    label: "Date & heure",
    description: "Obtient la date et l'heure actuelles.",
    icon: "clock",
  },
  {
    name: "system_status",
    label: "Statut de la machine",
    description: "Interroge la machine hôte : CPU, mémoire, uptime et système.",
    icon: "activity",
  },
  {
    name: "pc_control",
    label: "Contrôle PC",
    description: "Ouvre localement une application sûre, un dossier connu ou une URL sur le PC Windows.",
    icon: "monitor",
  },
  {
    name: "hud_action",
    label: "Action HUD",
    description: "Déclenche une animation de l'interface holographique (scan, alert, power_up, celebrate, ping).",
    icon: "radar",
  },
];

export const MAX_CONTEXT_MESSAGES = 24;
