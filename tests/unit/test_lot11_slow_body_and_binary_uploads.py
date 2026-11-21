# Copyright (c) 2026 kraynux - kraynux@proton.me - Licence MIT (voir fichier LICENSE)
"""Lot 11, constats de la mesure du §7 (decisions de l'auteur du 2026-11-14).

F1 - corps de requete : delai relance a chaque bloc recu, debit moyen minimal de 500 o/s (dans le code, pas une
option) ; un envoi lent mais regulier n'est plus coupe a read_timeout_seconds.
F2 - WAF : un fichier binaire reconnu a sa SIGNATURE (contenu reel, jamais l'extension) et annonce sous un type non
textuel n'est pas lu comme du texte ; formulaires, JSON, XML et texte restent inspectes."""
from __future__ import annotations

import asyncio
import os
import unittest

from omega_serv.domain.http.headers import HttpHeaders
from omega_serv.domain.http.request import HttpRequest
from omega_serv.domain.security.waf.binary_formats import (
    DEFAULT_BINARY_FORMATS,
    KNOWN_BINARY_FORMATS,
    detect_format,
    inspectable_body,
)
from omega_serv.domain.security.waf.config import parse_waf_config, validate_waf_config
from omega_serv.domain.security.waf.entities import RuleDefinition, RulePack
from omega_serv.domain.security.waf.signature_engine import compile_rule_pack
from omega_serv.infrastructure.server import http_parser
from omega_serv.infrastructure.server.http_parser import _read_body_with_deadline
from omega_serv.infrastructure.waf.python_waf_engine import PythonWafEngine

PNG = b"\x89PNG\r\n\x1a\n" + b"\x00\x00\x00\rIHDR"


async def _feed(reader: asyncio.StreamReader, pieces: list[tuple[float, bytes]]) -> None:
    for delay, data in pieces:
        await asyncio.sleep(delay)
        reader.feed_data(data)


class TestBodyDeadline(unittest.IsolatedAsyncioTestCase):
    async def _read(self, pieces, length, timeout=0.5):
        reader = asyncio.StreamReader()
        feeder = asyncio.create_task(_feed(reader, pieces))
        try:
            return await _read_body_with_deadline(reader, length, 16, timeout)
        finally:
            feeder.cancel()

    async def test_steady_body_longer_than_the_timeout_is_read(self):
        # 1 500 octets a ~1 500 o/s pendant 1 s (> 0,5 s de delai) : au-dessus du debit minimal, jamais 0,5 s sans octet.
        pieces = [(0.1, b"x" * 150)] * 10
        self.assertEqual(await self._read(pieces, 1500), b"x" * 16)

    async def test_trickle_under_the_minimum_rate_times_out(self):
        # 20 o toutes les 0,2 s = 100 o/s < 500 o/s : l'echeance totale (0,5 s + recu / 500) est depassee.
        with self.assertRaises(asyncio.TimeoutError):
            await self._read([(0.2, b"x" * 20)] * 50, 1000)

    async def test_pause_longer_than_the_timeout_times_out_even_after_a_fast_start(self):
        # 10 000 octets d'un coup (credit de 20 s au debit minimal), puis plus rien pendant 0,8 s > 0,5 s.
        with self.assertRaises(asyncio.TimeoutError):
            await self._read([(0, b"x" * 10_000), (0.8, b"x")], 10_001)

    async def test_incomplete_body_is_a_parse_error(self):
        reader = asyncio.StreamReader()
        reader.feed_data(b"abc")
        reader.feed_eof()
        with self.assertRaises(http_parser.HttpParseError):
            await _read_body_with_deadline(reader, 10, 0, 1.0)

    def test_minimum_rate_is_shared_with_the_native_engine(self):
        source = (os.path.dirname(__file__) + "/../../native/omega-http-core/src/server.cpp")
        with open(source, encoding="utf-8") as handle:
            self.assertIn(f"kBodyMinRateBytesPerSecond = {http_parser.BODY_MIN_RATE_BYTES_PER_SECOND}.0",
                          handle.read())


class TestBinaryFormats(unittest.TestCase):
    def test_signatures_not_extensions(self):
        self.assertEqual(detect_format(PNG + os.urandom(100), KNOWN_BINARY_FORMATS), "png")
        self.assertEqual(detect_format(b"\xff\xd8\xff\xe0" + os.urandom(100), KNOWN_BINARY_FORMATS), "jpeg")
        self.assertEqual(detect_format(b"RIFF\x00\x00\x00\x00WEBPVP8 ", KNOWN_BINARY_FORMATS), "webp")
        self.assertIsNone(detect_format(b"RIFF\x00\x00\x00\x00XXXX", ("webp", "wav")))  # RIFF seul ne suffit pas
        self.assertEqual(detect_format(b"\x00\x00\x00\x18ftypheic", KNOWN_BINARY_FORMATS), "mp4")
        self.assertEqual(detect_format(b"PK\x03\x04" + os.urandom(50), KNOWN_BINARY_FORMATS), "zip")
        self.assertEqual(detect_format(b"%PDF-1.7\n", KNOWN_BINARY_FORMATS), "pdf")
        self.assertIsNone(detect_format(b"MZ\x90\x00", KNOWN_BINARY_FORMATS))  # executable : jamais dans la liste
        self.assertIsNone(detect_format(PNG, ("jpeg",)))  # format retire de la liste

    def test_binary_body_with_a_non_text_type_is_not_inspected(self):
        body = PNG + b"; cat /etc/passwd"
        for content_type in ("image/png", "application/octet-stream", "image/jpeg"):
            self.assertEqual(inspectable_body(body, content_type, DEFAULT_BINARY_FORMATS), b"", content_type)

    def test_unknown_or_polluted_type_stays_inspected(self):
        """Scan de securite n° 2 (F17) : seul un type EXPLICITEMENT binaire saute l'inspection ; type absent,
        inconnu ou pollue (`...urlencoded,` lu par PHP comme un formulaire) : corps inspecte."""
        body = PNG + b"&id=1' UNION SELECT"
        for content_type in (None, "application/x-anything", "application/x-www-form-urlencoded,",
                             "application/x-www-form-urlencoded x"):
            self.assertEqual(inspectable_body(body, content_type, DEFAULT_BINARY_FORMATS), body, content_type)

    def test_fake_signature_on_a_text_type_stays_inspected(self):
        body = PNG + b"&cmd=$(id)"
        for content_type in ("application/x-www-form-urlencoded", "application/json; charset=utf-8", "text/plain",
                             "application/problem+json", "application/soap+xml"):
            self.assertEqual(inspectable_body(body, content_type, DEFAULT_BINARY_FORMATS), body, content_type)

    def test_unknown_bytes_stay_inspected(self):
        noise = os.urandom(4096)
        if detect_format(noise, KNOWN_BINARY_FORMATS) is None:
            self.assertEqual(inspectable_body(noise, "application/octet-stream", DEFAULT_BINARY_FORMATS), noise)

    def test_empty_list_inspects_everything(self):
        self.assertEqual(inspectable_body(PNG, "image/png", ()), PNG)

    def test_multipart_drops_only_recognised_file_parts(self):
        body = (b"--B\r\nContent-Disposition: form-data; name=\"comment\"\r\n\r\n$(id)\r\n"
                b"--B\r\nContent-Disposition: form-data; name=\"photo\"; filename=\"a.png\"\r\n"
                b"Content-Type: image/png\r\n\r\n" + PNG + b"`id`\r\n"
                b"--B\r\nContent-Disposition: form-data; name=\"csv\"; filename=\"a.csv\"\r\n\r\nx;`id`\r\n"
                b"--B--\r\n")
        kept = inspectable_body(body, "multipart/form-data; boundary=B", DEFAULT_BINARY_FORMATS)
        self.assertIn(b"$(id)", kept)  # champ texte
        self.assertIn(b"x;`id`", kept)  # fichier sans signature connue : inspecte
        self.assertNotIn(b"PNG", kept)  # image retiree
        self.assertIn(b'filename="a.png"', kept)  # ses en-tetes restent
        # un champ texte qui commence par une signature n'est pas un fichier : garde
        field = b"--B\r\nContent-Disposition: form-data; name=\"t\"\r\n\r\n" + PNG + b"$(id)\r\n--B--\r\n"
        self.assertEqual(inspectable_body(field, "multipart/form-data; boundary=B", DEFAULT_BINARY_FORMATS), field)

    def test_config_default_and_validation(self):
        self.assertEqual(parse_waf_config({"mode": "block"}).inspect.binary_formats, DEFAULT_BINARY_FORMATS)
        def format_errors(value):
            return [e for e in validate_waf_config(parse_waf_config({"inspect": {"binary_formats": value}}))
                    if "binary_formats" in e]
        self.assertEqual(format_errors(["png", "jpeg"]), [])
        self.assertEqual(format_errors([]), [])
        self.assertTrue(any("exe" in error for error in format_errors(["png", "exe"])))
        self.assertTrue(format_errors("png"))


def _cmdi_engine(**inspect):
    pack = compile_rule_pack(RulePack(version=1, pack="body-cmdi", enabled=True, rules=(
        RuleDefinition(id="CMDI-001", description="", scope=("body",), pattern=r"\$\([^)]+\)", weight=6),)))
    return PythonWafEngine((pack,), parse_waf_config({"mode": "block", "inspect": inspect}))


def _post(body: bytes, content_type: str | None) -> HttpRequest:
    headers = [("Content-Type", content_type)] if content_type else []
    return HttpRequest(request_id="r1", remote_ip="203.0.113.1", peer_ip="203.0.113.1", method="POST", path="/upload",
                       raw_path="/upload", query="", headers=HttpHeaders.from_pairs(headers), body=body,
                       content_length=len(body), is_tls=False)


class TestWafWithBinaryUploads(unittest.TestCase):
    def test_image_upload_passes_and_disguised_form_is_blocked(self):
        engine = _cmdi_engine()
        self.assertEqual(engine.inspect(_post(PNG + b"$(id)", "image/png")).action, "allow")
        self.assertEqual(engine.inspect(_post(PNG + b"$(id)", "application/x-www-form-urlencoded")).action, "block")
        self.assertEqual(engine.inspect(_post(b"junk $(id)", "application/octet-stream")).action, "block")

    def test_empty_list_restores_the_old_behaviour(self):
        self.assertEqual(_cmdi_engine(binary_formats=[]).inspect(_post(PNG + b"$(id)", "image/png")).action, "block")


if __name__ == "__main__":
    unittest.main()
