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

- `web_search` — Exa semantic web search
- `read_page` — public page reader with private/local network blocking
- `knowledge_search`
- `remember_fact`
- `system_status`
- `pc_control`

Deep Research requires:

```env
EXA_API_KEY="..."
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


## OpenRouter free provider

OpenRouter is supported as a first-class J.A.R.V.I.S. provider.

Recommended configuration:

```env
JARVIS_LLM_PROVIDER="openrouter"
JARVIS_LLM_BASE_URL="https://openrouter.ai/api/v1"
OPENROUTER_API_KEY="sk-or-v1-..."
JARVIS_LLM_MODEL="openrouter/free"
OPENROUTER_HTTP_REFERER=""
OPENROUTER_X_TITLE="J.A.R.V.I.S."
```

The older `JARVIS_LLM_API_KEY` variable remains supported for backward compatibility, but
`OPENROUTER_API_KEY` is clearer when using OpenRouter.

J.A.R.V.I.S. sends its normal OpenAI-style tool definitions to `openrouter/free`. OpenRouter's free
router can select a free model compatible with requested capabilities such as tool calling.

If an OpenRouter request fails, J.A.R.V.I.S. attempts the configured local Ollama endpoint before
surfacing an error.

For low-memory hands-free voice, use Vosk independently of the LLM provider:

```env
JARVIS_STT_PROVIDER="vosk"
JARVIS_VOSK_MODEL_PATH=""
```


## Python 3.14 + Vosk

On Windows with Python 3.14, the project uses `platypush-vosk>=0.3.45.post2`.
It is a repackaged build of upstream Vosk 0.3.45 and keeps the same Python import package:

```python
from vosk import Model, KaldiRecognizer, SetLogLevel
```

This avoids the nonexistent `vosk>=0.3.75` dependency and provides a Windows x86-64 wheel suitable
for current Python 3.14 installations.


## Hybrid high-accuracy speech transcription

For better French transcription quality while keeping the desktop lightweight:

```env
JARVIS_STT_PROVIDER="hybrid"
GROQ_API_KEY=""
JARVIS_GROQ_STT_MODEL="whisper-large-v3-turbo"

JARVIS_VOSK_MODEL_PATH=""
JARVIS_LANGUAGE="fr"
```

Behavior:

1. Vosk stays local for low-latency partial captions and the "Jarvis" interruption keyword.
2. The completed utterance is buffered as 16 kHz mono PCM.
3. When `GROQ_API_KEY` is configured, the final phrase is sent as WAV to Groq's
   OpenAI-compatible `/audio/transcriptions` endpoint.
4. `whisper-large-v3-turbo` produces the final transcript used by the agent.
5. If Groq is unavailable or no key is configured, J.A.R.V.I.S. falls back to Vosk.

The Groq request includes `language=fr`, temperature 0 and a small vocabulary prompt for common
J.A.R.V.I.S. project terms.

## Exa web search

J.A.R.V.I.S. uses Exa's native Search API for web retrieval.

```env
EXA_API_KEY="your_exa_api_key"
JARVIS_EXA_SNIPPET_CHARS="1800"
```

The integration follows Exa's official `build-with-exa` skill for coding agents:

- endpoint: `POST https://api.exa.ai/search`
- authentication: `x-api-key: $EXA_API_KEY`
- search type: `auto`
- content extraction: `contents: {"highlights": true}`
- `numResults` is sent only when J.A.R.V.I.S. intentionally requests a result count
- no category, domain, freshness, or synthesis controls are added unless the task explicitly needs them
- Exa highlights are normalized into the existing `snippet` field used by the agent
- highlights are locally compacted to a configurable character budget before entering the LLM context
- duplicate/empty URLs are removed and result URLs are canonicalized
- Exa request ID, search time and cost metadata are preserved for diagnostics
- Deep Research deduplicates sources across its multiple searches
- no Exa SDK dependency is required; the project uses its existing `httpx` dependency

Because J.A.R.V.I.S. already has OpenRouter as its reasoning/chat LLM, Exa is used as a retrieval tool rather than the Exa `/answer` endpoint.


## Agent platform extensions

The Python rewrite now includes the selected OpenJarvis-inspired platform capabilities.

### Operative mode

Select **OPERATIVE** in the desktop mode selector. Each operator has persistent JSON state and run history in SQLite. Scheduled operative tasks use an isolated operator id based on their task id.

### Persistent scheduler

Available agent tools:

- `schedule_task`
- `list_scheduled_tasks`
- `pause_scheduled_task`
- `resume_scheduled_task`
- `cancel_scheduled_task`

Supported schedule types:

- `once`: ISO 8601 datetime
- `interval`: seconds, minimum 60
- `cron`: standard cron expression

The desktop process or API server must be running for due work to execute.

### Safe workspace files

Configure:

```env
JARVIS_WORKSPACE_ROOT=""
```

Blank means the repository root. `file_read`, `file_write`, and `file_patch` cannot escape this root. Secret paths such as `.env`, `.git`, `.ssh`, credential files, and the JARVIS SQLite database are blocked.

### Restricted Python sandbox

`python_sandbox` runs short pure-computation Python snippets in an isolated temporary directory with:

- short timeout
- import allowlist
- restricted builtins
- no file-open builtin
- no subprocess/network modules exposed

It is intentionally not a general shell or OS security boundary.

### Skills

Create skills under:

```text
skills/<skill-name>/SKILL.md
skills/<skill-name>/skill.toml
```

The agent receives only a compact skill catalog in its system prompt and loads full instructions with `use_skill` when needed. Bundled scripts are never executed automatically.

An example is provided under `skills.example/code-review/`.

### MCP

Copy `mcp.example.json` to the runtime MCP config path (default: `data/mcp.json`) and configure only trusted servers.

```env
JARVIS_MCP_CONFIG=""
```

Blank uses `data/mcp.json`. Supported transports are configured stdio servers and secure Streamable HTTP URLs. Environment secrets can be referenced as `${NAME}`; JARVIS passes only explicitly listed variables to stdio MCP servers.

Agent tools:

- `mcp_servers`
- `mcp_list_tools`
- `mcp_call`

### Hybrid knowledge memory

BM25 remains the zero-configuration default. To add dense retrieval, point JARVIS at any OpenAI-compatible embeddings endpoint:

```env
JARVIS_EMBEDDING_BASE_URL=""
JARVIS_EMBEDDING_API_KEY=""
JARVIS_EMBEDDING_MODEL=""
JARVIS_HYBRID_DENSE_WEIGHT="0.35"
```

Newly indexed chunks receive embeddings when configured. Search combines normalized BM25 with cosine similarity. Existing chunks indexed before embeddings were enabled remain BM25-only until re-indexed.

### Local OpenAI-compatible API

Install/update dependencies, then start:

```powershell
python -m pip install -e .
python -m jarvis serve
```

Default endpoint:

```text
http://127.0.0.1:8000
```

Routes:

- `GET /health`
- `GET /v1/models`
- `POST /v1/chat/completions`

Select an agent mode through request metadata:

```json
{
  "model": "jarvis",
  "messages": [{"role": "user", "content": "Continue the project audit"}],
  "metadata": {
    "mode": "operative",
    "operator_id": "project-audit"
  }
}
```

For a non-loopback bind, set `JARVIS_API_TOKEN`; JARVIS refuses to expose the API on the network without one.


### Platform smoke test

After pulling the branch and installing dependencies:

```powershell
git pull
python -m pip install -e .
python -m jarvis selftest
```

The self-test is intentionally offline and checks Scheduler, Operative persistence, BM25 memory fallback,
Skills discovery, restricted Python sandbox, MCP configuration parsing and FastAPI imports without
calling OpenRouter, Exa or Groq.
