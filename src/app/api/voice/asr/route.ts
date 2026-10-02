import { NextRequest, NextResponse } from "next/server";
import ZAI from "z-ai-web-dev-sdk";

export const runtime = "nodejs";
export const maxDuration = 120;

const MAX_AUDIO_BYTES = 20 * 1024 * 1024; // 20 Mo

export async function POST(req: NextRequest) {
  try {
    const body = (await req.json()) as { audio?: string };
    const audio = typeof body.audio === "string" ? body.audio.trim() : "";

    if (!audio) {
      return NextResponse.json({ error: "Aucun audio fourni" }, { status: 400 });
    }

    // base64 attendu (avec ou sans préfixe data:)
    const b64 = audio.includes(",") && audio.startsWith("data:") ? audio.split(",")[1] : audio;
    if (!/^[A-Za-z0-9+/]+={0,2}$/.test(b64)) {
      return NextResponse.json({ error: "Audio base64 invalide" }, { status: 400 });
    }

    const buffer = Buffer.from(b64, "base64");
    if (buffer.length === 0) {
      return NextResponse.json({ error: "Audio vide" }, { status: 400 });
    }
    if (buffer.length > MAX_AUDIO_BYTES) {
      return NextResponse.json({ error: "Enregistrement trop long (20 Mo max)" }, { status: 413 });
    }

    const zai = await ZAI.create();
    const response = await zai.audio.asr.create({
      file_base64: buffer.toString("base64"),
    });

    const text = (response?.text ?? "").trim();
    if (!text) {
      return NextResponse.json(
        { error: "Aucune parole détectée dans l'enregistrement" },
        { status: 422 }
      );
    }

    return NextResponse.json({ text });
  } catch (e) {
    const message = e instanceof Error ? e.message : "Erreur inattendue de reconnaissance vocale";
    console.error("[asr]", message);
    return NextResponse.json({ error: message }, { status: 500 });
  }
}
