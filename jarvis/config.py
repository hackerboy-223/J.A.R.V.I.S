from __future__ import annotations

from dataclasses import dataclass
import os
from pathlib import Path
import sys

from dotenv import load_dotenv

from jarvis.paths import resolve_data_dir

IS_FROZEN = bool(getattr(sys, "frozen", False))
ROOT = (
    Path(sys.executable).resolve().parent
    if IS_FROZEN
    else Path(__file__).resolve().parent.parent
)
DATA_DIR = resolve_data_dir(
    root=ROOT,
    environ=os.environ,
    is_frozen=IS_FROZEN,
).expanduser().resolve()
DATA_DIR.mkdir(parents=True, exist_ok=True)

# Packaged builds keep mutable settings under the user's profile, never beside
# the executable or in PyInstaller's temporary extraction directory.
load_dotenv(DATA_DIR / ".env" if IS_FROZEN else ROOT / ".env")


def _env_path(name: str, default: Path) -> Path:
    raw = os.getenv(name, "").strip()
    return Path(raw or default).expanduser().resolve()


DEFAULT_WORKSPACE_DIR = DATA_DIR / "workspace" if IS_FROZEN else ROOT
DEFAULT_SKILLS_DIR = DATA_DIR / "skills" if IS_FROZEN else ROOT / "skills"


@dataclass(frozen=True)
class Settings:
    llm_provider: str = os.getenv("JARVIS_LLM_PROVIDER", "openrouter").strip().lower()
    llm_base_url: str = os.getenv("JARVIS_LLM_BASE_URL", "https://openrouter.ai/api/v1")
    llm_api_key: str = os.getenv(
        "OPENROUTER_API_KEY",
        os.getenv("JARVIS_LLM_API_KEY", ""),
    )
    llm_model: str = os.getenv("JARVIS_LLM_MODEL", "openrouter/free")
    openrouter_referer: str = os.getenv("OPENROUTER_HTTP_REFERER", "").strip()
    openrouter_title: str = os.getenv("OPENROUTER_X_TITLE", "J.A.R.V.I.S.").strip()
    hf_token: str = os.getenv("HF_TOKEN", os.getenv("HUGGING_FACE_HUB_TOKEN", ""))
    hf_model: str = os.getenv("JARVIS_HF_MODEL", "zai-org/GLM-5.3-Flash")
    hf_provider: str = os.getenv("JARVIS_HF_PROVIDER", "auto")
    exa_api_key: str = os.getenv("EXA_API_KEY", "").strip()
    exa_snippet_chars: int = max(
        400,
        min(6000, int(os.getenv("JARVIS_EXA_SNIPPET_CHARS", "1800"))),
    )
    workspace_root: Path = _env_path("JARVIS_WORKSPACE_ROOT", DEFAULT_WORKSPACE_DIR)
    skills_dir: Path = _env_path("JARVIS_SKILLS_DIR", DEFAULT_SKILLS_DIR)
    mcp_config_path: Path = _env_path("JARVIS_MCP_CONFIG", DATA_DIR / "mcp.json")
    scheduler_enabled: bool = os.getenv(
        "JARVIS_SCHEDULER_ENABLED", "true"
    ).lower() == "true"
    embedding_base_url: str = os.getenv(
        "JARVIS_EMBEDDING_BASE_URL", ""
    ).strip()
    embedding_api_key: str = os.getenv(
        "JARVIS_EMBEDDING_API_KEY", ""
    ).strip()
    embedding_model: str = os.getenv(
        "JARVIS_EMBEDDING_MODEL", ""
    ).strip()
    hybrid_dense_weight: float = max(
        0.0,
        min(1.0, float(os.getenv("JARVIS_HYBRID_DENSE_WEIGHT", "0.35"))),
    )
    api_host: str = os.getenv("JARVIS_API_HOST", "127.0.0.1").strip()
    api_port: int = int(os.getenv("JARVIS_API_PORT", "8000"))
    api_token: str = os.getenv("JARVIS_API_TOKEN", "").strip()
    allow_pc_control: bool = os.getenv("JARVIS_ALLOW_PC_CONTROL", "false").lower() == "true"
    confirm_safe_pc_actions: bool = os.getenv(
        "JARVIS_CONFIRM_SAFE_PC_ACTIONS", "false"
    ).lower() == "true"
    stt_provider: str = os.getenv("JARVIS_STT_PROVIDER", "hybrid").strip().lower()
    groq_api_key: str = os.getenv("GROQ_API_KEY", "").strip()
    groq_stt_model: str = os.getenv(
        "JARVIS_GROQ_STT_MODEL", "whisper-large-v3-turbo"
    ).strip()
    hf_asr_model: str = os.getenv("JARVIS_HF_ASR_MODEL", "").strip()
    vosk_model_path: str = os.getenv("JARVIS_VOSK_MODEL_PATH", "").strip()
    whisper_model: str = os.getenv("JARVIS_WHISPER_MODEL", "tiny")
    whisper_compute_type: str = os.getenv("JARVIS_WHISPER_COMPUTE", "int8")
    whisper_cpu_threads: int = max(1, int(os.getenv("JARVIS_WHISPER_CPU_THREADS", "2")))
    whisper_partial_transcripts: bool = os.getenv(
        "JARVIS_WHISPER_PARTIAL_TRANSCRIPTS", "false"
    ).lower() == "true"
    language: str = os.getenv("JARVIS_LANGUAGE", "fr")
    audio_device: str = os.getenv("JARVIS_AUDIO_DEVICE", "")
    ollama_base_url: str = os.getenv("JARVIS_OLLAMA_BASE_URL", "http://127.0.0.1:11434/v1")
    ollama_model: str = os.getenv("JARVIS_OLLAMA_MODEL", "qwen2.5:1.5b")
    database_path: Path = DATA_DIR / "jarvis.db"


settings = Settings()
