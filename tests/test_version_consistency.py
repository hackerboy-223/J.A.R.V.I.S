from __future__ import annotations

import json
import re
import tomllib
import unittest
from pathlib import Path

from jarvis.version import FALLBACK_VERSION


ROOT = Path(__file__).resolve().parents[1]


class VersionConsistencyTests(unittest.TestCase):
    def test_product_versions_match(self) -> None:
        with (ROOT / "pyproject.toml").open("rb") as handle:
            python_version = str(tomllib.load(handle)["project"]["version"])

        package = json.loads((ROOT / "package.json").read_text(encoding="utf-8"))
        web_version = str(package["version"])

        installer = (ROOT / "packaging" / "JARVIS.iss").read_text(encoding="utf-8")
        match = re.search(r'#define\s+MyAppVersion\s+"([^"]+)"', installer)
        self.assertIsNotNone(match)
        installer_version = str(match.group(1))

        self.assertEqual(FALLBACK_VERSION, python_version)
        self.assertEqual(web_version, python_version)
        self.assertEqual(installer_version, python_version)

    def test_distributed_pc_control_defaults_fail_closed(self) -> None:
        sample = (ROOT / ".env.python.example").read_text(encoding="utf-8")
        self.assertIn('JARVIS_ALLOW_PC_CONTROL="false"', sample)
        self.assertIn('JARVIS_CONFIRM_SAFE_PC_ACTIONS="true"', sample)


if __name__ == "__main__":
    unittest.main()
