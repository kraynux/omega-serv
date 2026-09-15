# Copyright (c) 2026 kraynux - kraynux@proton.me - Licence MIT (voir fichier LICENSE)
"""Parseur HTTP/1.1 minimal, bornee en taille des la lecture (spec §28.1 :
"un serveur HTTP maison" est la surface de securite la plus sensible du
projet - commencer par un perimetre reduit et strictement verifie).

Perimetre Phase 1 : ligne de requete + en-tetes + corps optionnel via
Content-Length uniquement. Transfer-Encoding est refuse explicitement
ici (400) plutot que devine - le support chunked correct et la gestion
de l'ambiguite Content-Length/Transfer-Encoding (risque de request
smuggling) sont un chantier de la Phase 2 (durcissement HTTP), pas
improvise maintenant.

N'utilise QUE des limites deja definies dans ServerConfig (Phase 0) -
aucune limite inventee ici.
"""
from __future__ import annotations

import asyncio
from dataclasses import dataclass

from omega_serv.domain.http.headers import has_control_characters
from omega_serv.domain.http.status_codes import HttpStatus

# Tampon brut asyncio, toujours superieur aux limites configurees reelles
# (server.max_request_line_size / max_header_size) - la verification
# precise se fait nous-memes juste apres lecture, ce tampon n'est qu'un
# filet de securite pour ne jamais accumuler une ligne sans fin en memoire.
RAW_LINE_BUFFER_LIMIT = 1_048_576

# Limite du NOMBRE d'en-tetes, distincte de max_header_size (leur taille
# TOTALE) - spec §11.1 "Limiter le nombre total de headers ET leur
# taille totale". Constante fixe plutot que configurable : aucune valeur
# legitime de ce projet n'a besoin de plus de 100 en-tetes, une valeur
# configurable ici n'apporterait rien face au risque qu'elle mitige.
MAX_HEADER_COUNT = 100


class HttpParseError(Exception):
    def __init__(self, status: HttpStatus, reason: str):
        self.status = status
        self.reason = reason
        super().__init__(reason)


class ConnectionClosedCleanly(Exception):
    """Le pair a ferme la connexion sans envoyer aucun octet - fin de
    vie normale d'une connexion (notamment en keep-alive, quand le
    client n'a simplement plus de requete a envoyer), jamais une
    erreur de protocole a journaliser ou a signaler au client."""


@dataclass(frozen=True)
class ParsedRequestHead:
    method: str
    target: str
    http_version: str
    headers: tuple[tuple[str, str], ...]

    def header(self, name: str) -> str | None:
        name_lower = name.lower()
        for header_name, value in self.headers:
            if header_name.lower() == name_lower:
                return value
        return None


async def _read_line_bounded(reader: asyncio.StreamReader, max_size: int, on_too_long: HttpStatus) -> bytes:
    try:
        raw = await reader.readuntil(b"\r\n")
    except asyncio.LimitOverrunError as e:
        raise HttpParseError(on_too_long, "ligne trop longue") from e
    except asyncio.IncompleteReadError as e:
        if not e.partial:
            raise ConnectionClosedCleanly() from e
        raise HttpParseError(HttpStatus.BAD_REQUEST, "connexion fermee de maniere inattendue") from e

    line = raw[:-2]  # retire le CRLF final
    if len(line) > max_size:
        raise HttpParseError(on_too_long, "ligne trop longue")
    return line


def _parse_request_line(raw_line: bytes) -> tuple[str, str, str]:
    # HTTP/1.1 §3.1.1 : la ligne de requete est en US-ASCII / latin-1,
    # jamais suppose UTF-8 - un decodage strict UTF-8 leverait sur une
    # entree pourtant syntaxiquement valide au sens HTTP.
    line = raw_line.decode("latin-1")
    parts = line.split(" ")
    if len(parts) != 3:
        raise HttpParseError(HttpStatus.BAD_REQUEST, "ligne de requete malformee")
    method, target, http_version = parts
    if not method or not target or not http_version.startswith("HTTP/"):
        raise HttpParseError(HttpStatus.BAD_REQUEST, "ligne de requete malformee")
    return method, target, http_version


def _parse_header_line(raw_line: bytes) -> tuple[str, str]:
    line = raw_line.decode("latin-1")
    if line and line[0] in (" ", "\t"):
        # Repliage d'en-tete obsolete (RFC 7230 §3.2.4) - jamais
        # supporte : source connue d'ambiguite de parsing, plus simple
        # et plus sur de refuser que d'essayer de le reconstituer.
        raise HttpParseError(HttpStatus.BAD_REQUEST, "repliage d'en-tete non supporte")
    if ":" not in line:
        raise HttpParseError(HttpStatus.BAD_REQUEST, "en-tete malforme (pas de ':')")
    name, _, value = line.partition(":")
    name = name.strip()
    value = value.strip()
    if not name:
        raise HttpParseError(HttpStatus.BAD_REQUEST, "en-tete malforme (nom vide)")
    if has_control_characters(name) or has_control_characters(value):
        raise HttpParseError(HttpStatus.BAD_REQUEST, "en-tete contient un caractere de controle")
    return name, value


async def read_request_head(
    reader: asyncio.StreamReader,
    max_request_line_size: int,
    max_header_size: int,
) -> ParsedRequestHead:
    """Lit et parse la ligne de requete et les en-tetes - jamais le
    corps (voir read_and_discard_body). Chaque limite est appliquee
    PENDANT la lecture, jamais seulement verifiee apres coup."""
    raw_request_line = await _read_line_bounded(reader, max_request_line_size, HttpStatus.URI_TOO_LONG)
    method, target, http_version = _parse_request_line(raw_request_line)

    headers: list[tuple[str, str]] = []
    total_header_bytes = 0
    while True:
        raw_line = await _read_line_bounded(reader, max_header_size, HttpStatus.REQUEST_HEADER_FIELDS_TOO_LARGE)
        total_header_bytes += len(raw_line) + 2
        if total_header_bytes > max_header_size:
            raise HttpParseError(HttpStatus.REQUEST_HEADER_FIELDS_TOO_LARGE, "en-tetes trop volumineux au total")
        if not raw_line:
            break
        if len(headers) >= MAX_HEADER_COUNT:
            raise HttpParseError(HttpStatus.REQUEST_HEADER_FIELDS_TOO_LARGE, "trop d'en-tetes")
        name, value = _parse_header_line(raw_line)
        headers.append((name, value))

    _reject_ambiguous_content_length(headers)
    _reject_unsupported_expect(headers)

    return ParsedRequestHead(method=method, target=target, http_version=http_version, headers=tuple(headers))


def _reject_unsupported_expect(headers: list[tuple[str, str]]) -> None:
    """`Expect: 100-continue` (spec §11.1) est refuse proprement (417)
    plutot que gere : rien dans le perimetre actuel n'a besoin d'une
    negociation "100 Continue" avant lecture du corps, et un
    demi-support serait plus risque qu'une absence de support assumee."""
    for name, _ in headers:
        if name.lower() == "expect":
            raise HttpParseError(HttpStatus.EXPECTATION_FAILED, "Expect non supporte")


def _reject_ambiguous_content_length(headers: list[tuple[str, str]]) -> None:
    """Refuse toute repetition de Content-Length (spec §11.1 : "Refuser
    les requetes avec Content-Length incoherent ou multiple ambigu") -
    meme si les valeurs sont identiques : des intermediaires differents
    (proxy, serveur) peuvent lire des occurrences differentes d'un
    en-tete duplique, source classique de request smuggling. Rejeter
    systematiquement plutot que choisir laquelle croire."""
    values = [value for name, value in headers if name.lower() == "content-length"]
    if len(values) > 1:
        raise HttpParseError(HttpStatus.BAD_REQUEST, "Content-Length duplique")


async def read_and_discard_body(
    reader: asyncio.StreamReader,
    head: ParsedRequestHead,
    max_request_size: int,
    capture_max_bytes: int = 0,
) -> tuple[int, bytes]:
    """Consomme le corps eventuel d'une requete (necessaire pour garder
    le flux synchronise avant la prochaine requete en keep-alive, meme
    si le corps n'a aucun usage pour un handler statique). Retient au
    plus `capture_max_bytes` octets pour l'inspection WAF eventuelle
    (doc WAF §7.3 : "waf.body_max_inspect_bytes" peut etre inferieur a
    la limite serveur - le reste est lu puis jete, jamais accumule
    au-dela de cette limite) - `capture_max_bytes=0` (par defaut) ne
    retient rien, comportement identique a l'ancien nom de la fonction.

    Refuse explicitement `Transfer-Encoding` (jamais devine) et tout
    Content-Length incoherent - la gestion fine de l'ambiguite
    Content-Length/Transfer-Encoding est un chantier de la Phase 2.

    Returns:
        (nombre d'octets de corps effectivement consommes, extrait capture).
    """
    if head.header("transfer-encoding") is not None:
        raise HttpParseError(HttpStatus.BAD_REQUEST, "Transfer-Encoding non supporte en Phase 1")

    content_length_header = head.header("content-length")
    if content_length_header is None:
        return 0, b""

    try:
        content_length = int(content_length_header)
    except ValueError as e:
        raise HttpParseError(HttpStatus.BAD_REQUEST, "Content-Length invalide") from e
    if content_length < 0:
        raise HttpParseError(HttpStatus.BAD_REQUEST, "Content-Length negatif")
    if content_length > max_request_size:
        raise HttpParseError(HttpStatus.PAYLOAD_TOO_LARGE, "corps de requete trop volumineux")

    captured = b""
    if content_length > 0:
        try:
            body = await reader.readexactly(content_length)
        except asyncio.IncompleteReadError as e:
            raise HttpParseError(HttpStatus.BAD_REQUEST, "corps de requete incomplet") from e
        if capture_max_bytes > 0:
            captured = body[:capture_max_bytes]
    return content_length, captured
