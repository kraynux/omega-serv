# Copyright (c) 2026 kraynux - kraynux@proton.me - Licence MIT (voir fichier LICENSE)
"""Contrat de rendu d'un leurre Niveau 1 (plan_active_defense_omega_serv.md,
Phase 3, section "Routage vers les leurres").

Revise par rapport a la V1 du port (Phase 0, `dispatch(request, assignment)
-> RoutingDecision`) : decider QUELLE decision de routage s'applique
(production/decoy_fixture/...) est une pure question d'etat (une
affectation active existe-t-elle ?), jamais un rendu HTTP - c'est
`application/active_defense/manage_deception.py::resolve_routing_decision`
qui produit desormais le `RoutingDecision`. Ce port se limite a la SEULE
responsabilite qui touche reellement une fixture concrete : etant donne
un nom de profil DEJA choisi, produire la reponse HTTP statique - ou
None si le profil est inconnu/indisponible (le fallback configure -
pass_through/reject - est alors applique par l'appelant, jamais ce
port lui-meme). Niveau 2 (backend reellement isole, Phase 5) n'implique
jamais ce port : il traduit sa RoutingDecision vers serve_proxy()
existant, un chemin de code entierement separe."""
from __future__ import annotations

from typing import Protocol

from omega_serv.domain.http.request import HttpRequest
from omega_serv.domain.http.response import HttpResponse


class DecoyDispatchPort(Protocol):
    def render(self, profile_name: str, request: HttpRequest) -> HttpResponse | None:
        ...
