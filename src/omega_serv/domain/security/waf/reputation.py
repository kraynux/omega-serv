"""Escalade de reputation (doc WAF §8) : separe le score WAF d'une
requete individuelle du comportement recidiviste d'une IP dans le
temps. Fonction pure - le comptage effectif des hits par IP/fenetre est
une responsabilite d'infrastructure/waf/reputation_tracker.py (etat
mutable), pas de ce module."""
from __future__ import annotations

import ipaddress
from dataclasses import dataclass

from omega_serv.core.i18n import _


@dataclass(frozen=True)
class ReputationDecision:
    should_escalate: bool
    reason: str


def evaluate_escalation(hit_count_in_window: int, suspicious_threshold: int) -> ReputationDecision:
    """`hit_count_in_window` est le nombre de requetes ayant declenche
    au moins un finding WAF pour une IP donnee, dans la fenetre
    configuree (reputation.window_seconds) - calcule par l'appelant
    (le tracker d'infrastructure), pas ici."""
    if suspicious_threshold <= 0:
        return ReputationDecision(should_escalate=False, reason="seuil désactivé (<= 0)")
    if hit_count_in_window >= suspicious_threshold:
        return ReputationDecision(
            should_escalate=True,
            reason=f"{hit_count_in_window} détections suspectes dans la fenêtre (seuil {suspicious_threshold})",
        )
    return ReputationDecision(should_escalate=False, reason="sous le seuil")


# Reseaux jamais bannis AUTOMATIQUEMENT (OMEGA-SERV_PLAN-DETAILLE_SENSITIVE_
# PATHS.md §3.13, decision utilisateur 2026-10-18 : "seulement ce qui vient
# de l'externe") - hote local, Tailscale (exactement 100.64.0.0/10, JAMAIS
# 100.0.0.0/8 qui contient des adresses publiques) et reseau local. Seul
# l'auto-ban est concerne : la requete elle-meme reste refusee/journalisee
# (niveau 1), et une entree MANUELLE de blocklist reste toujours possible.
LOOPBACK_NETWORKS: tuple[str, ...] = ("127.0.0.0/8", "::1/128")
DEFAULT_NEVER_AUTO_BLOCK: tuple[str, ...] = (
    *LOOPBACK_NETWORKS,
    "100.64.0.0/10", "fd7a:115c:a1e0::/48",
    "10.0.0.0/8", "172.16.0.0/12", "192.168.0.0/16", "169.254.0.0/16", "fc00::/7", "fe80::/10",
)


def _parse_networks(networks: tuple[str, ...]) -> list[ipaddress.IPv4Network | ipaddress.IPv6Network]:
    parsed: list[ipaddress.IPv4Network | ipaddress.IPv6Network] = []
    for network in networks:
        try:
            parsed.append(ipaddress.ip_network(network, strict=False))
        except ValueError:
            continue  # deja signale par validate_never_auto_block, jamais un crash par requete
    return parsed


def is_exempt_from_auto_block(ip: str, networks: tuple[str, ...]) -> bool:
    """`ip` est l'adresse client DEJA resolue (proxy de confiance compris).
    Forme IPv4-mappee-IPv6 normalisee avant comparaison (meme garde que
    trusted_proxy.normalize_ip : jamais de contournement par
    `::ffff:127.0.0.1`). Adresse illisible = non exemptee."""
    try:
        addr = ipaddress.ip_address(ip)
    except ValueError:
        return False
    if isinstance(addr, ipaddress.IPv6Address) and addr.ipv4_mapped is not None:
        addr = addr.ipv4_mapped
    return any(addr.version == net.version and addr in net for net in _parse_networks(networks))


def effective_never_auto_block(networks: tuple[str, ...], trusted_proxy_enabled: bool) -> tuple[str, ...]:
    """Garde-fou §3.14-a : sans proxy de confiance, un serveur place
    derriere un proxy LOCAL (tailscale serve/Funnel, nginx...) voit TOUT le
    trafic Internet comme 127.0.0.1 (constate sur craftdark avant le
    2026-10-03). Exempter le loopback reviendrait alors a exempter
    Internet entier : l'exemption loopback n'est donc appliquee QUE si
    `trusted_proxy` est actif. Les autres reseaux (Tailscale, local) ne
    peuvent pas apparaitre par ce biais et restent exemptes."""
    if trusted_proxy_enabled:
        return networks
    loopbacks = _parse_networks(LOOPBACK_NETWORKS)
    kept: list[str] = []
    for network in networks:
        try:
            parsed = ipaddress.ip_network(network, strict=False)
        except ValueError:
            kept.append(network)
            continue
        if any(parsed.version == lo.version and parsed.overlaps(lo) for lo in loopbacks):
            continue
        kept.append(network)
    return tuple(kept)


def validate_never_auto_block(networks: tuple[str, ...]) -> list[str]:
    errors: list[str] = []
    for network in networks:
        try:
            ipaddress.ip_network(network, strict=False)
        except ValueError:
            errors.append(_("options.waf.reputation.never_auto_block : réseau invalide : {network!r}").format(network=network))
    return errors
