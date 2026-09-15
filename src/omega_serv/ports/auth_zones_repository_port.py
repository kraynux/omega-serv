# Copyright (c) 2026 kraynux - kraynux@proton.me - Licence MIT (voir fichier LICENSE)
"""Contrat de lecture/ecriture du fichier de zones protegees (spec
§15.2, paths.auth_zones)."""
from __future__ import annotations

from typing import Protocol

from omega_serv.domain.security.auth.entities import AuthZone


class AuthZonesRepositoryPort(Protocol):
    def load(self) -> tuple[AuthZone, ...]:
        ...

    def save(self, zones: tuple[AuthZone, ...]) -> None:
        ...
