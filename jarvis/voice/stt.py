from __future__ import annotations

import gc
import io
import os
import queue
import threading
import time
import wave
from collections import deque
from collections.abc import Callable

# Keep CTranslate2/MKL conservative on memory before importing native backends.
os.environ.setdefault("OMP_NUM_THREADS", "2")
os.environ.setdefault("MKL_NUM_THREADS", "2")
os.environ.setdefault("CT2_PACKED_GEMM", "0")

import numpy as np
import sounddevice as sd
from faster_whisper import WhisperModel
from huggingface_hub import InferenceClient

from jarvis.config import settings


class HandsFreeListener:
    """Hands-free capture with remote HF ASR and low-memory local fallback."""

    def __init__(
        self,
        on_partial: Callable[[str], None],
        on_final: Callable[[str], None],
        on_status: Callable[[str], None] | None = None,
        on_error: Callable[[str], None] | None = None,
        on_level: Callable[[float], None] | None = None,
        target_rate: int = 16000,
    ) -> None:
        self.on_partial = on_partial
        self.on_final = on_final
        self.on_status = on_status or (lambda _: None)
        self.on_error = on_error or (lambda _: None)
        self.on_level = on_level or (lambda _: None)
        self.target_rate = target_rate

        self._audio_q: queue.Queue[np.ndarray] = queue.Queue(maxsize=160)
        self._transcribe_q: queue.Queue[tuple[np.ndarray, int, bool, int] | None] = queue.Queue(maxsize=2)
        self._active = threading.Event()
        self._shutdown = threading.Event()
        self._capture_thread: threading.Thread | None = None
        self._transcribe_thread: threading.Thread | None = None
        self._warm_thread: threading.Thread | None = None
        self._stream: sd.InputStream | None = None

        self._model: WhisperModel | None = None
        self._model_lock = threading.Lock()
        self._local_model_name = settings.whisper_model or "tiny"

        self._hf_client: InferenceClient | None = None
        self._hf_failed = False

        self._input_rate = target_rate
        self._utterance_id = 0
        self._last_partial_text = ""
        self._last_error = ""

    @staticmethod
    def input_devices() -> list[dict[str, object]]:
        devices = sd.query_devices()
        result: list[dict[str, object]] = []
        for index, dev in enumerate(devices):
            channels = int(dev.get("max_input_channels", 0))
            if channels <= 0:
                continue
            result.append(
                {
                    "index": index,
                    "name": str(dev.get("name", f"Input {index}")),
                    "channels": channels,
                    "sample_rate": int(float(dev.get("default_samplerate", 16000))),
                }
            )
        return result

    def _selected_device(self) -> tuple[int | None, dict]:
        requested = getattr(settings, "audio_device", "").strip()
        devices = sd.query_devices()

        if requested:
            if requested.isdigit():
                idx = int(requested)
                dev = devices[idx]
                if int(dev.get("max_input_channels", 0)) <= 0:
                    raise RuntimeError(f"Le périphérique audio {idx} n'a aucune entrée micro.")
                return idx, dev

            lowered = requested.lower()
            for idx, dev in enumerate(devices):
                name = str(dev.get("name", ""))
                if int(dev.get("max_input_channels", 0)) > 0 and lowered in name.lower():
                    return idx, dev
            raise RuntimeError(f"Micro configuré introuvable : {requested}")

        default_input = sd.default.device[0]
        if default_input is None or int(default_input) < 0:
            raise RuntimeError("Aucun microphone par défaut n'est configuré dans Windows.")

        idx = int(default_input)
        return idx, devices[idx]

    def _prefer_huggingface(self) -> bool:
        provider = settings.stt_provider
        if provider in {"huggingface", "hf"}:
            return bool(settings.hf_token) and not self._hf_failed
        if provider == "auto":
            return bool(settings.hf_token) and not self._hf_failed
        return False

    def _ensure_hf_client(self) -> InferenceClient:
        if not settings.hf_token:
            raise RuntimeError("HF_TOKEN n'est pas configuré.")
        if self._hf_client is None:
            self._hf_client = InferenceClient(api_key=settings.hf_token)
        return self._hf_client

    def _ensure_model(self) -> WhisperModel:
        if self._model is not None:
            return self._model

        with self._model_lock:
            if self._model is None:
                self.on_status(f"WHISPER · CHARGEMENT {self._local_model_name.upper()} LOW-MEM…")
                self._model = WhisperModel(
                    self._local_model_name,
                    device="cpu",
                    compute_type=settings.whisper_compute_type,
                    cpu_threads=settings.whisper_cpu_threads,
                    num_workers=1,
                )
                self.on_status(f"WHISPER · {self._local_model_name.upper()} PRÊT")
        return self._model

    def _release_local_model(self) -> None:
        with self._model_lock:
            self._model = None
        gc.collect()

    def _warm_model(self) -> None:
        try:
            if self._prefer_huggingface():
                self.on_status("LISTENING · HF ASR PRÊT")
                return

            try:
                self._ensure_model()
            except Exception as exc:
                if self._is_memory_error(exc) and self._local_model_name != "tiny":
                    self.on_status("WHISPER · MÉMOIRE FAIBLE → FALLBACK TINY")
                    self._release_local_model()
                    self._local_model_name = "tiny"
                    self._ensure_model()
                else:
                    raise

            if self._active.is_set():
                self.on_status(f"LISTENING · WHISPER {self._local_model_name.upper()} PRÊT")
        except Exception as exc:
            self._emit_error_once(f"Impossible de charger le moteur vocal : {exc}")

    def start(self) -> None:
        if self._active.is_set():
            return

        if self._shutdown.is_set():
            raise RuntimeError("Le moteur vocal a déjà été arrêté définitivement.")

        try:
            device_index, device = self._selected_device()
            self._input_rate = max(
                8000,
                int(float(device.get("default_samplerate", self.target_rate))),
            )
            device_name = str(device.get("name", f"Micro {device_index}"))

            sd.check_input_settings(
                device=device_index,
                channels=1,
                dtype="float32",
                samplerate=self._input_rate,
            )

            self._drain_audio_queue()
            self._active.set()
            self._last_error = ""

            if self._transcribe_thread is None or not self._transcribe_thread.is_alive():
                self._transcribe_thread = threading.Thread(
                    target=self._transcribe_loop,
                    name="jarvis-stt",
                    daemon=True,
                )
                self._transcribe_thread.start()

            if self._warm_thread is None or not self._warm_thread.is_alive():
                self._warm_thread = threading.Thread(
                    target=self._warm_model,
                    name="jarvis-stt-warmup",
                    daemon=True,
                )
                self._warm_thread.start()

            blocksize = max(256, int(self._input_rate * 0.05))
            self._stream = sd.InputStream(
                device=device_index,
                samplerate=self._input_rate,
                channels=1,
                dtype="float32",
                blocksize=blocksize,
                latency="low",
                callback=self._callback,
            )
            self._stream.start()

            self._capture_thread = threading.Thread(
                target=self._capture_loop,
                name="jarvis-mic",
                daemon=True,
            )
            self._capture_thread.start()

            backend = "HF ASR" if self._prefer_huggingface() else f"WHISPER {self._local_model_name.upper()}"
            self.on_status(f"LISTENING · {device_name} · {backend}")
        except Exception:
            self._active.clear()
            self._close_stream()
            raise

    def stop(self) -> None:
        self._active.clear()
        self._close_stream()
        self.on_level(0.0)

        capture = self._capture_thread
        if (
            capture is not None
            and capture.is_alive()
            and capture is not threading.current_thread()
        ):
            capture.join(timeout=0.7)
        if capture is self._capture_thread:
            self._capture_thread = None

    def shutdown(self) -> None:
        self.stop()
        self._shutdown.set()
        self._release_local_model()
        try:
            self._transcribe_q.put_nowait(None)
        except queue.Full:
            pass

    def _close_stream(self) -> None:
        stream = self._stream
        self._stream = None
        if stream is None:
            return
        try:
            stream.stop()
        except Exception:
            pass
        try:
            stream.close()
        except Exception:
            pass

    def _drain_audio_queue(self) -> None:
        while True:
            try:
                self._audio_q.get_nowait()
            except queue.Empty:
                break

    def _callback(self, indata, frames, time_info, status) -> None:
        del frames, time_info
        if status:
            self.on_status(f"MIC · {status}")
        if not self._active.is_set():
            return

        try:
            self._audio_q.put_nowait(indata[:, 0].copy())
        except queue.Full:
            try:
                self._audio_q.get_nowait()
            except queue.Empty:
                pass
            try:
                self._audio_q.put_nowait(indata[:, 0].copy())
            except queue.Full:
                pass

    def _capture_loop(self) -> None:
        pre_roll: deque[np.ndarray] = deque(maxlen=8)
        chunks: list[np.ndarray] = []
        speech_started = False
        last_voice = time.monotonic()
        last_partial_at = 0.0
        noise_floor = 0.0035
        utterance_id = self._utterance_id

        try:
            while self._active.is_set() and not self._shutdown.is_set():
                try:
                    chunk = self._audio_q.get(timeout=0.25)
                except queue.Empty:
                    continue

                rms = float(np.sqrt(np.mean(np.square(chunk))) + 1e-9)
                level = max(0.0, min(1.0, rms / 0.075))
                self.on_level(level)

                threshold = max(0.0045, noise_floor * 2.6)
                is_voice = rms >= threshold

                if not speech_started:
                    noise_floor = noise_floor * 0.96 + min(rms, 0.02) * 0.04
                    pre_roll.append(chunk)

                    if is_voice:
                        speech_started = True
                        self._utterance_id += 1
                        utterance_id = self._utterance_id
                        chunks = list(pre_roll)
                        last_voice = time.monotonic()
                        last_partial_at = last_voice
                        self.on_status("LISTENING · VOIX DÉTECTÉE")
                    continue

                chunks.append(chunk)
                now = time.monotonic()
                if is_voice:
                    last_voice = now

                duration = sum(len(c) for c in chunks) / self._input_rate
                silence = now - last_voice

                if (
                    settings.whisper_partial_transcripts
                    and duration >= 2.2
                    and now - last_partial_at >= 2.2
                ):
                    last_partial_at = now
                    self._queue_transcription(
                        chunks,
                        final=False,
                        utterance_id=utterance_id,
                    )

                if silence >= 0.90 and duration >= 0.40:
                    self.on_status("TRANSCRIBING · PHRASE REÇUE")
                    self._queue_transcription(
                        chunks,
                        final=True,
                        utterance_id=utterance_id,
                    )
                    self._active.clear()
                    self._close_stream()
                    self.on_level(0.0)
                    return

                if duration >= 15.0:
                    self.on_status("TRANSCRIBING · SEGMENT LONG")
                    self._queue_transcription(
                        chunks,
                        final=True,
                        utterance_id=utterance_id,
                    )
                    self._active.clear()
                    self._close_stream()
                    self.on_level(0.0)
                    return
        except Exception as exc:
            self._emit_error_once(f"Erreur capture microphone : {exc}")
            self._active.clear()
            self._close_stream()

    def _queue_transcription(
        self,
        chunks: list[np.ndarray],
        *,
        final: bool,
        utterance_id: int,
    ) -> None:
        if not chunks:
            return

        audio = np.concatenate(chunks).astype(np.float32, copy=True)
        job = (audio, self._input_rate, final, utterance_id)

        if final:
            while True:
                try:
                    self._transcribe_q.get_nowait()
                except queue.Empty:
                    break
            self._transcribe_q.put(job)
            return

        try:
            self._transcribe_q.put_nowait(job)
        except queue.Full:
            try:
                self._transcribe_q.get_nowait()
            except queue.Empty:
                return
            try:
                self._transcribe_q.put_nowait(job)
            except queue.Full:
                pass

    def _resample(self, audio: np.ndarray, source_rate: int) -> np.ndarray:
        if source_rate == self.target_rate:
            return audio.astype(np.float32, copy=False)
        if audio.size <= 1:
            return audio.astype(np.float32, copy=False)

        output_size = max(
            1,
            int(round(audio.size * self.target_rate / source_rate)),
        )
        old_x = np.linspace(0.0, 1.0, num=audio.size, endpoint=False)
        new_x = np.linspace(0.0, 1.0, num=output_size, endpoint=False)
        return np.interp(new_x, old_x, audio).astype(np.float32)

    def _wav_bytes(self, audio16: np.ndarray) -> bytes:
        pcm = (
            np.clip(audio16, -1.0, 1.0) * 32767.0
        ).astype(np.int16, copy=False)

        buffer = io.BytesIO()
        with wave.open(buffer, "wb") as wav:
            wav.setnchannels(1)
            wav.setsampwidth(2)
            wav.setframerate(self.target_rate)
            wav.writeframes(pcm.tobytes())
        return buffer.getvalue()

    def _transcribe_huggingface(self, audio16: np.ndarray) -> str:
        client = self._ensure_hf_client()
        model = settings.hf_asr_model or None
        output = client.automatic_speech_recognition(
            self._wav_bytes(audio16),
            model=model,
        )

        if isinstance(output, str):
            return output.strip()
        if isinstance(output, dict):
            return str(output.get("text", "")).strip()
        return str(getattr(output, "text", "") or "").strip()

    @staticmethod
    def _is_memory_error(exc: Exception) -> bool:
        message = str(exc).lower()
        return any(
            token in message
            for token in (
                "mkl_malloc",
                "failed to allocate memory",
                "cannot allocate memory",
                "out of memory",
                "bad allocation",
                "std::bad_alloc",
            )
        )

    def _transcribe_local(self, audio16: np.ndarray) -> str:
        def run_once() -> str:
            model = self._ensure_model()
            segments, _ = model.transcribe(
                audio16,
                language=settings.language,
                beam_size=1,
                vad_filter=True,
                condition_on_previous_text=False,
                without_timestamps=True,
            )
            return " ".join(
                segment.text.strip() for segment in segments
            ).strip()

        try:
            return run_once()
        except Exception as exc:
            if not self._is_memory_error(exc) or self._local_model_name == "tiny":
                raise

            self.on_status("WHISPER · MÉMOIRE FAIBLE → FALLBACK TINY")
            self._release_local_model()
            self._local_model_name = "tiny"
            gc.collect()
            return run_once()

    def _transcribe_audio(self, audio16: np.ndarray) -> str:
        if self._prefer_huggingface():
            try:
                self.on_status("TRANSCRIBING · HUGGING FACE ASR")
                return self._transcribe_huggingface(audio16)
            except Exception as exc:
                self._hf_failed = True
                self.on_status(
                    f"HF ASR INDISPONIBLE · FALLBACK LOCAL ({type(exc).__name__})"
                )

        self.on_status(
            f"TRANSCRIBING · WHISPER {self._local_model_name.upper()} LOW-MEM"
        )
        return self._transcribe_local(audio16)

    def _emit_error_once(self, message: str) -> None:
        if message == self._last_error:
            return
        self._last_error = message
        self.on_error(message)

    def _transcribe_loop(self) -> None:
        while not self._shutdown.is_set():
            try:
                job = self._transcribe_q.get(timeout=0.4)
            except queue.Empty:
                continue

            if job is None:
                return

            audio, source_rate, final, utterance_id = job

            try:
                audio16 = self._resample(audio, source_rate)
                text = self._transcribe_audio(audio16)

                if not text:
                    if final:
                        self.on_status("LISTENING · AUCUNE PAROLE RECONNUE")
                    continue

                if final:
                    self._last_partial_text = ""
                    self._last_error = ""
                    self.on_final(text)
                elif (
                    utterance_id == self._utterance_id
                    and text != self._last_partial_text
                ):
                    self._last_partial_text = text
                    self.on_partial(text)

            except Exception as exc:
                if self._is_memory_error(exc):
                    self._active.clear()
                    self._close_stream()
                    self._release_local_model()
                    self._emit_error_once(
                        "Mémoire insuffisante pour le STT local. "
                        "Configure HF_TOKEN pour utiliser Hugging Face ASR, "
                        "ou garde JARVIS_WHISPER_MODEL=tiny."
                    )
                else:
                    self._emit_error_once(
                        f"Erreur transcription vocale : {exc}"
                    )
