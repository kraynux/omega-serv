"""Optimisation du journal d'acces (OMEGA-SERV_ETUDE_PERFORMANCE.md, priorite 3) :
str.translate et un seul strftime doivent donner exactement le meme resultat qu'avant."""
import unittest
from datetime import datetime, timedelta, timezone

from omega_serv.domain.logging.access_log_format import (
    AccessLogEntry,
    _format_apache_timestamp,
    format_combined_log_line,
    sanitize_log_field,
)
from omega_serv.domain.logging.access_log_parser import parse_combined_log_line


def _reference_sanitize(value: str, max_length: int) -> str:
    controls = {chr(c) for c in range(0x20)}
    return "".join(" " if ch in controls else ch for ch in value)[:max_length]


class TestSanitizeEquivalence(unittest.TestCase):
    def test_same_output_as_the_character_by_character_version(self):
        samples = (
            "".join(chr(c) for c in range(0x40)),
            "GET /a\r\nInjected: 1 HTTP/1.1",
            "Mozilla/5.0 (éàü) 🚀 \x7f\x00\t",
            "x" * 3000,
            "",
        )
        for value in samples:
            for max_length in (0, 5, 64, 512, 4096):
                self.assertEqual(sanitize_log_field(value, max_length), _reference_sanitize(value, max_length))


class TestApacheTimestamp(unittest.TestCase):
    def test_utc_naive_and_offset_dates(self):
        moment = datetime(2026, 10, 26, 15, 4, 5)  # noqa: DTZ001 - date sans fuseau testee volontairement
        self.assertEqual(_format_apache_timestamp(moment.replace(tzinfo=timezone.utc)), "26/Oct/2026:15:04:05 +0000")
        self.assertEqual(_format_apache_timestamp(moment), "26/Oct/2026:15:04:05 +0000")
        paris = timezone(timedelta(hours=1))
        self.assertEqual(_format_apache_timestamp(moment.replace(tzinfo=paris)), "26/Oct/2026:15:04:05 +0100")


class TestRawRequestLine(unittest.TestCase):
    """Requete refusee pendant l'analyse de sa tete (plan moteur C++ §14, valide 2026-11-02)."""

    def _line(self, raw):
        return format_combined_log_line(AccessLogEntry(
            remote_ip="198.51.100.7", timestamp=datetime(2026, 11, 2, 12, 0, 0, tzinfo=timezone.utc),
            method="", request_target="", http_version="", status_code=400, response_size=0,
            referer=None, user_agent=None, request_id="0123456789abcdef", raw_request_line=raw))

    def test_raw_line_written_as_received_and_still_parsed(self):
        line = self._line("GET /a HTTP/9.9")
        self.assertEqual(line, '198.51.100.7 - - [02/Nov/2026:12:00:00 +0000] "GET /a HTTP/9.9" 400 - "-" "-" 0123456789abcdef')
        entry = parse_combined_log_line(line)
        self.assertEqual((entry.ip, entry.status_code, entry.path), ("198.51.100.7", 400, "/a"))

    def test_unreadable_line_is_a_dash(self):
        entry = parse_combined_log_line(self._line("-"))
        self.assertEqual((entry.ip, entry.status_code, entry.path), ("198.51.100.7", 400, ""))

    def test_client_quotes_are_escaped_like_nginx(self):
        # 2026-11-02 : un guillemet du client fermait le champ ; la ligne devenait illisible.
        line = format_combined_log_line(AccessLogEntry(
            remote_ip="198.51.100.7", timestamp=datetime(2026, 11, 2, 12, 0, 0, tzinfo=timezone.utc),
            method="GET", request_target='/a" 404 "x', http_version="HTTP/1.1", status_code=200, response_size=5,
            referer='http://r/"', user_agent='ua"2', request_id="0123456789abcdef"))
        self.assertEqual(line, '198.51.100.7 - - [02/Nov/2026:12:00:00 +0000] "GET /a\\x22 404 \\x22x HTTP/1.1" 200 5 '
                               '"http://r/\\x22" "ua\\x222" 0123456789abcdef')
        entry = parse_combined_log_line(line)
        self.assertEqual((entry.status_code, entry.path), (200, "/a\\x22"))


if __name__ == "__main__":
    unittest.main()
