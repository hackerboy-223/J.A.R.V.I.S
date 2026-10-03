from __future__ import annotations

from dataclasses import dataclass
import os
from pathlib import Path

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = ROOT / "data"
DATA_DIR.mkdir(exist_ok=True)
load_dotenv(ROOT / ".env")


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
