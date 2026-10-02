# J.A.R.V.I.S. — Python Desktop Rewrite

This branch is the native Python rewrite of J.A.R.V.I.S.

## Goal

Turn J.A.R.V.I.S. from a web assistant into a local desktop agent for H@CKERBOY:

- native PySide6 desktop UI
- persistent SQLite memory
- configurable OpenAI-compatible LLM endpoint
- local PC telemetry
- allowlisted PC actions with explicit confirmation
- offline speech-to-text with faster-whisper
- local text-to-speech
- hands-free loop: listen -> transcribe -> reason -> speak -> listen again
- auditable action log

## Current architecture

```
main.py
jarvis/
  config.py
  profile.py
  core/
    agent.py
    llm.py
    memory.py
    tools.py
  tools/
    pc.py
    system.py
  voice/
    stt.py
    tts.py
  ui/
    main_window.py
```

## Run on Windows

Use Python 3.11+.

```powershell
py -3.11 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
pip install -e .
Copy-Item .env.python.example .env
```

Edit `.env` and configure an OpenAI-compatible provider:

```env
JARVIS_LLM_BASE_URL="https://api.openai.com/v1"
JARVIS_LLM_API_KEY="..."
JARVIS_LLM_MODEL="gpt-4o-mini"
```

For local PC actions, opt in explicitly:

```env
JARVIS_ALLOW_PC_CONTROL="true"
```

Then:

```powershell
python main.py
```

The first faster-whisper run may download the selected speech model.

## Safety model

J.A.R.V.I.S. does not receive unrestricted shell access. PC actions are registered tools.
Actions that affect the desktop require an explicit confirmation dialog.
Every tool action is written to the SQLite action log.

## Migration status

Already rewritten in Python:
- owner profile/context
- core agent loop
- OpenAI-compatible LLM adapter
- SQLite conversation/fact/action memory
- tool registry
- system status
- allowlisted PC control
- PySide6 desktop HUD/chat
- offline TTS
- faster-whisper hands-free STT

Still to migrate/build:
- long-term semantic memory/RAG
- file knowledge base
- screen understanding and safe UI automation
- plugin SDK
- scheduler/reminders
- wake word
- barge-in / interruption while JARVIS is speaking
- richer HUD/telemetry
- settings UI
- provider manager
- encrypted secret storage
- packaging to Windows EXE
- automated tests
- migration importer for the old Prisma/SQLite data

The old Next.js implementation remains in this branch history during migration so features can be
compared. Remove the TypeScript/Next.js tree only after Python feature parity is validated.


## Hugging Face brain

Hugging Face is the default Python brain provider.

```env
JARVIS_LLM_PROVIDER="huggingface"
HF_TOKEN="hf_..."
JARVIS_HF_MODEL="zai-org/GLM-5.3-Flash"
JARVIS_HF_PROVIDER="auto"
```

With `JARVIS_HF_PROVIDER=auto`, Hugging Face selects an available inference provider for the model.
The Python agent keeps tool calling enabled, so compatible chat models can still invoke
`system_status` and `pc_control`.

## Neural HUD

The desktop application includes a native PySide6/QPainter neural core:

- animated neural nodes and links
- central reactor/core
- scanner sweep
- cyan idle/listening/speaking states
- amber thinking state
- red error state
- animation speed reacts to the active voice/agent state

It is entirely native Qt and does not use the old browser Canvas renderer.
