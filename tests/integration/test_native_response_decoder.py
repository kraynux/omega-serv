# Copyright (c) 2026 kraynux - kraynux@proton.me - Licence MIT (voir fichier LICENSE)
"""Plan proxy natif v2, lot 5 (C5 : S7 a S13) : l'analyseur de reponse du relais natif compare aux VRAIES fonctions
du proxy Python (`_read_final_head`, `_body_framing`, `_read_exactly`, `_read_chunked`, `_read_until_close` de
infrastructure/proxy/asyncio_http_proxy_client.py), sur un corpus de reponses ecrites a la main puis de mutations
aleatoires (graine fixe). Pour chaque reponse : accepte ou refuse, statut, decoupage, corps decode, octets restants
apres la reponse (D22 : une connexion avec des octets en trop n'est jamais recyclee).

Le binaire lit les reponses sur son entree (`--decode-responses`). Sans build, le test est saute."""
from __future__ import annotations

import asyncio
import random
import subprocess
import unittest

from omega_serv.infrastructure.proxy import asyncio_http_proxy_client as client
from tests.integration.proxy_harness import NATIVE_BINARY

BASES: list[tuple[str, bytes]] = [
    ("GET", b"HTTP/1.1 200 OK\r\nContent-Length: 5\r\n\r\nhello"),
    ("GET", b"HTTP/1.1 200 OK\r\nContent-Length: 5\r\n\r\nhelloEXTRA"),
    ("GET", b"HTTP/1.1 200 OK\r\nTransfer-Encoding: chunked\r\n\r\n5\r\nhello\r\n6\r\n world\r\n0\r\n\r\n"),
    ("GET", b"HTTP/1.1 200 OK\r\nTransfer-Encoding: chunked\r\n\r\n5;ext=1\r\nhello\r\n0\r\nX-T: 1\r\n\r\nSUITE"),
    ("GET", b"HTTP/1.1 200 OK\r\ntransfer-encoding: Chunked\r\n\r\na\r\n0123456789\r\n0\r\n\r\n"),
    ("GET", b"HTTP/1.1 200 OK\r\nConnection: close\r\n\r\nfin-par-fermeture"),
    ("GET", b"HTTP/1.0 200 OK\r\n\r\nfin"),
    ("GET", b"HTTP/1.1 100 Continue\r\n\r\nHTTP/1.1 200 OK\r\nContent-Length: 2\r\n\r\nok"),
    ("GET", b"HTTP/1.1 103 Early Hints\r\nLink: </a>\r\n\r\nHTTP/1.1 404 Not Found\r\nContent-Length: 0\r\n\r\n"),
    ("GET", b"HTTP/1.1 204 No Content\r\nContent-Length: 7\r\n\r\n"),
    ("GET", b"HTTP/1.1 304 Not Modified\r\nTransfer-Encoding: chunked\r\n\r\n"),
    ("HEAD", b"HTTP/1.1 200 OK\r\nContent-Length: 1234\r\n\r\n"),
    ("HEAD", b"HTTP/1.1 200 OK\r\nTransfer-Encoding: chunked\r\n\r\n"),
    ("GET", b"HTTP/1.1 200 OK\r\nContent-Length: 3\r\nContent-Length: 3\r\n\r\nabc"),
    ("GET", b"HTTP/1.1 200 OK\r\nContent-Length: 3\r\nTransfer-Encoding: chunked\r\n\r\n3\r\nabc\r\n0\r\n\r\n"),
    ("GET", b"HTTP/1.1 200 OK\r\nTransfer-Encoding: gzip, chunked\r\n\r\n0\r\n\r\n"),
    ("GET", b"HTTP/1.1 101 Switching Protocols\r\nUpgrade: websocket\r\n\r\n"),
    ("GET", b"HTTP/1.1 200 OK\nContent-Length: 2\n\nok"),
    ("GET", b"HTTP/1.1 200\r\nContent-Length: 2\r\n\r\nok"),
    ("GET", b"HTTP/1.1 200 OK\r\nX: a\r\n b\r\nContent-Length: 2\r\n\r\nok"),
    ("GET", b"HTTP/1.1 200 OK\r\nTransfer-Encoding: chunked\r\n\r\n" + b"1\r\nx\r\n" * 40 + b"0\r\n\r\n"),
    ("GET", b"HTTP/1.1 200 OK\r\nTransfer-Encoding: chunked\r\n\r\n000000000000000a\r\n0123456789\r\n0\r\n\r\n"),
    ("GET", b"HTTP/1.1 200 OK\r\nTransfer-Encoding: chunked\r\n\r\n00000000000000000a\r\n0123456789\r\n0\r\n\r\n"),
    ("GET", b"HTTP/1.1 200 OK\r\nTransfer-Encoding: chunked\r\n\r\n5;" + b"e" * 4092 + b"\r\nhello\r\n0\r\n\r\n"),
    ("GET", b"HTTP/1.1 200 OK\r\nTransfer-Encoding: chunked\r\n\r\n5;" + b"e" * 4093 + b"\r\nhello\r\n0\r\n\r\n"),
    ("GET", b"HTTP/1.1 200 OK\r\nTransfer-Encoding: chunked\r\n\r\n0\r\n"
     + b"".join(b"X-T%d: v\r\n" % i for i in range(32)) + b"\r\n"),
    ("GET", b"HTTP/1.1 200 OK\r\nTransfer-Encoding: chunked\r\n\r\n0\r\n"
     + b"".join(b"X-T%d: v\r\n" % i for i in range(33)) + b"\r\n"),
    ("GET", b"HTTP/1.1 200 OK\r\nTransfer-Encoding: chunked\r\n\r\n0\r\nX-T: " + b"v" * 16377 + b"\r\n\r\n"),
    ("GET", b"HTTP/1.1 200 OK\r\nTransfer-Encoding: chunked\r\n\r\n0\r\nX-T: " + b"v" * 16378 + b"\r\n\r\n"),
]
MUTATION_BYTES = b"\r\n;: \t0123456789abcdefABCDEFxX\x00\x7f-+,"


def corpus(seed: int = 20261113, count: int = 1500) -> list[tuple[str, bytes]]:
    rng = random.Random(seed)
    cases = list(BASES)
    for _ in range(count):
        method, data = rng.choice(BASES)
        data = bytearray(data)
        for _ in range(rng.randint(1, 3)):
            operation = rng.randrange(4)
            position = rng.randrange(len(data) + 1)
            if operation == 0 and data:  # remplacement
                data[min(position, len(data) - 1)] = rng.choice(MUTATION_BYTES)
            elif operation == 1:  # insertion
                data[position:position] = bytes([rng.choice(MUTATION_BYTES)])
            elif operation == 2 and data:  # suppression
                del data[min(position, len(data) - 1)]
            else:  # troncature
                del data[position:]
        cases.append((method, bytes(data)))
    return cases


async def _python_decode(method: str, data: bytes) -> str:
    """La lecture de _send_and_read, apres l'envoi : memes fonctions, memes exceptions rattrapees (502)."""
    reader = asyncio.StreamReader()  # limite par defaut (64 Kio), comme asyncio.open_connection
    reader.feed_data(data)
    reader.feed_eof()
    try:
        status_line = await reader.readline()
        if not status_line:
            return "error"
        _version, status, headers = await client._read_final_head(reader, 5, status_line)
        framing, length = client._body_framing(method, status, headers)
        if framing == "none":
            body = b""
        elif framing == "length":
            body = await client._read_exactly(reader, length, 5)
        elif framing == "chunked":
            body = await client._read_chunked(reader, 5, None)
        else:
            body = await client._read_until_close(reader, 5, None)
    except (asyncio.IncompleteReadError, ValueError, OSError):
        return "error"
    rest = 0 if framing == "close" else len(reader._buffer)
    return f"ok\t{status}\t{framing}\t{body.hex()}\t{rest}"


@unittest.skipUnless(NATIVE_BINARY.is_file(), "binaire natif non construit")
class TestNativeResponseDecoderMatchesPython(unittest.TestCase):
    def test_same_verdict_status_framing_body_and_rest(self):
        cases = corpus()
        stdin = "".join(f"{method}\t{data.hex()}\n" for method, data in cases)
        native = subprocess.run([str(NATIVE_BINARY), "--decode-responses"], input=stdin, capture_output=True,
                                text=True, timeout=60, check=True).stdout.splitlines()
        self.assertEqual(len(native), len(cases))

        async def python_all() -> list[str]:
            return [await _python_decode(method, data) for method, data in cases]

        python = asyncio.run(python_all())
        differences = [(method, data, py, nat) for (method, data), py, nat in zip(cases, python, native, strict=True)
                       if py != nat]
        self.assertEqual(differences[:5], [], f"{len(differences)} ecart(s) sur {len(cases)} reponses")
        # Le corpus couvre bien les quatre decoupages et les refus.
        for expected in ("\tnone\t", "\tlength\t", "\tchunked\t", "\tclose\t"):
            self.assertTrue(any(expected in line for line in python), expected)
        self.assertGreater(sum(line == "error" for line in python), 100)


if __name__ == "__main__":
    unittest.main()
