import { db } from "@/lib/db";
import { revealSecret } from "@/lib/server/secrets";
import {
  DEFAULT_MODEL,
  DEFAULT_VOICE,
  DEFAULT_VOICE_ENGINE,
  TTS_VOICES,
  type EngineMode,
  type PublicSettings,
  type VoiceEngine,
} from "@/lib/types";

const SINGLETON = "singleton";

export async function getSettingsRow() {
  let row = await db.settings.findUnique({ where: { id: SINGLETON } });
  if (!row) {
    row = await db.settings.create({ data: { id: SINGLETON } });
  }
  return { ...row, hfToken: revealSecret(row.hfToken) };
}

function maskToken(token: string): string {
  if (token.length <= 10) return `${token.slice(0, 3)}…`;
  return `${token.slice(0, 6)}…${token.slice(-4)}`;
}

const VALID_VOICES = new Set(TTS_VOICES.map((v) => v.name));

export function toPublicSettings(row: {
  hfToken: string | null;
  model: string;
  customModel: string | null;
  engine: string;
  temperature: number;
  maxSteps: number;
  systemPrompt: string | null;
  voiceEnabled: boolean;
  voiceName: string;
  voiceSpeed: number;
  voiceEngine: string | null;
  browserVoiceUri: string | null;
}): PublicSettings {
  const hfToken = revealSecret(row.hfToken);
  return {
    hasToken: !!hfToken,
    tokenPreview: hfToken ? maskToken(hfToken) : null,
    model: row.model || DEFAULT_MODEL,
    customModel: row.customModel,
    engine: (row.engine as EngineMode) || "auto",
    temperature: row.temperature ?? 0.7,
    maxSteps: row.maxSteps ?? 6,
    systemPrompt: row.systemPrompt,
    voiceEnabled: !!row.voiceEnabled,
    voiceName: VALID_VOICES.has(row.voiceName) ? row.voiceName : DEFAULT_VOICE,
    voiceSpeed: typeof row.voiceSpeed === "number" ? Math.min(Math.max(row.voiceSpeed, 0.5), 2) : 1,
    voiceEngine:
      row.voiceEngine === "stark" || row.voiceEngine === "browser"
        ? (row.voiceEngine as VoiceEngine)
        : DEFAULT_VOICE_ENGINE,
    browserVoiceUri: row.browserVoiceUri ?? null,
  };
}
