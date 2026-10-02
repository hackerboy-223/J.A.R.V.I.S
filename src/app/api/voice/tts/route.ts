import { NextRequest, NextResponse } from "next/server";
import ZAI from "z-ai-web-dev-sdk";
import { TTS_VOICES } from "@/lib/types";

export const runtime = "nodejs";
export const maxDuration = 120;

const MAX_INPUT_CHARS = 4000; // texte brut total accepté
const MAX_CHUNK_CHARS = 900; // limite TTS : 1024, marge de sécurité
const MAX_CHUNKS = 5;

const ALLOWED_VOICES = new Set(TTS_VOICES.map((v) => v.name));

/** Découpe un texte nettoyé en segments de phrases ≤ maxLen */
function splitIntoChunks(text: string, maxLen = MAX_CHUNK_CHARS): string[] {
  const sentences = text.match(/[^.!?…:;]+[.!?…:;]*\s*/g) ?? [text];
  const chunks: string[] = [];
  let current = "";
  for (const sentence of sentences) {
    const s = sentence.trim();
    if (!s) continue;
    if (s.length > maxLen) {
      // phrase anormalement longue : coupe par mots
      if (current) {
        chunks.push(current.trim());
        current = "";
      }
      const words = s.split(/\s+/);
      let line = "";
      for (const w of words) {
        if ((line + " " + w).trim().length > maxLen) {
          chunks.push(line.trim());
          line = w;
        } else {
          line = (line + " " + w).trim();
        }
      }
      if (line) current = line;
      continue;
    }
    if ((current + " " + s).trim().length <= maxLen) {
      current = (current + " " + s).trim();
    } else {
      if (current) chunks.push(current.trim());
      current = s;
    }
  }
  if (current.trim()) chunks.push(current.trim());
  return chunks;
}

/** Transforme du Markdown en texte parlé naturel */
function speechClean(markdown: string): string {
  let t = markdown;
  // retire les blocs de code (garder un commentaire court)
  t = t.replace(/```[\s\S]*?```/g, " (extrait de code) ");
  t = t.replace(/`([^`]+)`/g, "$1");
  // images et liens → texte visible
  t = t.replace(/!\[([^\]]*)\]\([^)]*\)/g, "$1");
  t = t.replace(/\[([^\]]+)\]\([^)]*\)/g, "$1");
  // tableaux : séparateur retiré, lignes → phrases
  t = t.replace(/^\|[-| :]+\|$/gm, "");
  t = t.replace(/^\|(.+)\|$/gm, (_m, row: string) =>
    row
      .split("|")
      .map((c: string) => c.trim())
      .filter(Boolean)
      .join(", ")
  );
  // embellissements markdown
  t = t.replace(/^#{1,6}\s*/gm, "");
  t = t.replace(/\*\*([^*]+)\*\*/g, "$1");
  t = t.replace(/\*([^*]+)\*/g, "$1");
  t = t.replace(/^>\s*/gm, "");
  t = t.replace(/^[-*+]\s+/gm, "");
  t = t.replace(/^\d+\.\s+/gm, "");
  // caractères parasites pour la voix
  t = t.replace(/[_~|]/g, " ");
  t = t.replace(/\s{2,}/g, " ");
  return t.trim();
}

export async function POST(req: NextRequest) {
  try {
    const body = (await req.json()) as {
      text?: string;
      voice?: string;
      speed?: number;
    };

    const rawText = typeof body.text === "string" ? body.text.trim() : "";
    if (!rawText) {
      return NextResponse.json({ error: "Texte vide" }, { status: 400 });
    }
    if (rawText.length > MAX_INPUT_CHARS) {
      return NextResponse.json(
        { error: `Texte trop long (${MAX_INPUT_CHARS} caractères max)` },
        { status: 400 }
      );
    }

    const voice =
      typeof body.voice === "string" && ALLOWED_VOICES.has(body.voice) ? body.voice : "jam";
    const speed =
      typeof body.speed === "number" && body.speed >= 0.5 && body.speed <= 2.0 ? body.speed : 1.0;

    const clean = speechClean(rawText);
    if (!clean) {
      return NextResponse.json({ error: "Rien à synthétiser" }, { status: 400 });
    }

    let chunks = splitIntoChunks(clean);
    if (chunks.length > MAX_CHUNKS) {
      chunks = chunks
        .slice(0, MAX_CHUNKS - 1)
        .concat([chunks.slice(MAX_CHUNKS - 1).join(" ").slice(0, MAX_CHUNK_CHARS)]);
    }

    const zai = await ZAI.create();

    const audioChunks: string[] = [];
    for (const chunk of chunks) {
      try {
        const response = await zai.audio.tts.create({
          input: chunk,
          voice: voice as "jam",
          speed,
          response_format: "wav",
          stream: false,
        });
        const arrayBuffer = await response.arrayBuffer();
        const buffer = Buffer.from(new Uint8Array(arrayBuffer));
        if (buffer.length === 0) throw new Error("Audio vide");
        audioChunks.push(buffer.toString("base64"));
      } catch (e) {
        const message = e instanceof Error ? e.message : String(e);
        console.error("[tts] chunk échoué:", message);
        if (audioChunks.length === 0) {
          return NextResponse.json(
            { error: `Synthèse vocale impossible : ${message.slice(0, 200)}` },
            { status: 500 }
          );
        }
        break; // on joue ce qu'on a déjà
      }
    }

    return NextResponse.json({ chunks: audioChunks, voice, speed });
  } catch (e) {
    const message = e instanceof Error ? e.message : "Erreur inattendue de synthèse vocale";
    console.error("[tts]", message);
    return NextResponse.json({ error: message }, { status: 500 });
  }
}
