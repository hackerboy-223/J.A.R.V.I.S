from __future__ import annotations

import os
import unittest
from unittest.mock import patch

from jarvis.core.logging_setup import _redact


class LoggingRedactionTests(unittest.TestCase):
    def test_redacts_bearer_tokens(self) -> None:
        value = "Bearer abcdefghijklmnopqrstuvwxyz"
        clean = _redact(value)
        self.assertNotIn("abcdefghijklmnopqrstuvwxyz", clean)
        self.assertIn("REDACTED", clean)

    def test_redacts_known_provider_key_prefixes(self) -> None:
        values = [
            "sk-or-v1-1234567890abcdefghijk",
            "hf_1234567890abcdefghijk",
            "gsk_1234567890abcdefghijk",
            "exa_1234567890abcdefghijk",
        ]
        for value in values:
            with self.subTest(value=value[:5]):
                self.assertNotIn(value, _redact(f"token={value}"))

    def test_redacts_secret_environment_values(self) -> None:
        secret = "custom-secret-value-987654"
        with patch.dict(os.environ, {"MY_PRIVATE_API_KEY": secret}, clear=False):
            clean = _redact(f"request failed with {secret}")
        self.assertNotIn(secret, clean)
        self.assertIn("REDACTED", clean)

    def test_keeps_normal_diagnostics_readable(self) -> None:
        text = "PortAudio 19.7.0 · microphone 48000 Hz"
        self.assertEqual(_redact(text), text)


if __name__ == "__main__":
    unittest.main()
