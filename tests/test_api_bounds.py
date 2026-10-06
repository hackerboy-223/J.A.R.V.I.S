from __future__ import annotations

import unittest

from fastapi import HTTPException

from jarvis.api import (
    _MAX_API_MESSAGES,
    _MAX_API_TOTAL_TEXT_CHARS,
    _validate_chat_messages,
)


class ApiBoundsTests(unittest.TestCase):
    def test_normal_chat_messages_are_accepted(self) -> None:
        messages = [
            {"role": "system", "content": "Tu es JARVIS."},
            {"role": "user", "content": "Bonjour"},
        ]
        self.assertEqual(_validate_chat_messages(messages), messages)

    def test_too_many_messages_are_rejected(self) -> None:
        messages = [
            {"role": "user", "content": "x"}
            for _ in range(_MAX_API_MESSAGES + 1)
        ]
        with self.assertRaises(HTTPException) as ctx:
            _validate_chat_messages(messages)
        self.assertEqual(ctx.exception.status_code, 413)

    def test_oversized_total_text_is_rejected(self) -> None:
        messages = [
            {
                "role": "user",
                "content": "x" * (_MAX_API_TOTAL_TEXT_CHARS + 1),
            }
        ]
        with self.assertRaises(HTTPException) as ctx:
            _validate_chat_messages(messages)
        self.assertEqual(ctx.exception.status_code, 413)

    def test_unknown_role_is_rejected(self) -> None:
        with self.assertRaises(HTTPException) as ctx:
            _validate_chat_messages([{"role": "root", "content": "x"}])
        self.assertEqual(ctx.exception.status_code, 400)

    def test_invalid_multipart_shape_is_rejected(self) -> None:
        with self.assertRaises(HTTPException) as ctx:
            _validate_chat_messages(
                [{"role": "user", "content": ["not-an-object"]}]
            )
        self.assertEqual(ctx.exception.status_code, 400)


if __name__ == "__main__":
    unittest.main()
