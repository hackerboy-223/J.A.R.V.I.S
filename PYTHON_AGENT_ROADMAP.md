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
- PyInstaller/Nuitka build
- auto-update strategy
- signed Windows installer
- first-run permissions wizard
- diagnostics and crash reports
- tests and CI

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
