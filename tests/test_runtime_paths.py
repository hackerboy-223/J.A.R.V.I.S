from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from jarvis.paths import resolve_data_dir


class ResolveDataDirTests(unittest.TestCase):
    def test_development_keeps_repository_data_directory(self) -> None:
        root = Path("/tmp/jarvis-source")
        self.assertEqual(
            resolve_data_dir(
                root=root,
                environ={},
                is_frozen=False,
                platform_name="win32",
                home=Path("/users/test"),
            ),
            root / "data",
        )

    def test_packaged_windows_uses_local_app_data(self) -> None:
        local_app_data = Path("/users/test/AppData/Local")
        self.assertEqual(
            resolve_data_dir(
                root=Path("/program files/JARVIS"),
                environ={"LOCALAPPDATA": str(local_app_data)},
                is_frozen=True,
                platform_name="win32",
                home=Path("/users/test"),
            ),
            local_app_data / "JARVIS",
        )

    def test_packaged_windows_falls_back_to_roaming_app_data(self) -> None:
        roaming_app_data = Path("/users/test/AppData/Roaming")
        self.assertEqual(
            resolve_data_dir(
                root=Path("/program files/JARVIS"),
                environ={"APPDATA": str(roaming_app_data)},
                is_frozen=True,
                platform_name="win32",
                home=Path("/users/test"),
            ),
            roaming_app_data / "JARVIS",
        )

    def test_explicit_data_directory_takes_precedence(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            custom = Path(temp_dir) / "jarvis-data"
            self.assertEqual(
                resolve_data_dir(
                    root=Path("/source"),
                    environ={"JARVIS_DATA_DIR": str(custom)},
                    is_frozen=True,
                    platform_name="win32",
                    home=Path("/users/test"),
                ),
                custom,
            )


if __name__ == "__main__":
    unittest.main()