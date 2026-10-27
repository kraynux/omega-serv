"""Envoi des gros fichiers par blocs (OMEGA-SERV_ETUDE_PERFORMANCE.md, priorite 1) :
au-dela de STREAM_THRESHOLD_BYTES, le fichier n'est jamais charge en memoire - copie
`sendfile` en HTTP, blocs lus hors de la boucle a travers TLS. Vrai serveur, vrais octets
compares a l'original, en HTTP et en HTTPS (certificat reel via openssl)."""
import asyncio
import gzip
import hashlib
import http.client
import os
import shutil
import ssl
import tempfile
import unittest
from pathlib import Path

from omega_serv.application.server.serve_static_file import STREAM_THRESHOLD_BYTES
from omega_serv.application.server.start_server import build_server
from omega_serv.domain.config.entities import OmegaServConfig
from omega_serv.domain.security.tls.entities import SelfSignedCertParams
from omega_serv.infrastructure.clock.system_clock import SystemClock
from omega_serv.infrastructure.filesystem.local_filesystem import LocalFilesystem
from omega_serv.infrastructure.logging.file_line_logger import FileLineLogger
from omega_serv.infrastructure.process.subprocess_runner import SubprocessRunner
from omega_serv.infrastructure.tls.openssl_certificate_tool import OpensslCertificateTool

_BIG = STREAM_THRESHOLD_BYTES * 8 + 12345  # taille volontairement non alignee


class _StreamingCase(unittest.IsolatedAsyncioTestCase):
    tls = False

    async def asyncSetUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.root = Path(self._tmp.name)
        webroot = self.root / "webroot"
        webroot.mkdir()
        self.big = os.urandom(_BIG)
        (webroot / "big.bin").write_bytes(self.big)
        (webroot / "small.txt").write_bytes(b"petit")
        self.css = b"body { color: red; }\n" * 200
        (webroot / "site.css").write_bytes(self.css)
        (webroot / "site.css.gz").write_bytes(gzip.compress(self.css))
        config = {"server": {"bind": "127.0.0.1", "port": 0}, "security": {"hsts_enabled": False},
                  "logs": {"access_log": "var/log/access.log"}}
        if self.tls:
            key = self.root / "secure/certificates/server/server.key"
            self.cert = self.root / "secure/certificates/server/server.pem"
            OpensslCertificateTool(SubprocessRunner()).generate_self_signed(
                SelfSignedCertParams(common_name="localhost", san_dns=("localhost",), san_ip=("127.0.0.1",)),
                key, self.cert,
            )
            config["tls"] = {"enabled": True, "mode": "direct", "certificate": {
                "certificate_path": "secure/certificates/server/server.pem",
                "private_key_path": "secure/certificates/server/server.key",
            }}
        self.server = build_server(OmegaServConfig.from_dict(config), self.root, LocalFilesystem(),
                                   FileLineLogger(), SystemClock())
        await self.server.start()
        self.port = self.server.sockets[0].getsockname()[1]

    async def asyncTearDown(self):
        await self.server.close()
        self._tmp.cleanup()

    def _connection(self):
        if not self.tls:
            return http.client.HTTPConnection("127.0.0.1", self.port, timeout=10)
        context = ssl.create_default_context(cafile=str(self.cert))
        context.check_hostname = False
        return http.client.HTTPSConnection("127.0.0.1", self.port, timeout=10, context=context)

    def _requests_sync(self, *requests):
        """Plusieurs requetes sur la MEME connexion (keep-alive apres un corps envoye par blocs)."""
        conn = self._connection()
        results = []
        try:
            for method, path in requests:
                conn.request(method, path)
                resp = conn.getresponse()
                results.append((resp.status, dict(resp.getheaders()), resp.read()))
        finally:
            conn.close()
        return results

    async def test_big_file_is_identical_and_connection_stays_usable(self):
        results = await asyncio.to_thread(
            self._requests_sync, ("GET", "/big.bin"), ("GET", "/small.txt"), ("GET", "/big.bin"),
        )
        (s1, h1, b1), (s2, _, b2), (s3, _, b3) = results
        self.assertEqual((s1, s2, s3), (200, 200, 200))
        self.assertEqual(int(h1["Content-Length"]), _BIG)
        self.assertEqual(hashlib.sha256(b1).digest(), hashlib.sha256(self.big).digest())
        self.assertEqual(b2, b"petit")
        self.assertEqual(b3, self.big)

    async def test_head_on_big_file_sends_length_without_body(self):
        [(status, headers, body)] = await asyncio.to_thread(self._requests_sync, ("HEAD", "/big.bin"))
        self.assertEqual(status, 200)
        self.assertEqual(int(headers["Content-Length"]), _BIG)
        self.assertEqual(body, b"")

    async def test_access_log_records_the_real_size(self):
        await asyncio.to_thread(self._requests_sync, ("GET", "/big.bin"))
        await asyncio.sleep(0.05)
        line = (self.root / "var/log/access.log").read_text().splitlines()[-1]
        self.assertIn(f" 200 {_BIG} ", line)


    def _raw_sync(self, method, path, headers):
        conn = self._connection()
        try:
            conn.request(method, path, headers=headers)
            resp = conn.getresponse()
            return resp.status, dict(resp.getheaders()), resp.read()
        finally:
            conn.close()

    async def test_revalidation_gives_an_empty_304(self):
        [(status, headers, _)] = await asyncio.to_thread(self._requests_sync, ("GET", "/big.bin"))
        self.assertEqual(status, 200)
        status, headers304, body = await asyncio.to_thread(
            self._raw_sync, "GET", "/big.bin", {"If-None-Match": headers["ETag"]},
        )
        self.assertEqual(status, 304)
        self.assertEqual(body, b"")
        self.assertNotIn("Content-Length", headers304)
        self.assertEqual(headers304["ETag"], headers["ETag"])

    async def test_precompressed_variant_is_served_when_accepted(self):
        status, headers, body = await asyncio.to_thread(
            self._raw_sync, "GET", "/site.css", {"Accept-Encoding": "gzip"},
        )
        self.assertEqual(status, 200)
        self.assertEqual(headers["Content-Encoding"], "gzip")
        self.assertEqual(headers["Vary"], "Accept-Encoding")
        self.assertEqual(gzip.decompress(body), self.css)
        status, headers, body = await asyncio.to_thread(self._raw_sync, "GET", "/site.css", {})
        self.assertNotIn("Content-Encoding", headers)
        self.assertEqual(body, self.css)

    async def test_resuming_a_big_file_from_an_offset(self):
        offset = _BIG - 300_000
        status, headers, body = await asyncio.to_thread(
            self._raw_sync, "GET", "/big.bin", {"Range": f"bytes={offset}-"},
        )
        self.assertEqual(status, 206)
        self.assertEqual(headers["Content-Range"], f"bytes {offset}-{_BIG - 1}/{_BIG}")
        self.assertEqual(body, self.big[offset:])


class TestStaticStreamingHttp(_StreamingCase):
    tls = False


@unittest.skipIf(shutil.which("openssl") is None, "openssl introuvable sur ce systeme")
class TestStaticStreamingHttps(_StreamingCase):
    tls = True


del _StreamingCase


if __name__ == "__main__":
    unittest.main()
