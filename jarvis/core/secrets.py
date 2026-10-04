from __future__ import annotations

import os
from typing import Final


_SERVICE: Final = "J.A.R.V.I.S."


class SecretStore:
    """Windows Credential Manager via keyring, with no silent plaintext fallback."""

    def __init__(self) -> None:
        try:
            import keyring  # type: ignore
        except Exception as exc:
            raise RuntimeError("Le package keyring n'est pas disponible.") from exc
        self._keyring = keyring

    def get(self, name: str) -> str:
        value = self._keyring.get_password(_SERVICE, name.strip())
        return str(value or "")

    def set(self, name: str, value: str) -> None:
        clean = name.strip()
        if not clean:
            raise ValueError("name est requis.")
        self._keyring.set_password(_SERVICE, clean, value)

    def delete(self, name: str) -> None:
        clean = name.strip()
        try:
            self._keyring.delete_password(_SERVICE, clean)
        except Exception:
            pass

    @staticmethod
    def from_env_or_store(env_name: str, secret_name: str) -> str:
        direct = os.getenv(env_name, "").strip()
        if direct:
            return direct
        try:
            return SecretStore().get(secret_name)
        except Exception:
            return ""
