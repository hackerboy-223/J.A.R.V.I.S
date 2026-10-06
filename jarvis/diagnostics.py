from __future__ import annotations

import importlib
import json
import os
from pathlib import Path
import platform
import sys
from typing import Any

from jarvis.config import DATA_DIR, IS_FROZEN
from jarvis.core.logging_setup import CRASH_DIR, LOG_FILE
from jarvis.version import __version__


def _check(name: str, ok: bool, detail: str, *, required: bool = True) -> dict[str, Any]:
    return {
        "name": name,
        "ok": bool(ok),
        "required": bool(required),
        "detail": str(detail),
    }


def _import_check(module_name: str, *, required: bool = True) -> dict[str, Any]:
    try:
        module = importlib.import_module(module_name)
        module_version = getattr(module, "__version__", "")
        detail = module_name + (f" {module_version}" if module_version else "")
        return _check(f"import:{module_name}", True, detail, required=required)
    except Exception as exc:
        return _check(
            f"import:{module_name}",
            False,
            f"{type(exc).__name__}: {exc}",
            required=required,
        )


def package_diagnostics() -> dict[str, Any]:
    """Offline checks that must pass inside the packaged Windows application."""
    checks: list[dict[str, Any]] = []

    for module_name in (
        "PySide6",
        "sounddevice",
        "_sounddevice_data",
        "vosk",
        "pyttsx3",
        "mcp",
        "keyring",
    ):
        checks.append(_import_check(module_name))

    try:
        import sounddevice as sd

        portaudio = sd.get_portaudio_version()
        checks.append(_check("portaudio", True, str(portaudio)))
    except Exception as exc:
        checks.append(
            _check("portaudio", False, f"{type(exc).__name__}: {exc}")
        )

    if platform.system() == "Windows":
        try:
            import _sounddevice_data

            roots = [Path(item) for item in _sounddevice_data.__path__]
            dlls = [
                dll
                for root in roots
                for dll in (root / "portaudio-binaries").glob("*.dll")
            ]
            checks.append(
                _check(
                    "portaudio-dll",
                    bool(dlls),
                    ", ".join(dll.name for dll in dlls) or "DLL PortAudio absente",
                )
            )
        except Exception as exc:
            checks.append(
                _check("portaudio-dll", False, f"{type(exc).__name__}: {exc}")
            )

    try:
        DATA_DIR.mkdir(parents=True, exist_ok=True)
        probe = DATA_DIR / ".write-test"
        probe.write_text("ok", encoding="utf-8")
        probe.unlink(missing_ok=True)
        checks.append(_check("data-dir", True, str(DATA_DIR)))
    except Exception as exc:
        checks.append(
            _check("data-dir", False, f"{type(exc).__name__}: {exc}")
        )

    required_checks = [item for item in checks if item["required"]]
    healthy = all(item["ok"] for item in required_checks)

    return {
        "healthy": healthy,
        "version": __version__,
        "frozen": IS_FROZEN,
        "python": platform.python_version(),
        "platform": platform.platform(),
        "executable": sys.executable,
        "data_dir": str(DATA_DIR),
        "log_file": str(LOG_FILE),
        "crash_dir": str(CRASH_DIR),
        "checks": checks,
    }


def _supported_rate(sd, device: int, info: dict[str, Any]) -> int | None:
    default_rate = int(float(info.get("default_samplerate", 16000) or 16000))
    attempted: list[int] = []
    for rate in (16000, default_rate, 48000, 44100):
        if rate <= 0 or rate in attempted:
            continue
        attempted.append(rate)
        try:
            sd.check_input_settings(
                device=device,
                channels=1,
                dtype="int16",
                samplerate=rate,
            )
            return rate
        except Exception:
            continue
    return None


def voice_diagnostics() -> dict[str, Any]:
    """Probe microphone/PortAudio without downloading or loading a Vosk model."""
    result = package_diagnostics()
    checks = list(result["checks"])
    inputs: list[dict[str, Any]] = []

    try:
        import sounddevice as sd

        devices = sd.query_devices()
        for index, raw in enumerate(devices):
            info = dict(raw)
            channels = int(info.get("max_input_channels", 0) or 0)
            if channels <= 0:
                continue
            inputs.append(
                {
                    "index": index,
                    "name": str(info.get("name", f"Input {index}")),
                    "channels": channels,
                    "default_samplerate": int(
                        float(info.get("default_samplerate", 16000) or 16000)
                    ),
                    "supported_samplerate": _supported_rate(sd, index, info),
                }
            )

        default_input = sd.default.device[0]
        checks.append(
            _check(
                "microphone",
                bool(inputs),
                (
                    f"{len(inputs)} entrée(s), défaut={default_input}"
                    if inputs
                    else "Aucune entrée microphone détectée"
                ),
            )
        )
        checks.append(
            _check(
                "microphone-format",
                any(item["supported_samplerate"] for item in inputs),
                "format PCM int16 compatible trouvé"
                if any(item["supported_samplerate"] for item in inputs)
                else "aucun format PCM int16 compatible",
            )
        )
    except Exception as exc:
        checks.append(
            _check("microphone", False, f"{type(exc).__name__}: {exc}")
        )

    result["checks"] = checks
    result["inputs"] = inputs
    result["healthy"] = all(
        item["ok"] for item in checks if item.get("required", True)
    )
    return result


def write_diagnostic_report(name: str, result: dict[str, Any]) -> Path:
    reports = (DATA_DIR / "logs" / "diagnostics").resolve()
    reports.mkdir(parents=True, exist_ok=True)
    safe_name = "".join(
        ch for ch in str(name or "diagnostic").lower()
        if ch.isalnum() or ch in {"-", "_"}
    ) or "diagnostic"
    path = reports / f"{safe_name}.json"
    path.write_text(
        json.dumps(result, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    return path
