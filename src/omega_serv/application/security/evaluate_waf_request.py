"""Cas d'usage EvaluateRequest (doc WAF, "Repartition Clean
Architecture" : application/security/ orchestre inspection WAF,
configuration, mode log-only/block et escalade).

Ordre suivi (doc WAF, "Ordre de pipeline conseille", etapes 7-12) :
blocklist -> rate limit global -> exclusions -> packs de regles ->
score/decision -> escalade de reputation. Les etapes 1-6 (limites de
connexion, parsing, tailles, normalisation, methode/Host, IP via proxy
de confiance) sont deja faites AVANT d'arriver ici (Phases 1/2) et ne
dependent jamais du WAF. Les politiques de service/zone
(waf_service_policies) ne sont PAS construites en V1 (voir
OMEGA-SERV_PLAN_DEVELOPPEMENT.md §3 Phase 5) - seule l'exclusion par
prefixe/extension existe, suffisante pour l'exemption /healthz (angle
mort §9.6).

DEVENU ASYNC (OMEGA-SERV_PLAN-DETAILLE_REFERER_ET_MAGNET_WAF.md, lot E,
decision D2) : seul changement necessaire pour integrer le script WAF
complementaire "magnet" sans jamais bloquer la boucle asyncio du
serveur - `magnet_port.inspect()` est synchrone (contrat `WafPort`
inchange) mais dispatche ici via `loop.run_in_executor()` sur un thread
dedie, jamais appele directement sur le thread de la boucle d'evenements.
`magnet_port`/`magnet_executor` a `None` (defaut) : comportement
IDENTIQUE a avant ce lot, aucun cout, aucun branchement mort - le seul
`await` ajoute au chemin "magnet desactive" est `evaluate_escalation`
qui, lui, ne fait aucune I/O (cout non mesurable). Les exclusions
restent evaluees une seule fois, EN AMONT des deux moteurs (natif ET
magnet) - etude §5.5 point 1, aucun des deux n'est meme invoque sur un
chemin exclu."""
from __future__ import annotations

import asyncio
import sys
from concurrent.futures import Executor
from datetime import datetime, timedelta, timezone

from omega_serv.domain.http.request import HttpRequest
from omega_serv.domain.security.waf.blocklist import validate_blocklist_entry
from omega_serv.domain.security.waf.combine_decisions import (
    combine_decisions,
    magnet_fallback_decision,
)
from omega_serv.domain.security.waf.config import WafConfig
from omega_serv.domain.security.waf.entities import (
    BlocklistEntry,
    KeywordListDefinition,
    WafDecision,
)
from omega_serv.domain.security.waf.exclusions import is_extension_excluded, matches_any_prefix
from omega_serv.domain.security.waf.reputation import evaluate_escalation, is_exempt_from_auto_block
from omega_serv.ports.blocklist_port import BlocklistPort
from omega_serv.ports.rate_limit_port import RateLimitPort
from omega_serv.ports.reputation_tracker_port import ReputationTrackerPort
from omega_serv.ports.waf_port import WafPort


async def evaluate_waf_request(
    request: HttpRequest,
    waf_config: WafConfig,
    waf_port: WafPort,
    blocklist_port: BlocklistPort,
    rate_limit_port: RateLimitPort,
    reputation_tracker: ReputationTrackerPort,
    magnet_port: WafPort | None = None,
    magnet_executor: Executor | None = None,
) -> WafDecision:
    blocked_entry = blocklist_port.is_blocked(request.remote_ip)
    if blocked_entry is not None:
        return WafDecision(
            action="block",
            status_code=403,
            score=0,
            blocked_reason=f"IP bloquee : {blocked_entry.reason}",
            log_level="warning",
        )

    if waf_config.rate_limit.enabled:
        policy = waf_config.rate_limit.global_
        result = rate_limit_port.check(request.remote_ip, policy.requests, policy.window_seconds)
        if not result.allowed:
            return WafDecision(
                action="block",
                status_code=policy.response_status,
                score=0,
                blocked_reason="rate limit global depasse",
                log_level="warning",
                retry_after_seconds=result.retry_after_seconds,
            )

    excluded = matches_any_prefix(request.path, waf_config.exclusions.path_prefixes) or is_extension_excluded(
        request.path, waf_config.exclusions.extensions
    )
    if excluded:
        return WafDecision(action="allow", status_code=None, score=0, log_level="debug")

    decision = waf_port.inspect(request)

    if magnet_port is not None and waf_config.magnet.enabled:
        magnet_decision = await _inspect_with_magnet(request, waf_config, magnet_port, magnet_executor)
        decision = combine_decisions(decision, magnet_decision)

    if decision.findings and waf_config.reputation.enabled:
        _apply_reputation(request.remote_ip, decision, waf_config, reputation_tracker, blocklist_port)

    return decision


def _apply_reputation(
    ip: str,
    decision: WafDecision,
    waf_config: WafConfig,
    reputation_tracker: ReputationTrackerPort,
    blocklist_port: BlocklistPort,
) -> None:
    """Recidive (OMEGA-SERV_PLAN-DETAILLE_SENSITIVE_PATHS.md §3.12) :
    - finding d'une keyword_list AVEC seuil propre -> compte UNIQUEMENT
      dans le compteur de cette liste (sinon le seuil commun, plus bas,
      se declencherait avant et rendrait le seuil de la liste inutile) ;
    - finding d'un pack JSON, du magnet, ou d'une liste SANS seuil propre
      -> compteur commun, exactement comme avant ce plan ;
    - finding d'une liste en observation (`observe_only`) -> aucun compteur.
    Plusieurs seuils depasses par la meme requete -> une seule entree de
    blocklist, avec la duree la plus longue. Reseaux exemptes (§3.13) :
    les compteurs avancent (diagnostic), mais jamais d'auto-ban."""
    reputation = waf_config.reputation
    lists_by_id = {definition.id: definition for definition in waf_config.keyword_lists}

    counts_globally = False
    own_threshold_lists: dict[str, KeywordListDefinition] = {}
    for finding in decision.findings:
        definition = lists_by_id.get(finding.pack)
        if definition is None or (definition.escalation_threshold <= 0 and not definition.observe_only):
            counts_globally = True
        elif not definition.observe_only:
            own_threshold_lists[definition.id] = definition

    escalations: list[tuple[str, int]] = []
    if counts_globally:
        reputation_tracker.record_hit(ip)
        hit_count = reputation_tracker.count_hits_in_window(ip, reputation.window_seconds)
        escalation = evaluate_escalation(hit_count, reputation.suspicious_threshold)
        if escalation.should_escalate:
            escalations.append((escalation.reason, reputation.auto_block_duration_seconds))
    for list_id, definition in own_threshold_lists.items():
        reputation_tracker.record_hit(ip, key=list_id)
        hit_count = reputation_tracker.count_hits_in_window(ip, definition.escalation_window_seconds, key=list_id)
        escalation = evaluate_escalation(hit_count, definition.escalation_threshold)
        if escalation.should_escalate:
            escalations.append((
                f"recidive {list_id} : {escalation.reason}",
                definition.auto_block_duration_seconds or reputation.auto_block_duration_seconds,
            ))

    if (
        escalations
        and reputation.auto_block
        and not is_exempt_from_auto_block(ip, reputation.never_auto_block)
        and blocklist_port.count_auto_entries() < reputation.auto_block_max_entries
    ):
        reason, duration_seconds = max(escalations, key=lambda item: item[1])
        _auto_block(ip, reason, duration_seconds, blocklist_port)


async def _inspect_with_magnet(
    request: HttpRequest, waf_config: WafConfig, magnet_port: WafPort, magnet_executor: Executor | None,
) -> WafDecision:
    """Dispatche l'appel magnet (synchrone, potentiellement lent) sur
    `magnet_executor` - jamais sur le thread de la boucle asyncio (D2).
    `asyncio.wait_for` bornE LA REQUETE a `timeout_ms`, mais ne peut pas
    interrompre le thread sous-jacent une fois lance (lupa n'expose
    aucun mecanisme d'interruption, voir infrastructure/waf/
    lua_waf_adapter.py) : un script vraiment bloque laisse son thread
    occupe au-dela du timeout - limite operationnelle connue et
    documentee, pas un risque pour la latence de LA REQUETE elle-meme,
    qui recoit sa decision de repli dans tous les cas."""
    loop = asyncio.get_running_loop()
    try:
        return await asyncio.wait_for(
            loop.run_in_executor(magnet_executor, magnet_port.inspect, request),
            timeout=waf_config.magnet.timeout_ms / 1000,
        )
    except TimeoutError:
        return magnet_fallback_decision(waf_config.magnet.on_error, waf_config.mode)


def _auto_block(ip: str, reason: str, duration_seconds: int, blocklist_port: BlocklistPort) -> None:
    now = datetime.now(timezone.utc)
    entry = BlocklistEntry(
        # /128 pour une IPv6 : "<ipv6>/32" serait un reseau IPv6 invalide
        # (refuse par validate_blocklist_entry), donc jamais bloque.
        network=f"{ip}/128" if ":" in ip else f"{ip}/32",
        reason=reason,
        created_at=now.isoformat(),
        expires_at=(now + timedelta(seconds=duration_seconds)).isoformat(),
        source="auto",
    )
    if validate_blocklist_entry(entry) is None:
        try:
            blocklist_port.add_entry(entry)
        except OSError as e:
            # Un ban qui ne peut pas etre ecrit (fichier illisible, ou secure/ non
            # inscriptible par le service systemd) ne doit JAMAIS faire echouer la
            # requete en cours : journalise (journalctl), la requete continue.
            print(f"ERREUR auto-ban de {ip} non enregistre : {e}", file=sys.stderr)
