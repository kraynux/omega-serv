# Copyright (c) 2026 kraynux - kraynux@proton.me - Licence MIT (voir fichier LICENSE)
"""Conteneur d'en-tetes HTTP et regles de validite pures.

Aucune I/O, aucun parsing de flux reseau (delegue a
infrastructure/server/http_parser.py en Phase 1) - uniquement la
structure de donnees et les regles metier de validite d'un en-tete deja
extrait.
"""
from __future__ import annotations

from collections.abc import Iterator
from dataclasses import dataclass, field

_CONTROL_CHARS = frozenset(chr(c) for c in range(0x20) if c not in (0x09,))  # tab tolere dans un header replie legacy, jamais utilise ici mais pas rejete au niveau structure


@dataclass(frozen=True)
class HttpHeaders:
    """Ensemble d'en-tetes HTTP, insensible a la casse du nom (RFC 7230
    §3.2 : les noms de champs d'en-tete sont insensibles a la casse)."""

    _values: dict[str, str] = field(default_factory=dict)

    @classmethod
    def from_pairs(cls, pairs: list[tuple[str, str]]) -> HttpHeaders:
        values: dict[str, str] = {}
        for name, value in pairs:
            values[name.lower()] = value
        return cls(_values=values)

    def get(self, name: str, default: str | None = None) -> str | None:
        return self._values.get(name.lower(), default)

    def __contains__(self, name: str) -> bool:
        return name.lower() in self._values

    def __iter__(self) -> Iterator[tuple[str, str]]:
        return iter(self._values.items())

    def __len__(self) -> int:
        return len(self._values)


def has_control_characters(value: str) -> bool:
    """Detecte un caractere de controle (dont CR/LF) dans une valeur
    d'en-tete - protection contre l'injection d'en-tete (header/CRLF
    injection), voir spec §11.1 "Rejeter les caracteres de controle dans
    l'URI et les headers"."""
    return any(ch in _CONTROL_CHARS for ch in value)


def total_size_bytes(pairs: list[tuple[str, str]]) -> int:
    """Taille totale approximative des en-tetes (nom + valeur + ": " +
    CRLF), utilisee pour la limite max_header_size (spec §10.1)."""
    return sum(len(name) + len(value) + 4 for name, value in pairs)
