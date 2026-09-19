"""Fuzzing par proprietes du parseur HTTP (porte de sortie Phase 2).

Un serveur HTTP maison est la surface de securite la plus sensible du
projet (spec §28.1) - la propriete fondamentale testee ici est qu'AUCUNE
sequence d'octets ne doit jamais produire une exception non geree
(UnicodeDecodeError, IndexError...) : seul un resultat structure
(ParsedRequestHead) ou une des deux exceptions de controle deja
prevues (HttpParseError, ConnectionClosedCleanly) sont des issues
acceptables.
"""
import asyncio
import unittest

from hypothesis import HealthCheck, given, settings
from hypothesis import strategies as st

from omega_serv.infrastructure.server.http_parser import (
    ConnectionClosedCleanly,
    HttpParseError,
    read_request_head,
)


def _reader_from_bytes(data: bytes) -> asyncio.StreamReader:
    reader = asyncio.StreamReader()
    reader.feed_data(data)
    reader.feed_eof()
    return reader


async def _parse(data: bytes) -> None:
    reader = _reader_from_bytes(data)
    try:
        await read_request_head(reader, max_request_line_size=8192, max_header_size=16384)
    except (HttpParseError, ConnectionClosedCleanly):
        pass  # rejet propre attendu, jamais un crash


class TestFuzzHttpParserRawBytes(unittest.TestCase):
    @given(st.binary(max_size=600))
    @settings(max_examples=2000, suppress_health_check=[HealthCheck.too_slow])
    def test_arbitrary_bytes_never_crash_parser(self, raw_bytes):
        asyncio.run(_parse(raw_bytes))


_RISKY_TEXT = st.text(alphabet="GETHOSPCONNAILhost: \r\n\x00\x01/.", max_size=40)


class TestFuzzHttpParserStructuredNoise(unittest.TestCase):
    @given(st.lists(_RISKY_TEXT, min_size=1, max_size=6))
    @settings(max_examples=2000, suppress_health_check=[HealthCheck.too_slow])
    def test_structured_noise_never_crashes(self, lines):
        raw = ("\r\n".join(lines) + "\r\n\r\n").encode("latin-1", errors="replace")
        asyncio.run(_parse(raw))


if __name__ == "__main__":
    unittest.main()
