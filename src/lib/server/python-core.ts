import { db } from "@/lib/db";
import type { ChatSseEvent } from "@/lib/types";

const CORE_URL = process.env.JARVIS_CORE_URL?.trim().replace(/\/$/, "") ?? "";
const CORE_TOKEN = process.env.JARVIS_CORE_TOKEN?.trim() ?? "";

function validatedCoreUrl(): string {
  if (!CORE_URL) {
    throw new Error("JARVIS_CORE_URL n'est pas configuré");
  }

  let parsed: URL;
  try {
    parsed = new URL(CORE_URL);
  } catch {
    throw new Error("JARVIS_CORE_URL est invalide");
  }

  if (parsed.username || parsed.password) {
    throw new Error("Les credentials intégrés dans JARVIS_CORE_URL sont interdits");
  }

  const host = parsed.hostname.toLowerCase();
  const loopback =
    host === "localhost" ||
    host === "127.0.0.1" ||
    host === "::1" ||
    host === "[::1]";

  if (parsed.protocol !== "https:" && !(parsed.protocol === "http:" && loopback)) {
    throw new Error(
      "Le Python Core distant doit utiliser HTTPS; HTTP est réservé à localhost"
    );
  }

  return parsed.toString().replace(/\/$/, "");
}

function makeTitle(content: string): string {
  const firstLine = content
    .split("\n")
    .map((line) => line.trim())
    .find(Boolean) ?? "Nouvelle conversation";
  const cleaned = firstLine.replace(/[#*\`>_\[\]]/g, "").replace(/\s+/g, " ").trim();
  return cleaned.length > 48 ? `${cleaned.slice(0, 48).trimEnd()}…` : cleaned;
}

export function pythonCoreEnabled(): boolean {
  return CORE_URL.length > 0;
}

export async function proxyPythonCoreChat(
  req: Request,
  input: {
    conversationId: string | null;
    content: string;
    voiceMode: boolean;
  },
): Promise<Response> {
  let conv = input.conversationId
    ? await db.conversation.findUnique({ where: { id: input.conversationId } })
    : null;

  if (!conv) {
    conv = await db.conversation.create({
      data: {
        title: makeTitle(input.content),
        model: "jarvis",
        engine: "python-core",
      },
    });
  }

  const userMessage = await db.message.create({
    data: {
      role: "user",
      content: input.content,
      conversationId: conv.id,
    },
  });

  const history = (
    await db.message.findMany({
      where: { conversationId: conv.id },
      orderBy: { createdAt: "desc" },
      take: 32,
    })
  ).reverse();

  const messages = history
    .filter((message) => message.role === "user" || message.role === "assistant")
    .map((message) => ({
      role: message.role,
      content: message.content,
    }));

  const headers: Record<string, string> = {
    "Content-Type": "application/json",
  };
  if (CORE_TOKEN) headers.Authorization = `Bearer ${CORE_TOKEN}`;

  let coreUrl: string;
  try {
    coreUrl = validatedCoreUrl();
  } catch (error) {
    const message =
      error instanceof Error ? error.message : "Configuration Python Core invalide";
    return Response.json({ error: message }, { status: 502 });
  }

  const upstream = await fetch(`${coreUrl}/v1/chat/completions`, {
    method: "POST",
    headers,
    body: JSON.stringify({
      model: "jarvis",
      stream: true,
      messages,
      metadata: {
        mode: "standard",
        operator_id: `web:${conv.id}`,
        voice_mode: input.voiceMode,
      },
    }),
    signal: req.signal,
    cache: "no-store",
  });

  if (!upstream.ok || !upstream.body) {
    const detail = await upstream.text().catch(() => "");
    return Response.json(
      {
        error: `Python Core indisponible (${upstream.status})${detail ? `: ${detail.slice(0, 300)}` : ""}`,
      },
      { status: 502 },
    );
  }

  const encoder = new TextEncoder();
  const decoder = new TextDecoder();
  const upstreamReader = upstream.body.getReader();
  const conversationId = conv.id;
  const title = conv.title || makeTitle(input.content);

  const stream = new ReadableStream<Uint8Array>({
    async start(controller) {
      let closed = false;
      let buffer = "";
      let assistantText = "";

      const send = (event: ChatSseEvent) => {
        if (closed || req.signal.aborted) return;
        try {
          controller.enqueue(encoder.encode(`data: ${JSON.stringify(event)}\n\n`));
        } catch {
          closed = true;
        }
      };

      send({
        type: "start",
        conversationId,
        userMessageId: userMessage.id,
        engine: "python-core",
        model: "jarvis",
      });

      const consumeData = (raw: string) => {
        if (!raw || raw === "[DONE]") return;
        try {
          const payload = JSON.parse(raw) as {
            choices?: Array<{
              delta?: { content?: string };
              finish_reason?: string | null;
            }>;
            jarvis?: { event?: string; message?: string };
          };

          if (payload.jarvis?.event === "progress" && payload.jarvis.message) {
            send({ type: "status", step: 1, status: payload.jarvis.message });
          }

          const delta = payload.choices?.[0]?.delta?.content;
          if (delta) {
            assistantText += delta;
            send({ type: "token", text: delta });
          }
        } catch {
          // Ignore malformed upstream SSE frames rather than killing the conversation.
        }
      };

      try {
        while (!req.signal.aborted) {
          const { value, done } = await upstreamReader.read();
          if (done) break;
          buffer += decoder.decode(value, { stream: true });

          let boundary = buffer.indexOf("\n\n");
          while (boundary >= 0) {
            const frame = buffer.slice(0, boundary);
            buffer = buffer.slice(boundary + 2);
            for (const line of frame.split("\n")) {
              if (line.startsWith("data:")) {
                consumeData(line.slice(5).trim());
              }
            }
            boundary = buffer.indexOf("\n\n");
          }
        }

        if (!req.signal.aborted) {
          const assistant = await db.message.create({
            data: {
              role: "assistant",
              content: assistantText,
              conversationId,
            },
          });
          await db.conversation.update({
            where: { id: conversationId },
            data: {
              title,
              model: "jarvis",
              engine: "python-core",
              updatedAt: new Date(),
            },
          });
          send({ type: "done", messageId: assistant.id, title });
        }
      } catch (error) {
        const message = error instanceof Error ? error.message : "Erreur Python Core";
        send({ type: "error", message });
      } finally {
        try {
          await upstreamReader.cancel();
        } catch {
          // already closed
        }
        try {
          controller.close();
        } catch {
          // already closed
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
      "X-JARVIS-Core": "python",
    },
  });
}
