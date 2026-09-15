# Copyright (c) 2026 kraynux - kraynux@proton.me - Licence MIT (voir fichier LICENSE)
"""Zones de reverse proxy sortant (OMEGA-SERV_PLAN-DETAILLE_REVERSE_PROXY.md,
etude de conception validee avant ce chantier) - OMEGA-SERV agit ici
lui-meme comme reverse proxy vers un backend, sens INVERSE de
`server.tls.mode = "behind_proxy"` (OMEGA-SERV derriere un proxy,
mecanisme existant et different).

Phase 2 (round-robin multi-upstreams, §9/§11 du document) : `upstreams`
devient une liste (au moins un element). Pas de verification de sante
des upstreams (§3 du document, deliberement differe) : un upstream mort
cause des echecs individuels periodiques (502) au lieu d'etre exclu de
la rotation.

Phase 3 (TLS vers l'upstream, §5.3/§12) : chaque `UpstreamTarget` porte
son propre `use_tls` (les upstreams d'une meme zone peuvent melanger
HTTP et HTTPS, ex. migration progressive d'un backend), tandis que
`ProxyZone.verify_upstream_tls` reste une politique de securite au
niveau de la zone (verification stricte par defaut, desactivable mais
documentee comme dangereuse - §5.3).

Phase 4 (WebSocket, §4/§14) : `ProxyZone.websocket_enabled` reste une
politique de ZONE (pas par upstream - un tube WebSocket une fois etabli
reste fige sur UN SEUL upstream pour toute sa duree de vie, choisi par
le meme `ProxyRoundRobinState` que le relai HTTP ordinaire, mais plus
aucune bascule possible ensuite - contrairement au relai HTTP ordinaire
qui peut choisir un upstream different a CHAQUE requete)."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from omega_serv.domain.routing.zone_resolver import Zone, resolve_zone


@dataclass(frozen=True)
class UpstreamTarget:
    host: str
    port: int
    use_tls: bool = False


@dataclass(frozen=True)
class ProxyZone:
    url_prefix: str
    upstreams: tuple[UpstreamTarget, ...] = ()
    connect_timeout_seconds: float = 5.0
    read_timeout_seconds: float = 30.0
    preserve_host_header: bool = False
    """Si vrai, transmet le Host: du client tel quel a l'upstream -
    sinon (par defaut), remplace par `host:port` de l'upstream choisi
    (comportement le plus previsible pour un backend qui ne connait
    pas le nom public expose par OMEGA-SERV)."""
    verify_upstream_tls: bool = True
    """Verification stricte du certificat presente par un upstream
    HTTPS (`UpstreamTarget.use_tls=True`) - desactivable (`False`) pour
    un backend interne en certificat auto-signe, mais explicitement
    dangereux (MITM possible sur le reseau intermediaire) - jamais un
    raccourci silencieux (§5.3 du document de conception). Sans effet
    sur un upstream HTTP (use_tls=False)."""
    websocket_enabled: bool = False
    """Autorise la mise a niveau `Upgrade: websocket` vers cette zone -
    desactive par defaut (§4 : chemin de code separe, jamais suppose).
    Sans effet sur les requetes HTTP ordinaires de la meme zone, qui
    continuent de suivre `serve_proxy()` normalement."""


def parse_proxy_zones(raw_list: list[dict[str, Any]]) -> list[ProxyZone]:
    return [
        ProxyZone(
            url_prefix=item["url_prefix"],
            upstreams=tuple(
                UpstreamTarget(host=u.get("host", ""), port=int(u.get("port", 0)), use_tls=bool(u.get("use_tls", False)))
                for u in item.get("upstreams", [])
            ),
            connect_timeout_seconds=float(item.get("connect_timeout_seconds", 5.0)),
            read_timeout_seconds=float(item.get("read_timeout_seconds", 30.0)),
            preserve_host_header=bool(item.get("preserve_host_header", False)),
            verify_upstream_tls=bool(item.get("verify_upstream_tls", True)),
            websocket_enabled=bool(item.get("websocket_enabled", False)),
        )
        for item in raw_list
    ]


def validate_proxy_zone(zone: ProxyZone) -> str | None:
    if not zone.url_prefix.startswith("/"):
        return f"url_prefix doit commencer par '/' : {zone.url_prefix!r}"
    if not zone.upstreams:
        return f"au moins un upstream est requis (zone {zone.url_prefix!r})"
    for upstream in zone.upstreams:
        if not upstream.host:
            return f"host d'upstream vide (zone {zone.url_prefix!r})"
        if not (1 <= upstream.port <= 65535):
            return f"port d'upstream invalide : {upstream.port!r} (zone {zone.url_prefix!r})"
    if zone.connect_timeout_seconds <= 0:
        return f"connect_timeout_seconds doit etre strictement positif (zone {zone.url_prefix!r})"
    if zone.read_timeout_seconds <= 0:
        return f"read_timeout_seconds doit etre strictement positif (zone {zone.url_prefix!r})"
    return None


def resolve_proxy_zone(path: str, zones: list[ProxyZone]) -> ProxyZone | None:
    """Plus-long-prefixe-gagne (meme ZoneResolver que fastcgi/access_control/
    alias/redirections/cache/dirlisting/auth/upload, plan de
    developpement §6) - None si aucune zone ne correspond."""
    if not zones:
        return None
    wrapped = [Zone(path_prefix=z.url_prefix, data=z) for z in zones]
    zone = resolve_zone(path, wrapped)
    return zone.data if zone is not None else None


class ProxyRoundRobinState:
    """Compteur de repartition de charge, un par zone (cle = url_prefix),
    construit UNE SEULE FOIS par serveur (bootstrap/container.py ou
    build_server, jamais recree par requete) - retour utilisateur, scope
    confirme des le depart de l'etude (backends multiples avec
    repartition de charge). Aucune verification de sante : la rotation
    continue meme si un upstream est mort, chaque echec individuel
    remonte en 502 (deliberement differe, §3 du document). Jamais de
    lock : un simple compteur incremente en Python reste atomique entre
    deux `await` (pas de veritable concurrence a l'interieur d'un seul
    increment), coherent avec le reste du projet (aucun autre etat
    partage de ce type n'utilise de verrou)."""

    def __init__(self) -> None:
        self._next_index: dict[str, int] = {}

    def pick(self, zone_key: str, upstream_count: int) -> int:
        index = self._next_index.get(zone_key, 0) % upstream_count
        self._next_index[zone_key] = index + 1
        return index
