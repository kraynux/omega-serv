# Copyright (c) 2026 kraynux - kraynux@proton.me - Licence MIT (voir fichier LICENSE)
"""Cas d'usage `omega-serv waf test` (doc WAF, "Tests WAF" - simulateur
CLI hors serveur). Reutilise evaluate_waf_request() avec les VRAIS
collaborateurs construits depuis la configuration reelle (meme objets
que build_server() cablerait pour une vraie requete) - jamais une
logique dupliquee ou simplifiee pour le test."""
from __future__ import annotations

from dataclasses import dataclass

from omega_serv.application.security.evaluate_waf_request import evaluate_waf_request
from omega_serv.application.server.start_server import WafCollaborators
from omega_serv.domain.http.headers import HttpHeaders
from omega_serv.domain.http.request import HttpRequest
from omega_serv.domain.security.waf.entities import WafDecision


@dataclass(frozen=True)
class WafSimulationReport:
    decision: WafDecision
    zone_id: str
    mode: str


def simulate_waf_request(
    method: str,
    path: str,
    query: str,
    body: str,
    remote_ip: str,
    waf: WafCollaborators,
) -> WafSimulationReport:
    request = HttpRequest(
        request_id="waf-test",
        remote_ip=remote_ip,
        peer_ip=remote_ip,
        method=method.upper(),
        path=path,
        raw_path=path + (f"?{query}" if query else ""),
        query=query,
        headers=HttpHeaders.from_pairs([]),
        body=body.encode("utf-8") if body else None,
        content_length=None,
        is_tls=False,
    )
    decision = evaluate_waf_request(
        request, waf.config, waf.waf_port, waf.blocklist_port, waf.rate_limit_port, waf.reputation_tracker,
    )
    return WafSimulationReport(decision=decision, zone_id=decision.matched_zone_id or "default", mode=waf.config.mode)
