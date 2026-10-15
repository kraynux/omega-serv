"""Teste LogsMaintenance.remove_ip contre un vrai fichier temporaire."""
from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from omega_serv.infrastructure.logging.logs_maintenance import LogsMaintenance

_LINE_A = '1.1.1.1 - - [08/Sep/2026:10:00:00 +0000] "GET / HTTP/1.1" 200 10 "-" "curl"\n'
_LINE_B = '2.2.2.2 - - [08/Sep/2026:10:01:00 +0000] "GET /a HTTP/1.1" 200 10 "-" "curl"\n'


class TestLogsMaintenance(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.path = Path(self._tmp.name) / "access.log"
        self.maintenance = LogsMaintenance()

    def tearDown(self):
        self._tmp.cleanup()

    def test_missing_file_returns_zero(self):
        self.assertEqual(self.maintenance.remove_ip("1.1.1.1", self.path), 0)

    def test_removes_only_matching_ip_lines(self):
        self.path.write_text(_LINE_A + _LINE_B + _LINE_A)
        removed = self.maintenance.remove_ip("1.1.1.1", self.path)
        self.assertEqual(removed, 2)
        self.assertEqual(self.path.read_text(), _LINE_B)

    def test_no_match_leaves_file_unchanged_and_returns_zero(self):
        self.path.write_text(_LINE_B)
        removed = self.maintenance.remove_ip("9.9.9.9", self.path)
        self.assertEqual(removed, 0)
        self.assertEqual(self.path.read_text(), _LINE_B)

    def test_unparseable_lines_are_preserved(self):
        self.path.write_text("garbage\n" + _LINE_A)
        removed = self.maintenance.remove_ip("1.1.1.1", self.path)
        self.assertEqual(removed, 1)
        self.assertEqual(self.path.read_text(), "garbage\n")

    def test_removes_ip_from_a_non_combined_format_line(self):
        """Regression (gestion des logs, refonte menu 2026-10-15) :
        l'ancienne implementation (parse_combined_log_line uniquement)
        ne reconnaissait jamais une IP dans une ligne auth.log/syslog -
        "Voir et traiter IP" generalise a n'importe quel log de la
        Bibliotheque ne pouvait donc jamais rien retirer en dehors de
        l'access log Combined d'Omega-Serv lui-meme."""
        auth_line = "Oct 10 10:00:00 host sshd[123]: Failed password for root from 1.1.1.1 port 4242 ssh2\n"
        self.path.write_text(auth_line + _LINE_B)
        removed = self.maintenance.remove_ip("1.1.1.1", self.path)
        self.assertEqual(removed, 1)
        self.assertEqual(self.path.read_text(), _LINE_B)

    def test_does_not_match_a_different_ip_sharing_a_prefix(self):
        self.path.write_text(_LINE_A + _LINE_B)
        removed = self.maintenance.remove_ip("1.1.1.11", self.path)
        self.assertEqual(removed, 0)
        self.assertEqual(self.path.read_text(), _LINE_A + _LINE_B)

    def test_write_is_atomic_no_leftover_tmp_file(self):
        self.path.write_text(_LINE_A + _LINE_B)
        self.maintenance.remove_ip("1.1.1.1", self.path)
        leftovers = list(self.path.parent.glob("*.omega-serv-tmp"))
        self.assertEqual(leftovers, [])


if __name__ == "__main__":
    unittest.main()
