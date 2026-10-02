import { NextRequest } from "next/server";
import { db } from "@/lib/db";
import { getSettingsRow } from "@/lib/server/settings";
import { buildSystemPrompt } from "@/lib/agent/prompt";
import { callLlm, type LlmMessage } from "@/lib/agent/engines";
import { executeTool } from "@/lib/agent/tools";
import { isValidToolCall } from "@/lib/agent/parse";
import { resolveModel, isStarkModel, MAX_CONTEXT_MESSAGES, type ActiveEngine, type ChatSseEvent } from "@/lib/types";
import { requireAuthorized } from "@/lib/server/auth";
import { enforceRateLimit } from "@/lib/server/rate-limit";

export const runtime = "nodejs";
export const maxDuration = 300;

const MAX_USER_CHARS = 32000;
const MAX_TOOL_STORE = 20000;
const MAX_TOOL_CONTEXT = 6000;

function makeTitle(content: string): string {
  const firstLine = content
    .split("\n")
    .map((l) => l.trim())
    .find((l) => l.length > 0) ?? "Nouvelle conversation";
  const cleaned = firstLine.replace(/[#*`>_\[\]]/g, "").replace(/\s+/g, " ").trim();
  return cleaned.length > 48 ? `${cleaned.slice(0, 48).trimEnd()}…` : cleaned || "Nouvelle conversation";
}

function truncate(s: string, max: number): string {
  return s.length > max ? `${s.slice(0, max)}…[tronqué]` : s;
}

function toolContextMessage(toolName: string, resultJson: string, isError: boolean): string {
  const truncated = truncate(resultJson, MAX_TOOL_CONTEXT);
  return isError
    ? `TOOL_ERROR (${toolName}): ${truncated}\nYou may retry with corrected arguments or answer without the tool.`
    : `TOOL_RESULT (${toolName}): ${truncated}`;
}

export async function POST(req: NextRequest) {
  const denied = requireAuthorized(req);
  if (denied) return denied;
  const limited = enforceRateLimit(req, { name: "chat", limit: 20, windowMs: 60_000 });
  if (limited) return limited;

  let conversationId: string | null = null;
  let content = "";
  let voiceMode = false;
  try {
    const body = (await req.json()) as { conversationId?: string; content?: string; voiceMode?: boolean };
    conversationId = typeof body.conversationId === "string" ? body.conversationId : null;
    content = typeof body.content === "string" ? body.content.trim() : "";
    voiceMode = body.voiceMode === true;
  } catch {
    return Response.json({ error: "Requête invalide" }, { status: 400 });
  }

  if (!content) {
    return Response.json({ error: "Le message est vide" }, { status: 400 });
  }
  if (content.length > MAX_USER_CHARS) {
    return Response.json({ error: "Message trop long (32 000 caractères max)" }, { status: 400 });
  }

  // Réglages + résolution du moteur
  const settings = await getSettingsRow();
  const model = resolveModel(settings.model, settings.customModel);
  const engineMode = settings.engine;
  const stark = isStarkModel(model); // modèle GLM → moteur Stark intégré, sans token
  let engine: ActiveEngine;
  if (stark) {
    engine = "demo";
  } else if (engineMode === "demo") {
    engine = "demo";
  } else if (engineMode === "hf") {
    if (!settings.hfToken) {
      return Response.json(
        {
          error:
            "Le moteur est réglé sur « Hugging Face » mais aucun token n'est configuré. Ajoute ton token dans les réglages, ou choisis un modèle GLM intégré (sans token).",
        },
        { status: 400 }
      );
    }
    engine = "hf";
  } else {
    engine = settings.hfToken ? "hf" : "demo";
  }

  // Conversation (existante ou nouvelle)
  let conv = conversationId
    ? await db.conversation.findUnique({ where: { id: conversationId } })
    : null;
  if (!conv) {
    conv = await db.conversation.create({
      data: { title: makeTitle(content), model, engine },
    });
  }

  // Message utilisateur
  const userMsg = await db.message.create({
    data: { role: "user", content, conversationId: conv.id },
  });

  // Contexte LLM : system + historique récent
  const history = (
    await db.message.findMany({
      where: { conversationId: conv.id },
      orderBy: { createdAt: "desc" },
      take: MAX_CONTEXT_MESSAGES,
    })
  ).reverse();

  const llmMessages: LlmMessage[] = [
    { role: "system", content: buildSystemPrompt({ maxSteps: settings.maxSteps, customPrompt: settings.systemPrompt, voiceMode }) },
  ];
  for (const m of history) {
    if (m.role === "user") {
      llmMessages.push({ role: "user", content: truncate(m.content, 12000) });
    } else if (m.role === "assistant" && m.content.trim()) {
      llmMessages.push({ role: "assistant", content: truncate(m.content, 8000) });
    } else if (m.role === "tool" && m.toolName) {
      llmMessages.push({
        role: "user",
        content: toolContextMessage(m.toolName, m.toolResult ?? "null", false),
      });
    }
  }

  // ----- Flux SSE -----
  const encoder = new TextEncoder();
  const stream = new ReadableStream<Uint8Array>({
    async start(controller) {
      let closed = false;
      const send = (ev: ChatSseEvent) => {
        if (closed || req.signal.aborted) return;
        try {
          controller.enqueue(encoder.encode(`data: ${JSON.stringify(ev)}\n\n`));
        } catch {
          closed = true;
        }
      };

      try {
        send({
          type: "start",
          conversationId: conv!.id,
          userMessageId: userMsg.id,
          engine,
          model,
        });

        const maxSteps = Math.min(Math.max(settings.maxSteps, 1), 10);
        let finalText: string | null = null;

        for (let step = 1; step <= maxSteps; step++) {
          if (req.signal.aborted) break;

          send({ type: "status", step, status: step === 1 ? "Réflexion…" : "Poursuite de l'analyse…" });

          const result = await callLlm({
            engine,
            token: settings.hfToken ?? undefined,
            model,
            messages: llmMessages,
            temperature: settings.temperature,
            maxTokens: 2048,
            signal: req.signal,
            onText: (delta) => send({ type: "token", text: delta }),
          });

          if (req.signal.aborted && !result.text) break;

          const tc = result.toolCall;
          if (tc && isValidToolCall(tc)) {
            // ---- Appel d'outil ----
            send({ type: "tool_start", step, tool: tc.tool, args: tc.args });
            const t0 = Date.now();
            const outcome = await executeTool(tc.tool, tc.args, { signal: req.signal });
            const durationMs = Date.now() - t0;
            const resultJson = outcome.ok
              ? JSON.stringify(outcome.data)
              : JSON.stringify({ error: outcome.error });

            // persistance
            await db.message.create({
              data: {
                role: "tool",
                content: "",
                toolName: tc.tool,
                toolArgs: JSON.stringify(tc.args),
                toolResult: truncate(resultJson, MAX_TOOL_STORE),
                step,
                durationMs,
                conversationId: conv!.id,
              },
            });

            send({
              type: "tool_result",
              step,
              tool: tc.tool,
              result: outcome.ok ? outcome.data : { error: outcome.error },
              durationMs,
              isError: !outcome.ok,
            });

            llmMessages.push({
              role: "assistant",
              content: JSON.stringify({ tool: tc.tool, args: tc.args }),
            });
            llmMessages.push({
              role: "user",
              content: toolContextMessage(tc.tool, resultJson, !outcome.ok),
            });
            continue;
          }

          if (tc && !isValidToolCall(tc)) {
            // Outil inconnu : on informe le modèle
            llmMessages.push({ role: "assistant", content: result.text });
            llmMessages.push({
              role: "user",
              content: `Error: unknown tool "${tc.tool}". Available tools: web_search, read_page, calculator, run_js, get_datetime, system_status, hud_action. Answer directly or use a valid tool.`,
            });
            continue;
          }

          // ---- Réponse finale ----
          finalText = result.text.trim();
          break;
        }

        // Étapes épuisées sans réponse finale : forcer une réponse
        if (finalText === null && !req.signal.aborted) {
          llmMessages.push({
            role: "user",
            content:
              "You have reached the maximum number of tool steps. Give your final answer NOW, in the user's language, without calling any tool.",
          });
          const forced = await callLlm({
            engine,
            token: settings.hfToken ?? undefined,
            model,
            messages: llmMessages,
            temperature: settings.temperature,
            maxTokens: 2048,
            signal: req.signal,
            onText: (delta) => send({ type: "token", text: delta }),
          });
          finalText = forced.toolCall
            ? "Je n'ai pas réussi à terminer dans la limite d'étapes d'outils. Réessaie avec une demande plus simple."
            : forced.text.trim();
        }

        if (req.signal.aborted) {
          send({ type: "done", messageId: "", title: conv!.title });
          return;
        }

        const assistantMsg = await db.message.create({
          data: {
            role: "assistant",
            content: finalText ?? "",
            conversationId: conv!.id,
          },
        });

        const title = conv!.title || makeTitle(content);
        await db.conversation.update({
          where: { id: conv!.id },
          data: { title, model, engine, updatedAt: new Date() },
        });

        send({ type: "done", messageId: assistantMsg.id, title });
      } catch (e) {
        console.error("[chat]", e);
        const message = e instanceof Error ? e.message : "Erreur inattendue de l'agent";
        send({ type: "error", message });
      } finally {
        try {
          controller.close();
        } catch {
          /* déjà fermé */
        }
      }
    },
  });

  return new Response(stream, {
    headers: {
      "Content-Type": "text/event-stream; charset=utf-8",
      "Cache-Control": "no-cache, no-transform",
      Connection: "keep-alive",
      "X-Accel-Buffering": "no",
    },
  });
}
