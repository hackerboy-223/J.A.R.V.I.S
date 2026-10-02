import { createHash, createHmac, timingSafeEqual } from "node:crypto";
import type { NextRequest } from "next/server";
import { NextResponse } from "next/server";

export const SESSION_COOKIE = "jarvis_session";
export const SESSION_TTL_SECONDS = 7 * 24 * 60 * 60;

function accessPassword(): string {
  return process.env.JARVIS_ACCESS_PASSWORD?.trim() ?? "";
}

function sessionSecret(): string {
  return process.env.JARVIS_SESSION_SECRET?.trim() ?? "";
}

export function isAuthRequired(): boolean {
  return process.env.NODE_ENV === "production" || accessPassword().length > 0;
}

export function isAuthConfigured(): boolean {
  return accessPassword().length > 0 && sessionSecret().length >= 24;
}

function safeEqual(a: string, b: string): boolean {
  const ah = createHash("sha256").update(a).digest();
  const bh = createHash("sha256").update(b).digest();
  return timingSafeEqual(ah, bh);
}

function sign(payload: string): string {
  const secret = sessionSecret();
  if (!secret) throw new Error("JARVIS_SESSION_SECRET manquant");
  return createHmac("sha256", secret).update(payload).digest("base64url");
}

export function verifyPassword(candidate: string): boolean {
  const expected = accessPassword();
  return expected.length > 0 && safeEqual(candidate, expected);
}

export function createSessionToken(): string {
  if (!isAuthConfigured()) {
    throw new Error(
      "Authentification non configurée : définis JARVIS_ACCESS_PASSWORD et JARVIS_SESSION_SECRET."
    );
  }
  const expiresAt = Math.floor(Date.now() / 1000) + SESSION_TTL_SECONDS;
  const payload = `v1.${expiresAt}`;
  return `${payload}.${sign(payload)}`;
}

export function verifySessionToken(token: string | undefined): boolean {
  if (!token || !isAuthConfigured()) return false;
  const parts = token.split(".");
  if (parts.length !== 3 || parts[0] !== "v1") return false;

  const expiresAt = Number(parts[1]);
  if (!Number.isFinite(expiresAt) || expiresAt <= Math.floor(Date.now() / 1000)) {
    return false;
  }

  const payload = `${parts[0]}.${parts[1]}`;
  const expected = sign(payload);
  return safeEqual(parts[2], expected);
}

export function isAuthorized(req: NextRequest): boolean {
  if (!isAuthRequired()) return true;
  return verifySessionToken(req.cookies.get(SESSION_COOKIE)?.value);
}

export function requireAuthorized(req: NextRequest): NextResponse | null {
  if (isAuthorized(req)) return null;
  if (!isAuthConfigured()) {
    return NextResponse.json(
      {
        error:
          "J.A.R.V.I.S. est verrouillé mais l'authentification serveur n'est pas configurée.",
      },
      { status: 503 }
    );
  }
  return NextResponse.json({ error: "Authentification requise" }, { status: 401 });
}
