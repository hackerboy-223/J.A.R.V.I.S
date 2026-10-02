from __future__ import annotations

import threading
import pyttsx3


class Speaker:
    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._engine = pyttsx3.init()
        self._engine.setProperty("rate", 178)

    def speak(self, text: str) -> None:
        if not text.strip():
            return
        with self._lock:
            self._engine.say(text)
            self._engine.runAndWait()

    def speak_async(self, text: str) -> None:
        threading.Thread(target=self.speak, args=(text,), daemon=True).start()

    def stop(self) -> None:
        with self._lock:
            self._engine.stop()
