from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from jarvis.core.file_index import FileIndex
from jarvis.core.undo import UndoManager


class FileIndexUndoTests(unittest.TestCase):
    def test_file_index_searches_names(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir) / "workspace"
            root.mkdir()
            (root / "kalanmali-roadmap.md").write_text("demo", encoding="utf-8")
            index = FileIndex(Path(temp_dir) / "index.db")
            result = index.rebuild(root)
            self.assertEqual(result["indexed"], 1)
            matches = index.search("kalanmali")
            self.assertTrue(matches)
            self.assertEqual(matches[0]["name"], "kalanmali-roadmap.md")

    def test_undo_restores_unchanged_post_patch_file(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "demo.txt"
            path.write_text("before", encoding="utf-8")
            undo = UndoManager()
            path.write_text("after", encoding="utf-8")
            undo_id = undo.record(path, "before", "after")
            result = undo.undo(undo_id)
            self.assertEqual(result["undone"], undo_id)
            self.assertEqual(path.read_text(encoding="utf-8"), "before")


if __name__ == "__main__":
    unittest.main()
