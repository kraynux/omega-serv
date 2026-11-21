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
import re
import urllib.parse
from collections.abc import Callable
from dataclasses import dataclass

from omega_serv.domain.http.headers import has_control_characters
from omega_serv.domain.http.status_codes import HttpStatus

RAW_LINE_BUFFER_LIMIT = 1_048_576

MAX_HEADER_COUNT = 100


_HTTP_VERSION_RE = re.compile(r"HTTP/[0-9]\.[0-9]")
"""RFC 9112 §2.3 : `HTTP/` chiffre `.` chiffre, chiffres ASCII seulement (jamais `\\d`, qui accepte tous les
chiffres Unicode)."""


class HttpParseError(Exception):
    def __init__(self, status: HttpStatus, reason: str):
        self.status = status
        self.reason = reason
        # Ce qui a pu etre lu avant l'erreur, pour la ligne d'access.log (plan moteur C++ §14, valide
        # 2026-11-02) : ligne de requete brute (None si illisible : trop longue, connexion coupee) et
        # en-tetes deja analyses (IP client via trusted_proxy, Referer, User-Agent).
        self.request_line: str | None = None
        self.headers: tuple[tuple[str, str], ...] = ()
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
        if len(e.partial) > max_size + 1:
            # Plan proxy natif v2, lot 1N (D38) : une ligne deja trop longue ne pouvait plus devenir valide (un `\r`
            # final tient encore dans max_size + 1) - meme statut que si le CRLF etait arrive, comme le natif (avant :
            # 400 ici, 414 / 431 en natif).
            raise HttpParseError(on_too_long, "ligne trop longue") from e
        raise HttpParseError(HttpStatus.BAD_REQUEST, "connexion fermée de manière inattendue") from e

    line = raw[:-2]  # retire le CRLF final
    if len(line) > max_size:
        raise HttpParseError(on_too_long, "ligne trop longue")
    return line


_TARGET_CONTROL_CHARACTER = re.compile(r"[\x00-\x20\x7f]")
"""Octet de controle dans la cible (< 0x21 ou 0x7F, lot 1 D26/P12) : une recherche en C au lieu d'un `ord` par
caractere (2026-11-19, ETUDE_PROXY_ET_MEMOIRE §12)."""


def is_supported_target_form(target: str) -> bool:
    """Scan de securite n° 2 (2026-11-20, F1-F3) : seules la forme origine (`/...`), la forme absolue http(s) et
    `*` (OPTIONS) sont servies. `GET private/x HTTP/1.1` etait accepte : aucune zone d'authentification ni regle
    d'acces (prefixe `/private`) ne le reconnaissait, mais le resolveur de fichiers servait `webroot/private/x`.
    Meme regle dans le natif (http_parser.cpp, is_supported_target_form)."""
    if target.startswith("/") or target == "*":
        return True
    lowered = target[:8].lower()
    return lowered.startswith(("http://", "https://"))


def has_dot_segment(target: str) -> bool:
    """Plan proxy natif v2, lot 1 (D26, decision de l'auteur) : segment « . » ou « .. » dans le chemin de la cible,
    ecrit tel quel ou encode (%2e ; %2f et %5c comptes comme separateurs, comme un backend qui les decode). Avant,
    `/api/../admin` restait dans la zone proxy /api/ et les regles d'acces voyaient le chemin brut."""
    # 2026-11-19 (ETUDE_PROXY_ET_MEMOIRE §12) : raccourci a resultat identique. Un segment « . » ou « .. » commence
    # par un point precede d'un « / » ; sans « % » ni « \\ » (seules sources d'un point ou d'un separateur encodes),
    # il faut donc un « /. » litteral dans la cible.
    if "/." not in target and "%" not in target and "\\" not in target:
        return False
    path = target
    if not target.startswith("/"):
        scheme_end = target.find("://")
        if scheme_end < 0:
            return False  # « * » ou forme d'autorite : aucun chemin
        rest = target[scheme_end + 3:]
        slash = rest.find("/")
        path = rest[slash:] if slash >= 0 else ""
    path = path.split("?", 1)[0].split("#", 1)[0]
    # Scan de securite n° 1 (2026-11-20, F18/F19/F23/F26/F29) : DEUX passes de decodage, comme le resolveur de
    # fichiers (path_policy._MAX_DECODE_PASSES). Une seule passe laissait passer `%252e%252e`, qui devenait `..`
    # au service du fichier et sortait d'une zone `allow`. Decodage octet par octet (latin-1) : jamais d'erreur.
    for _ in range(2):
        decoded = urllib.parse.unquote(path, encoding="latin-1")
        if decoded == path:
            break
        path = decoded
    # Scan de securite n° 2 (2026-11-20, F15) : `..;jsessionid` est un `..` pour un backend Java (parametre de
    # chemin), il sortait de la zone proxy : seule la partie avant `;` compte.
    return any(segment.split(";", 1)[0] in (".", "..") for segment in path.replace("\\", "/").split("/"))


def _parse_request_line(raw_line: bytes) -> tuple[str, str, str]:
    line = raw_line.decode("latin-1")
    parts = line.split(" ")
    if len(parts) != 3:
        raise HttpParseError(HttpStatus.BAD_REQUEST, "ligne de requête malformée")
    method, target, http_version = parts
    if not method or not target or not http_version.startswith("HTTP/"):
        raise HttpParseError(HttpStatus.BAD_REQUEST, "ligne de requête malformée")
    # Plan proxy natif v2, lot 1 (D26, P12, RFC 9112 §3.2) : aucun octet de controle dans la cible (< 0x21 ou 0x7F),
    # sur toutes les routes - le proxy la recopiait telle quelle vers le backend. Meme regle dans le natif.
    if _TARGET_CONTROL_CHARACTER.search(target) is not None:
        raise HttpParseError(HttpStatus.BAD_REQUEST, "caractère de contrôle dans la cible")
    if not is_supported_target_form(target):
        raise HttpParseError(HttpStatus.BAD_REQUEST, "cible de requête hors forme origine")
    if has_dot_segment(target):
        raise HttpParseError(HttpStatus.BAD_REQUEST, "segment . ou .. dans la cible")
    # Durcissement 2026-11-02 (RFC 9112 §2.3, RFC 9110 §6.2 ; plan moteur C++ §14) : toute version commencant
    # par « HTTP/ » etait servie (HTTP/9.9, HTTP/abc...). Version mal ecrite -> 400 ; majeure autre que 1 ->
    # 505 ; 1.2 a 1.9 -> traitee comme 1.1 (plus haute version 1.x prise en charge).
    if _HTTP_VERSION_RE.fullmatch(http_version) is None:
        raise HttpParseError(HttpStatus.BAD_REQUEST, "version HTTP malformée")
    if http_version[5] != "1":
        raise HttpParseError(HttpStatus.HTTP_VERSION_NOT_SUPPORTED, "version HTTP non supportée")
    if http_version[7] not in "01":
        http_version = "HTTP/1.1"
    return method, target, http_version


def _parse_header_line(raw_line: bytes) -> tuple[str, str]:
    line = raw_line.decode("latin-1")
    if line and line[0] in (" ", "\t"):
        raise HttpParseError(HttpStatus.BAD_REQUEST, "repliage d'en-tête non supporte")
    if ":" not in line:
        raise HttpParseError(HttpStatus.BAD_REQUEST, "en-tête malformé (pas de ':')")
    name, _, value = line.partition(":")
    if " " in name or "\t" in name:
        # Durcissement 2026-11-02 (RFC 9112 §5.1, plan moteur C++ §14) : « X-A : 1 » etait accepte (nom
        # nettoye par strip) - un intermediaire qui lit l'en-tete autrement ouvre la porte au smuggling.
        raise HttpParseError(HttpStatus.BAD_REQUEST, "en-tête malformé (espace dans le nom)")
    name = name.strip()
    value = value.strip()
    if not name:
        raise HttpParseError(HttpStatus.BAD_REQUEST, "en-tête malformé (nom vide)")
    if has_control_characters(name) or has_control_characters(value):
        raise HttpParseError(HttpStatus.BAD_REQUEST, "en-tête contient un caractère de contrôle")
    return name, value


async def read_request_head(
    reader: asyncio.StreamReader,
    max_request_line_size: int,
    max_header_size: int,
    on_request_line: Callable[[], object] | None = None,
) -> ParsedRequestHead:
    """Lit et parse la ligne de requete et les en-tetes - jamais le
    corps (voir read_and_discard_body). Chaque limite est appliquee
    PENDANT la lecture, jamais seulement verifiee apres coup.

    `on_request_line` (lot 7 du plan proxy natif) : appele des que la
    ligne de requete est lue - la connexion n'attend plus sa requete
    suivante, l'arret doit lui laisser le delai de grace."""
    raw_request_line = await _read_line_bounded(reader, max_request_line_size, HttpStatus.URI_TOO_LONG)
    if on_request_line is not None:
        on_request_line()
    headers: list[tuple[str, str]] = []
    try:
        method, target, http_version = _parse_request_line(raw_request_line)

        total_header_bytes = 0
        while True:
            raw_line = await _read_line_bounded(reader, max_header_size, HttpStatus.REQUEST_HEADER_FIELDS_TOO_LARGE)
            total_header_bytes += len(raw_line) + 2
            if total_header_bytes > max_header_size:
                raise HttpParseError(HttpStatus.REQUEST_HEADER_FIELDS_TOO_LARGE, "en-têtes trop volumineux au total")
            if not raw_line:
                break
            if len(headers) >= MAX_HEADER_COUNT:
                raise HttpParseError(HttpStatus.REQUEST_HEADER_FIELDS_TOO_LARGE, "trop d'en-têtes")
            name, value = _parse_header_line(raw_line)
            headers.append((name, value))

        _reject_ambiguous_content_length(headers)
        _reject_unsupported_expect(headers)
    except HttpParseError as e:
        e.request_line = raw_request_line.decode("latin-1")
        e.headers = tuple(headers)
        raise

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
        raise HttpParseError(HttpStatus.BAD_REQUEST, "Content-Length dupliqué")


async def read_and_discard_body(
    reader: asyncio.StreamReader,
    head: ParsedRequestHead,
    max_request_size: int,
    capture_max_bytes: int = 0,
    reject_over: int | None = None,
    timeout: float | None = None,
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

    `timeout` (lot 11, F1) : delai relance a chaque bloc recu, avec un debit moyen minimal
    (BODY_MIN_RATE_BYTES_PER_SECOND) ; asyncio.TimeoutError au-dela. None : aucun delai ici (l'appelant borne).

    Returns:
        (nombre d'octets de corps effectivement consommes, extrait capture).
    """
    if head.header("transfer-encoding") is not None:
        raise HttpParseError(HttpStatus.BAD_REQUEST, "Transfer-Encoding non supporte en Phase 1")

    content_length_header = head.header("content-length")
    if content_length_header is None:
        return 0, b""

    # Durcissement 2026-11-02 (plan moteur C++ §14) : chiffres ASCII seulement - int() acceptait aussi
    # "+5", "1_000", " 5" ou des chiffres non ASCII, lus autrement par d'autres serveurs (smuggling).
    if not (content_length_header.isascii() and content_length_header.isdigit()):
        unsigned = content_length_header[1:]
        if content_length_header.startswith("-") and unsigned.isascii() and unsigned.isdigit():
            raise HttpParseError(HttpStatus.BAD_REQUEST, "Content-Length négatif")
        raise HttpParseError(HttpStatus.BAD_REQUEST, "Content-Length invalide")
    content_length = int(content_length_header)
    if content_length > max_request_size:
        raise HttpParseError(HttpStatus.PAYLOAD_TOO_LARGE, "corps de requête trop volumineux")
    if reject_over is not None and content_length > reject_over:
        # Plan proxy natif v2, lot 2 : waf.inspect.body_over_limit = reject - rien de non inspecte ne passe.
        raise HttpParseError(HttpStatus.PAYLOAD_TOO_LARGE,
                             "corps plus grand que la partie inspectée par le WAF (waf.inspect.body_over_limit = reject)")

    captured = b""
    if content_length > 0 and timeout is not None:
        return content_length, await _read_body_with_deadline(reader, content_length, capture_max_bytes, timeout)
    if content_length > 0:
        try:
            body = await reader.readexactly(content_length)
        except asyncio.IncompleteReadError as e:
            raise HttpParseError(HttpStatus.BAD_REQUEST, "corps de requête incomplet") from e
        if capture_max_bytes > 0:
            captured = body[:capture_max_bytes]
    return content_length, captured


BODY_MIN_RATE_BYTES_PER_SECOND = 500
"""Lot 11, constat F1 (decision de l'auteur du 2026-11-14 : dans le code, pas une option) : le corps n'a plus a arriver
en entier dans `read_timeout_seconds`. Echeance = min(dernier octet + delai, debut du corps + delai + recu / 500 o/s),
comme mod_reqtimeout d'Apache (body=20,MinRate=500) - meme regle que le moteur natif (server.cpp, body_deadline)."""


async def _read_body_with_deadline(reader: asyncio.StreamReader, content_length: int, capture_max_bytes: int,
                                   timeout: float) -> bytes:
    """Lit `content_length` octets ; asyncio.TimeoutError si l'echeance (relancee a chaque bloc) est depassee. Ne
    garde que les `capture_max_bytes` premiers octets (le reste est lu puis jete)."""
    loop = asyncio.get_running_loop()
    started = last = loop.time()
    received = 0
    kept = bytearray()
    while received < content_length:
        remaining = min(last + timeout, started + timeout + received / BODY_MIN_RATE_BYTES_PER_SECOND) - loop.time()
        if remaining <= 0:
            raise asyncio.TimeoutError
        chunk = await asyncio.wait_for(reader.read(min(65536, content_length - received)), remaining)
        if not chunk:
            raise HttpParseError(HttpStatus.BAD_REQUEST, "corps de requête incomplet")
        received += len(chunk)
        last = loop.time()
        if len(kept) < capture_max_bytes:
            kept += chunk[:capture_max_bytes - len(kept)]
    return bytes(kept)
