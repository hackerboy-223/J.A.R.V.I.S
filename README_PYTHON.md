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


## Open JARVIS functional parity

The Python rewrite now follows the functional architecture of the MIT Open JARVIS reference more closely.

### Agent modes

The desktop mode selector exposes:

- STANDARD — normal tool-using JARVIS
- PARALLEL AGENTS — analyst + engineer + critic run concurrently, then JARVIS synthesizes
- SEQUENTIAL CHAIN — plan -> build -> review
- AI DEBATE — competing positions, rebuttal, final technical synthesis
- DEEP RESEARCH — generates search queries, searches the web, reads public pages and synthesizes sources

### Knowledge Base (RAG)

Use **AJOUTER DOCUMENT** to index local text/code files.

Supported formats include:

```
.txt .md .csv .json .py .js .ts .tsx .jsx
.html .xml .log .yaml .yml .sql .ps1
```

Documents are chunked locally and searched with BM25. Relevant chunks are automatically injected into
the standard agent context. The `knowledge_search` tool is also available to the model.

### Profile Memory

The **PROFILE** button displays the built-in H@CKERBOY profile plus facts explicitly stored by the
`remember_fact` tool. JARVIS is instructed to use that tool only when the user explicitly asks it
to remember something.

### Agent Memory

Non-standard workflow results are persisted in SQLite and shown through **AGENT MEMORY**.
Recent prior work is injected back into the agent context when useful.

### Web tools

Standard mode now exposes:

- `web_search` — Serper-backed web search
- `read_page` — public page reader with private/local network blocking
- `knowledge_search`
- `remember_fact`
- `system_status`
- `pc_control`

Deep Research requires:

```env
SERPER_API_KEY="..."
```

The page reader validates redirect targets to prevent redirects into localhost/private network ranges.


## Voice memory fallback

The speech pipeline is hybrid:

1. If `JARVIS_STT_PROVIDER=auto` and `HF_TOKEN` is configured, J.A.R.V.I.S. sends each completed utterance to Hugging Face ASR.
2. If Hugging Face ASR is unavailable, it falls back to local faster-whisper.
3. Local faster-whisper runs with `int8`, one worker and a small CPU thread count.
4. If the configured local model cannot allocate enough memory, J.A.R.V.I.S. releases it and retries with `tiny`.
5. Fatal STT memory errors stop hands-free mode instead of endlessly repeating the same diagnostic.

Recommended low-memory configuration:

```env
JARVIS_STT_PROVIDER="auto"
JARVIS_HF_ASR_MODEL=""
JARVIS_WHISPER_MODEL="tiny"
JARVIS_WHISPER_COMPUTE="int8"
JARVIS_WHISPER_CPU_THREADS="2"
JARVIS_WHISPER_PARTIAL_TRANSCRIPTS="false"
```

Local interim Whisper transcription is disabled by default because repeated inference increases memory
pressure. The neural HUD still reacts continuously to the live microphone level.
