# Copyright (c) 2026 kraynux - kraynux@proton.me - Licence MIT (voir fichier LICENSE)
"""Rapport complet (projets 3.0.0 §7.7 et §7.10, decisions de l'auteur du 2026-11-15) : voir d'un coup ce qui est
configure et actif, cote systeme et reglages (jamais le trafic des visiteurs).

Le rapport est d'abord une **charge brute** (codes, nombres, booleens, chemins), sans texte traduit : c'est l'export
JSON, comparable d'une date a l'autre, et la base de la presentation (`full_report_presentation.py`), rendue dans
la langue des exports. **Jamais de secret** : ni hachage, ni cle, ni jeton - au plus « defini » ou « absent » ;
les reglages detailles des options passent par `scrub` qui masque toute cle sensible."""
from __future__ import annotations

from typing import Any

SECTIONS_MINIMUM = ("identity", "service", "listen", "tls", "options", "counts", "security", "checks", "backups",
                    "logs")
"""Minimum non desactivable (liste validee par l'auteur le 2026-11-15)."""
DETAIL_KEYS = ("zones", "reverse_proxy", "waf", "active_defense", "logs_library", "options_settings", "audit")
"""Cases en plus du minimum : le detail va dans l'export (l'ecran montre le sommaire)."""

_SECRET_MARKERS = ("password", "secret", "token", "private_key", "api_key", "passphrase", "hash", "credential")


def scrub(value: Any) -> Any:
    """Copie sans secret : toute cle dont le nom evoque un secret devient « defini »/« absent » (booleen)."""
    if isinstance(value, dict):
        return {key: (bool(item) if any(marker in str(key).lower() for marker in _SECRET_MARKERS) else scrub(item))
                for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [scrub(item) for item in value]
    return value


def proxy_mode(proxy_enabled: bool, prefixes: list[str]) -> str:
    """« web », « proxy » (une zone couvre « / » : tout part vers les backends) ou « both »."""
    if not proxy_enabled or not prefixes:
        return "web"
    return "proxy" if "/" in prefixes else "both"
