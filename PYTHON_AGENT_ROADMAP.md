# Python Agent Roadmap

## P0 — stable local agent
- native desktop app
- LLM provider
- memory
- hands-free voice
- safe local tools
- confirmation policy
- action audit log

## P1 — complete personal agent
- screen capture + OCR/vision abstraction
- window discovery/focus
- safe UI automation with per-action confirmation
- file search and local RAG
- persistent user preferences/facts
- plugin registry
- task scheduler
- provider fallback
- encrypted credentials

## P2 — JARVIS experience
- wake word
- interruption/barge-in
- live streaming STT
- streaming TTS
- richer HUD animations
- system tray/background mode
- notifications
- multi-monitor awareness
- application-specific adapters

## P3 — distribution
- [x] PyInstaller Windows build recipe and CI artifact workflow (Windows runner validation pending)
- auto-update strategy
- signed Windows installer
- first-run permissions wizard
- diagnostics and crash reports
- [x] focused tests for packaged data paths and sandbox worker

## Permission tiers

### Read-only
Can run without confirmation:
- system telemetry
- memory lookup
- local knowledge search

### Reversible desktop actions
Ask once or per action depending on policy:
- open app
- open folder
- open URL
- focus window

### Data-changing actions
Always require explicit confirmation:
- write/rename/move files
- send a message/email
- install/uninstall software
- change system settings

### Disallowed by default
- unrestricted shell execution
- silent deletion
- credential extraction
- disabling security tools
- hidden persistence


## OpenJarvis gap batch — implemented on python-agent-rewrite

Selected batch:

- [x] 01 Scheduler — persistent SQLite tasks: once / interval / cron
- [x] 02 Operative Agent — operator_id, persistent state and run history
- [x] 03 File tools — safe workspace file_read / file_write / file_patch
- [x] 04 Code Sandbox — restricted Python runner, import allowlist and timeout
- [x] 06 Skills — SKILL.md / skill.toml discovery and on-demand loading
- [x] 07 MCP — explicit configured stdio / Streamable HTTP servers through MCP SDK v2
- [x] 08 Hybrid memory — BM25 plus optional OpenAI-compatible dense embeddings
- [x] 10 API — FastAPI OpenAI-compatible local server via `jarvis serve`

### Safety boundaries retained

- file tools cannot escape `JARVIS_WORKSPACE_ROOT`
- secret files such as `.env` and credential stores are blocked
- writes, patches, sandbox runs, schedule mutations and MCP calls require confirmation
- MCP servers must be preconfigured; the model cannot invent a command to spawn
- Python sandbox is restricted and is not an unrestricted operating-system shell
- API binds to localhost by default; non-loopback bind requires `JARVIS_API_TOKEN`
