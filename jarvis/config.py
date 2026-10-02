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
    llm_provider: str = os.getenv("JARVIS_LLM_PROVIDER", "huggingface").strip().lower()
    llm_base_url: str = os.getenv("JARVIS_LLM_BASE_URL", "https://api.openai.com/v1")
    llm_api_key: str = os.getenv("JARVIS_LLM_API_KEY", "")
    llm_model: str = os.getenv("JARVIS_LLM_MODEL", "zai-org/GLM-5.3-Flash")
    hf_token: str = os.getenv("HF_TOKEN", os.getenv("HUGGING_FACE_HUB_TOKEN", ""))
    hf_model: str = os.getenv("JARVIS_HF_MODEL", "zai-org/GLM-5.3-Flash")
    hf_provider: str = os.getenv("JARVIS_HF_PROVIDER", "auto")
    allow_pc_control: bool = os.getenv("JARVIS_ALLOW_PC_CONTROL", "false").lower() == "true"
    whisper_model: str = os.getenv("JARVIS_WHISPER_MODEL", "small")
    whisper_compute_type: str = os.getenv("JARVIS_WHISPER_COMPUTE", "int8")
    language: str = os.getenv("JARVIS_LANGUAGE", "fr")
    database_path: Path = DATA_DIR / "jarvis.db"


settings = Settings()
