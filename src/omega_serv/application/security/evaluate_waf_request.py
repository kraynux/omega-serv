# Copyright (c) 2026 kraynux - kraynux@proton.me - Licence MIT (voir fichier LICENSE)
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
mort §9.6)."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

from omega_serv.domain.http.request import HttpRequest
from omega_serv.domain.security.waf.blocklist import validate_blocklist_entry
from omega_serv.domain.security.waf.config import WafConfig
from omega_serv.domain.security.waf.entities import BlocklistEntry, WafDecision
from omega_serv.domain.security.waf.exclusions import is_extension_excluded, matches_any_prefix
from omega_serv.domain.security.waf.reputation import evaluate_escalation
from omega_serv.ports.blocklist_port import BlocklistPort
from omega_serv.ports.rate_limit_port import RateLimitPort
from omega_serv.ports.reputation_tracker_port import ReputationTrackerPort
from omega_serv.ports.waf_port import WafPort


def evaluate_waf_request(
    request: HttpRequest,
    waf_config: WafConfig,
    waf_port: WafPort,
    blocklist_port: BlocklistPort,
    rate_limit_port: RateLimitPort,
    reputation_tracker: ReputationTrackerPort,
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

    if decision.findings and waf_config.reputation.enabled:
        reputation_tracker.record_hit(request.remote_ip)
        hit_count = reputation_tracker.count_hits_in_window(request.remote_ip, waf_config.reputation.window_seconds)
        escalation = evaluate_escalation(hit_count, waf_config.reputation.suspicious_threshold)
        if (
            escalation.should_escalate
            and waf_config.reputation.auto_block
            and blocklist_port.count_auto_entries() < waf_config.reputation.auto_block_max_entries
        ):
            _auto_block(request.remote_ip, escalation.reason, waf_config, blocklist_port)

    return decision


def _auto_block(ip: str, reason: str, waf_config: WafConfig, blocklist_port: BlocklistPort) -> None:
    now = datetime.now(timezone.utc)
    entry = BlocklistEntry(
        network=f"{ip}/32",
        reason=reason,
        created_at=now.isoformat(),
        expires_at=(now + timedelta(seconds=waf_config.reputation.auto_block_duration_seconds)).isoformat(),
        source="auto",
    )
    if validate_blocklist_entry(entry) is None:
        blocklist_port.add_entry(entry)
