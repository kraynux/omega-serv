"""Volume envoye depuis le demarrage, lu dans l'access log (ecran Etat & Ressources, 2026-11-05)."""
from __future__ import annotations

import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path

from omega_serv.infrastructure.logging import access_log_volume
from omega_serv.infrastructure.logging.access_log_volume import sent_bytes_since

_BASE = datetime(2026, 11, 1, tzinfo=timezone.utc)


def _line(second: int, size: int) -> str:
    stamp = (_BASE + timedelta(seconds=second)).strftime("%d/%b/%Y:%H:%M:%S +0000")
    return f'1.2.3.4 - - [{stamp}] "GET /x HTTP/1.1" 200 {size} "-" "ua"\n'


class TestSentBytesSince(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.path = Path(self._tmp.name) / "access.log"
        self._search_stop = access_log_volume._SEARCH_STOP
        access_log_volume._SEARCH_STOP = 256  # petit fichier : la dichotomie travaille vraiment

    def tearDown(self):
        access_log_volume._SEARCH_STOP = self._search_stop
        self._tmp.cleanup()

    def test_only_lines_since_the_start_are_counted(self):
        self.path.write_text("".join(_line(i, 10) for i in range(2000)))
        total, offset = sent_bytes_since(self.path, _BASE + timedelta(seconds=1500))
        self.assertEqual(total, 500 * 10)
        self.assertEqual(offset, self.path.stat().st_size)

    def test_next_call_reads_only_new_complete_lines(self):
        self.path.write_text("".join(_line(i, 10) for i in range(100)))
        _total, offset = sent_bytes_since(self.path, _BASE)
        with self.path.open("a") as handle:
            handle.write(_line(100, 7) + '1.2.3.4 - - [partielle')
        added, offset = sent_bytes_since(self.path, _BASE, offset)
        self.assertEqual(added, 7)
        with self.path.open("a") as handle:
            handle.write(' coupee"\n' + _line(101, 5))
        self.assertEqual(sent_bytes_since(self.path, _BASE, offset)[0], 5)

    def test_rotated_file_is_read_again_from_the_start_of_the_period(self):
        self.path.write_text("".join(_line(i, 10) for i in range(100)))
        _total, offset = sent_bytes_since(self.path, _BASE)
        self.path.write_text(_line(200, 3))
        self.assertEqual(sent_bytes_since(self.path, _BASE, offset)[0], 3)

    def test_missing_file(self):
        self.assertEqual(sent_bytes_since(self.path, _BASE), (0, 0))


if __name__ == "__main__":
    unittest.main()
