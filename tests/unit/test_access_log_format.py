"""Optimisation du journal d'acces (OMEGA-SERV_ETUDE_PERFORMANCE.md, priorite 3) :
str.translate et un seul strftime doivent donner exactement le meme resultat qu'avant."""
import unittest
from datetime import datetime, timedelta, timezone

from omega_serv.domain.logging.access_log_format import _format_apache_timestamp, sanitize_log_field


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


if __name__ == "__main__":
    unittest.main()
