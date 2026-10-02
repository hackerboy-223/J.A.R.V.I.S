# Security Policy

## Production defaults

J.A.R.V.I.S. is designed as a personal/single-user assistant. Production mode is fail-closed:

- `JARVIS_ACCESS_PASSWORD` must contain at least 12 characters.
- `JARVIS_SESSION_SECRET` must contain at least 32 characters.
- `JARVIS_ENCRYPTION_KEY` is required when a Hugging Face token is stored.
- `run_js` is disabled in production unless `JARVIS_ALLOW_RUN_JS=true` is explicitly set.
- Chat, conversations, settings, voice and system telemetry APIs require a valid signed session.
- Expensive endpoints are rate-limited in-process.
- The public `/api` health endpoint exposes only status and timestamp.

## Important limitations

The current rate limiter is process-local. For a multi-instance/serverless deployment, replace it with a shared store such as Redis-compatible storage.

SQLite is suitable for local use or a single persistent server/volume. Do not rely on an ephemeral filesystem for production persistence.

The application currently implements a single-user access gate, not multi-user accounts or per-user conversation ownership.

## Dependency security

Before a public deployment, update Next.js to the latest patched Active LTS release and regenerate `bun.lock` using Bun. Do not hand-edit lockfile integrity metadata.

As of 2026-10-02, the Next.js project recommends **16.3.8** for the 16.x Active LTS line following the September 2026 security release.

Suggested local upgrade:

```bash
bun update next@16.3.8 eslint-config-next@16.3.8
bun run check
```

Commit the regenerated `package.json` / `bun.lock` together.

## Reporting a vulnerability

Do not publish credentials, tokens, database contents, session secrets, or exploit details in a public issue. Rotate any exposed secret immediately.
