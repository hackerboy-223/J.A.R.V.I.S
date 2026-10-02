import { NextRequest, NextResponse } from "next/server";
import { db } from "@/lib/db";
import type { ConversationDetail } from "@/lib/types";

export const runtime = "nodejs";

type Params = { params: Promise<{ id: string }> };

export async function GET(_req: NextRequest, { params }: Params) {
  try {
    const { id } = await params;
    const conv = await db.conversation.findUnique({
      where: { id },
      include: { messages: { orderBy: { createdAt: "asc" } } },
    });
    if (!conv) {
      return NextResponse.json({ error: "Conversation introuvable" }, { status: 404 });
    }
    const detail: ConversationDetail = {
      id: conv.id,
      title: conv.title,
      model: conv.model,
      engine: conv.engine,
      createdAt: conv.createdAt.toISOString(),
      updatedAt: conv.updatedAt.toISOString(),
      messages: conv.messages.map((m) => ({
        id: m.id,
        role: m.role as "user" | "assistant" | "tool",
        content: m.content,
        toolName: m.toolName ?? undefined,
        toolArgs: m.toolArgs ?? undefined,
        toolResult: m.toolResult ?? undefined,
        step: m.step,
        durationMs: m.durationMs ?? undefined,
        createdAt: m.createdAt.toISOString(),
      })),
    };
    return NextResponse.json(detail);
  } catch (e) {
    console.error("[conversation:GET]", e);
    return NextResponse.json({ error: "Erreur serveur" }, { status: 500 });
  }
}

export async function PATCH(req: NextRequest, { params }: Params) {
  try {
    const { id } = await params;
    const body = (await req.json()) as { title?: string };
    const title = typeof body.title === "string" ? body.title.trim().slice(0, 80) : "";
    if (!title) {
      return NextResponse.json({ error: "Titre invalide" }, { status: 400 });
    }
    const conv = await db.conversation.update({ where: { id }, data: { title } });
    return NextResponse.json({ id: conv.id, title: conv.title });
  } catch (e) {
    console.error("[conversation:PATCH]", e);
    return NextResponse.json({ error: "Échec du renommage" }, { status: 500 });
  }
}

export async function DELETE(_req: NextRequest, { params }: Params) {
  try {
    const { id } = await params;
    await db.conversation.delete({ where: { id } });
    return NextResponse.json({ ok: true });
  } catch (e) {
    console.error("[conversation:DELETE]", e);
    return NextResponse.json({ error: "Échec de la suppression" }, { status: 500 });
  }
}
