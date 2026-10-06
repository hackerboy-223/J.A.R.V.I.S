# Security Policy

## Scope

J.A.R.V.I.S. is designed primarily as a **personal, single-user, local-first assistant**.
The desktop build has local OS capabilities, so security is based on explicit capability
boundaries, confirmation, constrained workspaces, auditable actions, and fail-closed defaults.

## Production defaults

### Web

- `JARVIS_ACCESS_PASSWORD` must contain at least 12 characters.
- `JARVIS_SESSION_SECRET` must contain at least 32 characters.
- Signed session cookies are `HttpOnly`, `SameSite=Strict`, and `Secure` in production.
- Protected routes validate the signed session, not merely the presence of the cookie.
- Expensive endpoints are rate-limited in-process.
- Security headers deny framing and object embedding and restrict sensitive browser capabilities.
- Legacy `run_js` based on `node:vm` is **development-only** and is never enabled in production.
  Node.js explicitly does not consider `node:vm` a security boundary.

### Desktop / Python Core

- Distributed defaults keep `JARVIS_ALLOW_PC_CONTROL=false`.
- Safe desktop actions default to confirmation in the distributed example configuration.
- File tools are confined to `JARVIS_WORKSPACE_ROOT` and block known secret paths.
- Screen capture, clipboard read, file mutation, scheduler mutation, MCP calls, sandbox work,
  and semantic UI automation are permission-gated.
- Ambiguous window titles are rejected instead of acting on the first partial match.
- UI Automation escapes model-provided window text before constructing title patterns.
- API exposure outside loopback is refused unless `JARVIS_API_TOKEN` is configured.
- MCP servers must be explicitly configured; the model cannot invent an arbitrary server command.

## Secrets and diagnostics

Desktop provider secrets are stored through `keyring` / the OS credential manager when entered
in the native UI. There is no silent plaintext fallback.

Logs and Python crash reports redact:

- Bearer tokens;
- common OpenRouter / Hugging Face / Groq / Exa key formats;
- exact values of environment variables whose names indicate a token, secret, password, or API key.

Tool audit records intentionally store **metadata rather than payload contents** for sensitive
fields such as file content, clipboard text, sandbox code, prompts, and MCP arguments.

Useful local diagnostics:

```powershell
python -m jarvis package-doctor
python -m jarvis voice-doctor
python -m jarvis doctor
```

Packaged diagnostic reports are written under the per-user JARVIS data directory.

## Voice / native-runtime hardening

The Windows build explicitly packages the `sounddevice` PortAudio runtime. The hands-free path:

- probes a supported microphone sample rate instead of assuming 16 kHz;
- starts outside the Qt GUI thread;
- marshals worker results to Qt slots;
- keeps the PortAudio real-time callback minimal;
- downloads the Vosk model atomically into a temporary file;
- bounds archive/download sizes and validates extraction paths;
- records native faults with `faulthandler`.

## Local data

Packaged mutable data is stored separately from the install directory under the user profile
(`%LOCALAPPDATA%\JARVIS` on normal Windows installations).

SQLite stores use WAL mode, a busy timeout, foreign-key enforcement, and `synchronous=NORMAL`.
WAL is intended for local storage on the same host; do not place the live JARVIS database on a
network filesystem.

## Updates and release integrity

The updater only accepts HTTPS release assets from the official
`hackerboy-223/J.A.R.V.I.S` GitHub repository.

A Windows update is downloaded atomically and is launched only if the GitHub release exposes a
valid `sha256:` digest and the downloaded bytes match it.

Local Windows builds produce:

```text
dist/JARVIS-Setup-x64.exe
dist/JARVIS-Windows-x64.zip
dist/SHA256SUMS.txt
dist/J.A.R.V.I.S/BUILD-INFO.json
```

The build pipeline runs source tests, PyInstaller, then smoke-tests the **packaged executable**
before producing the final installer.

### Remaining distribution limitation

The installer is not Authenticode-signed unless a trusted code-signing certificate is supplied.
Windows SmartScreen may therefore warn on a fresh or low-reputation binary. Do not bypass this by
using fake certificates; public distribution should use a legitimate signing identity.

## Dependency security

The project tracks patched Next.js 16.x dependencies and uses Dependabot for both `pip` and
native `bun` ecosystems.

Do not hand-edit `bun.lock` integrity metadata. Regenerate it with Bun whenever JavaScript
dependencies change.

The repository's Windows workflows intentionally avoid third-party `uses:` actions because this
repository/account has previously enforced a restrictive Actions policy. The workflow is therefore
self-contained, but GitHub must still allocate a usable runner for it to execute.

## Important limitations

- The Web rate limiter is process-local. A future multi-instance deployment needs a shared store.
- The application has a single-user access gate, not multi-user accounts and per-user ownership.
- The restricted Python runner reduces capabilities but is not claimed to be an OS security
  boundary.
- External AI/search providers retain their own availability, quota, privacy, and regional limits.
- Vision capture does not by itself provide reliable visual understanding without a configured
  multimodal model.

## Reporting a vulnerability

Do not publish credentials, tokens, database contents, session secrets, private diagnostic logs,
or exploit details in a public issue. Rotate any exposed secret immediately.
