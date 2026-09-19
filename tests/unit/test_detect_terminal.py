import unittest

from omega_lib.terminal.models import TerminalSignals

from omega_serv.application.terminal.detect_terminal import detect_terminal


class _FakeTerminalDetector:
    def __init__(self, signals):
        self._signals = signals

    def detect(self):
        return self._signals


class TestDetectTerminal(unittest.TestCase):
    def test_delegates_to_detector_and_resolves_profile(self):
        signals = TerminalSignals(family="ghostty", columns=120, rows=40)
        detector = _FakeTerminalDetector(signals)
        result = detect_terminal(terminal_detector=detector)
        self.assertEqual(result.signals, signals)
        self.assertIsNotNone(result.render_profile)


if __name__ == "__main__":
    unittest.main()
