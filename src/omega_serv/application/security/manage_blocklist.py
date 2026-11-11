"""Cas d'usage de gestion de la blocklist (doc WAF, menu CLI "Gestion
blocklist"). Un bannissement permanent (`expires_at=None`) exige une
confirmation explicite de l'appelant (doc WAF §5, "Politique
recommandee" : "bannissement permanent uniquement depuis le CLI, avec
confirmation") - ce module refuse d'en creer un sans `confirm_permanent=True`."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

from omega_serv.core.i18n import _
from omega_serv.domain.security.waf.blocklist import validate_blocklist_entry, validate_origin
from omega_serv.domain.security.waf.entities import BlocklistEntry
from omega_serv.ports.blocklist_port import BlocklistPort


@dataclass(frozen=True)
class ManageBlocklistResult:
    success: bool
    message: str


def add_blocklist_entry(
    blocklist_port: BlocklistPort,
    network: str,
    reason: str,
    duration_seconds: int | None,
    confirm_permanent: bool = False,
    origin: str | None = None,
) -> ManageBlocklistResult:
    """`origin` (2026-11-10) : outil qui pose le ban (omega-fire, omega-jail...), garde dans l'entree ;
    il permet a cet outil de ne lever que ses propres bans (voir remove_blocklist_entry)."""
    now = datetime.now(timezone.utc)
    if origin is not None:
        origin_error = validate_origin(origin)
        if origin_error is not None:
            return ManageBlocklistResult(False, origin_error)
    if duration_seconds is None and not confirm_permanent:
        return ManageBlocklistResult(
            False,
            _("Bannissement permanent refusé sans confirmation explicite "
            "(passer --duration-seconds, ou --confirm-permanent pour un bannissement sans expiration)."),
        )

    expires_at = None if duration_seconds is None else (now + timedelta(seconds=duration_seconds)).isoformat()
    entry = BlocklistEntry(
        network=network, reason=reason, created_at=now.isoformat(), expires_at=expires_at, source="manual",
        origin=origin,
    )

    error = validate_blocklist_entry(entry)
    if error is not None:
        return ManageBlocklistResult(False, error)

    blocklist_port.add_entry(entry)
    return ManageBlocklistResult(True, _("Entrée ajoutée : {network} ({value})").format(network=network, value=_('permanent') if expires_at is None else _("expire le {date}").format(date=expires_at)))


def remove_blocklist_entry(
    blocklist_port: BlocklistPort, network: str, origin: str | None = None,
) -> ManageBlocklistResult:
    """Avec `origin` (2026-11-10) : ne leve l'entree que si elle porte cette origine, en une seule
    operation verrouillee (jamais une lecture puis un retrait separes : un ban pose entre-temps par le
    WAF ou RIPOSTE sur le meme reseau n'est jamais leve par un autre outil)."""
    if origin is not None:
        origin_error = validate_origin(origin)
        if origin_error is not None:
            return ManageBlocklistResult(False, origin_error)
        if not blocklist_port.remove_entry_if(network, lambda entry: entry.origin == origin):
            return ManageBlocklistResult(
                False, _("Aucune entrée d'origine {origin} pour {network}").format(origin=origin, network=network))
        return ManageBlocklistResult(True, _("Entrée retirée : {network}").format(network=network))
    removed = blocklist_port.remove_entry(network)
    if not removed:
        return ManageBlocklistResult(False, _("Aucune entrée pour {network}").format(network=network))
    return ManageBlocklistResult(True, _("Entrée retirée : {network}").format(network=network))
