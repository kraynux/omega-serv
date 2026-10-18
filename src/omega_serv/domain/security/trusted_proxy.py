"""Determination de l'adresse client reelle (spec §19).

Applique la decision de la revue des angles morts avant Phase 0
(OMEGA-SERV_PLAN_DEVELOPPEMENT.md §9.3) : toute adresse est normalisee
(IPv4-mappee-IPv6, `::ffff:203.0.113.10` -> `203.0.113.10`) avant
comparaison - sans cela, une blocklist ou une regle de confiance basee
sur l'IPv4 pourrait etre contournee par la forme IPv6-mappee
equivalente. Les en-tetes `X-Forwarded-For`/`Forwarded` ne sont
consultes QUE si l'adresse reelle du pair TCP appartient a un reseau de
confiance declare - jamais en provenance directe d'Internet."""
from __future__ import annotations

import ipaddress

from omega_serv.domain.http.headers import HttpHeaders


def normalize_ip(ip_str: str) -> str:
    try:
        addr = ipaddress.ip_address(ip_str)
    except ValueError:
        return ip_str
    if isinstance(addr, ipaddress.IPv6Address) and addr.ipv4_mapped is not None:
        return str(addr.ipv4_mapped)
    return str(addr)


def is_trusted_proxy(peer_ip: str, trusted_networks: list[str]) -> bool:
    normalized = normalize_ip(peer_ip)
    try:
        addr = ipaddress.ip_address(normalized)
    except ValueError:
        return False

    for network_str in trusted_networks:
        try:
            network = ipaddress.ip_network(network_str, strict=False)
        except ValueError:
            continue
        if addr in network:
            return True
    return False


def _forwarded_hop_for(hop: str) -> str | None:
    """Extrait le champ `for=` d'UN maillon d'un en-tete `Forwarded`
    (RFC 7239) - gere la forme IPv6 entre crochets (`for="[::1]:1234"`)
    et un eventuel port IPv4 (`for=1.2.3.4:5678`)."""
    for part in hop.split(";"):
        key, _, raw_value = part.strip().partition("=")
        if key.strip().lower() != "for":
            continue
        raw_value = raw_value.strip().strip('"')
        if raw_value.startswith("["):
            return raw_value[1:].split("]", 1)[0]
        return raw_value.split(":", 1)[0]
    return None


def _header_hops(header_name: str, value: str) -> list[str]:
    """Adresses de la chaine, dans l'ordre de l'en-tete (client d'origine
    pretendu a gauche, dernier proxy a droite)."""
    if header_name.lower() == "forwarded":
        hops = [_forwarded_hop_for(hop) for hop in value.split(",")]
        return [h for h in hops if h]
    return [h.strip() for h in value.split(",") if h.strip()]


def _rightmost_untrusted(hops: list[str], trusted_networks: list[str]) -> str:
    """OMEGA-SERV_PLAN-DETAILLE_SENSITIVE_PATHS.md §3.14-b (Q11, 2026-10-18) :
    la valeur la plus a GAUCHE est choisie par le client lui-meme - un
    proxy qui AJOUTE son adresse a un en-tete fourni par le client (au lieu
    de le remplacer) laissait alors n'importe qui se declarer `127.0.0.1`
    et echapper a la blocklist, au rate-limit et a l'auto-ban. On parcourt
    donc la chaine de DROITE a GAUCHE et on retient la premiere adresse qui
    n'est PAS un proxy de confiance (methode standard). Un seul proxy qui
    remplace l'en-tete : resultat identique a avant. Toute la chaine de
    confiance : la plus a gauche (comportement anterieur)."""
    for hop in reversed(hops):
        if not is_trusted_proxy(hop, trusted_networks):
            return normalize_ip(hop)
    return normalize_ip(hops[0])


def resolve_client_ip(
    peer_ip: str,
    headers: HttpHeaders,
    trusted_networks: list[str],
    header_preference: list[str],
) -> str:
    """Retourne l'adresse client a utiliser reellement (logs, blocklist,
    rate-limit) - le pair TCP normalise si non fiable, sinon l'adresse
    retenue dans le premier en-tete de confiance disponible (voir
    `_rightmost_untrusted`)."""
    normalized_peer = normalize_ip(peer_ip)

    if not is_trusted_proxy(peer_ip, trusted_networks):
        return normalized_peer

    for header_name in header_preference:
        value = headers.get(header_name)
        if not value:
            continue
        hops = _header_hops(header_name, value)
        if hops:
            return _rightmost_untrusted(hops, trusted_networks)

    return normalized_peer
