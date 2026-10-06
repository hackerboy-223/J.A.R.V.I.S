from __future__ import annotations

import unittest

from jarvis.core.updater import _is_newer, _parse_version, _trusted_release_url


class UpdaterSecurityTests(unittest.TestCase):
    def test_version_parser_accepts_normal_release_tags(self) -> None:
        self.assertEqual(_parse_version("v0.2.0"), (0, 2, 0))
        self.assertEqual(_parse_version("1.4.7"), (1, 4, 7))

    def test_invalid_versions_are_not_considered_newer(self) -> None:
        self.assertIsNone(_parse_version("latest"))
        self.assertFalse(_is_newer("latest", "0.2.0"))
        self.assertFalse(_is_newer("v0.2.0", "0.2.0"))
        self.assertFalse(_is_newer("v0.1.9", "0.2.0"))
        self.assertTrue(_is_newer("v0.2.1", "0.2.0"))

    def test_only_official_release_assets_are_trusted(self) -> None:
        good = (
            "https://github.com/hackerboy-223/J.A.R.V.I.S/"
            "releases/download/v0.2.0/JARVIS-Setup-x64.exe"
        )
        self.assertTrue(_trusted_release_url(good))
        self.assertFalse(
            _trusted_release_url(
                "http://github.com/hackerboy-223/J.A.R.V.I.S/"
                "releases/download/v0.2.0/JARVIS-Setup-x64.exe"
            )
        )
        self.assertFalse(
            _trusted_release_url(
                "https://github.com/other/repo/releases/download/v0.2.0/setup.exe"
            )
        )
        self.assertFalse(
            _trusted_release_url(
                "https://github.com.evil.example/hackerboy-223/J.A.R.V.I.S/"
                "releases/download/v0.2.0/setup.exe"
            )
        )


if __name__ == "__main__":
    unittest.main()
