"""Entite reponse HTTP.

Mutable (contrairement a HttpRequest) : les differentes etapes du
pipeline (spec §27 - handler, cache, headers de securite, WAF) ajoutent
des en-tetes successivement avant l'ecriture reseau finale, deleguee a
infrastructure/server/ (Phase 1).
"""
from __future__ import annotations

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

    @property
    def content_length(self) -> int:
        return self.body_file_length if self.body_file is not None else len(self.body)

    def set_header(self, name: str, value: str) -> None:
        """Definit un en-tete. Utilise par les etapes du pipeline en
        amont des en-tetes de securite serveur - voir
        force_security_header() pour la regle de non-negociabilite
        (decision transverse : le WAF/handler ne peut jamais ecraser les
        en-tetes de securite imposes en fin de pipeline)."""
        self.headers[name] = value

    def force_security_header(self, name: str, value: str) -> None:
        """Impose un en-tete de securite en ecrasant toute valeur deja
        posee par un handler en amont (FastCGI, WAF...) - jamais
        l'inverse. Voir OMEGA-SERV_PLAN_DEVELOPPEMENT.md §6 : "en-tetes
        de securite non negociables"."""
        self.headers[name] = value

    @classmethod
    def empty(cls, status: int) -> HttpResponse:
        return cls(status=status)
