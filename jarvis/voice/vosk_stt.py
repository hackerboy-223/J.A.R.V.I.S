from __future__ import annotations

import json
import queue
import threading
import time
import zipfile
from pathlib import Path
from collections.abc import Callable

import httpx
import sounddevice as sd
from vosk import KaldiRecognizer, Model, SetLogLevel

from jarvis.config import DATA_DIR, settings


VOSK_FR_MODEL_NAME = "vosk-model-small-fr-0.22"
VOSK_FR_MODEL_URL = (
    "https://alphacephei.com/vosk/models/"
    "vosk-model-small-fr-0.22.zip"
)


class VoskHandsFreeListener:
    """Low-memory streaming French STT for always-on desktop voice."""

    def __init__(
        self,
        on_partial: Callable[[str], None],
        on_final: Callable[[str], None],
        on_status: Callable[[str], None] | None = None,
        on_error: Callable[[str], None] | None = None,
        on_level: Callable[[float], None] | None = None,
    ) -> None:
        self.on_partial = on_partial
        self.on_final = on_final
        self.on_status = on_status or (lambda _: None)
        self.on_error = on_error or (lambda _: None)
        self.on_level = on_level or (lambda _: None)

        self.sample_rate = 16000
        self._active = threading.Event()
        self._shutdown = threading.Event()
        self._audio_q: queue.Queue[bytes] = queue.Queue(maxsize=120)
        self._stream: sd.RawInputStream | None = None
        self._thread: threading.Thread | None = None
        self._model: Model | None = None
        self._last_partial = ""
        self._last_voice_at = time.monotonic()

        SetLogLevel(-1)

    @staticmethod
    def input_devices() -> list[dict[str, object]]:
        devices = sd.query_devices()
        result = []
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

    def _selected_device(self) -> int | None:
        requested = settings.audio_device.strip()
        devices = sd.query_devices()

        if requested:
            if requested.isdigit():
                idx = int(requested)
                if int(devices[idx].get("max_input_channels", 0)) <= 0:
                    raise RuntimeError("Le périphérique choisi n'a pas d'entrée micro.")
                return idx

            lowered = requested.lower()
            for idx, dev in enumerate(devices):
                name = str(dev.get("name", ""))
                if int(dev.get("max_input_channels", 0)) > 0 and lowered in name.lower():
                    return idx
            raise RuntimeError(f"Micro configuré introuvable : {requested}")

        default_input = sd.default.device[0]
        if default_input is None or int(default_input) < 0:
            raise RuntimeError("Aucun microphone Windows par défaut n'est configuré.")
        return int(default_input)

    def _model_path(self) -> Path:
        custom = settings.vosk_model_path.strip()
        if custom:
            return Path(custom).expanduser().resolve()
        return DATA_DIR / "models" / VOSK_FR_MODEL_NAME

    def _ensure_model_files(self) -> Path:
        target = self._model_path()
        if target.exists():
            return target

        if settings.vosk_model_path.strip():
            raise RuntimeError(f"Modèle Vosk introuvable : {target}")

        models_dir = DATA_DIR / "models"
        models_dir.mkdir(parents=True, exist_ok=True)
        archive = models_dir / f"{VOSK_FR_MODEL_NAME}.zip"

        self.on_status("VOSK · TÉLÉCHARGEMENT MODÈLE FRANÇAIS…")
        with httpx.stream("GET", VOSK_FR_MODEL_URL, timeout=90, follow_redirects=True) as response:
            response.raise_for_status()
            with archive.open("wb") as handle:
                for chunk in response.iter_bytes(chunk_size=1024 * 256):
                    handle.write(chunk)

        self.on_status("VOSK · INSTALLATION DU MODÈLE…")
        with zipfile.ZipFile(archive) as zf:
            zf.extractall(models_dir)

        try:
            archive.unlink()
        except OSError:
            pass

        if not target.exists():
            raise RuntimeError("Le modèle Vosk a été téléchargé mais son dossier est introuvable.")
        return target

    def _ensure_model(self) -> Model:
        if self._model is None:
            path = self._ensure_model_files()
            self.on_status("VOSK · CHARGEMENT LOW-MEM…")
            self._model = Model(str(path))
            self.on_status("VOSK · PRÊT")
        return self._model

    def start(self) -> None:
        if self._active.is_set():
            return
        if self._shutdown.is_set():
            raise RuntimeError("Le moteur vocal est déjà arrêté.")

        device = self._selected_device()
        model = self._ensure_model()

        self._drain_queue()
        self._active.set()
        self._last_partial = ""

        recognizer = KaldiRecognizer(model, self.sample_rate)
        recognizer.SetWords(False)

        self._stream = sd.RawInputStream(
            samplerate=self.sample_rate,
            blocksize=4000,
            device=device,
            dtype="int16",
            channels=1,
            callback=self._callback,
        )
        self._stream.start()

        self._thread = threading.Thread(
            target=self._loop,
            args=(recognizer,),
            name="jarvis-vosk",
            daemon=True,
        )
        self._thread.start()

        device_name = str(sd.query_devices(device).get("name", f"Micro {device}"))
        self.on_status(f"LISTENING · {device_name} · VOSK FR")

    def stop(self) -> None:
        self._active.clear()
        stream = self._stream
        self._stream = None
        if stream is not None:
            try:
                stream.stop()
            except Exception:
                pass
            try:
                stream.close()
            except Exception:
                pass
        self.on_level(0.0)

    def shutdown(self) -> None:
        self.stop()
        self._shutdown.set()

    def _drain_queue(self) -> None:
        while True:
            try:
                self._audio_q.get_nowait()
            except queue.Empty:
                return

    def _callback(self, indata, frames, time_info, status) -> None:
        del frames, time_info
        if status:
            self.on_status(f"MIC · {status}")
        if not self._active.is_set():
            return

        raw = bytes(indata)
        # int16 mono approximate live energy without numpy allocation.
        if len(raw) >= 2:
            sample_count = len(raw) // 2
            view = memoryview(raw).cast("h")
            stride = max(1, sample_count // 100)
            peak = max((abs(view[i]) for i in range(0, sample_count, stride)), default=0)
            self.on_level(min(1.0, peak / 12000.0))

        try:
            self._audio_q.put_nowait(raw)
        except queue.Full:
            try:
                self._audio_q.get_nowait()
                self._audio_q.put_nowait(raw)
            except queue.Empty:
                pass

    def _loop(self, recognizer: KaldiRecognizer) -> None:
        try:
            while self._active.is_set() and not self._shutdown.is_set():
                try:
                    data = self._audio_q.get(timeout=0.25)
                except queue.Empty:
                    continue

                if recognizer.AcceptWaveform(data):
                    payload = json.loads(recognizer.Result())
                    text = str(payload.get("text", "")).strip()
                    if not text:
                        continue

                    self.on_status("TRANSCRIBING · PHRASE REÇUE")
                    self.stop()
                    self.on_final(text)
                    return

                payload = json.loads(recognizer.PartialResult())
                partial = str(payload.get("partial", "")).strip()
                if partial and partial != self._last_partial:
                    self._last_partial = partial
                    self.on_partial(partial)
        except Exception as exc:
            self.stop()
            self.on_error(f"Erreur Vosk : {exc}")
