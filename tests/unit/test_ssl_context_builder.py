# Copyright (c) 2026 kraynux - kraynux@proton.me - Licence MIT (voir fichier LICENSE)
"""Couvre build_client_ssl_context (contexte CLIENT pour le reverse
proxy sortant vers un upstream HTTPS, OMEGA-SERV_PLAN-DETAILLE_
REVERSE_PROXY.md §5.3) - build_ssl_context (contexte SERVEUR) n'avait
jamais eu de test unitaire dedie avant l'audit securite du
2026-09-14 (seulement les tests d'integration TLS reels,
tests/integration/test_tls_server.py) ; TestBuildServerSslContextCiphers
ci-dessous couvre desormais specifiquement la restriction de suites de
chiffrement ajoutee par ce correctif, avec un vrai certificat auto-signe
(openssl reel, meme discipline que test_asyncio_http_proxy_client.py)."""
import shutil
import ssl
import tempfile
import unittest
from pathlib import Path

from omega_serv.domain.config.entities import TlsConfig
from omega_serv.domain.security.tls.entities import SelfSignedCertParams
from omega_serv.infrastructure.process.subprocess_runner import SubprocessRunner
from omega_serv.infrastructure.tls.openssl_certificate_tool import OpensslCertificateTool
from omega_serv.infrastructure.tls.ssl_context_builder import (
    build_client_ssl_context,
    build_ssl_context,
)

_OPENSSL_MISSING = shutil.which("openssl") is None


class TestBuildClientSslContext(unittest.TestCase):
    def test_verified_by_default_uses_strict_verification(self):
        context = build_client_ssl_context()
        self.assertTrue(context.check_hostname)
        self.assertEqual(context.verify_mode, ssl.CERT_REQUIRED)

    def test_explicit_verified_true_matches_default(self):
        context = build_client_ssl_context(verify_upstream_tls=True)
        self.assertTrue(context.check_hostname)
        self.assertEqual(context.verify_mode, ssl.CERT_REQUIRED)

    def test_unverified_disables_hostname_check_and_verification(self):
        context = build_client_ssl_context(verify_upstream_tls=False)
        self.assertFalse(context.check_hostname)
        self.assertEqual(context.verify_mode, ssl.CERT_NONE)

    def test_returns_a_client_purpose_context(self):
        # PROTOCOL_TLS_CLIENT (via create_default_context), jamais un
        # contexte serveur - distinction non negociable du §5.3.
        context = build_client_ssl_context()
        self.assertEqual(context.protocol, ssl.PROTOCOL_TLS_CLIENT)


@unittest.skipIf(_OPENSSL_MISSING, "openssl introuvable sur ce systeme")
class TestBuildServerSslContextCiphers(unittest.TestCase):
    """Retour utilisateur (audit securite) : les bornes de version TLS
    etaient deja configurables, mais aucune suite de chiffrement n'etait
    fixee explicitement - la selection dependait entierement des
    defauts OpenSSL du systeme, qui peuvent encore autoriser des suites
    CBC/sans confidentialite persistante en TLS1.2."""

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.root = Path(self._tmp.name)
        key_path = self.root / "secure" / "certificates" / "server" / "server.key"
        cert_path = self.root / "secure" / "certificates" / "server" / "server.pem"
        key_path.parent.mkdir(parents=True)
        tool = OpensslCertificateTool(SubprocessRunner())
        params = SelfSignedCertParams(common_name="localhost", san_dns=("localhost",), san_ip=("127.0.0.1",))
        tool.generate_self_signed(params, key_path, cert_path)

    def tearDown(self):
        self._tmp.cleanup()

    def test_only_ecdhe_and_aead_ciphers_are_enabled(self):
        context = build_ssl_context(TlsConfig(), self.root)
        cipher_names = {c["name"] for c in context.get_ciphers()}
        self.assertTrue(cipher_names, "aucune suite de chiffrement activee")
        for name in cipher_names:
            # TLS 1.3 (TLS_*) est deja exclusivement AEAD par construction
            # du protocole, jamais concerne par set_ciphers() - seules les
            # suites TLS 1.2 nommees explicitement sont verifiees ici.
            if name.startswith("TLS_"):
                continue
            self.assertTrue(name.startswith("ECDHE-"), f"suite non-ECDHE inattendue : {name}")
            self.assertTrue(
                "GCM" in name or "CHACHA20" in name,
                f"suite non-AEAD inattendue (probablement CBC) : {name}",
            )

    def test_known_weak_ciphers_are_never_enabled(self):
        context = build_ssl_context(TlsConfig(), self.root)
        cipher_names = {c["name"] for c in context.get_ciphers()}
        for weak_fragment in ("RC4", "3DES", "MD5", "NULL", "EXPORT", "CBC"):
            self.assertFalse(
                any(weak_fragment in name for name in cipher_names),
                f"suite faible activee contenant {weak_fragment!r}",
            )


if __name__ == "__main__":
    unittest.main()
