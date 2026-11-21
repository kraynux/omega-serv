"""Route reservee `/.omega-serv-admin/` - canal d'administration a
chaud entre le TUI et le processus serveur reel EN COURS D'EXECUTION
(OMEGA-SERV_PLAN-DETAILLE_REVERSE_PROXY.md §22, reouverte : les deux
besoins restes bloques depuis la Phase 6/8 - declencheur TUI DRAINING/
MAINTENANCE et ratio hits/miss du cache - necessitaient tous deux un
canal que le mecanisme existant (TUI -> config -> SIGHUP) ne fournit
pas, puisqu'ils portent sur un etat EPHEMERE qui ne vit que dans la
memoire du processus serveur, jamais sur disque).

Meme famille que `/.omega-serv-load/` (`serve_proxy_load.py`) :
protegee par `trusted_proxy`, fail-CLOSED si absent/desactive ou
`trusted_networks` vide (§19.1, meme garde non negociable) - le TUI
interroge sa PROPRE instance en HTTP local, `127.0.0.1` doit donc
figurer dans `trusted_networks` pour que cette route fonctionne (meme
prerequis que le mode natif de charge, §19.3 - documente, jamais un
repli silencieux "localhost toujours autorise").

JAMAIS un contrat public : consommee UNIQUEMENT par le TUI de cette
MEME installation (aucune compatibilite externe a maintenir, aucune
version, aucun client tiers envisage)."""
from __future__ import annotations

import json
from urllib.parse import parse_qs

from omega_serv.domain.config.entities import OmegaServConfig
from omega_serv.domain.http.request import HttpRequest
from omega_serv.domain.http.response import HttpResponse
from omega_serv.domain.http.status_codes import HttpStatus
from omega_serv.domain.routing.proxy_backend_traffic import BackendTraffic
from omega_serv.domain.routing.proxy_cache_metrics import ProxyCacheMetrics
from omega_serv.domain.routing.proxy_health import ProxyHealthState
from omega_serv.domain.routing.proxy_zone import (
    ProxyLoadBalancerState,
    ProxyZone,
    parse_proxy_zones,
    upstream_key,
)
from omega_serv.domain.security.trusted_proxy import is_internal_route_caller

ADMIN_URL_PREFIX = "/.omega-serv-admin/"

_VALID_MANUAL_STATUSES = ("draining", "maintenance", "clear")


def _json_response(payload: dict, *, status: HttpStatus = HttpStatus.OK) -> HttpResponse:
    response = HttpResponse.empty(status)
    response.set_header("Content-Type", "application/json")
    response.body = json.dumps(payload).encode("utf-8")
    return response


def _find_zone(config: OmegaServConfig, url_prefix: str) -> ProxyZone | None:
    proxy_settings = config.options.get("reverse_proxy")
    if proxy_settings is None or not proxy_settings.enabled:
        return None
    for zone in parse_proxy_zones(proxy_settings.settings.get("zones", [])):
        if zone.url_prefix == url_prefix:
            return zone
    return None


def _handle_health_get(config: OmegaServConfig, proxy_health_state: ProxyHealthState, zone_prefix: str) -> HttpResponse:
    zone = _find_zone(config, zone_prefix)
    if zone is None:
        return HttpResponse.empty(HttpStatus.NOT_FOUND)
    statuses = {upstream_key(u): proxy_health_state.status_for(zone.url_prefix, u) for u in zone.upstreams}
    payload: dict = {"zone": zone.url_prefix, "upstreams": statuses}
    backends = proxy_health_state.backend_statuses(zone.url_prefix)
    if backends is not None:  # lot 6 : zone relayee par le natif - une entree par adresse (nom DNS)
        payload["backends"] = backends
    return _json_response(payload)


def _handle_health_post(
    config: OmegaServConfig, proxy_health_state: ProxyHealthState,
    zone_prefix: str, target_upstream_key: str, new_status: str,
) -> HttpResponse:
    zone = _find_zone(config, zone_prefix)
    if zone is None:
        return HttpResponse.empty(HttpStatus.NOT_FOUND)
    if target_upstream_key not in {upstream_key(u) for u in zone.upstreams}:
        return HttpResponse.empty(HttpStatus.NOT_FOUND)
    if new_status not in _VALID_MANUAL_STATUSES:
        return HttpResponse.empty(HttpStatus.BAD_REQUEST)
    if new_status == "draining":
        proxy_health_state.mark_draining(zone.url_prefix, target_upstream_key)
    elif new_status == "maintenance":
        proxy_health_state.mark_maintenance(zone.url_prefix, target_upstream_key)
    else:
        proxy_health_state.clear_manual_state(zone.url_prefix, target_upstream_key)
    return _json_response({"zone": zone.url_prefix, "upstream": target_upstream_key, "status": new_status})


def backend_traffic_rows(
    config: OmegaServConfig, proxy_health_state: ProxyHealthState, load_balancer: ProxyLoadBalancerState | None,
) -> list[BackendTraffic]:
    """Tableau de bord par type d'instance (2026-11-16) : une ligne par backend de chaque zone de reverse proxy, dans
    l'ordre de la configuration. Zone relayee par le natif : ses mesures (une ligne par adresse) ; zone servie par ce
    processus : ses propres compteurs."""
    proxy_settings = config.options.get("reverse_proxy")
    if proxy_settings is None or not proxy_settings.enabled:
        return []
    rows: list[BackendTraffic] = []
    for zone in parse_proxy_zones(proxy_settings.settings.get("zones", [])):
        relayed = proxy_health_state.relayed_traffic(zone.url_prefix)
        if relayed is not None:
            rows.extend(relayed)
            continue
        for upstream in zone.upstreams:
            key = upstream_key(upstream)
            requests, errors_502, errors_504 = proxy_health_state.traffic_counts(zone.url_prefix, upstream)
            average = load_balancer.response_time_average(zone.url_prefix, upstream) if load_balancer else None
            rows.append(BackendTraffic(
                zone=zone.url_prefix, name=key, address=key, engine="python",
                status=proxy_health_state.status_for(zone.url_prefix, upstream), requests=requests,
                errors_502=errors_502, errors_504=errors_504,
                avg_ms=None if average is None else average * 1000.0,
                active=load_balancer.active_count(zone.url_prefix, upstream) if load_balancer else 0,
            ))
    return rows


def _handle_backends_get(
    config: OmegaServConfig, proxy_health_state: ProxyHealthState, load_balancer: ProxyLoadBalancerState | None,
) -> HttpResponse:
    rows = backend_traffic_rows(config, proxy_health_state, load_balancer)
    return _json_response({"backends": [row.to_dict() for row in rows]})


def _handle_cache_stats_get(proxy_cache_metrics: ProxyCacheMetrics, zone_prefix: str | None) -> HttpResponse:
    hits, misses = proxy_cache_metrics.snapshot(zone_prefix)
    return _json_response({"zone": zone_prefix, "hits": hits, "misses": misses})


def handle_admin_request(
    request: HttpRequest,
    trusted_networks: list[str],
    config: OmegaServConfig,
    proxy_health_state: ProxyHealthState,
    proxy_cache_metrics: ProxyCacheMetrics,
    load_balancer: ProxyLoadBalancerState | None = None,
) -> HttpResponse:
    if not is_internal_route_caller(request.peer_ip, trusted_networks, (name for name, _ in request.headers)):
        return HttpResponse.empty(HttpStatus.FORBIDDEN)  # scan de securite n° 1 : pair de confiance, sans relais

    subpath = request.path[len(ADMIN_URL_PREFIX):].rstrip("/")
    query = {k: v[0] for k, v in parse_qs(request.query).items()}

    if subpath == "health" and request.method == "GET":
        zone_prefix = query.get("zone")
        if not zone_prefix:
            return HttpResponse.empty(HttpStatus.BAD_REQUEST)
        return _handle_health_get(config, proxy_health_state, zone_prefix)

    if subpath == "health" and request.method == "POST":
        zone_prefix = query.get("zone")
        target_upstream_key = query.get("upstream")
        new_status = query.get("status")
        if not zone_prefix or not target_upstream_key or not new_status:
            return HttpResponse.empty(HttpStatus.BAD_REQUEST)
        return _handle_health_post(config, proxy_health_state, zone_prefix, target_upstream_key, new_status)

    if subpath == "backends" and request.method == "GET":
        return _handle_backends_get(config, proxy_health_state, load_balancer)

    if subpath == "cache-stats" and request.method == "GET":
        return _handle_cache_stats_get(proxy_cache_metrics, query.get("zone"))

    return HttpResponse.empty(HttpStatus.NOT_FOUND)
