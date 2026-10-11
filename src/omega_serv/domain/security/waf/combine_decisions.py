"""Combinaison natif + magnet (OMEGA-SERV_ETUDE_INCLUDE_ET_MAGNET_LUA.md
§5.5, OMEGA-SERV_PLAN-DETAILLE_REFERER_ET_MAGNET_WAF.md lot E). Fonction
pure : ne connait ni Lua ni le reseau, prend deux `WafDecision` deja
calculees et en rend une seule.

Regle retenue (etude §5.5, reponse directe a "a qui donner la
priorite ?") : le plus restrictif gagne TOUJOURS, quelle que soit la
source - le magnet est complementaire par definition, un renfort ne
doit jamais pouvoir lever un blocage decide par le natif. En
consequence, `most_restrictive` EST `native_wins` dans le seul cas qui
compte (le natif a deja bloque) et ne laisse le magnet decider que
lorsque le natif ne s'est pas prononce (natif = "allow") - une seule
politique suffit, jamais rendue configurable (etude §5.5 point 3).

Les deux decisions "gagnante" et "perdante" restent neanmoins visibles
ensemble : score additionne, findings concatenes (etude §5.5 point a,
"redondance" = probleme d'attribution via `WafFinding.pack`, jamais de
deduplication automatique tentee ici)."""
from __future__ import annotations

from dataclasses import replace

from omega_serv.domain.security.waf.entities import WafDecision

_ACTION_RANK: dict[str, int] = {"allow": 0, "log": 1, "block": 2}


def combine_decisions(native: WafDecision, magnet: WafDecision | None) -> WafDecision:
    """`magnet=None` : magnet desactive ou chemin exclu (etude §5.5
    point 1 - les exclusions s'evaluent une seule fois, en amont des
    DEUX moteurs, jamais ici) - retourne `native` inchangee."""
    if magnet is None:
        return native

    winner = native if _ACTION_RANK[native.action] >= _ACTION_RANK[magnet.action] else magnet
    return replace(
        winner,
        score=native.score + magnet.score,
        findings=native.findings + magnet.findings,
    )


def magnet_fallback_decision(on_error: str, mode: str) -> WafDecision:
    """Decision de repli quand le magnet echoue (exception Lua, sortie
    malformee, ou timeout - ce dernier cas ne pouvant etre detecte que
    par l'appelant asyncio, jamais par l'adaptateur lui-meme). Partagee
    entre infrastructure/waf/lua_waf_adapter.py (erreurs internes) et
    application/security/evaluate_waf_request.py (timeout) - UNE SEULE
    politique a maintenir.

    `mode` respecte l'invariant central du WAF (scoring.py, decision a
    retenir #14) : `log-only` ne bloque JAMAIS, meme en `fail-closed` -
    un script casse ne doit pas pouvoir, par son seul echec, produire un
    comportement que le mode configure interdit explicitement."""
    if on_error == "fail-closed" and mode == "block":
        return WafDecision(
            action="block", status_code=503, score=0, findings=(),
            log_level="critical", blocked_reason="erreur du script magnet (on_error=fail-closed)",
        )
    return WafDecision(
        action="allow" if on_error == "ignore" else "log",
        status_code=None, score=0, findings=(),
        log_level="debug" if on_error == "ignore" else "error",
    )
