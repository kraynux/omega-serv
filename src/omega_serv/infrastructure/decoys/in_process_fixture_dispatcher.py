# Copyright (c) 2026 kraynux - kraynux@proton.me - Licence MIT (voir fichier LICENSE)
"""Implemente ports.decoy_dispatch_port.DecoyDispatchPort - Niveau 1
(fixture in-process, plan_active_defense_omega_serv.md, Phase 3).
Retourne None si le profil est inconnu (jamais une exception) - le
fallback configure (pass_through/reject) est alors applique par
l'appelant (infrastructure/server/asyncio_server.py), jamais ce
dispatcher lui-meme."""
from __future__ import annotations

from omega_serv.domain.http.request import HttpRequest
from omega_serv.domain.http.response import HttpResponse
from omega_serv.infrastructure.decoys.registry import FIXTURE_HANDLERS


class InProcessFixtureDispatcher:
    def render(self, profile_name: str, request: HttpRequest) -> HttpResponse | None:
        handler = FIXTURE_HANDLERS.get(profile_name)
        return None if handler is None else handler(request)
