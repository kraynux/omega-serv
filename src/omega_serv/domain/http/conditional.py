"""Validation de cache et requetes partielles pour les fichiers statiques
(OMEGA-SERV_ETUDE_PERFORMANCE.md, priorite 2 ; RFC 9110 §8.8, §13, §14).

- ETag fort derive de la taille et de la date de modification (meme principe que
  nginx : aucune lecture du fichier) + Last-Modified ;
- requete conditionnelle -> 304 (If-None-Match prioritaire sur If-Modified-Since) ;
- Range a un seul intervalle -> 206 ; plusieurs intervalles -> reponse complete 200
  (autorise par la RFC, jamais de multipart) ; intervalle hors du fichier -> 416 ;
  If-Range qui ne correspond plus -> reponse complete.

Fonctions pures : aucune I/O, les metadonnees du fichier viennent de l'appelant."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from email.utils import format_datetime, parsedate_to_datetime


def make_etag(size: int, mtime: float) -> str:
    return f'"{int(mtime):x}-{size:x}"'


def http_date(mtime: float) -> str:
    return format_datetime(datetime.fromtimestamp(int(mtime), tz=timezone.utc), usegmt=True)


def _parse_http_date(value: str) -> float | None:
    try:
        parsed = parsedate_to_datetime(value)
    except (TypeError, ValueError, IndexError):
        return None
    if parsed is None:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.timestamp()


def _etag_list_matches(header: str, etag: str) -> bool:
    """Comparaison faible (If-None-Match, RFC 9110 §13.1.2) : W/ ignore."""
    if header.strip() == "*":
        return True
    wanted = etag.removeprefix("W/")
    return any(candidate.strip().removeprefix("W/") == wanted for candidate in header.split(","))


def is_not_modified(if_none_match: str | None, if_modified_since: str | None, etag: str, mtime: float) -> bool:
    if if_none_match is not None:
        return _etag_list_matches(if_none_match, etag)
    if if_modified_since is not None:
        since = _parse_http_date(if_modified_since)
        return since is not None and int(mtime) <= int(since)
    return False


@dataclass(frozen=True)
class ByteRange:
    start: int
    end: int  # inclus

    @property
    def length(self) -> int:
        return self.end - self.start + 1


@dataclass(frozen=True)
class RangeDecision:
    """`byte_range` defini -> 206 ; `unsatisfiable` -> 416 ; sinon reponse complete."""
    byte_range: ByteRange | None = None
    unsatisfiable: bool = False


_FULL = RangeDecision()


def _if_range_allows(if_range: str | None, etag: str, mtime: float) -> bool:
    if if_range is None:
        return True
    value = if_range.strip()
    if value.startswith(('"', "W/")):
        return value == etag  # comparaison forte, un ETag faible ne vaut jamais
    since = _parse_http_date(value)
    return since is not None and int(mtime) == int(since)


def resolve_range(range_header: str | None, if_range: str | None, size: int, etag: str, mtime: float) -> RangeDecision:
    if range_header is None or not _if_range_allows(if_range, etag, mtime):
        return _FULL
    unit, _, spec = range_header.strip().partition("=")
    if unit.strip().lower() != "bytes" or not spec or "," in spec:
        return _FULL  # unite inconnue, ou plusieurs intervalles : reponse complete
    first, dash, last = spec.strip().partition("-")
    if not dash:
        return _FULL
    first, last = first.strip(), last.strip()
    if not (first.isdigit() or first == "") or not (last.isdigit() or last == "") or (first == last == ""):
        return _FULL
    if first == "":  # suffixe : les N derniers octets
        suffix = int(last)
        if suffix == 0 or size == 0:
            return RangeDecision(unsatisfiable=True)
        return RangeDecision(byte_range=ByteRange(max(size - suffix, 0), size - 1))
    start = int(first)
    if start >= size:
        return RangeDecision(unsatisfiable=True)
    end = min(int(last), size - 1) if last else size - 1
    if end < start:
        return _FULL
    return RangeDecision(byte_range=ByteRange(start, end))
