"""Ban reseau de RIPOSTE (OMEGA-SERV_PLAN-DETAILLE_RIPOSTE.md §3.6, lot 6) : omega-serv n'a pas les droits
de bannir au niveau du pare-feu ; il ECRIT une ligne dans `riposte-decisions.jsonl`, lue par les jails
fail2ban installees par omega-jail (une jail par duree, par instance : `<service>-riposte-<duree>`).

Les jails ont des durees FIXES (1 h, 6 h, 24 h, 7 j) alors que les paliers RIPOSTE sont reglables :
decision utilisateur 2026-11-02, chaque ban reseau va a la jail dont la duree est la plus proche SANS
DEPASSER le palier (au moins 1 h) - l'interface l'affiche (« palier 2 h -> jail 1 h »).

Format de ligne : contrat avec les filtres fail2ban d'omega-jail (catalog.yaml), cles dans un ordre FIXE,
`"remote_ip": "<ip>", "jail": "<duree>"` cote a cote. Jamais traduit. Pur : aucune I/O."""
from __future__ import annotations

import json
from datetime import datetime

from omega_serv.domain.security.riposte.config import DAY, HOUR

JAIL_DURATIONS: tuple[tuple[int, str], ...] = (
    (HOUR, "1h"), (6 * HOUR, "6h"), (DAY, "24h"), (7 * DAY, "7d"),
)
"""(secondes, suffixe du nom de jail) - identiques aux jails du catalogue omega-jail."""


def jail_for(duration_seconds: int) -> tuple[int, str]:
    """La jail la plus longue qui ne depasse pas `duration_seconds` ; la plus courte si le palier est
    plus court que toutes."""
    chosen = JAIL_DURATIONS[0]
    for jail in JAIL_DURATIONS:
        if jail[0] <= duration_seconds:
            chosen = jail
    return chosen


def jail_name(service_name: str, duration_seconds: int) -> str:
    return f"{service_name}-riposte-{jail_for(duration_seconds)[1]}"


def network_ban_line(*, at: datetime, ip: str, action_id: str, policy_id: str, tier_index: int | None,
                     duration_seconds: int) -> str:
    """Une ligne JSON par ban reseau. L'ordre des cles est un contrat (filtres fail2ban)."""
    seconds, suffix = jail_for(duration_seconds)
    return json.dumps({
        "timestamp": at.isoformat(), "event": "network_ban",
        "remote_ip": ip, "jail": suffix,
        "jail_seconds": seconds, "duration_seconds": duration_seconds,
        "tier": (tier_index or 0) + 1, "policy_id": policy_id, "action_id": action_id,
    }, ensure_ascii=False)
