"""Entite requete HTTP.

Forme fixee dans OMEGA-SERV_WAF_LUA_DEPERSONNALISATION.md ("Acquisition
de requete") : c'est la representation normalisee que le serveur
construit et que TOUT le reste (WAF, auth, zones, handlers) consomme,
sans jamais dependre de l'implementation reseau/parsing sous-jacente.
"""
from __future__ import annotations

from dataclasses import dataclass

from omega_serv.domain.http.headers import HttpHeaders


@dataclass(frozen=True)
class HttpRequest:
    request_id: str
    remote_ip: str
    peer_ip: str
    method: str
    path: str
    raw_path: str
    query: str
    headers: HttpHeaders
    body: bytes | None
    content_length: int | None
    is_tls: bool

    def header(self, name: str, default: str | None = None) -> str | None:
        return self.headers.get(name, default)


def split_request_target(target: str) -> tuple[str, str]:
    """Separe le chemin de la query string d'une cible de requete brute
    (spec §11.2 etape 1 : "Extraire uniquement le chemin URI, sans query
    string" avant toute normalisation)."""
    path, _, query = target.partition("?")
    return path, query
