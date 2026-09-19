"""Construction du ssl.SSLContext reel (doc TLS §2 : "infrastructure/ :
... gestion contexte ssl.SSLContext Python", §12.1). La validation
metier de coherence (fichiers presents, cle/certificat correspondants,
expiration...) reste dans domain/application - ce module se contente de
charger un contexte a partir d'une configuration deja validee."""
from __future__ import annotations

import os
import ssl
from pathlib import Path

from omega_serv.domain.config.entities import TlsConfig

_VERSION_MAP: dict[str, ssl.TLSVersion] = {
    "TLS1.2": ssl.TLSVersion.TLSv1_2,
    "TLS1.3": ssl.TLSVersion.TLSv1_3,
}

_MODERN_CIPHER_SUITES = (
    "ECDHE-ECDSA-AES128-GCM-SHA256:ECDHE-RSA-AES128-GCM-SHA256:"
    "ECDHE-ECDSA-AES256-GCM-SHA384:ECDHE-RSA-AES256-GCM-SHA384:"
    "ECDHE-ECDSA-CHACHA20-POLY1305:ECDHE-RSA-CHACHA20-POLY1305"
)


def build_ssl_context(tls_config: TlsConfig, project_root: Path) -> ssl.SSLContext:
    context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
    context.minimum_version = _VERSION_MAP[tls_config.min_version]
    context.maximum_version = _VERSION_MAP[tls_config.max_version]
    context.set_ciphers(_MODERN_CIPHER_SUITES)

    passphrase = None
    if tls_config.private_key_passphrase_env:
        passphrase = os.environ.get(tls_config.private_key_passphrase_env) or None

    cert_path = project_root / tls_config.certificate_path
    key_path = project_root / tls_config.private_key_path
    context.load_cert_chain(certfile=str(cert_path), keyfile=str(key_path), password=passphrase)
    return context


def build_client_ssl_context(verify_upstream_tls: bool = True) -> ssl.SSLContext:
    """Contexte CLIENT (verifie le certificat d'un backend), pour le
    reverse proxy sortant vers un upstream HTTPS (OMEGA-SERV_PLAN-
    DETAILLE_REVERSE_PROXY.md §5.3) - jamais un contexte serveur comme
    build_ssl_context ci-dessus. Verification stricte par defaut
    (magasin de confiance systeme, via ssl.create_default_context) ;
    `verify_upstream_tls=False` desactive explicitement la verification
    (backend interne en certificat auto-signe) - documente comme
    dangereux (MITM possible sur le reseau intermediaire), jamais un
    raccourci silencieux."""
    context = ssl.create_default_context()
    if not verify_upstream_tls:
        context.check_hostname = False
        context.verify_mode = ssl.CERT_NONE
    return context
