"""Codes de statut HTTP utilises par OMEGA-SERV.

Limite volontairement aux codes reellement produits par le serveur
(voir OMEGA-SERV_SPECIFICATION.md et OMEGA-SERV_WAF_LUA_DEPERSONNALISATION.md,
tableau "Politique de reponses HTTP") plutot qu'une enumeration complete
de la RFC - un code absent d'ici n'a pas d'usage identifie dans le projet.
"""
from __future__ import annotations

import http
from enum import IntEnum


class HttpStatus(IntEnum):
    OK = 200
    MOVED_PERMANENTLY = 301
    FOUND = 302
    TEMPORARY_REDIRECT = 307
    PERMANENT_REDIRECT = 308
    BAD_REQUEST = 400
    UNAUTHORIZED = 401
    FORBIDDEN = 403
    NOT_FOUND = 404
    METHOD_NOT_ALLOWED = 405
    REQUEST_TIMEOUT = 408
    EXPECTATION_FAILED = 417
    PAYLOAD_TOO_LARGE = 413
    URI_TOO_LONG = 414
    TOO_MANY_REQUESTS = 429
    REQUEST_HEADER_FIELDS_TOO_LARGE = 431
    UNAVAILABLE_FOR_LEGAL_REASONS = 451
    INTERNAL_SERVER_ERROR = 500
    BAD_GATEWAY = 502
    SERVICE_UNAVAILABLE = 503

    @property
    def reason_phrase(self) -> str:
        return _REASON_PHRASES[self]


_REASON_PHRASES: dict[HttpStatus, str] = {
    HttpStatus.OK: "OK",
    HttpStatus.MOVED_PERMANENTLY: "Moved Permanently",
    HttpStatus.FOUND: "Found",
    HttpStatus.TEMPORARY_REDIRECT: "Temporary Redirect",
    HttpStatus.PERMANENT_REDIRECT: "Permanent Redirect",
    HttpStatus.BAD_REQUEST: "Bad Request",
    HttpStatus.UNAUTHORIZED: "Unauthorized",
    HttpStatus.FORBIDDEN: "Forbidden",
    HttpStatus.NOT_FOUND: "Not Found",
    HttpStatus.METHOD_NOT_ALLOWED: "Method Not Allowed",
    HttpStatus.REQUEST_TIMEOUT: "Request Timeout",
    HttpStatus.EXPECTATION_FAILED: "Expectation Failed",
    HttpStatus.PAYLOAD_TOO_LARGE: "Payload Too Large",
    HttpStatus.URI_TOO_LONG: "URI Too Long",
    HttpStatus.TOO_MANY_REQUESTS: "Too Many Requests",
    HttpStatus.REQUEST_HEADER_FIELDS_TOO_LARGE: "Request Header Fields Too Large",
    HttpStatus.UNAVAILABLE_FOR_LEGAL_REASONS: "Unavailable For Legal Reasons",
    HttpStatus.INTERNAL_SERVER_ERROR: "Internal Server Error",
    HttpStatus.BAD_GATEWAY: "Bad Gateway",
    HttpStatus.SERVICE_UNAVAILABLE: "Service Unavailable",
}


def reason_phrase_for(code: int) -> str:
    """Phrase de raison pour un code arbitraire - necessaire pour
    FastCGI (Phase 8) : un script PHP peut renvoyer n'importe quel code
    HTTP standard (201, 204, 422...), pas seulement ceux produits en
    interne par OMEGA-SERV et couverts par HttpStatus (enumeration
    volontairement fermee, voir docstring de module). Repli sur
    `http.HTTPStatus` (stdlib, couvre l'ensemble des codes IANA
    enregistres) plutot que d'agrandir HttpStatus pour un usage qui
    n'est pas produit par le coeur du serveur lui-meme."""
    try:
        return HttpStatus(code).reason_phrase
    except ValueError:
        pass
    try:
        return http.HTTPStatus(code).phrase
    except ValueError:
        return ""
