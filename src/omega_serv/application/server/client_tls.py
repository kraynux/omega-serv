# Copyright (c) 2026 kraynux - kraynux@proton.me - Licence MIT (voir fichier LICENSE)
"""Fabrique du contexte TLS client de secours (scan de securite n° 1, F36 : un backend HTTPS ne recoit jamais
None). Enregistree au demarrage par start_server (build_client_ssl_context) : ni la couche application ni la TUI
n'importent l'infrastructure TLS, et ce module leger ne charge pas le code du proxy quand l'option est coupee."""
from __future__ import annotations

import functools
from collections.abc import Callable
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    import ssl

_factory: Callable[[bool], ssl.SSLContext] | None = None


def set_client_context_factory(factory: Callable[[bool], ssl.SSLContext]) -> None:
    global _factory
    _factory = factory
    fallback_client_context.cache_clear()


@functools.cache
def fallback_client_context(verify: bool) -> ssl.SSLContext:
    """Jamais de requete en clair a la place : sans fabrique enregistree, la requete echoue (502)."""
    if _factory is None:
        raise ConnectionError("client TLS context unavailable")
    return _factory(verify)
