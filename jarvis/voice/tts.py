from __future__ import annotations

import threading
import pyttsx3


class Speaker:
    def __init__(self) -> None:
        self._lock = threading.Lock()

    def speak(self, text: str) -> None:
        if not text.strip():
            return
        with self._lock:
            engine = pyttsx3.init()
            engine.setProperty("rate", 178)
            engine.say(text)
            engine.runAndWait()
            engine.stop()

    def stop(self) -> None:
        # Barge-in/interruption will use a dedicated TTS worker in the next phase.
        return
