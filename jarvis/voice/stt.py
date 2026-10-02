from __future__ import annotations

import queue
import threading
import time
from collections.abc import Callable

import numpy as np
import sounddevice as sd
from faster_whisper import WhisperModel

from jarvis.config import settings


class HandsFreeListener:
    def __init__(
        self,
        on_partial: Callable[[str], None],
        on_final: Callable[[str], None],
        sample_rate: int = 16000,
    ) -> None:
        self.on_partial = on_partial
        self.on_final = on_final
        self.sample_rate = sample_rate
        self._audio_q: queue.Queue[np.ndarray] = queue.Queue()
        self._running = False
        self._thread: threading.Thread | None = None
        self._stream: sd.InputStream | None = None
        self._model: WhisperModel | None = None

    def _ensure_model(self) -> WhisperModel:
        if self._model is None:
            self._model = WhisperModel(
                settings.whisper_model,
                device="cpu",
                compute_type=settings.whisper_compute_type,
            )
        return self._model

    def start(self) -> None:
        if self._running:
            return
        self._running = True
        self._thread = threading.Thread(target=self._loop, daemon=True)
        self._thread.start()
        self._stream = sd.InputStream(
            samplerate=self.sample_rate,
            channels=1,
            dtype="float32",
            blocksize=1600,
            callback=self._callback,
        )
        self._stream.start()

    def stop(self) -> None:
        self._running = False
        if self._stream is not None:
            self._stream.stop()
            self._stream.close()
            self._stream = None

    def _callback(self, indata, frames, time_info, status) -> None:
        del frames, time_info, status
        if self._running:
            self._audio_q.put(indata[:, 0].copy())

    def _loop(self) -> None:
        chunks: list[np.ndarray] = []
        last_voice = time.monotonic()

        while self._running:
            try:
                chunk = self._audio_q.get(timeout=0.2)
            except queue.Empty:
                continue

            rms = float(np.sqrt(np.mean(np.square(chunk))) + 1e-9)
            if rms > 0.012:
                last_voice = time.monotonic()
                chunks.append(chunk)
            elif chunks:
                chunks.append(chunk)

            duration = sum(len(c) for c in chunks) / self.sample_rate
            silence = time.monotonic() - last_voice

            if duration >= 0.9 and len(chunks) % 6 == 0:
                self._transcribe(chunks, final=False)

            if chunks and silence >= 1.0 and duration >= 0.5:
                self._transcribe(chunks, final=True)
                chunks = []

    def _transcribe(self, chunks: list[np.ndarray], final: bool) -> None:
        audio = np.concatenate(chunks).astype(np.float32)
        model = self._ensure_model()
        segments, _ = model.transcribe(
            audio,
            language=settings.language,
            beam_size=1,
            vad_filter=True,
        )
        text = " ".join(segment.text.strip() for segment in segments).strip()
        if not text:
            return
        if final:
            self.on_final(text)
        else:
            self.on_partial(text)
