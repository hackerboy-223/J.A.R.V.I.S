from __future__ import annotations

import re
from typing import Any


class LocalCommandRouter:
    """Deterministic fallback for basic JARVIS actions when no LLM is available."""

    def parse(self, text: str) -> tuple[str, dict[str, Any]] | None:
        clean = " ".join(text.lower().strip().split())

        if clean in {"yo", "salut", "bonjour", "hello", "hey", "cc", "jarvis"}:
            return "local_reply", {
                "text": "En ligne, H@CKERBOY. Tous les systèmes locaux sont disponibles."
            }

        app_map = {
            "calculatrice": "calculator",
            "calculator": "calculator",
            "bloc-notes": "notepad",
            "bloc notes": "notepad",
            "notepad": "notepad",
            "explorateur": "explorer",
            "explorer": "explorer",
        }
        for phrase, target in app_map.items():
            if re.search(rf"\b(ouvre|lance|démarre)\b.*\b{re.escape(phrase)}\b", clean):
                return "pc_control", {"action": "open_app", "target": target}

        folder_map = {
            "téléchargements": "downloads",
            "telechargements": "downloads",
            "downloads": "downloads",
            "documents": "documents",
            "bureau": "desktop",
            "desktop": "desktop",
            "projet": "project",
        }
        for phrase, target in folder_map.items():
            if re.search(rf"\b(ouvre|affiche)\b.*\b{re.escape(phrase)}\b", clean):
                return "pc_control", {"action": "open_folder", "target": target}

        if any(
            phrase in clean
            for phrase in (
                "état du pc",
                "etat du pc",
                "état de mon pc",
                "etat de mon pc",
                "statut du pc",
                "ram",
                "cpu",
            )
        ):
            return "system_status", {}

        return None
