# Copyright (c) 2026 kraynux - kraynux@proton.me - Licence MIT (voir fichier LICENSE)
"""Contrat d'inspection WAF (OMEGA-SERV_WAF_LUA_DEPERSONNALISATION.md,
"Decision d'integration recommandee" : `class WafPort(Protocol): def
inspect(self, request: HttpRequest) -> WafDecision`). Le moteur ne
controle jamais le socket HTTP ni ne rend de HTML - il ne fait que
lire une requete normalisee et rendre une decision structuree.

Une implementation Lua (`LuaWafAdapter`, doc WAF "Reutilisation du WAF
Lua") pourra un jour satisfaire ce meme contrat sans que
l'application/interfaces n'ait a changer - option ulterieure, pas v1
(voir OMEGA-SERV_PLAN_DEVELOPPEMENT.md §3 Phase 5)."""
from __future__ import annotations

from typing import Protocol

from omega_serv.domain.http.request import HttpRequest
from omega_serv.domain.security.waf.entities import WafDecision


class WafPort(Protocol):
    def inspect(self, request: HttpRequest) -> WafDecision:
        ...
