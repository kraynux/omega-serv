# Copyright (c) 2026 kraynux - kraynux@proton.me - Licence MIT (voir fichier LICENSE)
"""Teste le parseur pur du format combine (domain/logging/access_log_parser.py)."""
from __future__ import annotations

import unittest
from datetime import timezone

from omega_serv.domain.logging.access_log_parser import parse_combined_log_line


class TestParseCombinedLogLine(unittest.TestCase):
    def test_parses_well_formed_line_with_request_id(self):
        line = (
            '127.0.0.1 - - [08/Sep/2026:10:00:00 +0000] '
            '"GET / HTTP/1.1" 200 100 "-" "curl/8.0" req-123'
        )
        entry = parse_combined_log_line(line)
        self.assertIsNotNone(entry)
        self.assertEqual(entry.ip, "127.0.0.1")
        self.assertEqual(entry.status_code, 200)
        self.assertEqual(entry.timestamp.year, 2026)
        self.assertEqual(entry.timestamp.tzinfo, timezone.utc)

    def test_parses_well_formed_line_without_request_id(self):
        line = (
            '10.0.0.5 - - [08/Sep/2026:10:00:00 +0000] '
            '"GET /a HTTP/1.1" 404 50 "-" "curl/8.0"'
        )
        entry = parse_combined_log_line(line)
        self.assertIsNotNone(entry)
        self.assertEqual(entry.ip, "10.0.0.5")
        self.assertEqual(entry.status_code, 404)

    def test_parses_response_size(self):
        line = (
            '127.0.0.1 - - [08/Sep/2026:10:00:00 +0000] '
            '"GET / HTTP/1.1" 200 156 "-" "curl/8.0" req-123'
        )
        entry = parse_combined_log_line(line)
        self.assertIsNotNone(entry)
        self.assertEqual(entry.response_size, 156)

    def test_dash_response_size_defaults_to_zero(self):
        line = (
            '127.0.0.1 - - [08/Sep/2026:10:00:00 +0000] '
            '"GET / HTTP/1.1" 304 - "-" "curl/8.0"'
        )
        entry = parse_combined_log_line(line)
        self.assertIsNotNone(entry)
        self.assertEqual(entry.response_size, 0)

    def test_malformed_line_returns_none(self):
        self.assertIsNone(parse_combined_log_line("not a log line at all"))

    def test_invalid_timestamp_returns_none(self):
        line = '127.0.0.1 - - [not-a-date] "GET / HTTP/1.1" 200 100 "-" "curl/8.0"'
        self.assertIsNone(parse_combined_log_line(line))

    def test_empty_line_returns_none(self):
        self.assertIsNone(parse_combined_log_line(""))


if __name__ == "__main__":
    unittest.main()
