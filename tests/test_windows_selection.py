from __future__ import annotations

import unittest

from jarvis.tools.windows import _select_window


class WindowSelectionTests(unittest.TestCase):
    def setUp(self) -> None:
        self.windows = [
            {"hwnd": 1, "title": "Notepad - notes.txt"},
            {"hwnd": 2, "title": "Notepad - todo.txt"},
            {"hwnd": 3, "title": "Calculator"},
        ]

    def test_exact_title_wins(self) -> None:
        item = _select_window(self.windows, "Calculator")
        self.assertEqual(item["hwnd"], 3)

    def test_unique_partial_title_is_allowed(self) -> None:
        item = _select_window(self.windows, "todo.txt")
        self.assertEqual(item["hwnd"], 2)

    def test_ambiguous_partial_title_is_rejected(self) -> None:
        with self.assertRaisesRegex(ValueError, "ambigu"):
            _select_window(self.windows, "Notepad")

    def test_missing_title_is_rejected(self) -> None:
        with self.assertRaisesRegex(ValueError, "introuvable"):
            _select_window(self.windows, "Browser")


if __name__ == "__main__":
    unittest.main()
