import { NextRequest, NextResponse } from "next/server";
import { db } from "@/lib/db";
import { getSettingsRow, toPublicSettings } from "@/lib/server/settings";
import { TTS_VOICES } from "@/lib/types";
import { requireAuthorized } from "@/lib/server/auth";
import { enforceRateLimit } from "@/lib/server/rate-limit";
import { protectSecret } from "@/lib/server/secrets";

export const runtime = "nodejs";

const MAX_VOICE_URI = 200;

export async function GET(req: NextRequest) {
  const denied = requireAuthorized(req);
  if (denied) return denied;
  try {
    const row = await getSettingsRow();
    return NextResponse.json(toPublicSettings(row));
  } catch (e) {
    console.error("[settings:GET]", e);
    return NextResponse.json({ error: "Impossible de lire les réglages" }, { status: 500 });
  }
}

export async function PUT(req: NextRequest) {
  const denied = requireAuthorized(req);
  if (denied) return denied;
  const limited = enforceRateLimit(req, { name: "settings-write", limit: 20, windowMs: 60_000 });
  if (limited) return limited;
  try {
    const body = (await req.json()) as Record<string, unknown>;
    await getSettingsRow();

    const data: Record<string, unknown> = {};

    if ("hfToken" in body) {
      const t = body.hfToken;
      if (t === null || t === "") {
        data.hfToken = null;
      } else if (typeof t === "string") {
        const token = t.trim();
        if (token && !/^hf_[A-Za-z0-9]{8,}$/.test(token) && !/^[A-Za-z0-9_-]{20,}$/.test(token)) {
          return NextResponse.json(
            { error: "Format de token invalide (attendu : hf_xxx…)" },
            { status: 400 }
          );
        }
        if (token) data.hfToken = protectSecret(token);
      }
    }

    if (typeof body.model === "string" && body.model) {
      data.model = body.model.slice(0, 120);
    }
    if ("customModel" in body) {
      data.customModel =
        typeof body.customModel === "string" && body.customModel.trim()
          ? body.customModel.trim().slice(0, 120)
          : null;
    }
    if (typeof body.engine === "string" && ["auto", "hf", "demo"].includes(body.engine)) {
      data.engine = body.engine;
    }
    if (typeof body.temperature === "number" && Number.isFinite(body.temperature)) {
      data.temperature = Math.min(Math.max(body.temperature, 0), 2);
    }
    if (typeof body.maxSteps === "number" && Number.isFinite(body.maxSteps)) {
      data.maxSteps = Math.min(Math.max(Math.round(body.maxSteps), 1), 10);
    }
    if ("systemPrompt" in body) {
      data.systemPrompt =
        typeof body.systemPrompt === "string" && body.systemPrompt.trim()
          ? body.systemPrompt.trim().slice(0, 4000)
          : null;
    }
    if (typeof body.voiceEnabled === "boolean") {
      data.voiceEnabled = body.voiceEnabled;
    }
    if (typeof body.voiceName === "string" && TTS_VOICES.some((v) => v.name === body.voiceName)) {
      data.voiceName = body.voiceName;
    }
    if (typeof body.voiceSpeed === "number" && Number.isFinite(body.voiceSpeed)) {
      data.voiceSpeed = Math.min(Math.max(body.voiceSpeed, 0.5), 2);
    }
    if (typeof body.voiceEngine === "string" && ["stark", "browser"].includes(body.voiceEngine)) {
      data.voiceEngine = body.voiceEngine;
    }
    if ("browserVoiceUri" in body) {
      data.browserVoiceUri =
        typeof body.browserVoiceUri === "string" && body.browserVoiceUri.trim()
          ? body.browserVoiceUri.trim().slice(0, MAX_VOICE_URI)
          : null;
    }

    if (Object.keys(data).length === 0) {
      return NextResponse.json({ error: "Aucun champ valide fourni" }, { status: 400 });
    }

    const row = await db.settings.update({ where: { id: "singleton" }, data });
    return NextResponse.json(toPublicSettings(row));
  } catch (e) {
    console.error("[settings:PUT]", e);
    return NextResponse.json({ error: "Échec de l'enregistrement des réglages" }, { status: 500 });
  }
}
