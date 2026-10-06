from __future__ import annotations

import unittest

from jarvis.core.network import (
    is_loopback_url,
    service_endpoint,
    validate_service_base_url,
)


class NetworkPolicyTests(unittest.TestCase):
    def test_loopback_http_is_allowed(self) -> None:
        self.assertTrue(is_loopback_url("http://127.0.0.1:11434/v1"))
        self.assertTrue(is_loopback_url("http://localhost:8000"))
        self.assertEqual(
            validate_service_base_url("http://127.0.0.1:11434/v1"),
            "http://127.0.0.1:11434/v1",
        )

    def test_remote_https_is_allowed(self) -> None:
        self.assertEqual(
            validate_service_base_url("https://api.example.com/v1"),
            "https://api.example.com/v1",
        )

    def test_remote_plain_http_is_rejected(self) -> None:
        with self.assertRaisesRegex(ValueError, "HTTPS"):
            validate_service_base_url("http://api.example.com/v1")

    def test_credentials_in_url_are_rejected(self) -> None:
        with self.assertRaisesRegex(ValueError, "credentials"):
            validate_service_base_url("https://user:secret@example.com/v1")

    def test_endpoint_join_is_predictable(self) -> None:
        self.assertEqual(
            service_endpoint("https://api.example.com/v1/", "/chat/completions"),
            "https://api.example.com/v1/chat/completions",
        )


if __name__ == "__main__":
    unittest.main()
