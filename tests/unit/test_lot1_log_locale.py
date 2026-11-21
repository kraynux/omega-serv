# Copyright (c) 2026 kraynux - kraynux@proton.me - Licence MIT (voir fichier LICENSE)
"""Plan proxy natif v2, lot 1 (D41) : le mois du journal d'acces ne depend jamais de la locale (LC_TIME).

`%b` suivait LC_TIME : sous une locale francaise, « nov. » au lieu de « Nov » - les failregex d'omega-jail, lnav,
les statistiques et le moteur natif ne liraient plus la ligne. Meme chose pour les dates d'openssl."""
from __future__ import annotations

import locale
import unittest
from datetime import datetime, timezone

from omega_serv.domain.logging.access_log_format import AccessLogEntry, format_combined_log_line
from omega_serv.domain.logging.access_log_parser import (
    parse_apache_timestamp,
    parse_combined_log_line,
)
from omega_serv.infrastructure.tls.openssl_certificate_tool import _parse_openssl_date

_FOREIGN_LOCALES = ("fr_FR.UTF-8", "fr_FR.utf8", "de_DE.UTF-8", "de_DE.utf8", "es_ES.UTF-8", "es_ES.utf8")


class TestMonthIndependentOfLocale(unittest.TestCase):
    def setUp(self):
        self.previous = locale.setlocale(locale.LC_TIME)
        for name in _FOREIGN_LOCALES:
            try:
                locale.setlocale(locale.LC_TIME, name)
                break
            except locale.Error:
                continue
        else:
            self.skipTest("aucune locale francaise, allemande ou espagnole installee")
        self.addCleanup(locale.setlocale, locale.LC_TIME, self.previous)
        self.assertNotEqual(datetime(2026, 11, 12, tzinfo=timezone.utc).strftime("%b"), "Nov")  # la locale change bien %b

    def test_access_log_line_uses_english_month_and_reads_back(self):
        entry = AccessLogEntry(remote_ip="203.0.113.9", timestamp=datetime(2026, 11, 12, 10, 0, tzinfo=timezone.utc),
                               method="GET", request_target="/", http_version="HTTP/1.1", status_code=200,
                               response_size=5, referer=None, user_agent=None, request_id="r1")
        line = format_combined_log_line(entry)
        self.assertIn("[12/Nov/2026:10:00:00 +0000]", line)
        parsed = parse_combined_log_line(line)
        self.assertIsNotNone(parsed)

    def test_parsers_read_english_months(self):
        self.assertEqual(parse_apache_timestamp("01/Dec/2026:00:00:00 +0000").month, 12)
        self.assertEqual(_parse_openssl_date("Nov  2 10:00:00 2026 GMT"), datetime(2026, 11, 2, 10, tzinfo=timezone.utc))
        with self.assertRaises(ValueError):
            parse_apache_timestamp("01/nov./2026:00:00:00 +0000")


if __name__ == "__main__":
    unittest.main()
