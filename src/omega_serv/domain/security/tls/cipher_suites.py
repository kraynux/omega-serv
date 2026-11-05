"""Suites de chiffrement TLS 1.2 du serveur (doc TLS §12.1) - une seule source pour le contexte ssl Python
(infrastructure/tls/ssl_context_builder.py) et pour le moteur natif (instantane, plan moteur C++ lot 3b).
TLS 1.3 : suites par defaut d'OpenSSL, des deux cotes."""
from __future__ import annotations

MODERN_CIPHER_SUITES = (
    "ECDHE-ECDSA-AES128-GCM-SHA256:ECDHE-RSA-AES128-GCM-SHA256:"
    "ECDHE-ECDSA-AES256-GCM-SHA384:ECDHE-RSA-AES256-GCM-SHA384:"
    "ECDHE-ECDSA-CHACHA20-POLY1305:ECDHE-RSA-CHACHA20-POLY1305"
)
