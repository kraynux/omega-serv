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
le meme mecanisme de repartition que le relai HTTP ordinaire, mais plus
aucune bascule possible ensuite - contrairement au relai HTTP ordinaire
qui peut choisir un upstream different a CHAQUE requete).

Phase 5 (strategies de repartition, OMEGA-SERV_PLAN-DETAILLE_
REVERSE_PROXY.md §16/§27.1) : `ProxyZone.load_balancing` et
`UpstreamTarget.weight` sont des champs NOUVEAUX a cette phase (le
document de conception supposait a tort qu'ils existaient depuis la
Phase 1 - corrige ici). `ProxyLoadBalancerState` REMPLACE
`ProxyRoundRobinState` (supprimee) comme etat injecte dans
`serve_proxy()`/`serve_websocket_proxy()` - PARTOUT ou ces deux
fonctions sont appelees, y compris pour les zones leurres de l'Active
Defense (`_serve_decoy_proxy`, meme fonction `serve_proxy()` partagee) :
une zone leurre reste un `ProxyZone` ordinaire avec `load_balancing`
par defaut ("round_robin", jamais configure autrement cote TUI pour un
leurre - comportement inchange pour ce cas). TOUT l'etat interne de
`ProxyLoadBalancerState` est cle par identite STABLE d'upstream
(`host:port` via `upstream_key()`), jamais par position dans le tuple
`upstreams` : un upstream ajoute/retire/reordonne via le TUI ne doit
jamais heriter l'historique (connexions actives, temps de reponse
moyen, tour de round-robin pondere) d'un autre upstream qui occupait la
meme position avant lui (§27.1, le risque le plus important identifie
par l'etude).

Phase 5bis (affinite de session + routage conditionnel, §17/§27.2/§27.3) :
`ProxyZone.sticky_session_enabled`/`sticky_cookie_name`/
`sticky_cookie_max_age_seconds` et `ProxyZone.routing_rules` sont
NOUVEAUX. Ordre de preseance fixe (§27.2, implemente dans
`application/server/serve_proxy.py::_resolve_upstream`, PAS ici) :
regle d'en-tete > cookie sticky > strategie active du `pick()` normal.
Valeur du cookie sticky = `sticky_cookie_value_for(upstream)`, un hash
a sens unique de l'identite stable (`host:port`) - JAMAIS l'host:port
en clair (fuite de topologie interne, §17) - ni une valeur signee par
cle secrete (aucune infrastructure de signature de cookie n'existe
ailleurs dans le projet, verifie avant d'ecrire ce module ; un cookie
falsifie ne correspond simplement a aucun upstream connu et retombe
silencieusement sur la strategie active, jamais une faille de
securite). Filtrage d'eligibilite (DOWN/MAINTENANCE/backpressure,
etape 3 du §27.2) PAS ENCORE APPLIQUE a la regle d'en-tete/au cookie
sticky : la Phase 6 n'existe pas encore, aucun etat de sante a
consulter - a corriger explicitement quand `ProxyHealthState`
existera (angle mort documente, pas oublie).

Phase 6 (sante et etats operationnels, §18) : `ProxyHealthState`
(domain/routing/proxy_health.py, module separe - concern distinct du
choix de charge) referme cet angle mort - `application/server/
serve_proxy.py::resolve_upstream` filtre desormais regle/cookie/
strategie par eligibilite (`is_eligible`). `ProxyZone.unhealthy_after`/
`healthy_after` sont NOUVEAUX. Controle ACTIF (§18.2) et backpressure
(§20, Phase 7bis) restent differes - cf. docstring de `proxy_health.py`."""
from __future__ import annotations

import hashlib
import time
import zlib
from collections.abc import Callable
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

from omega_serv.core.i18n import _
from omega_serv.domain.routing.zone_resolver import Zone, resolve_zone

if TYPE_CHECKING:
    from omega_serv.domain.routing.proxy_health import ProxyHealthState

PROXY_LOAD_BALANCING_STRATEGIES = (
    "round_robin",
    "weighted_round_robin",
    "least_connections",
    "weighted_least_connections",
    "ip_hash",
    "least_response_time",
    "real_load",
)
"""Valeurs admises pour `ProxyZone.load_balancing` (§16 du document de
conception) - aucune execution de script (Lua/JS/Python) pour la
selection, rejetee explicitement lors de l'etude (YAGNI, §17).
"real_load" (Phase 7, §19) necessite au moins un upstream avec
`load_source != "none"` pour produire un score - repli automatique sur
least-connections pour les upstreams sans score valide (§19.2)."""

_VALID_LOAD_SOURCES = ("none", "native", "declarative")


@dataclass(frozen=True)
class UpstreamTarget:
    host: str
    port: int
    use_tls: bool = False
    weight: int = 1
    """Poids statique (`weighted_round_robin`/`weighted_least_connections`
    et pondere aussi `ip_hash`, §16.1) - sans effet sur les autres
    strategies. Toujours >= 1 (valide par `validate_proxy_zone`)."""
    load_source: str = "none"
    """"none" (par defaut, aucun polling de charge), "native" (backend
    OMEGA-SERV, interroge `/.omega-serv-load/` - §19.1) ou "declarative"
    (backend heterogene, interroge `load_check_path` - §19.2). Granularite
    PAR UPSTREAM, jamais par zone (§19.3) - une meme zone peut melanger
    un backend natif et un backend declaratif."""
    load_check_path: str = "/"
    """Chemin interroge en mode "declarative" uniquement (§19.2) - sans
    effet pour "none"/"native" (le natif utilise toujours le chemin
    reserve fixe `/.omega-serv-load/`, jamais configurable)."""
    max_concurrent_requests: int | None = None
    """Plafond de backpressure (Phase 7bis, §20) - `None` (defaut) =
    illimite, jamais une limite imposee sans configuration explicite.
    Au-dela, cet upstream est temporairement exclu des NOUVEAUX choix
    (meme mecanisme d'exclusion que `DOWN`, mais pour une raison
    DIFFERENTE - saturation deliberee, pas une panne) jusqu'a ce qu'une
    connexion se libere."""
    active_health_check_enabled: bool = False
    """Controle ACTIF (§18.2, differe depuis la Phase 6, ferme a la
    reouverture du §23 angle mort) - sonde PERIODIQUE independante du
    trafic reel, `False` par defaut (jamais une requete supplementaire
    non demandee). Reutilise LE MEME mecanisme de tache de fond que le
    polling de charge (`poll_upstream_load.py`) - sans effet sur le
    score de charge (reste `load_source`, independant) : un upstream
    peut activer l'un, l'autre, les deux, ou aucun."""
    active_health_check_path: str = "/"
    """Chemin interroge par la sonde active - sans effet si
    `active_health_check_enabled=False`. Distinct de `load_check_path`
    (qui ne sert qu'au mode "declarative" de la charge) meme si les deux
    peuvent pointer vers le meme chemin sur un backend qui expose une
    seule route de sonde generique."""


def upstream_key(upstream: UpstreamTarget) -> str:
    """Identite STABLE d'un upstream (`host:port`) - cle de tout l'etat
    de repartition de charge (§27.1), jamais la position dans le tuple
    `ProxyZone.upstreams`."""
    return f"{upstream.host}:{upstream.port}"


def sticky_cookie_value_for(upstream: UpstreamTarget) -> str:
    """Valeur opaque posee dans le cookie sticky (§17) - hash a sens
    unique de l'identite stable, jamais l'host:port en clair. Pas une
    signature cryptographique (pas de cle secrete a gerer/faire
    tourner) : un cookie falsifie ne correspond simplement a aucun
    upstream de la zone courante (`resolve_sticky_upstream` retourne
    None) et la requete retombe sur la strategie active - jamais une
    faille de securite, seulement une perte de l'affinite de session."""
    return hashlib.sha256(upstream_key(upstream).encode("utf-8")).hexdigest()[:16]


@dataclass(frozen=True)
class RoutingRule:
    header_name: str
    pattern: str
    upstream_key: str
    """Identite stable (`host:port`) de l'upstream cible - JAMAIS une
    position dans `ProxyZone.upstreams` (§16.1/§27.1). Doit correspondre
    a un upstream reellement present dans la zone (verifie par
    `validate_proxy_zone`)."""


def _header_value_matches(value: str, pattern: str) -> bool:
    """Motif SIMPLE (§17, jamais une expression reguliere complete) :
    egalite exacte, ou - si `pattern` se termine par "*" - correspondance
    de PREFIXE (le "*" final est retire avant comparaison)."""
    if pattern.endswith("*"):
        return value.startswith(pattern[:-1])
    return value == pattern


def resolve_routing_rule_upstream(
    zone: ProxyZone, header_lookup: Callable[[str], str | None],
) -> UpstreamTarget | None:
    """Premiere regle (dans l'ordre declare) dont l'en-tete correspond
    ET dont l'upstream cible existe encore dans la zone - None sinon
    (retombe sur le cookie sticky puis la strategie active, §27.2).
    `header_lookup` plutot qu'un `HttpRequest`/`HttpHeaders` direct :
    garde ce module (domain/routing) independant de domain/http, la
    couche appelante (application/server/serve_proxy.py) fournit
    simplement `request.header`."""
    for rule in zone.routing_rules:
        value = header_lookup(rule.header_name)
        if value is None or not _header_value_matches(value, rule.pattern):
            continue
        for upstream in zone.upstreams:
            if upstream_key(upstream) == rule.upstream_key:
                return upstream
    return None


def resolve_sticky_upstream(zone: ProxyZone, cookie_value: str) -> UpstreamTarget | None:
    """None si `cookie_value` ne correspond a aucun upstream ACTUEL de
    la zone (upstream retire depuis, ou cookie invalide/falsifie) -
    l'appelant retombe alors sur la strategie active plutot que
    d'echouer (§17)."""
    for upstream in zone.upstreams:
        if sticky_cookie_value_for(upstream) == cookie_value:
            return upstream
    return None


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
    load_balancing: str = "round_robin"
    """Strategie de repartition parmi `PROXY_LOAD_BALANCING_STRATEGIES`
    (§16). Sans effet si un seul upstream est declare."""
    sticky_session_enabled: bool = False
    """Affinite de session par cookie (§17) - pose `sticky_cookie_name`
    dans la reponse, honore au choix d'upstream des requetes suivantes
    du meme client tant que l'upstream cible existe toujours dans la
    zone."""
    sticky_cookie_name: str = "omega_proxy_sticky"
    sticky_cookie_max_age_seconds: int = 7200
    routing_rules: tuple[RoutingRule, ...] = ()
    """Regles de routage conditionnel sur en-tete (§17), evaluees AVANT
    le cookie sticky et la strategie active (§27.2) - jamais de scripting
    embarque (Lua/JS/Python), motif simple uniquement (`_header_value_
    matches`)."""
    unhealthy_after: int = 3
    """"fall" (§18.3) : nombre d'echecs CONSECUTIFS (erreur de connexion
    deja observee par serve_proxy()/serve_websocket_proxy(), controle
    PASSIF uniquement a ce stade) avant de marquer un upstream `DOWN`."""
    healthy_after: int = 2
    """"rise" (§18.3) : nombre de succes CONSECUTIFS avant de sortir
    pleinement de `DOWN` - distinct de `unhealthy_after` pour reduire le
    risque de flapping (un seul succes isole ne suffit plus)."""
    load_poll_interval_seconds: float = 10.0
    """Periode entre deux sondes de charge (§19.1) - sans effet si aucun
    upstream de la zone n'a `load_source != "none"`."""
    load_poll_timeout_seconds: float = 1.0
    """Timeout COURT et dedie de la sonde de charge (§19.1, discipline
    asyncio ajoutee lors de la relecture du 2026-10-14) - bien en-deca de
    `read_timeout_seconds` du trafic reel, jamais une attente bloquante."""
    load_smoothing_samples: int = 3
    """Nombre d'echantillons sur lesquels lisser le score de charge par
    moyenne glissante (§19.4) - attenue le flapping de decision (distinct
    du flapping de sante, §18.3) sans masquer une degradation reelle et
    durable."""
    load_sample_max_age_seconds: float = 60.0
    """Au-dela de cet age, le dernier echantillon de charge est considere
    PERIME (§19.5, distinct d'un upstream mort - §18) - repli sur
    least-connections pour cet upstream precis, sans affecter les autres
    upstreams de la zone dont l'echantillon reste frais."""
    cache_enabled: bool = False
    """Cache des reponses proxiees (Phase 8, §21) - desactive par defaut.
    A NE JAMAIS CONFONDRE avec la politique `Cache-Control` existante
    (`domain/routing/cache_policy.py`, en-tete sortant pour le fallback
    fichier statique) - deux mecanismes distincts, voir docstring de
    `domain/routing/proxy_cache.py`."""
    cache_default_ttl_seconds: float = 60.0
    """Utilise seulement si le backend ne pose aucun `Cache-Control`
    exploitable (ou si `cache_respect_upstream_headers=False`)."""
    cache_respect_upstream_headers: bool = True
    """Si `False`, ignore `Cache-Control` (`no-store`/`no-cache`/
    `private`/`max-age`) et met TOUJOURS en cache selon `cache_default_
    ttl_seconds` - raccourci EXPLICITEMENT DANGEREUX (meme philosophie
    que `verify_upstream_tls=False`, §5.3), jamais le defaut."""
    cache_allow_set_cookie: bool = False
    """Si `False` (defaut), une reponse portant `Set-Cookie` n'est
    JAMAIS mise en cache, quoi que disent les autres options - lever
    cette garde (`True`) risque de resservir le cookie d'un client a un
    autre, option separee et desactivee par defaut, documentee comme
    risquee (§21)."""


def parse_proxy_zones(raw_list: list[dict[str, Any]]) -> list[ProxyZone]:
    return [
        ProxyZone(
            url_prefix=item["url_prefix"],
            upstreams=tuple(
                UpstreamTarget(
                    host=u.get("host", ""), port=int(u.get("port", 0)), use_tls=bool(u.get("use_tls", False)),
                    weight=int(u.get("weight", 1)), load_source=str(u.get("load_source", "none")),
                    load_check_path=str(u.get("load_check_path", "/")),
                    max_concurrent_requests=(
                        int(u["max_concurrent_requests"]) if u.get("max_concurrent_requests") is not None else None
                    ),
                    active_health_check_enabled=bool(u.get("active_health_check_enabled", False)),
                    active_health_check_path=str(u.get("active_health_check_path", "/")),
                )
                for u in item.get("upstreams", [])
            ),
            connect_timeout_seconds=float(item.get("connect_timeout_seconds", 5.0)),
            read_timeout_seconds=float(item.get("read_timeout_seconds", 30.0)),
            preserve_host_header=bool(item.get("preserve_host_header", False)),
            verify_upstream_tls=bool(item.get("verify_upstream_tls", True)),
            websocket_enabled=bool(item.get("websocket_enabled", False)),
            load_balancing=str(item.get("load_balancing", "round_robin")),
            sticky_session_enabled=bool(item.get("sticky_session_enabled", False)),
            sticky_cookie_name=str(item.get("sticky_cookie_name", "omega_proxy_sticky")),
            sticky_cookie_max_age_seconds=int(item.get("sticky_cookie_max_age_seconds", 7200)),
            routing_rules=tuple(
                RoutingRule(
                    header_name=r.get("header_name", ""), pattern=r.get("pattern", ""),
                    upstream_key=r.get("upstream_key", ""),
                )
                for r in item.get("routing_rules", [])
            ),
            unhealthy_after=int(item.get("unhealthy_after", 3)),
            healthy_after=int(item.get("healthy_after", 2)),
            load_poll_interval_seconds=float(item.get("load_poll_interval_seconds", 10.0)),
            load_poll_timeout_seconds=float(item.get("load_poll_timeout_seconds", 1.0)),
            load_smoothing_samples=int(item.get("load_smoothing_samples", 3)),
            load_sample_max_age_seconds=float(item.get("load_sample_max_age_seconds", 60.0)),
            cache_enabled=bool(item.get("cache_enabled", False)),
            cache_default_ttl_seconds=float(item.get("cache_default_ttl_seconds", 60.0)),
            cache_respect_upstream_headers=bool(item.get("cache_respect_upstream_headers", True)),
            cache_allow_set_cookie=bool(item.get("cache_allow_set_cookie", False)),
        )
        for item in raw_list
    ]


def validate_proxy_zone(zone: ProxyZone) -> str | None:
    if not zone.url_prefix.startswith("/"):
        return _("url_prefix doit commencer par '/' : {url_prefix!r}").format(url_prefix=zone.url_prefix)
    if not zone.upstreams:
        return _("au moins un upstream est requis (zone {url_prefix!r})").format(url_prefix=zone.url_prefix)
    for upstream in zone.upstreams:
        if not upstream.host:
            return _("host d'upstream vide (zone {url_prefix!r})").format(url_prefix=zone.url_prefix)
        if not (1 <= upstream.port <= 65535):
            return _("port d'upstream invalide : {port!r} (zone {url_prefix!r})").format(port=upstream.port, url_prefix=zone.url_prefix)
        if upstream.weight < 1:
            return _("weight d'upstream invalide : {weight!r} (zone {url_prefix!r}, doit être >= 1)").format(weight=upstream.weight, url_prefix=zone.url_prefix)
        if upstream.load_source not in _VALID_LOAD_SOURCES:
            return (
                _("load_source invalide : {load_source!r} (zone {url_prefix!r}, attendu l'un de {VALID_LOAD_SOURCES})").format(load_source=upstream.load_source, url_prefix=zone.url_prefix, VALID_LOAD_SOURCES=_VALID_LOAD_SOURCES)
            )
        if upstream.load_source == "declarative" and not upstream.load_check_path.startswith("/"):
            return _("load_check_path doit commencer par '/' : {load_check_path!r} (zone {url_prefix!r})").format(load_check_path=upstream.load_check_path, url_prefix=zone.url_prefix)
        if upstream.active_health_check_enabled and not upstream.active_health_check_path.startswith("/"):
            return (
                _("active_health_check_path doit commencer par '/' : {active_health_check_path!r} (zone {url_prefix!r})").format(active_health_check_path=upstream.active_health_check_path, url_prefix=zone.url_prefix)
            )
        if upstream.max_concurrent_requests is not None and upstream.max_concurrent_requests < 1:
            return (
                _("max_concurrent_requests invalide : {max_concurrent_requests!r} (zone {url_prefix!r}, doit être >= 1 ou absent/null pour illimité)").format(max_concurrent_requests=upstream.max_concurrent_requests, url_prefix=zone.url_prefix)
            )
    if zone.connect_timeout_seconds <= 0:
        return _("connect_timeout_seconds doit être strictement positif (zone {url_prefix!r})").format(url_prefix=zone.url_prefix)
    if zone.read_timeout_seconds <= 0:
        return _("read_timeout_seconds doit être strictement positif (zone {url_prefix!r})").format(url_prefix=zone.url_prefix)
    if zone.load_balancing not in PROXY_LOAD_BALANCING_STRATEGIES:
        return (
            _("load_balancing invalide : {load_balancing!r} (zone {url_prefix!r}, attendu l'un de {value})").format(load_balancing=zone.load_balancing, url_prefix=zone.url_prefix, value=', '.join(PROXY_LOAD_BALANCING_STRATEGIES))
        )
    if zone.sticky_session_enabled:
        if not zone.sticky_cookie_name.strip():
            return _("sticky_cookie_name ne peut pas être vide quand sticky_session_enabled=true (zone {url_prefix!r})").format(url_prefix=zone.url_prefix)
        if zone.sticky_cookie_max_age_seconds <= 0:
            return _("sticky_cookie_max_age_seconds doit être strictement positif (zone {url_prefix!r})").format(url_prefix=zone.url_prefix)
    known_upstream_keys = {upstream_key(u) for u in zone.upstreams}
    for rule in zone.routing_rules:
        if not rule.header_name.strip():
            return _("header_name ne peut pas être vide (règle de routage, zone {url_prefix!r})").format(url_prefix=zone.url_prefix)
        if not rule.pattern:
            return _("pattern ne peut pas être vide (règle de routage, zone {url_prefix!r})").format(url_prefix=zone.url_prefix)
        if rule.upstream_key not in known_upstream_keys:
            return (
                _("upstream_key {upstream_key!r} inconnu dans cette zone (règle de routage, zone {url_prefix!r}, upstreams connus : {value})").format(upstream_key=rule.upstream_key, url_prefix=zone.url_prefix, value=sorted(known_upstream_keys))
            )
    if zone.unhealthy_after < 1:
        return _("unhealthy_after doit être >= 1 (zone {url_prefix!r})").format(url_prefix=zone.url_prefix)
    if zone.healthy_after < 1:
        return _("healthy_after doit être >= 1 (zone {url_prefix!r})").format(url_prefix=zone.url_prefix)
    if zone.load_poll_interval_seconds <= 0:
        return _("load_poll_interval_seconds doit être strictement positif (zone {url_prefix!r})").format(url_prefix=zone.url_prefix)
    if zone.load_poll_timeout_seconds <= 0:
        return _("load_poll_timeout_seconds doit être strictement positif (zone {url_prefix!r})").format(url_prefix=zone.url_prefix)
    if zone.load_smoothing_samples < 1:
        return _("load_smoothing_samples doit être >= 1 (zone {url_prefix!r})").format(url_prefix=zone.url_prefix)
    if zone.load_sample_max_age_seconds <= 0:
        return _("load_sample_max_age_seconds doit être strictement positif (zone {url_prefix!r})").format(url_prefix=zone.url_prefix)
    if zone.cache_default_ttl_seconds <= 0:
        return _("cache_default_ttl_seconds doit être strictement positif (zone {url_prefix!r})").format(url_prefix=zone.url_prefix)
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


class ProxyLoadBalancerState:
    """Etat de repartition de charge pour les zones de reverse proxy
    (Phase 5, §16/§27.1) - une seule instance construite par serveur
    (meme convention que `ProxyRoundRobinState`, jamais recreee par
    requete), injectee dans `serve_proxy()`/`serve_websocket_proxy()` a
    la place de `ProxyRoundRobinState`. TOUT l'etat interne (connexions
    actives, temps de reponse moyen, poids courant) est cle par
    `(zone_key=url_prefix, upstream_key=host:port)` - jamais par index
    de tuple, pour que l'ajout/retrait/reordonnement d'un upstream via
    le TUI ne fasse jamais heriter l'historique d'un autre upstream.

    `acquire`/`release`/`record_response_time` sont appeles pour TOUTE
    requete proxy quelle que soit la strategie active de la zone (cout
    negligeable, et permet de changer de strategie a chaud - SIGHUP -
    sans repartir d'un historique vide)."""

    def __init__(self) -> None:
        self._round_robin_next: dict[str, int] = {}
        self._weighted_round_robin_current: dict[str, dict[str, int]] = {}
        self._active_connections: dict[str, dict[str, int]] = {}
        self._response_time_avg_seconds: dict[str, dict[str, float]] = {}

    def select(
        self, zone: ProxyZone, client_ip: str, *,
        upstreams: tuple[UpstreamTarget, ...] | None = None,
        health_state: ProxyHealthState | None = None,
    ) -> UpstreamTarget:
        """`upstreams`, si fourni, REMPLACE `zone.upstreams` comme
        bassin de candidats (Phase 6, §18.3/§27.2) - utilise par
        `resolve_upstream()` pour ne presenter que les upstreams
        ELIGIBLES (exclut DOWN/MAINTENANCE/DRAINING) a la strategie,
        sans jamais modifier la zone elle-meme. Compteurs internes
        (round-robin, poids) restent cles par `zone.url_prefix` quel
        que soit le sous-ensemble presente - pas de nouvel etat par
        combinaison de candidats. `health_state` n'est consulte QUE par
        la strategie "real_load" (Phase 7, §19) - absent/`None` pour
        toutes les autres, jamais une dependance dure sur `ProxyHealthState`
        (import `TYPE_CHECKING` uniquement, evite un cycle avec
        `proxy_health.py` qui importe deja ce module)."""
        upstreams = upstreams if upstreams is not None else zone.upstreams
        strategy = zone.load_balancing
        if strategy == "weighted_round_robin":
            return self._pick_weighted_round_robin(zone.url_prefix, upstreams)
        if strategy == "least_connections":
            return self._pick_least_connections(zone.url_prefix, upstreams, weighted=False)
        if strategy == "weighted_least_connections":
            return self._pick_least_connections(zone.url_prefix, upstreams, weighted=True)
        if strategy == "ip_hash":
            return self._pick_ip_hash(upstreams, client_ip)
        if strategy == "least_response_time":
            return self._pick_least_response_time(zone.url_prefix, upstreams)
        if strategy == "real_load" and health_state is not None:
            return self._pick_real_load(zone, upstreams, health_state)
        return self._pick_round_robin(zone.url_prefix, upstreams)

    def _pick_round_robin(self, zone_key: str, upstreams: tuple[UpstreamTarget, ...]) -> UpstreamTarget:
        index = self._round_robin_next.get(zone_key, 0) % len(upstreams)
        self._round_robin_next[zone_key] = index + 1
        return upstreams[index]

    def _pick_weighted_round_robin(self, zone_key: str, upstreams: tuple[UpstreamTarget, ...]) -> UpstreamTarget:
        """Repartition pondere lisse (algorithme "smooth weighted
        round-robin", meme principe que nginx) : chaque upstream
        accumule son poids a chaque tour, le plus charge en poids
        courant est choisi puis se voit retrancher le poids total - un
        poids de 3 obtient en moyenne 3x plus de tours qu'un poids de 1,
        sans jamais enchainer deux selections consecutives du meme
        upstream tant qu'un autre est disponible."""
        current = self._weighted_round_robin_current.setdefault(zone_key, {})
        total_weight = sum(max(1, u.weight) for u in upstreams)
        chosen: UpstreamTarget | None = None
        chosen_key = ""
        chosen_value = None
        for upstream in upstreams:
            key = upstream_key(upstream)
            value = current.get(key, 0) + max(1, upstream.weight)
            current[key] = value
            if chosen_value is None or value > chosen_value:
                chosen, chosen_key, chosen_value = upstream, key, value
        assert chosen is not None  # upstreams non vide garanti par validate_proxy_zone
        current[chosen_key] -= total_weight
        return chosen

    def _pick_least_connections(
        self, zone_key: str, upstreams: tuple[UpstreamTarget, ...], *, weighted: bool,
    ) -> UpstreamTarget:
        counts = self._active_connections.get(zone_key, {})

        def load(upstream: UpstreamTarget) -> float:
            count = counts.get(upstream_key(upstream), 0)
            return count / max(1, upstream.weight) if weighted else float(count)

        return min(upstreams, key=load)

    def _pick_ip_hash(self, upstreams: tuple[UpstreamTarget, ...], client_ip: str) -> UpstreamTarget:
        """Repartition deterministe par IP cliente (meme client -> meme
        upstream tant que la liste d'upstreams ne change pas) - ponderee
        en repetant chaque upstream `weight` fois dans la liste etendue
        avant hachage (§16.1). `crc32` plutot que `hash()` : stable
        entre deux executions du processus (contrairement a `hash()`
        d'une str, sale aleatoirement par defaut - PYTHONHASHSEED),
        propriete utile mais non requise ici (coherence attendue
        seulement pendant la duree de vie d'un meme processus)."""
        expanded = [upstream for upstream in upstreams for _ in range(max(1, upstream.weight))]
        digest = zlib.crc32(client_ip.encode("utf-8"))
        return expanded[digest % len(expanded)]

    def _pick_least_response_time(self, zone_key: str, upstreams: tuple[UpstreamTarget, ...]) -> UpstreamTarget:
        """Un upstream jamais encore sollicite (aucune moyenne
        enregistree) vaut 0.0 - le plus favorable - pour garantir qu'il
        soit essaye au moins une fois plutot que jamais choisi."""
        averages = self._response_time_avg_seconds.get(zone_key, {})
        return min(upstreams, key=lambda upstream: averages.get(upstream_key(upstream), 0.0))

    def _pick_real_load(
        self, zone: ProxyZone, upstreams: tuple[UpstreamTarget, ...], health_state: ProxyHealthState,
    ) -> UpstreamTarget:
        """Charge reelle (§19) : le score le plus bas l'emporte, parmi
        les upstreams dont l'echantillon est a la fois VALIDE et FRAIS
        (`load_score_for`, §19.5 - None si perime ou jamais echantillonne).
        Repli sur least-connections (filet de securite, §25 : "least-
        connections reste toujours le filet de securite") des qu'AUCUN
        upstream n'a de score exploitable - jamais un echec sec."""
        now = time.monotonic()
        scored = [
            (score, upstream) for upstream in upstreams
            if (score := health_state.load_score_for(
                zone.url_prefix, upstream, max_age_seconds=zone.load_sample_max_age_seconds, now=now,
            )) is not None
        ]
        if not scored:
            return self._pick_least_connections(zone.url_prefix, upstreams, weighted=False)
        return min(scored, key=lambda pair: pair[0])[1]

    def acquire(self, zone_key: str, upstream: UpstreamTarget) -> None:
        counts = self._active_connections.setdefault(zone_key, {})
        key = upstream_key(upstream)
        counts[key] = counts.get(key, 0) + 1

    def release(self, zone_key: str, upstream: UpstreamTarget) -> None:
        counts = self._active_connections.setdefault(zone_key, {})
        key = upstream_key(upstream)
        counts[key] = max(0, counts.get(key, 0) - 1)

    def is_at_capacity(self, zone_key: str, upstream: UpstreamTarget) -> bool:
        """Phase 7bis (§20) : `False` si `max_concurrent_requests` est
        `None` (illimite, defaut). Lit le MEME compteur que `acquire`/
        `release` (connexions actives) - aucun etat separe, la
        backpressure est une lecture differente du meme signal deja
        tenu a jour pour `least_connections`."""
        if upstream.max_concurrent_requests is None:
            return False
        count = self._active_connections.get(zone_key, {}).get(upstream_key(upstream), 0)
        return count >= upstream.max_concurrent_requests

    def record_response_time(self, zone_key: str, upstream: UpstreamTarget, seconds: float) -> None:
        """Moyenne mobile exponentielle (facteur 0.3) plutot qu'une
        simple derniere valeur - lisse les pics transitoires sans
        reagir trop lentement a une degradation reelle et durable."""
        averages = self._response_time_avg_seconds.setdefault(zone_key, {})
        key = upstream_key(upstream)
        previous = averages.get(key)
        averages[key] = seconds if previous is None else (previous * 0.7 + seconds * 0.3)
