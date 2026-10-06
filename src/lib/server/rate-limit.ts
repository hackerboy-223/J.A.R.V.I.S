import { createHash } from "node:crypto";
import type { NextRequest } from "next/server";
import { NextResponse } from "next/server";
import { SESSION_COOKIE } from "@/lib/server/auth";

type Bucket = { count: number; resetAt: number };

const globalStore = globalThis as unknown as {
  jarvisRateLimit?: Map<string, Bucket>;
  jarvisRateLimitOps?: number;
};

const store = globalStore.jarvisRateLimit ?? new Map<string, Bucket>();
globalStore.jarvisRateLimit = store;

function clientId(req: NextRequest): string {
  const session = req.cookies.get(SESSION_COOKIE)?.value;
  if (session) {
    const digest = createHash("sha256").update(session).digest("hex").slice(0, 24);
    return `session:${digest}`;
  }

  // J.A.R.V.I.S. is single-user. Anonymous endpoints intentionally share one
  // bucket instead of trusting spoofable forwarding headers.
  return "anonymous";
}

function cleanup(now: number) {
  globalStore.jarvisRateLimitOps = (globalStore.jarvisRateLimitOps ?? 0) + 1;
  if ((globalStore.jarvisRateLimitOps ?? 0) % 100 !== 0 && store.size < 1000) return;
  for (const [key, bucket] of store) {
    if (bucket.resetAt <= now) store.delete(key);
  }
}

export function enforceRateLimit(
  req: NextRequest,
  opts: { name: string; limit: number; windowMs: number }
): NextResponse | null {
  const now = Date.now();
  cleanup(now);

  const limit = Math.max(1, Math.min(Math.trunc(opts.limit), 10_000));
  const windowMs = Math.max(1_000, Math.min(Math.trunc(opts.windowMs), 24 * 60 * 60 * 1000));
  const key = `${opts.name}:${clientId(req)}`;
  const current = store.get(key);

  if (!current || current.resetAt <= now) {
    store.set(key, { count: 1, resetAt: now + windowMs });
    return null;
  }

  if (current.count >= limit) {
    const retryAfter = Math.max(1, Math.ceil((current.resetAt - now) / 1000));
    return NextResponse.json(
      { error: "Trop de requêtes. Réessaie dans quelques instants." },
      {
        status: 429,
        headers: {
          "Retry-After": String(retryAfter),
          "X-RateLimit-Limit": String(limit),
          "X-RateLimit-Remaining": "0",
        },
      }
    );
  }

  current.count += 1;
  return null;
}
