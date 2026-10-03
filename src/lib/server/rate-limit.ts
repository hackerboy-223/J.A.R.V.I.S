import type { NextRequest } from "next/server";
import { NextResponse } from "next/server";

type Bucket = { count: number; resetAt: number };

const globalStore = globalThis as unknown as {
  jarvisRateLimit?: Map<string, Bucket>;
  jarvisRateLimitOps?: number;
};

const store = globalStore.jarvisRateLimit ?? new Map<string, Bucket>();
globalStore.jarvisRateLimit = store;

function clientId(req: NextRequest): string {
  const forwarded = req.headers.get("x-forwarded-for")?.split(",")[0]?.trim();
  return forwarded || req.headers.get("x-real-ip") || "local";
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

  const key = `${opts.name}:${clientId(req)}`;
  const current = store.get(key);

  if (!current || current.resetAt <= now) {
    store.set(key, { count: 1, resetAt: now + opts.windowMs });
    return null;
  }

  if (current.count >= opts.limit) {
    const retryAfter = Math.max(1, Math.ceil((current.resetAt - now) / 1000));
    return NextResponse.json(
      { error: "Trop de requêtes. Réessaie dans quelques instants." },
      {
        status: 429,
        headers: {
          "Retry-After": String(retryAfter),
          "X-RateLimit-Limit": String(opts.limit),
          "X-RateLimit-Remaining": "0",
        },
      }
    );
  }

  current.count += 1;
  return null;
}
