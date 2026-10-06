from __future__ import annotations

import unittest

from jarvis.diagnostics import _supported_rate


class _FakeSoundDevice:
    def __init__(self, accepted: set[int]) -> None:
        self.accepted = accepted
        self.calls: list[int] = []

    def check_input_settings(self, *, device, channels, dtype, samplerate):
        del device, channels, dtype
        self.calls.append(int(samplerate))
        if int(samplerate) not in self.accepted:
            raise RuntimeError("unsupported")


class VoiceDiagnosticsTests(unittest.TestCase):
    def test_prefers_16khz_when_supported(self) -> None:
        sd = _FakeSoundDevice({16000, 48000})
        rate = _supported_rate(sd, 2, {"default_samplerate": 48000})
        self.assertEqual(rate, 16000)
        self.assertEqual(sd.calls[0], 16000)

    def test_falls_back_to_device_default_rate(self) -> None:
        sd = _FakeSoundDevice({48000})
        rate = _supported_rate(sd, 1, {"default_samplerate": 48000})
        self.assertEqual(rate, 48000)
        self.assertEqual(sd.calls[:2], [16000, 48000])

    def test_returns_none_when_no_candidate_works(self) -> None:
        sd = _FakeSoundDevice(set())
        rate = _supported_rate(sd, 0, {"default_samplerate": 32000})
        self.assertIsNone(rate)


if __name__ == "__main__":
    unittest.main()
