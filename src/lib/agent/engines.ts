import { InferenceClient } from "@huggingface/inference";
import ZAI from "z-ai-web-dev-sdk";
import { extractToolCall, looksLikeToolCallStart, type ToolCall } from "./parse";

export interface LlmMessage {
  role: "system" | "user" | "assistant";
  content: string;
}

export interface LlmCallOptions {
  engine: "hf" | "demo";
  token?: string;
  model: string;
  messages: LlmMessage[];
  temperature: number;
  maxTokens?: number;
  onText: (delta: string) => void;
  signal?: AbortSignal;
}

export interface LlmResult {
  text: string;
  toolCall: ToolCall | null;
}

// ---------------------------------------------------------------
// Mapping des erreurs Hugging Face en messages clairs
// ---------------------------------------------------------------

export function mapHfError(e: unknown, model?: string): Error {
  const err = e as { status?: number; message?: string; name?: string };
  const status = err?.status;
  const raw = err?.message ?? String(e);
  if (
    status === 401 ||
    status === 403 ||
    /401|403|unauthorized|invalid.*token|invalid.*credential|invalid username|invalid password|forbidden/i.test(
      raw
    )
  ) {
    return new Error(
      "Token Hugging Face invalide, expiré ou sans l'accès « Make calls to Inference Providers ». Vérifie tes réglages."
    );
  }
  if (status === 404 || /404|not found|does not exist|no inference provider/i.test(raw)) {
    return new Error(
      `Le modèle « ${model ?? "?"} » n'est pas disponible via les Inference Providers. Essaie un autre modèle (ex : meta-llama/Llama-3.3-70B-Instruct).`
    );
  }
  if (status === 429 || /429|rate limit|quota/i.test(raw)) {
    return new Error(
      "Limite de débit Hugging Face atteinte. Attends quelques secondes avant de réessayer."
    );
  }
  if (status === 503 || /503|unavailable|loading/i.test(raw)) {
    return new Error(
      `Le modèle « ${model ?? "?"} » est momentanément indisponible côté provider. Réessaie ou change de modèle.`
    );
  }
  if (status === 402 || /402|payment|credits/i.test(raw)) {
    return new Error(
      "Crédits Hugging Face insuffisants pour ce modèle. Utilise un modèle plus léger ou vérifie ton compte HF."
    );
  }
  return new Error(`Erreur Hugging Face : ${raw.slice(0, 300)}`);
}

// ---------------------------------------------------------------
// Moteur Hugging Face (Inference Providers) — streaming réel
// ---------------------------------------------------------------

async function callHf(opts: LlmCallOptions): Promise<LlmResult> {
  if (!opts.token) {
    throw new Error("Aucun token Hugging Face configuré. Ajoute-le dans les réglages.");
  }
  const client = new InferenceClient(opts.token);

  let buffer = "";
  let emitted = 0;

  const maybeEmit = () => {
    if (looksLikeToolCallStart(buffer)) return; // potentiel appel d'outil : on retient
    // émet tout en gardant une marge de 10 caractères (fence ```json en cours de frappe)
    const safeEnd = Math.max(0, buffer.length - 10);
    if (safeEnd > emitted) {
      opts.onText(buffer.slice(emitted, safeEnd));
      emitted = safeEnd;
    }
  };

  let stream: AsyncIterable<{ choices?: Array<{ delta?: { content?: string } }> }>;
  try {
    stream = await client.chatCompletionStream({
      model: opts.model,
      messages: opts.messages as never,
      temperature: opts.temperature,
      max_tokens: opts.maxTokens ?? 2048,
      provider: "auto",
    });
  } catch (e) {
    throw mapHfError(e, opts.model);
  }

  try {
    for await (const chunk of stream) {
      if (opts.signal?.aborted) break;
      const delta = chunk.choices?.[0]?.delta?.content;
      if (delta) {
        buffer += delta;
        maybeEmit();
      }
    }
  } catch (e) {
    throw mapHfError(e, opts.model);
  }

  const toolCall = extractToolCall(buffer);
  if (toolCall) {
    return { text: buffer, toolCall };
  }
  if (emitted < buffer.length) {
    opts.onText(buffer.slice(emitted));
  }
  return { text: buffer, toolCall: null };
}

// ---------------------------------------------------------------
// Moteur démo (z-ai-web-dev-sdk, backend uniquement)
// ---------------------------------------------------------------

const sleep = (ms: number) => new Promise((r) => setTimeout(r, ms));

async function callDemo(opts: LlmCallOptions): Promise<LlmResult> {
  let zai: Awaited<ReturnType<typeof ZAI.create>>;
  try {
    zai = await ZAI.create();
  } catch {
    throw new Error("Impossible d'initialiser le moteur Stark. Réessaie plus tard.");
  }

  // Le SDK z-ai attend le prompt système avec le rôle "assistant"
  const messages = opts.messages.map((m, i) =>
    i === 0 && m.role === "system" ? { role: "assistant" as const, content: m.content } : m
  );

  // Modèle GLM sélectionné (ex : glm-4.6) — sinon modèle par défaut du SDK
  const request: Record<string, unknown> = {
    messages,
    thinking: { type: "disabled" },
  };
  if (/^glm-[\d]/i.test(opts.model)) {
    request.model = opts.model;
  }

  let text = "";
  try {
    const completion = await zai.chat.completions.create(
      request as Parameters<typeof zai.chat.completions.create>[0]
    );
    text = completion.choices?.[0]?.message?.content ?? "";
  } catch (e) {
    throw new Error(
      `Erreur du moteur Stark : ${e instanceof Error ? e.message.slice(0, 300) : String(e)}`
    );
  }

  if (!text.trim()) {
    throw new Error("Le moteur Stark a renvoyé une réponse vide. Réessaie.");
  }

  const toolCall = extractToolCall(text);
  if (toolCall) {
    return { text, toolCall };
  }

  // Simule le streaming pour une UX homogène
  const clean = text;
  let i = 0;
  while (i < clean.length) {
    if (opts.signal?.aborted) break;
    const size = 3 + Math.floor(Math.random() * 5); // ~3-7 caractères
    const piece = clean.slice(i, i + size);
    opts.onText(piece);
    i += size;
    if (i % 60 < size) await sleep(12);
  }
  return { text: clean, toolCall: null };
}

// ---------------------------------------------------------------

export function callLlm(opts: LlmCallOptions): Promise<LlmResult> {
  return opts.engine === "hf" ? callHf(opts) : callDemo(opts);
}
