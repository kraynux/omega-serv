"""Outils de l'editeur de listes de chemins (OMEGA-SERV_PLAN-DETAILLE_
SENSITIVE_PATHS.md, lots 4.5/4.6) - calcul pur, sans I/O : l'ecran fournit
le texte en cours d'edition, les lignes du journal d'acces et la reference.

- `replay_successful_paths` ("Verifier contre mes logs", garde-fou §3.10-4) :
  quelles lignes de la liste auraient touche des requetes qui ont REUSSI
  (2xx/3xx), donc probablement legitimes ?
- `reference_news` ("Nouveautes de la reference", §3.11) : entrees de la
  reference absentes de la liste locale et jamais retirees volontairement.
- `retired_markers` : commentaires `#retire: /x` ajoutes a l'enregistrement
  quand l'utilisateur supprime une ligne venant de la reference - visibles
  et modifiables (aucun fichier cache), ils empechent la reference de la
  reproposer."""
from __future__ import annotations

import re
from collections import Counter
from collections.abc import Iterable
from dataclasses import dataclass

from omega_serv.core.i18n import _
from omega_serv.domain.logging.access_log_parser import parse_combined_log_line
from omega_serv.domain.security.waf.keyword_list import (
    analyze_path_list_text,
    compile_path_list_pattern,
    compile_path_token,
)
from omega_serv.domain.security.waf.normalization import decode_bounded_for_inspection

RETIRED_PREFIX = "#retire: "
_DECODE_DEPTH = 2  # meme profondeur que le moteur (InspectConfig.decode_depth par defaut)


@dataclass(frozen=True)
class LogHit:
    line: int
    entry: str
    hits: int
    examples: tuple[str, ...]


def _entries_with_lines(text: str, anchor: str) -> list[tuple[int, str]]:
    analysis = analyze_path_list_text(text, anchor)
    valid = set(analysis.entries)
    found: list[tuple[int, str]] = []
    for number, raw in enumerate(text.splitlines(), start=1):
        token = raw.strip()
        if token in valid:
            found.append((number, token))
            valid.discard(token)
    return found


def replay_successful_paths(text: str, anchor: str, log_lines: Iterable[str], max_examples: int = 3) -> tuple[LogHit, ...]:
    """Les chemins sont normalises comme dans le moteur (query retiree,
    decodage URL borne + NFKC) ; une exception `!/x` de la liste retire le
    chemin du comptage, comme en production. Resultat trie par nombre de
    requetes reussies, decroissant."""
    successful: Counter[str] = Counter()
    for line in log_lines:
        entry = parse_combined_log_line(line)
        if entry is None or not entry.path or not 200 <= entry.status_code < 400:
            continue
        successful[decode_bounded_for_inspection(entry.path.split("?", 1)[0], _DECODE_DEPTH)] += 1

    exceptions = analyze_path_list_text(text, anchor).exceptions
    excluded = re.compile(compile_path_list_pattern(exceptions, anchor), re.IGNORECASE) if exceptions else None
    hits: list[LogHit] = []
    for number, token in _entries_with_lines(text, anchor):
        compiled = re.compile(compile_path_token(token, anchor), re.IGNORECASE)
        matched = [
            (path, count) for path, count in successful.items()
            if compiled.search(path) and not (excluded is not None and excluded.search(path))
        ]
        if matched:
            matched.sort(key=lambda item: -item[1])
            hits.append(LogHit(
                line=number, entry=token, hits=sum(count for _, count in matched),
                examples=tuple(path for path, _ in matched[:max_examples]),
            ))
    hits.sort(key=lambda hit: -hit.hits)
    return tuple(hits)


def _known_tokens(text: str) -> set[str]:
    known: set[str] = set()
    for raw in text.splitlines():
        line = raw.strip()
        if line.startswith(RETIRED_PREFIX):
            known.add(line[len(RETIRED_PREFIX):].strip().lower())
        elif line and not line.startswith("#"):
            known.add(line.lstrip("!").lower())
    return known


def reference_news(local_text: str, reference_text: str) -> tuple[str, ...]:
    known = _known_tokens(local_text)
    news: list[str] = []
    for raw in reference_text.splitlines():
        line = raw.strip()
        if line and not line.startswith("#") and line.lstrip("!").lower() not in known:
            news.append(line)
    return tuple(news)


def retired_markers(original_text: str, new_text: str, reference_text: str) -> tuple[str, ...]:
    """Lignes `#retire: /x` a AJOUTER a `new_text` : entrees presentes a
    l'ouverture, venant de la reference, et absentes du texte enregistre."""
    reference = {line.strip().lower() for line in reference_text.splitlines()
                 if line.strip() and not line.strip().startswith("#")}
    still_known = _known_tokens(new_text)
    markers: list[str] = []
    for raw in original_text.splitlines():
        line = raw.strip()
        key = line.lower()
        if line and not line.startswith("#") and key in reference and key.lstrip("!") not in still_known:
            markers.append(f"{RETIRED_PREFIX}{line}")
            still_known.add(key.lstrip("!"))
    return tuple(markers)


def explain_path(text: str, anchor: str, value: str) -> str:
    """Bouton "Tester" de l'editeur : que ferait la liste EN COURS d'edition
    de ce chemin ? Meme normalisation que le moteur (query retiree, decodage
    URL borne + NFKC), meme priorite (exception > entree)."""
    analysis = analyze_path_list_text(text, anchor)
    if analysis.errors:
        return _("corrigez d'abord les erreurs de la liste")
    path = decode_bounded_for_inspection(value.split("?", 1)[0], _DECODE_DEPTH)
    if not path.startswith("/"):
        return _("un chemin commence par '/'")
    exceptions = set(analysis.exceptions)
    entries = set(analysis.entries)
    first_exception: tuple[int, str] | None = None
    first_entry: tuple[int, str] | None = None
    for number, raw in enumerate(text.splitlines(), start=1):
        line = raw.strip()
        token = line.removeprefix("!")
        is_exception = line.startswith("!") and token in exceptions
        if not (is_exception or line in entries):
            continue
        if re.search(compile_path_token(token, anchor), path, re.IGNORECASE):
            if is_exception and first_exception is None:
                first_exception = (number, line)
            elif not is_exception and first_entry is None:
                first_entry = (number, line)
    if first_exception is not None and first_entry is not None:
        return _("AUTORISÉ : l'exception ligne {value} ({value2}) l'emporte sur la ligne {value3}").format(value=first_exception[0], value2=first_exception[1], value3=first_entry[0])
    if first_exception is not None:
        return _("AUTORISÉ : exception ligne {value} ({value2})").format(value=first_exception[0], value2=first_exception[1])
    if first_entry is not None:
        return _("DÉTECTÉ par la ligne {value} ({value2})").format(value=first_entry[0], value2=first_entry[1])
    return _("aucune ligne de la liste ne correspond")
