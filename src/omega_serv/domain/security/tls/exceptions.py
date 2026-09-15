# Copyright (c) 2026 kraynux - kraynux@proton.me - Licence MIT (voir fichier LICENSE)
"""Exceptions du module TLS."""
from __future__ import annotations

from omega_serv.core.exceptions import OmegaServError


class TlsError(OmegaServError):
    """Racine des erreurs TLS."""


class CertificateToolError(TlsError):
    """Echec d'un appel a l'outil de certificat (openssl) - generation,
    inspection ou verification de correspondance cle/certificat."""
