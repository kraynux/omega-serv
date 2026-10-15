"""Cas d'usage : relayer une requete vers un backend HTTP amont
(reverse proxy sortant, OMEGA-SERV_PLAN-DETAILLE_REVERSE_PROXY.md §2).

Deux points non negociables (meme document, §5) :
- En-tetes "hop-by-hop" (RFC 7230 §6.1) retires dans les DEUX sens -
  un oubli casserait le keep-alive ou fuiterait des details de
  connexion internes.
- X-Forwarded-* toujours ECRASES avec les valeurs entrantes du client,
  jamais fusionnes - sinon un client peut usurper son IP auprès du
  backend (injection d'en-tete classique).

Phase 3 (§5.3/§12) : deux contextes TLS CLIENT construits une seule
fois (jamais par requete) et passes ici en parametres - le contexte
"verified" ou "unverified" est choisi selon `zone.verify_upstream_tls`,
applique seulement quand l'upstream choisi a `use_tls=True`.

`HOP_BY_HOP_HEADERS`/`build_outgoing_headers` sont reutilises tels
quels par `serve_websocket_proxy.py` (phase 4, §4) - SEULE exception :
une requete de mise a niveau WebSocket doit transmettre `Connection`/
`Upgrade` a l'upstream (le seul cas ou ces deux en-tetes ne sont PAS
hop-by-hop, §5.1), via `preserve_upgrade=True`.

Phase 5 (§16/§27.1) : `ProxyLoadBalancerState` remplace
`ProxyRoundRobinState` ici - `acquire`/`release` encadrent l'appel
upstream (connexions actives, utilisees par les strategies
least_connections) et `record_response_time` est toujours appele,
avec une penalite (`zone.read_timeout_seconds`) sur erreur de connexion
plutot qu'aucune mesure - un upstream en panne doit devenir MOINS
attractif pour `least_response_time`, pas rester neutre.

Phase 5bis (§17/§27.2) : `resolve_upstream` implemente l'ordre de
preseance - regle d'en-tete (`resolve_routing_rule_upstream`) > cookie
sticky (`resolve_sticky_upstream`) > strategie active du
`load_balancer` - partagee telle quelle par `serve_websocket_proxy.py`.
Le cookie sticky n'est (re)pose QUE sur une reponse effectivement
obtenue d'un upstream (jamais sur un 502 de connexion - coller un
client a un upstream qui vient d'echouer serait contre-productif) -
et colle au backend qui a REELLEMENT servi (important avec le retry
de la Phase 6 : si le premier choix echoue et qu'un second repond,
le cookie pointe vers le second, jamais vers celui qui a echoue).

Phase 6 (§18.1/§18.3/§18.4) : `resolve_upstream` filtre desormais
CHAQUE etape (regle, cookie, strategie) par `health_state.is_eligible`
- une regle/un cookie qui cible un upstream `DOWN`/`DRAINING`/
`MAINTENANCE` retombe proprement sur l'etape suivante (§27.2), jamais
un choix fige aveuglement. Si TOUS les upstreams sont ineligibles,
repli sur la liste COMPLETE plutot qu'echouer sec (angle mort §18.1,
retenter quand meme le moins pire). `record_failure`/`record_success`
alimentent `ProxyHealthState` a partir des memes evenements deja
observes pour `record_response_time` - controle PASSIF uniquement
(§18.1), le controle ACTIF (§18.2) reste differe (voir docstring de
`domain/routing/proxy_health.py`). Retry automatique (§18.4) : UNE
seule tentative supplementaire, sur un AUTRE upstream eligible,
UNIQUEMENT si la premiere tentative a echoue AVANT tout octet de
reponse (`HttpProxyConnectionError`) ET que la methode est idempotente
(GET/HEAD/OPTIONS) - jamais sur POST/PUT/DELETE (risquerait de
dupliquer une action reelle cote backend si la premiere tentative
avait en fait reussi mais que seule la reponse s'est perdue).

Phase 7 (§19) : `resolve_upstream` transmet desormais `health_state` a
`load_balancer.select()` - consulte UNIQUEMENT par la strategie
"real_load" (score de charge reelle, alimente par la tache de fond
`application/server/poll_upstream_load.py`, jamais par ce module
lui-meme).

Phase 7bis (§20) : `AllUpstreamsAtCapacityError` distingue EXPLICITEMENT
la saturation deliberee (backpressure, `max_concurrent_requests`) de la
panne (`DOWN`, §18.1) - les deux se "ressemblent" (plus aucun upstream
utilisable) mais appellent une reponse OPPOSEE : un upstream mort,
retenter quand meme le moins pire (comportement deja etabli) ; un
upstream SATURE par construction (plafond deliberement fixe par
l'operateur), refuser proprement (503) plutot que de se mentir en
depassant la limite en silence - jamais le meme code de statut que
"tous DOWN" (502), qui suggererait a tort une panne.

Phase 8 (§21) : `serve_proxy` encadre desormais la logique de relai
(renommee `_serve_proxy_uncached`) d'une couche de cache - lookup AVANT
tout choix d'upstream (un hit ne doit JAMAIS compter comme une
connexion active ni influencer une strategie quelconque, §27.4/§30.2),
verrou anti-stampede (`ProxyCacheLocks`) autour de la reconstitution sur
MISS. Les regles non negociables (methode, statut, `Set-Cookie`) et le
"respect" optionnel de `Cache-Control` amont vivent dans `domain/
routing/proxy_cache.py` - jamais dans ce module, qui ne fait
qu'orchestrer. `X-Omega-Cache: HIT`/`MISS`/`BYPASS` toujours pose.

Garde-fou anti-boucle indirecte entre instances (§23 angle mort #16,
§29.9) : la boucle DIRECTE (un upstream pointant vers cette meme
instance) est deja bloquee a la validation de config
(`domain/config/validation.py`) - structurellement incapable de
detecter la boucle INDIRECTE (instance A proxie vers B, B proxie vers
A, ou une chaine plus longue), chaque instance n'ayant acces qu'a son
propre fichier de configuration. Meme principe que `Max-Forwards` en
HTTP standard : `PROXY_HOPS_HEADER` est incremente a CHAQUE relai (y
compris pour le WebSocket, `serve_websocket_proxy.py` reutilise
`incoming_proxy_hop_count`), refuse en 502 (jamais une boucle infinie)
au-dela de `MAX_PROXY_HOPS` - verifie AVANT toute selection d'upstream
(jamais un cycle de connexion inutile a une sonde de charge ou un
backend deja sature)."""
from __future__ import annotations

import time
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    import ssl

    from omega_serv.application.server.proxy_cache_locks import ProxyCacheLocks
    from omega_serv.domain.routing.proxy_cache_metrics import ProxyCacheMetrics
    from omega_serv.ports.proxy_cache_store_port import ProxyCacheStorePort

from omega_serv.domain.http.cookies import build_set_cookie_header, parse_cookie_header
from omega_serv.domain.http.request import HttpRequest
from omega_serv.domain.http.response import HttpResponse
from omega_serv.domain.http.status_codes import HttpStatus
from omega_serv.domain.routing.proxy_cache import (
    ProxyCacheEntry,
    entry_matches_request,
    is_cacheable_request,
    is_cacheable_response,
    is_expired,
    parse_vary_header,
    primary_cache_key,
    resolve_cache_ttl_seconds,
    variant_cache_key,
)
from omega_serv.domain.routing.proxy_health import ProxyHealthState
from omega_serv.domain.routing.proxy_zone import (
    ProxyLoadBalancerState,
    ProxyZone,
    UpstreamTarget,
    resolve_routing_rule_upstream,
    resolve_sticky_upstream,
    sticky_cookie_value_for,
    upstream_key,
)
from omega_serv.ports.http_proxy_client_port import (
    HttpProxyClientPort,
    HttpProxyConnectionError,
    HttpProxyResult,
)

_IDEMPOTENT_RETRY_METHODS = frozenset({"GET", "HEAD", "OPTIONS"})


class AllUpstreamsAtCapacityError(Exception):
    """Levee par `resolve_upstream` quand tous les upstreams SAINS
    (§18) de la zone sont au plafond de backpressure (§20) - jamais une
    tentative silencieuse qui depasserait la limite deliberement fixee
    par l'operateur, contrairement au cas "tous DOWN" (§18.1, retenter
    quand meme). L'appelant (`serve_proxy`/`serve_websocket_proxy`) la
    traduit en 503 - jamais un 502 qui suggererait a tort une panne."""

HOP_BY_HOP_HEADERS = frozenset({
    "connection", "keep-alive", "proxy-authenticate", "proxy-authorization",
    "te", "trailers", "transfer-encoding", "upgrade",
})

PROXY_HOPS_HEADER = "X-Omega-Proxy-Hops"
MAX_PROXY_HOPS = 5
"""Seuil du garde-fou anti-boucle indirecte (§23 angle mort #16) - meme
principe que `Max-Forwards` en HTTP standard, pas une valeur
configurable (une boucle reelle merite d'etre corrigee a la source,
jamais contournee en augmentant le seuil)."""


def incoming_proxy_hop_count(request: HttpRequest) -> int:
    """Nombre de relais OMEGA-SERV deja traverses par cette requete,
    0 si l'en-tete est absent ou invalide (jamais une erreur - une
    requete directe d'un client normal n'a simplement jamais traverse
    de relai). Reutilise par `serve_websocket_proxy.py` (meme garde-fou
    pour les deux chemins de code)."""
    raw = request.header(PROXY_HOPS_HEADER)
    if raw is None:
        return 0
    try:
        return max(0, int(raw.strip()))
    except ValueError:
        return 0


def build_outgoing_headers(
    request: HttpRequest, zone: ProxyZone, upstream: UpstreamTarget, *, preserve_upgrade: bool = False,
) -> tuple[tuple[str, str], ...]:
    hop_by_hop = HOP_BY_HOP_HEADERS - {"connection", "upgrade"} if preserve_upgrade else HOP_BY_HOP_HEADERS
    original_host = request.header("host")
    headers = [
        (name, value) for name, value in request.headers
        if name not in hop_by_hop
        and name not in ("host", "x-forwarded-for", "x-forwarded-proto", "x-forwarded-host", PROXY_HOPS_HEADER.lower())
    ]
    headers.append(("Host", original_host if zone.preserve_host_header and original_host else f"{upstream.host}:{upstream.port}"))
    headers.append(("X-Forwarded-For", request.remote_ip))
    headers.append(("X-Forwarded-Proto", "https" if request.is_tls else "http"))
    if original_host:
        headers.append(("X-Forwarded-Host", original_host))
    headers.append((PROXY_HOPS_HEADER, str(incoming_proxy_hop_count(request) + 1)))
    return tuple(headers)


def resolve_upstream(
    request: HttpRequest, zone: ProxyZone, load_balancer: ProxyLoadBalancerState, health_state: ProxyHealthState,
    *, exclude: frozenset[str] = frozenset(),
) -> UpstreamTarget:
    """Ordre de preseance fixe (§27.2) : regle d'en-tete > cookie
    sticky > strategie active - partagee par `serve_websocket_proxy.py`
    (§27.3 : le choix initial d'un upgrade WebSocket suit exactement la
    meme regle qu'une requete HTTP ordinaire). Chaque etape est filtree
    par eligibilite (`health_state.is_eligible`, §27.2 etape 3) ET par
    capacite (`load_balancer.is_at_capacity`, §20) - une regle/un cookie
    qui cible un upstream ineligible OU sature retombe sur l'etape
    suivante plutot que d'etre honore aveuglement. `exclude` (identites
    stables deja tentees) sert uniquement au retry (§18.4) - vide sur
    le premier choix.

    Leve `AllUpstreamsAtCapacityError` si au moins un upstream est SAIN
    mais qu'AUCUN sain n'a de capacite disponible (§20) - distinct du
    cas "tous DOWN" (§18.1), qui retombe au contraire sur la liste
    complete pour retenter quand meme."""
    zone_key = zone.url_prefix

    def usable(upstream: UpstreamTarget) -> bool:
        return (
            upstream_key(upstream) not in exclude
            and health_state.is_eligible(zone_key, upstream)
            and not load_balancer.is_at_capacity(zone_key, upstream)
        )

    rule_upstream = resolve_routing_rule_upstream(zone, request.header)
    if rule_upstream is not None and usable(rule_upstream):
        return rule_upstream
    if zone.sticky_session_enabled:
        cookies = parse_cookie_header(request.header("cookie"))
        cookie_value = cookies.get(zone.sticky_cookie_name)
        if cookie_value is not None:
            sticky_upstream = resolve_sticky_upstream(zone, cookie_value)
            if sticky_upstream is not None and usable(sticky_upstream):
                return sticky_upstream

    remaining = [u for u in zone.upstreams if upstream_key(u) not in exclude]
    healthy = [u for u in remaining if health_state.is_eligible(zone_key, u)]
    if not healthy:
        # §18.1 : rien de sain - retenter quand meme le moins pire plutot que refuser.
        return load_balancer.select(zone, request.remote_ip, upstreams=tuple(remaining), health_state=health_state)
    has_capacity = [u for u in healthy if not load_balancer.is_at_capacity(zone_key, u)]
    if not has_capacity:
        # §20 : capacite DELIBEREMENT fixee - jamais depassee en silence, refus explicite.
        raise AllUpstreamsAtCapacityError(zone_key)
    return load_balancer.select(zone, request.remote_ip, upstreams=tuple(has_capacity), health_state=health_state)


async def _attempt_forward(
    request: HttpRequest,
    zone: ProxyZone,
    upstream: UpstreamTarget,
    proxy_client: HttpProxyClientPort,
    load_balancer: ProxyLoadBalancerState,
    health_state: ProxyHealthState,
    client_ssl_context_verified: ssl.SSLContext | None,
    client_ssl_context_unverified: ssl.SSLContext | None,
) -> HttpProxyResult | None:
    """Une tentative vers UN upstream deja choisi - retourne le
    `HttpProxyResult` sur succes, `None` sur erreur de connexion (deja
    enregistree aupres de `load_balancer`/`health_state` dans les deux
    cas, succes comme echec)."""
    zone_key = zone.url_prefix
    target = request.path + (f"?{request.query}" if request.query else "")
    outgoing_headers = build_outgoing_headers(request, zone, upstream)

    ssl_context = None
    if upstream.use_tls:
        ssl_context = client_ssl_context_verified if zone.verify_upstream_tls else client_ssl_context_unverified

    load_balancer.acquire(zone_key, upstream)
    started_at = time.monotonic()
    try:
        try:
            result = await proxy_client.forward_request(
                upstream.host, upstream.port, request.method, target,
                outgoing_headers, request.body or b"", zone.connect_timeout_seconds, zone.read_timeout_seconds,
                ssl_context,
            )
        except HttpProxyConnectionError:
            load_balancer.record_response_time(zone_key, upstream, zone.read_timeout_seconds)
            health_state.record_failure(zone_key, upstream, unhealthy_after=zone.unhealthy_after)
            return None
        load_balancer.record_response_time(zone_key, upstream, time.monotonic() - started_at)
        health_state.record_success(zone_key, upstream, healthy_after=zone.healthy_after)
        return result
    finally:
        load_balancer.release(zone_key, upstream)


async def _serve_proxy_uncached(
    request: HttpRequest,
    zone: ProxyZone,
    proxy_client: HttpProxyClientPort,
    load_balancer: ProxyLoadBalancerState,
    health_state: ProxyHealthState,
    client_ssl_context_verified: ssl.SSLContext | None,
    client_ssl_context_unverified: ssl.SSLContext | None,
) -> HttpResponse:
    if incoming_proxy_hop_count(request) >= MAX_PROXY_HOPS:
        # Boucle indirecte entre instances (§23 angle mort #16) - refus AVANT toute
        # selection d'upstream, jamais une tentative de connexion supplementaire inutile.
        return HttpResponse.empty(HttpStatus.BAD_GATEWAY)
    try:
        upstream = resolve_upstream(request, zone, load_balancer, health_state)
    except AllUpstreamsAtCapacityError:
        return HttpResponse.empty(HttpStatus.SERVICE_UNAVAILABLE)
    result = await _attempt_forward(
        request, zone, upstream, proxy_client, load_balancer, health_state,
        client_ssl_context_verified, client_ssl_context_unverified,
    )

    if result is None and request.method in _IDEMPOTENT_RETRY_METHODS and len(zone.upstreams) > 1:
        # `exclude` garantit un upstream different de celui qui vient d'echouer (len(zone.upstreams) > 1).
        try:
            retry_upstream = resolve_upstream(
                request, zone, load_balancer, health_state, exclude=frozenset({upstream_key(upstream)}),
            )
        except AllUpstreamsAtCapacityError:
            retry_upstream = None
        if retry_upstream is not None:
            result = await _attempt_forward(
                request, zone, retry_upstream, proxy_client, load_balancer, health_state,
                client_ssl_context_verified, client_ssl_context_unverified,
            )
            if result is not None:
                upstream = retry_upstream

    if result is None:
        return HttpResponse.empty(HttpStatus.BAD_GATEWAY)

    response = HttpResponse.empty(result.status_code)
    for name, value in result.headers:
        if name.lower() not in HOP_BY_HOP_HEADERS:
            response.set_header(name, value)
    response.body = result.body
    if zone.sticky_session_enabled:
        response.set_header("Set-Cookie", build_set_cookie_header(
            zone.sticky_cookie_name, sticky_cookie_value_for(upstream),
            max_age_seconds=zone.sticky_cookie_max_age_seconds,
        ))
    return response


def _cache_entry_to_response(entry: ProxyCacheEntry) -> HttpResponse:
    response = HttpResponse.empty(entry.status_code)
    for name, value in entry.headers:
        response.set_header(name, value)
    response.body = entry.body
    return response


async def serve_proxy(
    request: HttpRequest,
    zone: ProxyZone,
    proxy_client: HttpProxyClientPort,
    load_balancer: ProxyLoadBalancerState,
    health_state: ProxyHealthState,
    client_ssl_context_verified: ssl.SSLContext | None = None,
    client_ssl_context_unverified: ssl.SSLContext | None = None,
    cache_store: ProxyCacheStorePort | None = None,
    cache_locks: ProxyCacheLocks | None = None,
    cache_metrics: ProxyCacheMetrics | None = None,
) -> HttpResponse:
    if not zone.cache_enabled or cache_store is None or cache_locks is None or not is_cacheable_request(request.method):
        response = await _serve_proxy_uncached(
            request, zone, proxy_client, load_balancer, health_state,
            client_ssl_context_verified, client_ssl_context_unverified,
        )
        response.set_header("X-Omega-Cache", "BYPASS")
        return response

    zone_key = zone.url_prefix
    primary_key = primary_cache_key(request.method, request.header("host") or "", request.path, request.query)

    def lookup() -> ProxyCacheEntry | None:
        now = time.time()
        for variant in cache_store.get_variants(zone_key, primary_key):
            if not is_expired(variant, now=now) and entry_matches_request(variant, request.header):
                return variant
        return None

    cached = lookup()
    if cached is not None:
        if cache_metrics is not None:
            cache_metrics.record_hit(zone_key)
        response = _cache_entry_to_response(cached)
        response.set_header("X-Omega-Cache", "HIT")
        return response

    # Verrou sur la cle PRIMAIRE (pas la variante, encore inconnue avant la reponse
    # amont) - §21 anti-stampede : deux requetes concurrentes pour des variantes
    # DIFFERENTES de la meme ressource se serialisent donc l'une l'autre, compromis
    # mineur delibere plutot qu'un verrou par variante (complexite non justifiee).
    async with cache_locks.get_lock(zone_key, primary_key):
        # Re-verification apres acquisition du verrou (§21, anti-stampede) : une autre
        # coroutine a peut-etre deja reconstitue l'entree pendant l'attente du verrou.
        cached = lookup()
        if cached is not None:
            if cache_metrics is not None:
                cache_metrics.record_hit(zone_key)
            response = _cache_entry_to_response(cached)
            response.set_header("X-Omega-Cache", "HIT")
            return response

        response = await _serve_proxy_uncached(
            request, zone, proxy_client, load_balancer, health_state,
            client_ssl_context_verified, client_ssl_context_unverified,
        )
        headers_tuple = tuple(response.headers.items())
        if is_cacheable_response(response.status, headers_tuple, allow_set_cookie=zone.cache_allow_set_cookie):
            ttl_seconds = resolve_cache_ttl_seconds(
                headers_tuple, respect_upstream_headers=zone.cache_respect_upstream_headers,
                default_ttl_seconds=zone.cache_default_ttl_seconds,
            )
            if ttl_seconds is not None:
                vary_raw = next((v for n, v in headers_tuple if n.lower() == "vary"), None)
                vary_names = parse_vary_header(vary_raw)
                vary_values = tuple(request.header(name) or "" for name in vary_names)
                entry = ProxyCacheEntry(
                    status_code=response.status, headers=headers_tuple, body=response.body,
                    stored_at=time.time(), ttl_seconds=ttl_seconds,
                    vary_header_names=vary_names, vary_header_values=vary_values,
                )
                cache_store.set(zone_key, variant_cache_key(primary_key, vary_names, vary_values), entry)
        if cache_metrics is not None:
            cache_metrics.record_miss(zone_key)
        response.set_header("X-Omega-Cache", "MISS")
        return response
