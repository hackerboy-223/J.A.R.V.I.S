import { NextRequest, NextResponse } from "next/server";
import { db } from "@/lib/db";
import type { ConversationSummary } from "@/lib/types";
import { requireAuthorized } from "@/lib/server/auth";

export const runtime = "nodejs";

export async function GET(req: NextRequest) {
  const denied = requireAuthorized(req);
  if (denied) return denied;
  try {
    const rows = await db.conversation.findMany({
      orderBy: { updatedAt: "desc" },
      take: 100,
      include: { _count: { select: { messages: true } } },
    });
    const conversations: ConversationSummary[] = rows.map((c) => ({
      id: c.id,
      title: c.title,
      model: c.model,
      engine: c.engine,
      createdAt: c.createdAt.toISOString(),
      updatedAt: c.updatedAt.toISOString(),
      messageCount: c._count.messages,
    }));
    return NextResponse.json({ conversations });
  } catch (e) {
    console.error("[conversations:GET]", e);
    return NextResponse.json({ error: "Impossible de lister les conversations" }, { status: 500 });
  }
}
