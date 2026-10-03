import { NextRequest, NextResponse } from "next/server";
import { executeTool } from "@/lib/agent/tools";
import { requireAuthorized } from "@/lib/server/auth";
import { enforceRateLimit } from "@/lib/server/rate-limit";

export const runtime = "nodejs";

const ALLOWED_APPS = new Set(["calculator", "notepad", "explorer"]);
const ALLOWED_FOLDERS = new Set(["desktop", "documents", "downloads", "project"]);

export async function POST(req: NextRequest) {
  const denied = requireAuthorized(req);
  if (denied) return denied;

  const limited = enforceRateLimit(req, {
    name: "pc-action",
    limit: 24,
    windowMs: 60_000,
  });
  if (limited) return limited;

  let body: Record<string, unknown>;
  try {
    body = (await req.json()) as Record<string, unknown>;
  } catch {
    return NextResponse.json({ error: "Requête invalide" }, { status: 400 });
  }

  const action = typeof body.action === "string" ? body.action : "";
  const target = typeof body.target === "string" ? body.target.trim() : "";

  const valid =
    (action === "open_app" && ALLOWED_APPS.has(target)) ||
    (action === "open_folder" && ALLOWED_FOLDERS.has(target));

  if (!valid) {
    return NextResponse.json(
      { error: "Action refusée : seules les applications et dossiers explicitement autorisés sont acceptés." },
      { status: 400 }
    );
  }

  const outcome = await executeTool("pc_control", { action, target });
  if (!outcome.ok) {
    return NextResponse.json({ error: outcome.error }, { status: 403 });
  }

  return NextResponse.json({ ok: true, result: outcome.data });
}
