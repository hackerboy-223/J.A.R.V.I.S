import {
  createCipheriv,
  createDecipheriv,
  createHash,
  randomBytes,
} from "node:crypto";

const PREFIX = "enc:v1:";

function encryptionKey(): Buffer | null {
  const raw = process.env.JARVIS_ENCRYPTION_KEY?.trim();
  if (!raw) return null;
  return createHash("sha256").update(raw).digest();
}

export function protectSecret(value: string | null | undefined): string | null {
  if (!value) return null;
  if (value.startsWith(PREFIX)) return value;

  const key = encryptionKey();
  if (!key) {
    if (process.env.NODE_ENV === "production") {
      throw new Error(
        "JARVIS_ENCRYPTION_KEY est requis en production pour stocker un secret."
      );
    }
    return value;
  }

  const iv = randomBytes(12);
  const cipher = createCipheriv("aes-256-gcm", key, iv);
  const encrypted = Buffer.concat([cipher.update(value, "utf8"), cipher.final()]);
  const tag = cipher.getAuthTag();

  return (
    PREFIX +
    [iv, tag, encrypted].map((part) => part.toString("base64url")).join(".")
  );
}

export function revealSecret(value: string | null | undefined): string | null {
  if (!value) return null;
  if (!value.startsWith(PREFIX)) return value;

  const key = encryptionKey();
  if (!key) {
    throw new Error(
      "JARVIS_ENCRYPTION_KEY manquant : impossible de déchiffrer le secret stocké."
    );
  }

  const encoded = value.slice(PREFIX.length).split(".");
  if (encoded.length !== 3) throw new Error("Secret chiffré invalide");

  const [ivRaw, tagRaw, dataRaw] = encoded.map((v) => Buffer.from(v, "base64url"));
  const decipher = createDecipheriv("aes-256-gcm", key, ivRaw);
  decipher.setAuthTag(tagRaw);
  return Buffer.concat([decipher.update(dataRaw), decipher.final()]).toString("utf8");
}
