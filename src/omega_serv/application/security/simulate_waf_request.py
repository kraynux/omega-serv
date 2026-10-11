"""Cas d'usage `omega-serv waf test` (doc WAF, "Tests WAF" - simulateur
CLI hors serveur). Reutilise evaluate_waf_request() avec les VRAIS
collaborateurs construits depuis la configuration reelle (meme objets
que build_server() cablerait pour une vraie requete) - jamais une
logique dupliquee ou simplifiee pour le test.

`native_decision`/`magnet_decision` AJOUTES (OMEGA-SERV_PLAN-DETAILLE_
REFERER_ET_MAGNET_WAF.md, lot E, E12/etude §5.6) : appels DIAGNOSTIQUES
supplementaires, directs, en plus de l'appel reel via
`evaluate_waf_request` (qui reste l'unique source du champ `decision`
final, authoritaire). Permet a l'utilisateur de voir d'OU vient un
blocage quand natif et magnet sont tous les deux actifs - jamais une
duplication de la logique de decision elle-meme, juste de son
observabilite."""
from __future__ import annotations

import asyncio
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
    native_decision: WafDecision | None = None
    magnet_decision: WafDecision | None = None
    magnet_unsupported_members: frozenset[str] | None = None
    magnet_error: str | None = None


async def simulate_waf_request(
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

    native_decision = waf.waf_port.inspect(request)
    magnet_decision: WafDecision | None = None
    magnet_unsupported_members: frozenset[str] | None = None
    magnet_error: str | None = None
    if waf.magnet_port is not None and waf.config.magnet.enabled:
        loop = asyncio.get_running_loop()
        magnet_decision = await loop.run_in_executor(waf.magnet_executor, waf.magnet_port.inspect, request)
        # Diagnostics specifiques a LuaWafAdapter, PAS du contrat WafPort
        # (voir infrastructure/waf/lua_waf_adapter.py) - lus via getattr,
        # jamais exiges de toute autre implementation de WafPort.
        magnet_unsupported_members = getattr(waf.magnet_port, "unsupported_members", None)
        magnet_error = getattr(waf.magnet_port, "last_error", None)

    decision = await evaluate_waf_request(
        request, waf.config, waf.waf_port, waf.blocklist_port, waf.rate_limit_port, waf.reputation_tracker,
        waf.magnet_port, waf.magnet_executor,
    )
    return WafSimulationReport(
        decision=decision, zone_id=decision.matched_zone_id or "default", mode=waf.config.mode,
        native_decision=native_decision, magnet_decision=magnet_decision,
        magnet_unsupported_members=magnet_unsupported_members, magnet_error=magnet_error,
    )
