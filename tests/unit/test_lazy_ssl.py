"""`ssl` charge seulement quand il sert (memoire, 2026-11-19, OMEGA-SERV_ETUDE_PROXY_ET_MEMOIRE.md §11) : asyncio
charge sans `ssl` puis rebranche au premier `import ssl` ; contextes TLS client du reverse proxy seulement avec un
backend HTTPS. Chaque cas dans un interpreteur neuf (`defer_ssl_import` n'agit qu'avant le premier import d'asyncio)."""
from __future__ import annotations

import ast
import asyncio
import json
import subprocess
import sys
import unittest
from pathlib import Path

from omega_serv.infrastructure.process.lazy_ssl import ASYNCIO_SSL_USERS

_SRC = Path(__file__).resolve().parents[2] / "src"

_TLS_AFTER_DEFER = """
import json, subprocess, sys, tempfile
from pathlib import Path
from omega_serv.infrastructure.process.lazy_ssl import defer_ssl_import
applied = defer_ssl_import()
import asyncio, asyncio.base_events
before = {"applied": applied, "ssl_loaded": "ssl" in sys.modules, "asyncio_ssl": asyncio.base_events.ssl is None}
import ssl  # premier vrai import : rebranche dans asyncio
tmp = Path(tempfile.mkdtemp())
subprocess.run(["openssl", "req", "-x509", "-newkey", "ec", "-pkeyopt", "ec_paramgen_curve:prime256v1", "-nodes",
                "-keyout", str(tmp / "k.pem"), "-out", str(tmp / "c.pem"), "-days", "1", "-subj", "/CN=localhost"],
               check=True, capture_output=True)
server_ctx = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER); server_ctx.load_cert_chain(tmp / "c.pem", tmp / "k.pem")
client_ctx = ssl.create_default_context(); client_ctx.check_hostname = False; client_ctx.verify_mode = ssl.CERT_NONE

async def main():
    async def handle(reader, writer):
        writer.write(await reader.readline()); await writer.drain(); writer.close()
    server = await asyncio.start_server(handle, "127.0.0.1", 0, ssl=server_ctx)
    port = server.sockets[0].getsockname()[1]
    reader, writer = await asyncio.open_connection("127.0.0.1", port, ssl=client_ctx)
    writer.write(b"bonjour\\n"); await writer.drain()
    answer = await reader.readline(); writer.close(); server.close()
    return answer.decode()

import asyncio.sslproto
print(json.dumps({**before, "echo": asyncio.run(main()),
                  "patched": all(sys.modules[m].ssl is ssl for m in %r),
                  "again_errors": hasattr(asyncio.sslproto, "SSLAgainErrors")}))
"""

_PROXY_CONTEXTS = """
import json, sys, tempfile
from pathlib import Path
from omega_serv.infrastructure.process.lazy_ssl import defer_ssl_import
defer_ssl_import()
from omega_serv.application.server.start_server import build_server, reload_server
from omega_serv.domain.config.entities import OmegaServConfig
from omega_serv.infrastructure.filesystem.local_filesystem import LocalFilesystem
from omega_serv.infrastructure.logging.file_line_logger import FileLineLogger
root = Path(tempfile.mkdtemp()); (root / "webroot").mkdir()
fs = LocalFilesystem()
def config(use_tls):
    return OmegaServConfig.from_dict({"server": {"bind": "127.0.0.1", "port": 0}, "options": {"reverse_proxy": {
        "enabled": True, "zones": [{"url_prefix": "/api/", "upstreams": [{"host": "127.0.0.1", "port": 9,
                                                                         "use_tls": use_tls}]}]}}})
server = build_server(config(False), root, fs, FileLineLogger())
http_only = {"tls": server.has_proxy_tls, "ssl_loaded": "ssl" in sys.modules}
reload_server(server, config(True), root, fs)
print(json.dumps({"http_only": http_only, "after_https_reload": server.has_proxy_tls}))
"""


def _run(code: str) -> dict:
    done = subprocess.run([sys.executable, "-I", "-c", f"import sys; sys.path.insert(0, {str(_SRC)!r})\n{code}"],
                          capture_output=True, text=True, timeout=120, check=True)
    return json.loads(done.stdout.strip().splitlines()[-1])


class TestDeferredSsl(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.result = _run(_TLS_AFTER_DEFER % (ASYNCIO_SSL_USERS,))

    def test_asyncio_loaded_without_ssl(self):
        self.assertEqual((self.result["applied"], self.result["ssl_loaded"], self.result["asyncio_ssl"]),
                         (True, False, True))

    def test_tls_server_and_client_work_after_late_import(self):
        self.assertEqual(self.result["echo"], "bonjour\n")
        self.assertTrue(self.result["patched"])
        self.assertTrue(self.result["again_errors"])

    def test_noop_when_asyncio_already_loaded(self):
        from omega_serv.infrastructure.process.lazy_ssl import defer_ssl_import
        self.assertIn("asyncio", sys.modules)
        self.assertFalse(defer_ssl_import())


class TestAsyncioSslUsersStillKnown(unittest.TestCase):
    """Une version de Python qui ajouterait un module d'asyncio dependant de `ssl` a l'import ferait echouer ce
    test : ASYNCIO_SSL_USERS (et le rebranchement) serait alors a completer."""

    def test_modules_importing_ssl(self):
        folder = Path(asyncio.__file__).parent
        users = set()
        for path in folder.glob("*.py"):
            tree = ast.parse(path.read_text(encoding="utf-8"))
            for node in tree.body:
                imports = [node] if isinstance(node, ast.Import) else [
                    n for n in ast.walk(node) if isinstance(n, ast.Import)] if isinstance(node, ast.Try) else []
                if any(alias.name == "ssl" for imp in imports for alias in imp.names):
                    users.add(f"asyncio.{path.stem}")
        self.assertEqual(users, set(ASYNCIO_SSL_USERS))

    def test_only_sslproto_computes_from_ssl_at_import(self):
        folder = Path(asyncio.__file__).parent
        computed = {}
        for name in ASYNCIO_SSL_USERS:
            tree = ast.parse((folder / f"{name.split('.')[1]}.py").read_text(encoding="utf-8"))
            for node in tree.body:
                if isinstance(node, ast.If) and "ssl" in ast.unparse(node.test):
                    computed[name] = sorted(t.id for n in ast.walk(node) if isinstance(n, ast.Assign)
                                            for t in n.targets if isinstance(t, ast.Name))
        self.assertEqual(computed, {"asyncio.sslproto": ["SSLAgainErrors"]})


class TestProxyTlsContexts(unittest.TestCase):
    def test_created_only_with_an_https_backend(self):
        result = _run(_PROXY_CONTEXTS)
        self.assertEqual(result["http_only"], {"tls": False, "ssl_loaded": False})
        self.assertTrue(result["after_https_reload"])


if __name__ == "__main__":
    unittest.main()
