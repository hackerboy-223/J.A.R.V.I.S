from __future__ import annotations

import threading
import pyttsx3


def _decode_language(value: object) -> str:
    if isinstance(value, bytes):
        return value.decode("utf-8", errors="ignore").replace("\x05", "")
    return str(value or "")


class Speaker:
    def __init__(self) -> None:
        self._lock = threading.Lock()

    def _pick_voice(self, engine) -> str | None:
        voices = engine.getProperty("voices") or []
        scored: list[tuple[int, str]] = []

        for voice in voices:
            voice_id = str(getattr(voice, "id", "") or "")
            name = str(getattr(voice, "name", "") or "")
            languages = " ".join(
                _decode_language(item)
                for item in (getattr(voice, "languages", None) or [])
            ).lower()
            haystack = f"{name} {voice_id} {languages}".lower()

            score = 0
            if "fr-fr" in haystack or "fr_fr" in haystack:
                score += 8
            if "français" in haystack or "french" in haystack:
                score += 6
            if any(token in haystack for token in ("hortense", "paul", "denise", "henri", "julie")):
                score += 4
            if score:
                scored.append((score, voice_id))

        if not scored:
            return None
        scored.sort(reverse=True)
        return scored[0][1]

    def speak(self, text: str) -> None:
        clean = text.strip()
        if not clean:
            return

        with self._lock:
            engine = pyttsx3.init()
            try:
                voice_id = self._pick_voice(engine)
                if voice_id:
                    engine.setProperty("voice", voice_id)
                engine.setProperty("rate", 178)
                engine.setProperty("volume", 1.0)
                engine.say(clean)
                engine.runAndWait()
            finally:
                engine.stop()

    def test(self) -> None:
        self.speak("Systèmes vocaux opérationnels. À votre service, H@CKERBOY.")

    def stop(self) -> None:
        # A dedicated interruptible TTS worker will handle barge-in later.
        return
