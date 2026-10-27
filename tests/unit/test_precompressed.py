"""Fichiers pre-compresses (OMEGA-SERV_ETUDE_PERFORMANCE.md, priorite 5)."""
import gzip
import os
import tempfile
import time
import unittest
from dataclasses import replace
from pathlib import Path

from omega_serv.application.server.serve_static_file import serve_static_file
from omega_serv.domain.config.entities import SecurityConfig
from omega_serv.domain.http.headers import HttpHeaders
from omega_serv.domain.http.precompressed import is_compressible, preferred_encodings
from omega_serv.domain.http.status_codes import HttpStatus
from omega_serv.infrastructure.filesystem.local_filesystem import LocalFilesystem
from omega_serv.infrastructure.filesystem.safe_path_resolver import SafePathResolver
from tests.unit.test_serve_static_file import _make_request


class TestPreferredEncodings(unittest.TestCase):
    def test_order_and_quality(self):
        self.assertEqual(preferred_encodings("gzip, deflate, br"), [("br", ".br"), ("gzip", ".gz")])
        self.assertEqual(preferred_encodings("gzip;q=1, br;q=0.5"), [("gzip", ".gz"), ("br", ".br")])
        self.assertEqual(preferred_encodings("gzip"), [("gzip", ".gz")])
        self.assertEqual(preferred_encodings("br;q=0, gzip"), [("gzip", ".gz")])
        self.assertEqual(preferred_encodings("*"), [("br", ".br"), ("gzip", ".gz")])
        self.assertEqual(preferred_encodings("*, br;q=0"), [("gzip", ".gz")])
        self.assertEqual(preferred_encodings("identity"), [])
        self.assertEqual(preferred_encodings(None), [])
        self.assertEqual(preferred_encodings("gzip;q=abc"), [])

    def test_only_text_types(self):
        for name in ("a.css", "A.JS", "x.html", "d.json", "i.svg"):
            self.assertTrue(is_compressible(name), name)
        for name in ("a.png", "v.mp4", "z.gz", "noext"):
            self.assertFalse(is_compressible(name), name)


class TestServePrecompressed(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        base = Path(self._tmp.name).resolve()
        self.webroot = base / "webroot"
        self.webroot.mkdir()
        self.css = b"body { color: red; }\n" * 50
        (self.webroot / "app.css").write_bytes(self.css)
        (self.webroot / "app.css.gz").write_bytes(gzip.compress(self.css))
        (self.webroot / "app.css.br").write_bytes(b"BROTLI")
        (self.webroot / "img.png").write_bytes(b"png")
        (self.webroot / "img.png.gz").write_bytes(b"jamais")
        self.resolver = SafePathResolver(LocalFilesystem(), self.webroot)

    def tearDown(self):
        self._tmp.cleanup()

    def _get(self, path, **headers):
        request = replace(_make_request("GET", path), headers=HttpHeaders.from_pairs(list(headers.items())))
        return serve_static_file(request, self.resolver, LocalFilesystem(), SecurityConfig(), index_files=("index.html",))

    def test_brotli_preferred_then_gzip_then_identity(self):
        br = self._get("/app.css", **{"accept-encoding": "gzip, br"})
        self.assertEqual((br.headers["Content-Encoding"], br.body), ("br", b"BROTLI"))
        self.assertEqual(br.headers["Content-Type"], "text/css; charset=utf-8")
        self.assertEqual(br.headers["Vary"], "Accept-Encoding")
        gz = self._get("/app.css", **{"accept-encoding": "gzip"})
        self.assertEqual(gzip.decompress(gz.body), self.css)
        self.assertEqual(gz.headers["Content-Length"], str(len(gz.body)))
        plain = self._get("/app.css")
        self.assertNotIn("Content-Encoding", plain.headers)
        self.assertEqual(plain.headers["Vary"], "Accept-Encoding")
        self.assertEqual(plain.body, self.css)
        self.assertEqual(len({br.headers["ETag"], gz.headers["ETag"], plain.headers["ETag"]}), 3)

    def test_revalidation_uses_the_encoded_etag(self):
        gz = self._get("/app.css", **{"accept-encoding": "gzip"})
        again = self._get("/app.css", **{"accept-encoding": "gzip", "if-none-match": gz.headers["ETag"]})
        self.assertEqual(again.status, HttpStatus.NOT_MODIFIED)
        changed = self._get("/app.css", **{"if-none-match": gz.headers["ETag"]})
        self.assertEqual(changed.status, HttpStatus.OK)

    def test_stale_variant_is_ignored(self):
        old = time.time() - 3600
        os.utime(self.webroot / "app.css.br", (old, old))
        response = self._get("/app.css", **{"accept-encoding": "br, gzip"})
        self.assertEqual(response.headers["Content-Encoding"], "gzip")

    def test_variant_linking_elsewhere_is_ignored(self):
        outside = self.webroot.parent / "ailleurs.gz"
        outside.write_bytes(b"secret")
        (self.webroot / "app.css.gz").unlink()
        (self.webroot / "app.css.gz").symlink_to(outside)
        response = self._get("/app.css", **{"accept-encoding": "gzip"})
        self.assertNotIn("Content-Encoding", response.headers)
        self.assertEqual(response.body, self.css)

    def test_images_are_never_looked_up(self):
        response = self._get("/img.png", **{"accept-encoding": "gzip"})
        self.assertEqual(response.body, b"png")
        self.assertNotIn("Vary", response.headers)


if __name__ == "__main__":
    unittest.main()
