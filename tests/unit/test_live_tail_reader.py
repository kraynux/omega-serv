"""Teste LiveTailReader contre un vrai fichier temporaire (pas de mock) -
seek/lecture incrementale, rotation/troncature."""
from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from omega_serv.infrastructure.logging.live_tail_reader import LiveTailReader


class TestLiveTailReader(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.path = Path(self._tmp.name) / "test.log"

    def tearDown(self):
        self._tmp.cleanup()

    def test_missing_file_returns_empty_list(self):
        reader = LiveTailReader(self.path)
        self.assertEqual(reader.read_new_lines(), [])

    def test_starts_from_current_end_ignores_preexisting_content(self):
        self.path.write_text("old line 1\nold line 2\n")
        reader = LiveTailReader(self.path)
        self.assertEqual(reader.read_new_lines(), [])

    def test_reads_only_newly_appended_lines(self):
        self.path.write_text("old line\n")
        reader = LiveTailReader(self.path)
        with self.path.open("a", encoding="utf-8") as f:
            f.write("new line 1\nnew line 2\n")
        self.assertEqual(reader.read_new_lines(), ["new line 1", "new line 2"])
        self.assertEqual(reader.read_new_lines(), [])

    def test_multiple_polls_only_return_new_content_each_time(self):
        self.path.write_text("")
        reader = LiveTailReader(self.path)
        with self.path.open("a", encoding="utf-8") as f:
            f.write("first\n")
        self.assertEqual(reader.read_new_lines(), ["first"])
        with self.path.open("a", encoding="utf-8") as f:
            f.write("second\n")
        self.assertEqual(reader.read_new_lines(), ["second"])

    def test_truncated_file_restarts_from_beginning(self):
        self.path.write_text("a" * 200 + "\n")
        reader = LiveTailReader(self.path)
        with self.path.open("a", encoding="utf-8") as f:
            f.write("appended\n")
        self.assertEqual(reader.read_new_lines(), ["appended"])
        self.path.write_text("short\n")
        self.assertEqual(reader.read_new_lines(), ["short"])


if __name__ == "__main__":
    unittest.main()
