from __future__ import annotations

import contextlib
import io
import json
import unittest
from unittest.mock import patch

from jarvis.sandbox_runner import run_sandbox_runner


class SandboxRunnerTests(unittest.TestCase):
    def test_runs_restricted_code_from_stdin(self) -> None:
        output = io.StringIO()
        with (
            patch("sys.stdin", io.StringIO(json.dumps({"code": "print(sum([4, 5]))"}))),
            contextlib.redirect_stdout(output),
        ):
            result = run_sandbox_runner()

        self.assertEqual(result, 0)
        self.assertEqual(output.getvalue().strip(), "9")

    def test_rejects_imports_outside_allowlist(self) -> None:
        output = io.StringIO()
        with (
            patch("sys.stdin", io.StringIO(json.dumps({"code": "import os"}))),
            contextlib.redirect_stderr(output),
        ):
            result = run_sandbox_runner()

        self.assertEqual(result, 1)
        self.assertIn("Import interdit", output.getvalue())


if __name__ == "__main__":
    unittest.main()