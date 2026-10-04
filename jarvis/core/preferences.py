from __future__ import annotations

from typing import Any

from PySide6.QtCore import QSettings

try:
    import keyring
except Exception:  # pragma: no cover - optional backend failure
    keyring = None


_ORGANIZATION = "HACKERBOY"
_APPLICATION = "JARVIS"
_SECRET_SERVICE = "J.A.R.V.I.S."


class Preferences:
    def __init__(self) -> None:
        self._settings = QSettings(_ORGANIZATION, _APPLICATION)

    def get(self, key: str, default: Any = None) -> Any:
        return self._settings.value(key, default)

    def set(self, key: str, value: Any) -> None:
        self._settings.setValue(key, value)
        self._settings.sync()

    def get_bool(self, key: str, default: bool = False) -> bool:
        value = self.get(key, default)
        if isinstance(value, bool):
            return value
        return str(value).strip().lower() in {"1", "true", "yes", "on"}

    @property
    def first_run_complete(self) -> bool:
        return self.get_bool("onboarding/complete", False)

    def complete_first_run(self) -> None:
        self.set("onboarding/complete", True)


class SecretStore:
    """OS credential storage. Never falls back to plaintext."""

    def available(self) -> bool:
        return keyring is not None

    def set(self, name: str, value: str) -> None:
        if keyring is None:
            raise RuntimeError("Aucun backend keyring sécurisé n'est disponible.")
        if not value:
            self.delete(name)
            return
        keyring.set_password(_SECRET_SERVICE, name, value)

    def get(self, name: str) -> str | None:
        if keyring is None:
            return None
        return keyring.get_password(_SECRET_SERVICE, name)

    def delete(self, name: str) -> None:
        if keyring is None:
            return
        try:
            keyring.delete_password(_SECRET_SERVICE, name)
        except Exception:
            pass
