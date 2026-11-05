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


class InvalidAbsoluteTarget(ValueError):
    """Cible en forme absolue inutilisable (hote vide, identifiants `user@`, caractere de controle ou espace)."""


def absolute_form_parts(target: str) -> tuple[str, str] | None:
    """Forme absolue `http://hote/chemin?requete` (RFC 9112 §3.2.2, plan moteur C++ §14, validee 2026-11-02) :
    un serveur DOIT l'accepter. Retourne (hote, cible en forme origine) ; None si la cible n'est pas en forme
    absolue http/https (elle suit alors le chemin habituel, inchange). Le schema est insensible a la casse.

    L'hote finit au premier `/` ou `?` ; un chemin absent devient `/`. Refus (InvalidAbsoluteTarget) : hote
    vide, `@` (identifiants interdits dans une URI http, RFC 9110 §4.2.4), espace ou caractere de controle -
    l'hote remplace l'en-tete Host (RFC 9112 §3.2.2) et ne doit jamais pouvoir y injecter quoi que ce soit."""
    lowered = target[:8].lower()
    if lowered.startswith("http://"):
        rest = target[7:]
    elif lowered.startswith("https://"):
        rest = target[8:]
    else:
        return None
    end = len(rest)
    for index, char in enumerate(rest):
        if char in "/?":
            end = index
            break
    host, origin = rest[:end], rest[end:]
    if not host or any(char == "@" or ord(char) <= 0x20 or ord(char) == 0x7F for char in host):
        raise InvalidAbsoluteTarget(target)
    if not origin.startswith("/"):
        origin = "/" + origin
    return host, origin
