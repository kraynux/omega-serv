"""Politique de score -> decision (doc WAF §10, "WafDecision"). Fonction
pure : ne connait ni le reseau ni les logs, prend une liste de findings
deja calcules et une configuration de scoring, rend une decision.

Regle centrale (doc WAF, decision a retenir #14) : `mode == "log-only"`
ne bloque JAMAIS, meme au-dessus du seuil - seul `mode == "block"`
peut produire `action == "block"`. C'est la seule maniere sure de
tester des regles en production sans risque de faux positif bloquant."""
from __future__ import annotations

from omega_serv.domain.security.waf.config import ScoringConfig
from omega_serv.domain.security.waf.entities import WafDecision, WafFinding


def compute_decision(
    findings: tuple[WafFinding, ...],
    scoring: ScoringConfig,
    mode: str,
) -> WafDecision:
    score = sum(f.weight for f in findings)

    if not findings:
        return WafDecision(action="allow", status_code=None, score=0, findings=(), log_level="debug")

    if score >= scoring.block_threshold:
        if mode == "block":
            return WafDecision(
                action="block",
                status_code=scoring.response_status,
                score=score,
                findings=findings,
                log_level="warning" if score < scoring.high_score_threshold else "critical",
                blocked_reason="score >= block_threshold",
            )
        return WafDecision(
            action="log",
            status_code=None,
            score=score,
            findings=findings,
            log_level="warning" if score < scoring.high_score_threshold else "critical",
        )

    return WafDecision(action="log", status_code=None, score=score, findings=findings, log_level="info")
