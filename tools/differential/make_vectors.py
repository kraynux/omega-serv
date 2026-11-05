#!/usr/bin/env python3
# Copyright (c) 2026 kraynux - kraynux@proton.me - Licence MIT (voir fichier LICENSE)
"""Vecteurs de reference pour les regles pures du moteur natif (plan moteur C++, lot 2, 2026-11-02) -
outil de developpement.

Calcule, avec les VRAIES fonctions Python d'omega-serv, la reponse attendue pour des milliers d'entrees
(cas choisis + aleatoires a graine fixe) ; le test C++ (native/omega-http-core/tests/test_vectors.cpp) les
rejoue et exige le meme resultat. Format : une ligne par cas, champs separes par une tabulation, chaque champ
en hexadecimal (entrees arbitraires, octets compris).

  .venv/bin/python tools/differential/make_vectors.py native/omega-http-core/tests/vectors/rules.tsv
"""
from __future__ import annotations

import random
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "src"))

from omega_serv.domain.http import conditional
from omega_serv.domain.http.mime_types import guess_mime_type
from omega_serv.domain.http.precompressed import is_compressible, preferred_encodings
from omega_serv.domain.routing.cache_policy import (
    DEFAULT_EXTENSION_CACHE,
    CachePolicy,
    resolve_cache_control,
)
from omega_serv.domain.security.path_policy import normalize_uri_path

RNG = random.Random(20261102)


def hx(value: str | bytes) -> str:
    data = value.encode("latin-1") if isinstance(value, str) else value
    return data.hex()


def utf8hx(value: str) -> str:
    return value.encode("utf-8").hex()


def rand_text(alphabet: str, lo: int, hi: int) -> str:
    return "".join(RNG.choice(alphabet) for _ in range(RNG.randint(lo, hi)))


def path_cases() -> list[str]:
    fixed = ["/", "/a/b", "/a/../b", "/../x", "/a/./b//c", "/%2e%2e/x", "/%252e%252e/x", "/%25252e/x", "/%00",
             "/a%00b", "/%0a", "/%c3%a9t%c3%a9", "/%c3", "/%ff", "/%e2%82", "/%ed%a0%80", "/%f0%9f%98%80",
             "/caf\xe9", "/caf\xe9%c3%a9", "/a\\..\\b", "/%5c..%5cx", "/%zz", "/%4", "/%", "/%%41", "/%2541",
             "/a%2fb", "/a/%2e/b", "/\x7f", "/%7f", "/%c0%af", "/%e0%80%af", "", "/%20x%20", "/..", "/a/..",
             "/a/b/../../..", "/%2e", "/.%2e/x", "/x\x85y", "/%c2%85"]
    alphabet = "abc/.%\\2eE5cC0fF8\xe9\xff\x00\x1f "
    randoms = [rand_text(alphabet, 1, 14) for _ in range(3000)]
    lines = []
    for raw in fixed + randoms:
        decision = normalize_uri_path(raw)
        if decision.ok:
            expected = "OK" + "".join("\x1f" + segment for segment in decision.segments)
        else:
            expected = str(int(decision.suggested_status))
        lines.append(f"path\t{hx(raw)}\t{utf8hx(expected)}")
    return lines


def date_cases() -> list[str]:
    fixed = ["Tue, 14 Nov 2023 22:13:20 GMT", "Tuesday, 14-Nov-23 22:13:20 GMT", "Tue Nov 14 22:13:20 2023",
             "14 Nov 2023 22:13:20 +0100", "14 Nov 2023 22:13:20 -0000", "14 Nov 2023 22:13 EST", "Nov 14 2023 22:13:20",
             "14 Nov 23 22:13:20", "14 Nov 69 1:2:3", "14 Nov 68 1:2:3", "31 Feb 2023 00:00:00", "29 Feb 2024 00:00:00 Z",
             "29 Feb 2023 00:00:00", "14 Nov 2023 24:00:00", "14 Nov 2023 23:59:60", "14 Nov 2023 22.13.20",
             "14 Nov 2023 22.13", "garbage", "", "   ", "14 Nov 2023 22:13:20 +2400", "14 Nov 2023 22:13:20 +2359",
             "14 Nov 2023 22:13:20 PDT", "14 nov 2023 22:13:20 gmt", "Tue, 14 Nov 2023 22:13:20", "14 Nov 2023,",
             "Tue, 14 Nov 0001 00:00:00 GMT", "Tue, 14 Nov 10000 00:00:00 GMT", "14 Nov 2_023 22:13:20",
             "14 Nov +2023 22:13:20", "x,14 Nov 2023 22:13:20", "14 Nov 2023 22:13:20 +05_30"]
    alphabet = "0123456789 :,-+.NovTueGMTEDSTZ"
    randoms = [rand_text(alphabet, 3, 30) for _ in range(3000)]
    lines = []
    for value in fixed + randoms:
        parsed = conditional._parse_http_date(value)
        expected = "N" if parsed is None else str(int(parsed))
        lines.append(f"date\t{hx(value)}\t{hx(expected)}")
    return lines


def range_cases() -> list[str]:
    lines = []
    etag = conditional.make_etag(1000, 1700000000)
    specs = ["bytes=0-9", "bytes=-16", "bytes=5-", "bytes=999-", "bytes=1000-", "bytes=0-0", "bytes=10-5",
             "bytes=0-9,20-30", "items=0-9", "bytes=", "bytes=-", "bytes=-0", "bytes= 3 - 7 ", "BYTES=1-2",
             "bytes=abc", "bytes=1-x", "bytes=99999999999999999999999-", "bytes=-99999999999999999999",
             " bytes = 4-8", "bytes=4"]
    if_ranges = [None, etag, 'W/' + etag, '"autre"', "Tue, 14 Nov 2023 22:13:20 GMT", "Mon, 01 Jan 2001 00:00:00 GMT",
                 "n'importe quoi"]
    for size in (0, 1, 1000):
        for spec in specs:
            for if_range in if_ranges:
                d = conditional.resolve_range(spec, if_range, size, etag, 1700000000)
                expected = ("UNSAT" if d.unsatisfiable else
                            f"{d.byte_range.start}-{d.byte_range.end}" if d.byte_range else "FULL")
                lines.append(f"range\t{hx(spec)}\t{hx(if_range or '')}\t{1 if if_range is not None else 0}\t"
                             f"{hx(str(size))}\t{hx(expected)}")
    return lines


def conditional_cases() -> list[str]:
    lines = []
    etag = conditional.make_etag(927, 1700000000)
    for inm in (None, etag, "*", 'W/' + etag, '"x", ' + etag, '"x"', ""):
        for ims in (None, "Tue, 14 Nov 2023 22:13:20 GMT", "Tue, 14 Nov 2023 22:13:19 GMT", "garbage",
                    "Wed, 15 Nov 2023 00:00:00 GMT"):
            result = conditional.is_not_modified(inm, ims, etag, 1700000000)
            lines.append(f"cond\t{hx(inm or '')}\t{1 if inm is not None else 0}\t{hx(ims or '')}\t"
                         f"{1 if ims is not None else 0}\t{'1' if result else '0'}")
    for _ in range(300):
        mtime = RNG.randint(0, 4_000_000_000)
        size = RNG.randint(0, 10**9)
        lines.append(f"etag\t{hx(str(mtime))}\t{hx(str(size))}\t{hx(conditional.make_etag(size, mtime))}\t"
                     f"{hx(conditional.http_date(mtime))}")
    return lines


def misc_cases() -> list[str]:
    lines = []
    names = ["a.html", "A.HTML", "x.Css", "noext", "archive.tar.gz", "font.woff2", ".htaccess", "photo.JPEG",
             "data.json", "page.htm", "t.TXT", "s.svg", "x.", "readme.md", "a.MJS", "f.pdf", "\xe9.HTML"]
    policy = CachePolicy(extensions=dict(DEFAULT_EXTENSION_CACHE))
    for name in names:
        lines.append(f"mime\t{utf8hx(name)}\t{hx(guess_mime_type(name))}")
        lines.append(f"compress\t{utf8hx(name)}\t{'1' if is_compressible(name) else '0'}")
        lines.append(f"cache\t{hx('/x/' + name)}\t{utf8hx(name)}\t{hx(resolve_cache_control('/x/' + name, name, policy))}")
    encodings = [None, "", "gzip", "br", "gzip, br", "br;q=0.5, gzip;q=0.8", "*", "*;q=0", "gzip;q=0, *",
                 "identity", "BR, GZIP", "br;q=abc, gzip", "gzip;q=1;foo=bar", "br;q=0.0", "gzip, gzip;q=0",
                 ";q=1, br", "br ; q = 0.3 , gzip ; q = 0.3", "deflate, *;q=0.2", "br;q=nan, gzip;q=inf"]
    for value in encodings:
        result = ",".join(encoding for encoding, _ in preferred_encodings(value))
        lines.append(f"enc\t{hx(value or '')}\t{1 if value is not None else 0}\t{hx(result)}")
    return lines


def ip_cases() -> list[str]:
    from omega_serv.domain.http.headers import HttpHeaders
    from omega_serv.domain.security.trusted_proxy import (
        is_trusted_proxy,
        normalize_ip,
        resolve_client_ip,
    )

    fixed = ["1.2.3.4", "01.2.3.4", "1.2.3.4 ", "256.1.1.1", "0.0.0.0", "::", "::1", "::ffff:1.2.3.4", "::1.2.3.4",
             "1:0:0:0:0:0:0:1", "1:0:0:2:0:0:0:3", "FE80::A", "fe80::1%eth0", "fe80::1%", "fe80::1%a%b", "1::2:3:4:5:6:7",
             "1:2:3:4:5:6:7::", "::ffff:0:1.2.3.4", "1:2:3:4:5:6:7:8:9", ":1:2:3:4:5:6:7", "1:2:3:4:5:6:7:", "1::2::3",
             "12345::", "g::1", "1.2.3", "::ffff:1.2.3.4%x", "2001:db8::", "2001:db8:0:0:1:0:0:1", "unknown", "",
             "1:2:3:4:5:6:1.2.3.4", "::1.2.3", "[::1]", " ::1", "0::0", "000::0000", "::00001",
             "fe80::1%" + "z" * 36, "fe80::1%" + "z" * 37, "fe80::1%" + "z" * 50, "::ffff:1.2.3.4%" + "q" * 31,
             "fe80::1%\u00e9t", "1.2.3.\u00b2", "\u00b9.2.3.4", "fe80::\u00b2"]
    alphabet = "0123456789abcdefABCDEF:.%"
    randoms = [rand_text(alphabet, 1, 20) for _ in range(4000)]
    lines = []
    for value in fixed + randoms:
        lines.append(f"normip\t{hx(value)}\t{hx(normalize_ip(value))}")
    networks = ["127.0.0.1", "10.0.0.0/8", "1.2.3.4/24", "1.2.3.0/255.255.255.0", "1.2.3.0/0.0.0.255",
                "1.2.3.0/255.0.255.0", "::1", "fd00::/8", "2001:db8::/32", "bad", "1.2.3.4/33", "2001:db8::/129",
                "1.2.3.4/+8", "1.2.3.4/08", "100.64.0.0/10", "fe80::/10"]
    peers = ["127.0.0.1", "10.1.2.3", "1.2.3.77", "::1", "fd12::3", "2001:db8:1::1", "::ffff:127.0.0.1", "fe80::5%eth0",
             "8.8.8.8", "100.100.1.1", "bad", "::1%" + "z" * 50, "::1%" + "z" * 30]
    for i, network in enumerate(networks):
        for peer in peers:
            lines.append(f"trusted\t{hx(peer)}\t{hx(network)}\t{'1' if is_trusted_proxy(peer, [network]) else '0'}")
    trusted = ["127.0.0.1", "::1", "10.0.0.0/8"]
    xffs = [None, "", "203.0.113.5", "203.0.113.5, 10.0.0.2", "10.0.0.2, 203.0.113.5", "10.0.0.1, 10.0.0.2",
            " 1.1.1.1 ,, 2.2.2.2 ", "::ffff:8.8.8.8", "garbage, 10.0.0.9", "1.2.3.4:80"]
    fwds = [None, "for=192.0.2.60;proto=http", 'for="[2001:db8::1]:4711"', "for=10.0.0.1, for=198.51.100.17",
            "proto=https", 'For="_hidden"', "for=1.2.3.4:5678;by=x", "for=", "for=\"\""]
    for peer in ("127.0.0.1", "203.0.113.9", "::1"):
        for xff in xffs:
            for fwd in fwds:
                for pref in (["X-Forwarded-For"], ["Forwarded", "X-Forwarded-For"]):
                    pairs = []
                    if xff is not None:
                        pairs.append(("X-Forwarded-For", xff))
                    if fwd is not None:
                        pairs.append(("Forwarded", fwd))
                    got = resolve_client_ip(peer, HttpHeaders.from_pairs(pairs), trusted, pref)
                    lines.append(f"client\t{hx(peer)}\t{hx(xff or '')}\t{1 if xff is not None else 0}\t{hx(fwd or '')}\t"
                                 f"{1 if fwd is not None else 0}\t{hx(','.join(pref))}\t{hx(got)}")
    return lines


def csp_cases() -> list[str]:
    from omega_serv.domain.security.csp import allow_inline_styles_by_hash

    policies = ["default-src 'none'; style-src 'self'", "default-src 'self'", "script-src 'self'",
                "style-src 'self' 'unsafe-inline'", "style-src 'none'", "default-src 'self'; style-src  'self'  x ;",
                " ; ;default-src a;default-src b", "style-src", "img-src x;  style-src\u00a0'self'", "",
                "default-src\u2003'self'; style-src 'self'\u3000y", "STYLE-SRC 'self'", "style-src 'self';style-src z"]
    htmls = ["", "<p>rien</p>", "<style>a{}</style>", "<STYLE type=x>b{}</style >", "<style>a{}</style><style>a{}</style>",
             "<styles>x</styles>", "<style>sans fin", "<style a=1>x</style\t\n>", "<style>x</style>>y<style>z</STYLE>",
             "<style\n>y</style>", "<style_x>q</style>", "<style>\u00e9</style>", "<style><style></style></style>",
             "<style>a</ style>", "<style>a</style x>"]
    lines = []
    for policy in policies:
        for html in htmls:
            data = html.encode("utf-8")
            lines.append(f"csp\t{hx(policy.encode())}\t{hx(data)}\t{hx(allow_inline_styles_by_hash(policy, data).encode())}")
    alphabet = ["<style>", "</style>", "<STYLE ", ">", " ", "a", "</style\n >", "<style", "x"]
    for _ in range(600):
        html = "".join(RNG.choice(alphabet) for _ in range(RNG.randint(0, 12)))
        policy = RNG.choice(policies)
        data = html.encode("utf-8")
        lines.append(f"csp\t{hx(policy.encode())}\t{hx(data)}\t{hx(allow_inline_styles_by_hash(policy, data).encode())}")
    return lines


def target_cases() -> list[str]:
    """Forme absolue de la cible et ligne de requete (version stricte, 505) - plan §14, 2026-11-02."""
    import asyncio

    from omega_serv.domain.http.request import InvalidAbsoluteTarget, absolute_form_parts
    from omega_serv.infrastructure.server.http_parser import (
        ConnectionClosedCleanly,
        HttpParseError,
        read_request_head,
    )

    fixed = ["/", "/a?b", "*", "http://h/a?b", "HTTPS://h:1/x", "http://", "https://", "http:///a", "http://h",
             "http://h?q", "http://u@h/", "http://a b/", "http://a\tb/", "http://a\x7fb/", "http://\xe9/\xe9",
             "http:/h", "httpx://h/", "ftp://h/", "http://[::1]:8/x", "http://h//x", "http://h/a?b?c", "Http://h#x/y"]
    alphabet = "hH:/tps?@#a\x00\x7f\xe9 1.[]"
    targets = fixed + [rand_text(alphabet, 0, 14) for _ in range(1500)]
    lines = []
    for target in targets:
        try:
            parts = absolute_form_parts(target)
            got = "none" if parts is None else f"valid {parts[0]} {parts[1]}"
        except InvalidAbsoluteTarget:
            got = "invalid"
        lines.append(f"absform\t{hx(target)}\t{hx(got)}")

    async def parse(raw: bytes) -> str:
        reader = asyncio.StreamReader()
        reader.feed_data(raw)
        reader.feed_eof()
        try:
            head = await read_request_head(reader, 8192, 16384)
        except ConnectionClosedCleanly:
            return "closed"
        except HttpParseError as e:
            line = "-" if e.request_line is None else e.request_line
            return f"{int(e.status)} {e.reason} | {line} | {len(e.headers)}"
        return f"ok {head.method} {head.target} {head.http_version}"

    versions = ["HTTP/1.1", "HTTP/1.0", "HTTP/1.9", "HTTP/9.9", "HTTP/0.9", "HTTP/2.0", "HTTP/abc", "HTTP/1.10",
                "HTTP/1", "HTTP/", "HTTP/1.\xb9", "HTTP/\xb9.1", "http/1.1", "HTTP/1,1", "HTTP/01.1", "HTTP/1.1 "]
    heads = ["", "Host: h\r\n", "User-Agent: u\r\nX-A : 1\r\n", "Host: a\r\nExpect: x\r\n"]
    for version in versions + ["HTTP/" + rand_text("0123456789.ab", 0, 4) for _ in range(200)]:
        for extra in heads:
            raw = f"GET /p {version}\r\n{extra}\r\n".encode("latin-1")
            lines.append(f"reqline\t{hx(raw)}\t{hx(asyncio.run(parse(raw)))}")
    # flux coupe (fin de flux apres ces octets)
    for raw in (b"", b"G", b"GET /p HTTP/1.1", b"GET /p HTTP/1.1\r\n", b"GET /p HTTP/1.1\r\nHost: h\r\n",
                b"GET /p HTTP/1.1\r\nHo", b"GET /p HTTP/1.1\r\nHost: h\r", b"GET /p HTTP/9.9\r\n"):
        lines.append(f"reqline\t{hx(raw)}\t{hx(asyncio.run(parse(raw)))}")
    return lines


def ipc_cases() -> list[str]:
    """Trames du contrat IPC (lot 3) : Python encode, le C++ doit produire les memes octets et relire les memes
    champs ; trames invalides refusees des deux cotes."""
    from omega_serv.infrastructure.server import native_ipc as ipc

    frames = [
        ipc.Frame(ipc.HELLO).add_uint(1, 1, 2).add(2, "0.1.0").add(3, "static").add(3, "range").add_uint(4, 4242, 4),
        ipc.hello_ack(True),
        ipc.hello_ack(False, "contrat différent"),
        ipc.config_frame(7, b'{"format": 1}'),
        ipc.Frame(ipc.CONFIG_ACK, generation=7).add_uint(1, 0, 1).add(2, "erreur é"),
        ipc.Frame(ipc.HEALTH, generation=3).add_uint(1, 12, 8).add_uint(2, 1 << 40, 8).add_uint(3, 0, 8).add_uint(4, 3, 4),
        ipc.shutdown_frame(2.5),
        ipc.Frame(ipc.ERROR, request_id=(1 << 64) - 1).add_uint(1, 9, 2).add(2, ""),
        ipc.Frame(99, request_id=5, generation=1).add(999, b"\x00\xff"),  # type et tag inconnus : gardes tels quels
        ipc.Frame(ipc.HEALTH),
    ]
    for _ in range(300):
        frame = ipc.Frame(RNG.randint(0, 65535), RNG.randint(0, (1 << 64) - 1), RNG.randint(0, (1 << 32) - 1))
        for _ in range(RNG.randint(0, 6)):
            frame.add(RNG.randint(0, 65535), bytes(RNG.randint(0, 255) for _ in range(RNG.randint(0, 40))))
        frames.append(frame)
    lines = []
    for frame in frames:
        fields = ";".join(f"{tag}:{value.hex()}" for tag, value in frame.fields)
        lines.append(f"ipc\t{ipc.encode(frame).hex()}\t{frame.type}\t{frame.request_id}\t{frame.generation}\t{fields}")
    good = ipc.encode(ipc.hello_ack(True))
    bad = [
        good[:10],
        b"XXXX" + good[4:],
        good[:4] + (2).to_bytes(2, "little") + good[6:],
        good + b"\x00",
        good[:-1],
        ipc.encode(ipc.Frame(1).add(1, b"abc"))[:-1][:20] + (9).to_bytes(4, "little") + b"\x01\x00\x03\x00\x00\x00ab",
    ]
    for _ in range(300):
        data = bytearray(ipc.encode(RNG.choice(frames)))
        for _ in range(RNG.randint(1, 3)):
            data[RNG.randrange(len(data))] = RNG.randint(0, 255)
        bad.append(bytes(data))
    for data in bad:
        try:
            ipc.decode(data)
            verdict = "ok"
        except ipc.FrameError:
            verdict = "refuse"
        lines.append(f"ipcdecode\t{data.hex()}\t{verdict}")
    return lines


def main() -> int:
    out = Path(sys.argv[1])
    out.parent.mkdir(parents=True, exist_ok=True)
    lines = path_cases() + date_cases() + range_cases() + conditional_cases() + misc_cases() + ip_cases() + csp_cases() + target_cases() + ipc_cases()
    out.write_text("\n".join(lines) + "\n", encoding="ascii")
    print(f"{len(lines)} vecteurs -> {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
