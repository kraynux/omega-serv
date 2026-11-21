"""Moteur des zones du reverse proxy (plan proxy natif v2, lot 3 : P8 et budgets C2).

`options.reverse_proxy.engine` :
- `auto` (defaut) : chaque zone est relayee par le moteur natif si elle le peut, confiee a Python sinon ;
- `native` : une zone qui ne peut pas etre native est une erreur de configuration ;
- `python` : toutes les zones sont confiees a Python (retour en arriere sans recompiler).
Sans effet avec `server.engine = python` (decision de l'auteur du 2026-11-13) : ce retour en arriere doit toujours
demarrer.

Budgets globaux du relais natif (decision de l'auteur du 2026-11-13 : options reglables), jamais appliques par le
moteur Python. Budget epuise : 503 immediat (C2)."""
from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Any

from omega_serv.core.i18n import _

PROXY_ENGINES = ("auto", "native", "python")

DEFAULT_MAX_PENDING_BODY_MB = 128
"""Memoire de tous les corps de requete recus en entier avant leur envoi au backend (C2)."""
DEFAULT_MAX_CONCURRENT_INSPECTIONS = 64
"""INSPECT en attente de verdict, tous fils confondus (C2)."""
DEFAULT_MAX_UPSTREAM_CONNECTIONS = 512
"""Connexions ouvertes vers les backends, tous fils confondus (C2, C9 : plafond global reparti, jamais multiplie)."""

_LIMITS = {
    "max_pending_body_mb": (1, 65_536),
    "max_concurrent_inspections": (1, 100_000),
    "max_upstream_connections": (1, 1_000_000),
}


@dataclass(frozen=True)
class ProxyEngineSettings:
    engine: str = "auto"
    max_pending_body_mb: int = DEFAULT_MAX_PENDING_BODY_MB
    max_concurrent_inspections: int = DEFAULT_MAX_CONCURRENT_INSPECTIONS
    max_upstream_connections: int = DEFAULT_MAX_UPSTREAM_CONNECTIONS

    @property
    def max_pending_body_bytes(self) -> int:
        return self.max_pending_body_mb * 1024 * 1024


def _is_int(value: Any) -> bool:
    return isinstance(value, int) and not isinstance(value, bool)


def parse_proxy_engine_settings(settings: dict[str, Any]) -> ProxyEngineSettings:
    """Valeurs deja validees par `validate_proxy_engine_settings` ; une valeur illisible reprend son defaut."""
    defaults = ProxyEngineSettings()
    engine = settings.get("engine", defaults.engine)

    def number(key: str, default: int) -> int:
        value = settings.get(key, default)
        return value if _is_int(value) else default

    return ProxyEngineSettings(
        engine=engine if engine in PROXY_ENGINES else defaults.engine,
        max_pending_body_mb=number("max_pending_body_mb", defaults.max_pending_body_mb),
        max_concurrent_inspections=number("max_concurrent_inspections", defaults.max_concurrent_inspections),
        max_upstream_connections=number("max_upstream_connections", defaults.max_upstream_connections),
    )


def validate_proxy_engine_settings(settings: dict[str, Any], max_request_size: int) -> list[str]:
    errors: list[str] = []
    engine = settings.get("engine", "auto")
    if engine not in PROXY_ENGINES:
        errors.append(_("options.reverse_proxy.engine doit valoir {values} (reçu : {value!r})").format(
            values=", ".join(PROXY_ENGINES), value=engine))
    for key, (low, high) in _LIMITS.items():
        if key not in settings:
            continue
        value = settings[key]
        if not _is_int(value) or not low <= value <= high:
            errors.append(_("options.reverse_proxy.{key} doit être un entier entre {low} et {high}").format(
                key=key, low=low, high=high))
    pending = settings.get("max_pending_body_mb", DEFAULT_MAX_PENDING_BODY_MB)
    if _is_int(pending) and pending * 1024 * 1024 < max_request_size:
        # Un corps de la taille maximale acceptee doit pouvoir attendre son envoi : sinon 503 a coup sur.
        errors.append(_("options.reverse_proxy.max_pending_body_mb ({value} Mo) doit être au moins égal à "
                        "server.max_request_size ({needed} Mo)").format(
            value=pending, needed=math.ceil(max_request_size / (1024 * 1024))))
    return errors
