"""Regle commune de correspondance d'une IP dans une ligne de log (recherche manuelle et retrait, 2026-11-07)."""
from __future__ import annotations

import os
import tempfile
import unittest
from pathlib import Path

from omega_serv.application.logs.ip_occurrences import IpOccurrences, count_ip_occurrences
from omega_serv.domain.logs.exceptions import LogPermissionError
from omega_serv.domain.logs.ip_match import ip_line_pattern, line_contains_ip, normalize_ip


def _matches(ip: str, line: str) -> bool:
    return line_contains_ip(line, ip, ip_line_pattern(ip))


class TestNormalizeIp(unittest.TestCase):
    def test_valid_addresses_are_normalized(self):
        self.assertEqual(normalize_ip(" 203.0.113.42 "), "203.0.113.42")
        self.assertEqual(normalize_ip("2A03:2880:F800:0015::"), "2a03:2880:f800:15::")

    def test_invalid_text_gives_none(self):
        for text in ("", "1.2.3", "300.1.1.1", "example.org", "1.1.1.1/24"):
            self.assertIsNone(normalize_ip(text), text)


class TestIpLinePattern(unittest.TestCase):
    def test_ipv4_at_line_start_and_inside_text(self):
        self.assertTrue(_matches("1.1.1.1", '1.1.1.1 - - [08/Sep/2026:10:00:00 +0000] "GET / HTTP/1.1" 200'))
        self.assertTrue(_matches("1.1.1.1", "sshd[1]: Failed password for root from 1.1.1.1 port 4242"))

    def test_ipv4_never_matches_a_longer_address(self):
        self.assertFalse(_matches("1.1.1.1", "1.1.1.11 - - x"))
        self.assertFalse(_matches("1.1.1.1", "21.1.1.1 - - x"))
        self.assertFalse(_matches("1.1.1.1", "1.1.1.1.5 - - x"))

    def test_ipv4_with_port_or_mapped_in_ipv6(self):
        self.assertTrue(_matches("1.1.1.1", "client 1.1.1.1:443 closed"))
        self.assertTrue(_matches("1.1.1.1", "::ffff:1.1.1.1 - - x"))

    def test_ipv6_ending_with_double_colon(self):
        """Regression : la limite de mot \\b ne trouvait jamais cette adresse (0 ligne retiree)."""
        self.assertTrue(_matches("2a03:2880:f800:15::", "2a03:2880:f800:15:: host - [04/Oct/2026] x"))

    def test_ipv6_never_matches_a_longer_address(self):
        self.assertFalse(_matches("2a03:2880:f800:15::", "2a03:2880:f800:15::1 host - x"))
        self.assertFalse(_matches("2001:db8::1", "2001:db8::12 host - x"))
        self.assertTrue(_matches("2001:db8::1", "[2001:db8::1]:443 host - x"))


class TestCountIpOccurrences(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.root = Path(self._tmp.name)

    def tearDown(self):
        self._tmp.cleanup()

    def test_counts_lines_per_file_missing_file_is_zero(self):
        first = self.root / "a.log"
        first.write_text("1.1.1.1 x\n2.2.2.2 x\n1.1.1.1 y\n1.1.1.11 z\n")
        second = self.root / "b.log"
        second.write_text("2.2.2.2 x\n")
        missing = self.root / "absent.log"
        self.assertEqual(
            count_ip_occurrences("1.1.1.1", [str(first), str(second), str(missing)]),
            [IpOccurrences(str(first), 2), IpOccurrences(str(second), 0), IpOccurrences(str(missing), 0)],
        )

    @unittest.skipIf(os.geteuid() == 0, "root lit tout")
    def test_unreadable_file_raises_log_permission_error(self):
        path = self.root / "secret.log"
        path.write_text("1.1.1.1 x\n")
        path.chmod(0o000)
        try:
            with self.assertRaises(LogPermissionError) as raised:
                count_ip_occurrences("1.1.1.1", [str(path)])
            self.assertEqual(raised.exception.path, str(path))
        finally:
            path.chmod(0o644)


if __name__ == "__main__":
    unittest.main()
