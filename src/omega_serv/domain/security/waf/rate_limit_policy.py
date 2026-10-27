"""Choix de la regle de debit applicable a une requete
(OMEGA-SERV_ETUDE_RATE_LIMIT_EXCLUSIONS.md, decisions D1-D5) - fonctions
pures, aucune I/O.

- D1 : une regle specifique REMPLACE la limite globale (valeur libre,
  `requests == 0` = illimite) et a son propre compteur.
- D2 : priorite dossier (plus long prefixe) > IP/reseau (reseau le plus
  precis) > global.
- D4 : source sure = reseaux `never_auto_block` (deja passes par le
  garde-fou du proxy de confiance) OU regle IP/reseau cochee `trusted` ;
  un depassement d'une source sure n'est jamais bannissable.
- D5 : correspondance des prefixes par `zone_resolver.path_matches_prefix`
  (frontiere de segment, "/" final cosmetique) - le meme mecanisme que les
  alias/redirections/cache."""
from __future__ import annotations

import ipaddress
from dataclasses import dataclass

from omega_serv.domain.routing.zone_resolver import Zone, resolve_zone
from omega_serv.domain.security.waf.config import (
    GlobalRateLimitConfig,
    RateLimitConfig,
    SourceRateLimitPolicy,
)
from omega_serv.domain.security.waf.reputation import LOOPBACK_NETWORKS, is_exempt_from_auto_block

_IpNetwork = ipaddress.IPv4Network | ipaddress.IPv6Network


@dataclass(frozen=True)
class SelectedRateLimit:
    """`key` = cle du compteur (jamais partagee entre deux regles) ;
    `label` = motif du rejet journalise ; `requests == 0` = pas de comptage."""
    key: str
    requests: int
    window_seconds: int
    label: str
    # "path" | "source" | "global" - une regle explicite ("path"/"source") fait
    # foi pour le volume, y compris face au rate limit propre a magnet.
    scope: str = "global"


def _parse_ip(ip: str) -> ipaddress.IPv4Address | ipaddress.IPv6Address | None:
    try:
        addr = ipaddress.ip_address(ip)
    except ValueError:
        return None
    if isinstance(addr, ipaddress.IPv6Address) and addr.ipv4_mapped is not None:
        return addr.ipv4_mapped
    return addr


def _parse_network(network: str) -> _IpNetwork | None:
    try:
        return ipaddress.ip_network(network, strict=False)
    except ValueError:
        return None  # deja signale par validate_rate_limit_policies, jamais un crash par requete


def matching_source_policy(ip: str, policies: tuple[SourceRateLimitPolicy, ...]) -> SourceRateLimitPolicy | None:
    """Regle IP/reseau la plus precise (plus grand prefixlen) contenant `ip`."""
    addr = _parse_ip(ip)
    if addr is None:
        return None
    best: tuple[int, SourceRateLimitPolicy] | None = None
    for policy in policies:
        net = _parse_network(policy.network)
        if net is None or net.version != addr.version or addr not in net:
            continue
        if best is None or net.prefixlen > best[0]:
            best = (net.prefixlen, policy)
    return best[1] if best is not None else None


def select_rate_limit(path: str, ip: str, config: RateLimitConfig) -> SelectedRateLimit:
    zones = [Zone(policy.prefix, policy) for policy in config.path_policies]
    zone = resolve_zone(path, zones)
    if zone is not None:
        policy = zone.data
        return SelectedRateLimit(
            key=f"{ip}|path:{policy.prefix}", requests=policy.requests,
            window_seconds=policy.window_seconds, label=f"débit {policy.prefix}", scope="path",
        )
    source = matching_source_policy(ip, config.source_policies)
    if source is not None:
        return SelectedRateLimit(
            key=f"{ip}|net:{source.network}", requests=source.requests,
            window_seconds=source.window_seconds, label=f"débit {source.network}", scope="source",
        )
    global_: GlobalRateLimitConfig = config.global_
    return SelectedRateLimit(
        key=ip, requests=global_.requests, window_seconds=global_.window_seconds, label="rate limit global",
    )


def is_trusted_rate_limit_source(
    ip: str, never_auto_block: tuple[str, ...], policies: tuple[SourceRateLimitPolicy, ...],
) -> bool:
    if is_exempt_from_auto_block(ip, never_auto_block):
        return True
    addr = _parse_ip(ip)
    if addr is None:
        return False
    for policy in policies:
        if not policy.trusted:
            continue
        net = _parse_network(policy.network)
        if net is not None and net.version == addr.version and addr in net:
            return True
    return False


def effective_source_policies(
    policies: tuple[SourceRateLimitPolicy, ...], trusted_proxy_enabled: bool,
) -> tuple[SourceRateLimitPolicy, ...]:
    """Meme garde-fou que `effective_never_auto_block` (§3.14-a) : sans
    proxy de confiance, tout le trafic d'un proxy local arrive en 127.0.0.1 -
    une regle couvrant le loopback s'appliquerait a Internet entier. Ces
    regles sont donc ignorees tant que `trusted_proxy` n'est pas actif."""
    if trusted_proxy_enabled:
        return policies
    loopbacks = [ipaddress.ip_network(n) for n in LOOPBACK_NETWORKS]
    kept: list[SourceRateLimitPolicy] = []
    for policy in policies:
        net = _parse_network(policy.network)
        if net is not None and any(net.version == lo.version and net.overlaps(lo) for lo in loopbacks):
            continue
        kept.append(policy)
    return tuple(kept)
