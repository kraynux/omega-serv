"""Entite reponse HTTP.

Mutable (contrairement a HttpRequest) : les differentes etapes du
pipeline (spec §27 - handler, cache, headers de securite, WAF) ajoutent
des en-tetes successivement avant l'ecriture reseau finale, deleguee a
infrastructure/server/ (Phase 1).
"""
from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass, field
from pathlib import Path


@dataclass
class HttpResponse:
    status: int
    headers: dict[str, str] = field(default_factory=dict)
    body: bytes = b""
    # Corps envoye directement depuis un fichier, par blocs, sans jamais le
    # charger en memoire (OMEGA-SERV_ETUDE_PERFORMANCE.md, priorite 1 : 3
    # telechargements de 300 Mo faisaient monter le serveur a 1,8 Go et le
    # figeaient jusqu'a 2 s). `body` reste vide quand `body_file` est defini.
    body_file: Path | None = None
    body_file_offset: int = 0
    body_file_length: int = 0
    # Plan proxy natif v2, lot 1 (D6) : en-tetes qui ne se combinent pas en une seule ligne (`Set-Cookie`), ecrits
    # apres `headers` dans l'ordre d'ajout - le dict n'en gardait qu'un (un seul cookie du backend survivait).
    repeated_headers: list[tuple[str, str]] = field(default_factory=list)

    @property
    def content_length(self) -> int:
        return self.body_file_length if self.body_file is not None else len(self.body)

    def set_header(self, name: str, value: str) -> None:
        """Definit un en-tete. Utilise par les etapes du pipeline en
        amont des en-tetes de securite serveur - voir
        force_security_header() pour la regle de non-negociabilite
        (decision transverse : le WAF/handler ne peut jamais ecraser les
        en-tetes de securite imposes en fin de pipeline). Lot 1 (D27) :
        une variante de casse deja posee (`x-frame-options` du backend) est
        remplacee, jamais gardee a cote."""
        self._drop_case_variants(name)
        self.headers[name] = value

    def add_header(self, name: str, value: str) -> None:
        """Lot 1 (D6) : en-tete repete (`Set-Cookie`), jamais fusionne ni ecrase."""
        self.repeated_headers.append((name, value))

    def all_headers(self) -> list[tuple[str, str]]:
        return [*self.headers.items(), *self.repeated_headers]

    def _drop_case_variants(self, name: str) -> None:
        lowered = name.lower()
        for existing in [key for key in self.headers if key != name and key.lower() == lowered]:
            del self.headers[existing]

    def force_security_header(self, name: str, value: str) -> None:
        """Impose un en-tete de securite en ecrasant toute valeur deja
        posee par un handler en amont (FastCGI, WAF...) - jamais
        l'inverse. Voir OMEGA-SERV_PLAN_DEVELOPPEMENT.md §6 : "en-tetes
        de securite non negociables". Lot 1 (D27) : sans doublon du a la casse."""
        self._drop_case_variants(name)
        self.headers[name] = value

    def force_security_headers(self, items: Iterable[tuple[str, str]]) -> None:
        """Meme effet que force_security_header() appele pour chaque couple, dans l'ordre, mais en une passe : les
        noms en minuscules ne sont calcules qu'une fois par reponse (2026-11-19, ETUDE_PROXY_ET_MEMOIRE §12 : une
        dizaine d'en-tetes imposes, chacun parcourant tous les autres, coutaient ~5 % de debit)."""
        headers = self.headers
        by_lowered: dict[str, list[str]] = {}
        for key in headers:
            by_lowered.setdefault(key.lower(), []).append(key)
        for name, value in items:
            lowered = name.lower()
            for existing in by_lowered.get(lowered, ()):
                if existing != name:
                    del headers[existing]
            headers[name] = value
            by_lowered[lowered] = [name]

    @classmethod
    def empty(cls, status: int) -> HttpResponse:
        return cls(status=status)
