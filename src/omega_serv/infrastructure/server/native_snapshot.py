"""Instantane de configuration du moteur natif omega-http-core (plan moteur C++, lot 2, 2026-11-02 ;
contrat IPC `OMEGA-SERV_CONTRAT_IPC_MOTEUR.md` §4).

Python reste la SEULE source de verite : la configuration est chargee et validee ici, comme pour le moteur
Python, puis traduite en un JSON que le natif applique sans rien interpreter (aucune valeur par defaut devinee
cote C++). Toutes les tables viennent des memes fonctions que le moteur Python (`build_routing_tables`,
`apply_security_headers`, `render_default_error_page`...) : une regle ajoutee ici sans passer par elles serait
une seconde implementation, exactement ce que le plan interdit.

`native_unsupported_features` (application/server/engine_selection.py, reexportee ici) liste ce que le natif ne sait pas encore faire : une seule entree = repli moteur
Python (plan §6), jamais un serveur partiellement fonctionnel."""
from __future__ import annotations

import http
import ipaddress
import json
from collections.abc import Callable, Iterable
from dataclasses import replace
from pathlib import Path
from typing import TYPE_CHECKING, Any

from omega_serv.application.server.engine_selection import (
    native_unsupported_features,  # noqa: F401 - reexport
)

if TYPE_CHECKING:
    from omega_serv.domain.config.entities import OmegaServConfig
    from omega_serv.domain.routing.proxy_zone import ProxyZone, UpstreamTarget
    from omega_serv.domain.security.waf.config import RateLimitConfig, WafConfig
    from omega_serv.domain.security.waf.signature_engine import CompiledRulePack


SNAPSHOT_FORMAT = 1
_UNKNOWN_THEME = "\x00theme-inconnu"
"""Theme absent de toute palette : base_css() y repond par le theme par defaut - c'est ce repli que le natif
sert pour un theme inconnu, calcule par la vraie fonction plutot que suppose."""


INSPECT_BASE_TIMEOUT_MS = 60_000
"""Le moteur Python n'a AUCUNE limite sur l'etape de securite : celle-ci ne doit jamais se declencher en
fonctionnement normal (processus de securite arrete ou bloque seulement). S'y ajoute le ralentissement maximal du
mode guerre, qui retient volontairement le verdict."""


def inspect_section(config: OmegaServConfig, project_root: Path | None = None,
                    security_processes: int = 1) -> dict[str, Any] | None:
    """Lot 4 : null si aucune fonction de l'etape de securite n'est active (zero aller-retour) ; sinon ce que le
    natif doit savoir pour soumettre chaque requete au processus Python. Lu par les VRAIES fonctions de
    configuration (parse_waf_config, parse_active_defense_config), jamais recopie."""
    from omega_serv.application.server.engine_selection import decide_proxy_zones
    from omega_serv.application.server.routing_tables import build_routing_tables
    from omega_serv.domain.security.active_defense.config import parse_active_defense_config
    from omega_serv.domain.security.waf.config import parse_waf_config
    waf = parse_waf_config(config.options["waf"].settings) if config.option_enabled("waf") else None
    auth = config.option_enabled("auth")
    active_defense = (parse_active_defense_config(config.options["active_defense"].settings)
                      if config.option_enabled("active_defense") else None)
    security_stage = waf is not None or auth or active_defense is not None
    # Lot 5 : routes deleguees - listing de repertoire, /load et /admin (reseaux de confiance du trusted_proxy)
    delegated_routes = config.option_enabled("dirlisting") or config.option_enabled("trusted_proxy")
    # Lot 6 : routes applicatives -> connexion confiee a Python (prefixes : sur-ensemble, Python tranche)
    tables = build_routing_tables(config)
    handoff_any: list[str] = []
    # Projets 3.0.0 §8.1 : toutes les zones FastCGI, arretees comprises (Python y repond 503, maintenance).
    handoff_any.extend(zone.path_prefix for zone in tables.fastcgi_zones)
    # Plan proxy natif v2, lot 4 : seules les zones que decide_proxy_zones confie a Python ; les zones natives sont
    # relayees par le natif (options.reverse_proxy.engine = native, apercu jusqu'au lot 11).
    delegated_zones = {decision.url_prefix for decision in decide_proxy_zones(config) if decision.engine == "python"}
    for zone in tables.proxy_zones or ():
        if zone.url_prefix in delegated_zones:
            handoff_any.append(zone.url_prefix)
    handoff_post = [zone.path_prefix for zone in tables.upload_zones]
    handoff_any = sorted({p for prefix in handoff_any for p in (prefix, prefix.rstrip("/")) if p})
    handoff_post = sorted({p for prefix in handoff_post for p in (prefix, prefix.rstrip("/")) if p})
    # Plan proxy natif v2, lot 3 (P6) : au moins un processus de securite des qu'une zone proxy existe, meme sans
    # option de securite ni zone confiee (sondes, route d'administration).
    proxy_zones = bool(tables.proxy_zones)
    if not security_stage and not delegated_routes and not handoff_any and not handoff_post and not proxy_zones:
        return None
    timeout_ms = INSPECT_BASE_TIMEOUT_MS
    if active_defense is not None:
        slowdown = active_defense.war_mode.slowdown
        timeout_ms += slowdown.maximum_ms + slowdown.jitter_ms
    # Auth : jamais une zone protegee servie sans controle -> toujours fail-closed (decision 2026-11-02, a signaler).
    on_error = "fail-closed" if auth else (waf.on_internal_error if waf is not None else "fail-open")
    return {
        "body_methods": list(waf.inspect.body_methods) if waf is not None else [],
        # Plan proxy natif v2, lot 4 (S23, P10 revu) : plus de plafond lie au canal, le corps capture passe par
        # memfd au-dela d'une trame - les deux moteurs inspectent la meme part (C20).
        "body_bytes": waf.inspect.body_max_inspect_bytes if waf is not None else 0,
        "timeout_ms": timeout_ms,
        "on_error": on_error,
        "security_stage": security_stage,
        "handoff_any": handoff_any,
        "handoff_post": handoff_post,
        # Plan proxy natif v2, lot 3 (P6) : le fil i est servi par le processus i % N ; /.omega-serv-admin/ part
        # toujours chez le n° 0 (seul responsable de la sante), quel que soit le fil qui a accepte la connexion.
        "security_processes": max(1, security_processes),
        # Decision utilisateur 2026-11-02 : en fail-open, une adresse deja bannie reste refusee (451) - le natif lit
        # la MEME blocklist que le WAF Python (JsonBlocklistStore), seulement quand le controle est indisponible.
        "blocklist": (str(project_root / waf.blocklist.path)
                      if waf is not None and project_root is not None else None),
        # Lot 2 : waf.inspect.body_over_limit = reject (WAF en mode "block") - corps plus grand que la partie
        # inspectee refuse (413) apres la validation du Content-Length, comme read_and_discard_body.
        "body_reject_over": (waf.inspect.body_max_inspect_bytes
                             if waf is not None and waf.mode == "block" and waf.inspect.body_over_limit == "reject"
                             else None),
        # Lot 1N (D36, P4) : refus decides par le natif seul (banni ou debit depasse en fail-open) -> meme ligne
        # waf-alerts que _log_waf_alert. Les 503 d'indisponibilite n'y vont pas (decision de l'auteur du 2026-11-12) :
        # ce sont des pannes du serveur, pas des actes du visiteur - error.log seulement.
        "waf_alerts": ({"path": str(project_root / waf.logging.path),
                        "max_path_chars": waf.logging.max_path_chars,
                        "max_user_agent_chars": waf.logging.max_user_agent_chars,
                        "include_body_excerpt": waf.logging.include_body_excerpt,
                        "body_excerpt_max_bytes": waf.logging.body_excerpt_max_bytes}
                       if waf is not None and project_root is not None else None),
    }


def _status_codes() -> list[int]:
    """Tout code d'erreur que le serveur peut produire (HttpStatus) ou relayer (http.HTTPStatus)."""
    from omega_serv.domain.http.status_codes import HttpStatus
    return sorted({int(s) for s in HttpStatus} | {int(s) for s in http.HTTPStatus})


def _text(data: bytes) -> str:
    return data.decode("utf-8")  # strict : un octet non UTF-8 ne peut pas voyager dans le JSON


def _option_settings(config: OmegaServConfig, name: str) -> dict[str, Any] | None:
    option = config.options.get(name)
    if option is None or not option.enabled:
        return None
    return option.settings


def waf_filter_section(config: OmegaServConfig, project_root: Path) -> dict[str, Any] | None:
    """Regles du WAF retraduites pour le natif (OMEGA-SERV_PLAN-DETAILLE_WAF_NATIF.md, lot 0) : null sans WAF.
    Memes packs et memes listes que build_waf_collaborators, compiles par les MEMES fonctions. Le natif ne s'en
    sert que pour reconnaitre une requete sans aucune correspondance ; « available: false » (pack illisible) ou
    une regle dans `unexported` -> les requetes concernees vont a Python, comme aujourd'hui."""
    from omega_serv.domain.security.active_defense.config import parse_active_defense_config
    from omega_serv.domain.security.waf.config import parse_waf_config
    from omega_serv.domain.security.waf.exceptions import WafRuleLoadError, WafRuleValidationError
    from omega_serv.domain.security.waf.rate_limit_policy import effective_source_policies
    from omega_serv.domain.security.waf.reputation import effective_never_auto_block
    from omega_serv.infrastructure.filesystem.local_filesystem import LocalFilesystem
    from omega_serv.infrastructure.waf.keyword_list_loader import load_keyword_lists
    from omega_serv.infrastructure.waf.rule_pack_loader import load_rule_packs
    if not config.option_enabled("waf"):
        return None
    waf = parse_waf_config(config.options["waf"].settings)
    filesystem = LocalFilesystem()
    try:
        packs = load_rule_packs(filesystem, tuple(project_root / p for p in waf.rule_paths)) + load_keyword_lists(
            filesystem, project_root, waf.keyword_lists,
        )
    except (WafRuleLoadError, WafRuleValidationError, OSError) as e:
        return {"available": False, "reason": str(e)}
    payload = waf_filter_payload(waf, packs)
    # Lot 2 : le natif ne decide seul (requete propre servie sans Python) que si AUCUNE fonction ne demande Python
    # pour chaque requete. Codes de raison (jamais du texte affiche) : premier motif trouve.
    reasons = []
    if waf.magnet.enabled:
        reasons.append("magnet")  # script Lua : appele pour chaque requete
    if waf.rate_limit.enabled:
        reasons.append("rate_limit")  # compte chaque requete (lot 6 : compte par le natif)
    if config.option_enabled("active_defense") and parse_active_defense_config(
            config.options["active_defense"].settings).deception.enabled:
        reasons.append("deception")  # source deja affectee a un leurre (lot 3 : sources suivies)
    if config.option_enabled("auth"):
        try:
            payload["auth_prefixes"] = sorted({zone.path_prefix for zone in _auth_zones(config, project_root)})
        except Exception:  # noqa: BLE001 - zones illisibles : Python tranche toute requete, comme aujourd'hui
            reasons.append("auth_zones")
    payload["native_decides"] = not reasons
    # Lot 6 : la limite de debit est comptee par le natif (toutes les requetes, etiquette INSPECT 11) - champ que
    # seul un natif recent lit ; un natif plus ancien voit les deux champs ci-dessus a false et envoie tout ici.
    if waf.rate_limit.enabled:
        source_policies = effective_source_policies(waf.rate_limit.source_policies, config.option_enabled("trusted_proxy"))
        payload["rate_limit"] = rate_limit_payload(replace(waf.rate_limit, source_policies=source_policies))
        # Plan proxy natif v2, lot 1N (decision de l'auteur du 2026-11-12) : pendant une indisponibilite du controle
        # en fail-open, le natif repond lui-meme au depassement - meme statut, et alerte « throttle » pour une source
        # sure (is_trusted_rate_limit_source : never_auto_block effectif + regles IP/reseau cochees `trusted`).
        payload["rate_limit"]["response_status"] = waf.rate_limit.global_.response_status
        payload["rate_limit"]["trusted_networks"] = _normalized_networks(
            [*effective_never_auto_block(waf.reputation.never_auto_block, config.option_enabled("trusted_proxy")),
             *(policy.network for policy in source_policies if policy.trusted)])
    blocking = [r for r in reasons if r not in ("deception", "rate_limit")]
    payload["native_decides_with_rate_limit"] = not blocking
    # Lot 3 : avec les leurres, le natif decide seul a condition de connaitre les sources suivies (trame WATCH) -
    # champ que seul un natif recent lit ; un natif plus ancien voit `native_decides: false` et envoie tout ici.
    payload["native_decides_with_watch"] = not [reason for reason in reasons if reason != "deception"]
    # Raison affichee : ce qui empeche vraiment le natif de decider seul (leurres et debit ne l'empechent plus).
    payload["python_reason"] = next(iter(blocking or reasons), None)
    return payload


def _normalized_networks(networks: list[str]) -> list[str]:
    """`ip_network(strict=False)`, illisibles ignores - comme _parse_networks et _parse_network cote Python."""
    normalized = []
    for network in networks:
        try:
            normalized.append(str(ipaddress.ip_network(network, strict=False)))
        except ValueError:
            continue
    return normalized


def _auth_zones(config: OmegaServConfig, project_root: Path) -> list[Any]:
    # meme fichier que start_server.build_auth_zones_repository (sans importer tout le demarrage du serveur)
    from omega_serv.infrastructure.auth.auth_zones_repository import JsonAuthZonesRepository
    from omega_serv.infrastructure.filesystem.local_filesystem import LocalFilesystem
    return list(JsonAuthZonesRepository(LocalFilesystem(), project_root / config.paths.auth_zones).load())


def rate_limit_payload(rate_limit: RateLimitConfig) -> dict[str, Any]:
    """Section `waf_filter.rate_limit` (lot 6) : regles de select_rate_limit, deja filtrees par
    effective_source_policies comme au demarrage (start_server) ; reseaux illisibles transmis tels quels (ignores des
    deux cotes). La feuille de style des pages d'erreur n'est jamais comptee (evaluate_waf_request)."""
    from omega_serv.domain.http.error_pages import ERROR_CSS_PATH
    return {
        "global": {"requests": rate_limit.global_.requests, "window_seconds": rate_limit.global_.window_seconds},
        "path_policies": [{"prefix": p.prefix, "requests": p.requests, "window_seconds": p.window_seconds}
                          for p in rate_limit.path_policies],
        "source_policies": [{"network": p.network, "requests": p.requests, "window_seconds": p.window_seconds}
                            for p in rate_limit.source_policies],
        "error_css_path": ERROR_CSS_PATH,
    }


def waf_filter_payload(waf: WafConfig, packs: tuple[CompiledRulePack, ...]) -> dict[str, Any]:
    """Section `waf_filter` pour des packs deja compiles (instantane, et vecteurs de tools/differential)."""
    from omega_serv.domain.security.waf.native_rule_export import export_rule_packs
    exported, unexported = export_rule_packs(packs)
    return {
        "available": True,
        "decode_depth": waf.inspect.decode_depth,
        "inspect_path": waf.inspect.path,
        "inspect_query": waf.inspect.query,
        "inspect_headers": waf.inspect.headers,
        "rules": [{"id": r.rule_id, "pack": r.pack, "scopes": list(r.scopes), "pattern": r.pattern,
                   "exclude": r.exclude, "lowered": r.lowered, "controls": [[t, m] for t, m in r.controls]}
                  for r in exported],
        "check_every": waf.native_check_every,  # lot 4 : controle 1/N (0 = jamais)
        "unexported": [{"id": r.rule_id, "pack": r.pack, "scopes": list(r.scopes), "reason": r.reason}
                       for r in unexported],
        # Lot 2 (completes par waf_filter_section selon la configuration) : decision seule permise, et prefixes des
        # zones protegees (Auth : requete dans une zone -> Python, meme comparaison que zone_resolver).
        "native_decides": True,
        "native_decides_with_watch": True,
        "python_reason": None,
        "auth_prefixes": [],
    }


def _zone_inspect_mode(zone: ProxyZone, security_stage: bool, waf_filter: dict[str, Any] | None,
                      auth_prefixes: list[str]) -> str:
    """Plan proxy natif v2, lot 3 (C1, C20) : INSPECT demande par la zone.
    - « never » : aucune option de securite - zero aller-retour ;
    - « filter » : la preselection native decide requete par requete, comme pour le statique (correspondance ou
      doute -> INSPECT, plus la part check_every) ;
    - « always » : chaque requete (magnet, filtre indisponible, zones Auth illisibles, zone entierement protegee)."""
    if not security_stage:
        return "never"
    if waf_filter is None or not waf_filter.get("available") or not waf_filter.get("native_decides_with_watch"):
        return "always"
    if any(zone.url_prefix.startswith(prefix) for prefix in auth_prefixes):
        return "always"
    return "filter"


Resolver = Callable[[Iterable[str]], dict[str, tuple[str, ...]]]

_LAST_RESOLVED: dict[str, tuple[str, ...]] = {}
"""Plan proxy natif v2, lot 6 (C18, decision de l'auteur du 2026-11-13) : dernieres adresses connues de chaque nom DNS
de backend, dans le superviseur. Un rechargement dont la resolution echoue garde ces adresses ; sans elles (premier
demarrage), le backend est hors service jusqu'au rechargement suivant."""


def _default_resolver(hosts: Iterable[str]) -> dict[str, tuple[str, ...]]:
    from omega_serv.infrastructure.probe.local_addresses import resolve_hosts
    return resolve_hosts(hosts)


def _native_backends(config: OmegaServConfig, zone: ProxyZone, resolver: Resolver, notes: list[str]) -> list[dict]:
    """Lot 6 (Q2, C18, S27) : chaque adresse d'un nom DNS devient un backend (comme nginx) - poids, plafond, cookie
    collant et sante par adresse (decision de l'auteur du 2026-11-13) ; `name` (`hote:port`) reste la cible des regles
    par en-tete et des etats manuels. Une adresse qui designe ce serveur lui-meme (boucle) est hors service."""
    from omega_serv.domain.routing.proxy_zone import (
        normalize_host_address,
        upstream_key,
        upstream_targets_this_server,
    )
    names = [u.host for u in zone.upstreams if normalize_host_address(u.host) is None]
    resolved = resolver(dict.fromkeys(names)) if names else {}
    local: frozenset[str] | None = None
    backends: list[dict] = []
    for upstream in zone.upstreams:
        literal = normalize_host_address(upstream.host)
        if literal is not None:
            backends.append(_backend(upstream, upstream_key(upstream), literal, None))
            continue
        addresses = tuple(a for a in (normalize_host_address(x) for x in resolved.get(upstream.host, ())) if a)
        name = upstream_key(upstream)
        if addresses:
            _LAST_RESOLVED[name] = addresses
            notes.append(f"reverse proxy : {name} résolu en {', '.join(addresses)} (zone {zone.url_prefix})")
        elif name in _LAST_RESOLVED:
            addresses = _LAST_RESOLVED[name]
            notes.append(f"reverse proxy : {name} ne se résout pas : adresses précédentes gardées "
                         f"({', '.join(addresses)}) (zone {zone.url_prefix})")
        else:
            notes.append(f"reverse proxy : {name} ne se résout pas : backend hors service jusqu'au prochain "
                         f"rechargement (zone {zone.url_prefix})")
            backends.append(_backend(upstream, name, None, "dns"))
            continue
        for address in addresses:
            key = f"{upstream.host} ({address}):{upstream.port}"
            unusable = None
            if upstream.port == config.server.port:
                if local is None:
                    from omega_serv.infrastructure.probe.local_addresses import (
                        local_interface_addresses,
                    )
                    local = local_interface_addresses()
                if upstream_targets_this_server(address, upstream.port, config.server.bind, config.server.port, local):
                    unusable = "boucle"
                    notes.append(f"reverse proxy : {key} désigne ce serveur lui-même : adresse hors service "
                                 f"(boucle) (zone {zone.url_prefix})")
            backends.append(_backend(upstream, key, address, unusable))
    return backends


def _backend(upstream: UpstreamTarget, key: str, address: str | None, unusable: str | None) -> dict[str, Any]:
    from omega_serv.domain.routing.proxy_zone import (
        host_header_value,
        sticky_cookie_value_for_key,
        upstream_key,
    )
    return {
        "key": key,
        "name": upstream_key(upstream),
        "host": upstream.host,
        "port": upstream.port,
        "host_header": host_header_value(upstream.host, upstream.port),
        # Adresse IP canonique (litterale, ou resolue par Python pour une zone native) ; null : nom non resolu.
        "address": address,
        "tls": upstream.use_tls,
        "weight": upstream.weight,
        "max_concurrent": upstream.max_concurrent_requests,
        "load_source": upstream.load_source,
        "active_check": upstream.active_health_check_enabled,
        "cookie": sticky_cookie_value_for_key(key),
        "unusable": unusable,  # null | "dns" (nom non resolu) | "boucle" (adresse de ce serveur)
    }


def proxy_section(config: OmegaServConfig, security_stage: bool, waf_filter: dict[str, Any] | None,
                  resolver: Resolver | None = None, notes: list[str] | None = None) -> dict[str, Any] | None:
    """Plan proxy natif v2, lot 3 : zones, backends, regles, delais, budgets et INSPECT par zone, lus par les VRAIES
    fonctions (parse_proxy_zones, decide_proxy_zones). Le natif le lit et le verifie ; il ne relaie rien avant le
    lot 4 (toute zone reste dans inspect.handoff_any)."""
    from omega_serv.application.server.engine_selection import decide_proxy_zones
    from omega_serv.domain.routing.proxy_engine import parse_proxy_engine_settings
    from omega_serv.domain.routing.proxy_zone import (
        DEFAULT_MAX_RESPONSE_BODY_MB,
        normalize_host_address,
        parse_proxy_zones,
        upstream_key,
    )
    option = config.options.get("reverse_proxy")
    if option is None or not option.enabled:
        return None
    settings = parse_proxy_engine_settings(option.settings)
    decisions = {decision.url_prefix: decision for decision in decide_proxy_zones(config)}
    auth_prefixes = list(waf_filter.get("auth_prefixes", [])) if waf_filter else []
    max_body_mb = option.settings.get("max_response_body_mb", DEFAULT_MAX_RESPONSE_BODY_MB)
    zones = []
    for zone in parse_proxy_zones(option.settings.get("zones", [])):
        decision = decisions[zone.url_prefix]
        zones.append({
            "prefix": zone.url_prefix,
            "engine": decision.engine,
            "reasons": list(decision.reasons),
            "inspect": _zone_inspect_mode(zone, security_stage, waf_filter, auth_prefixes),
            "connect_timeout_ms": round(zone.connect_timeout_seconds * 1000),
            "read_timeout_ms": round(zone.read_timeout_seconds * 1000),
            "preserve_host": zone.preserve_host_header,
            "verify_tls": zone.verify_upstream_tls,
            "websocket": zone.websocket_enabled,
            "websocket_idle_timeout_ms": round(zone.websocket_idle_timeout_seconds * 1000),  # lot 10 : 0 = aucun
            "load_balancing": zone.load_balancing,
            "sticky": ({"cookie_name": zone.sticky_cookie_name, "max_age_seconds": zone.sticky_cookie_max_age_seconds}
                       if zone.sticky_session_enabled else None),
            "routing_rules": [{"header": rule.header_name, "pattern": rule.pattern, "upstream": rule.upstream_key}
                              for rule in zone.routing_rules],
            "unhealthy_after": zone.unhealthy_after,
            "healthy_after": zone.healthy_after,
            "load_sample_max_age_ms": round(zone.load_sample_max_age_seconds * 1000),
            # Lot 6 : une zone native resout ses noms DNS ici (une adresse = un backend) ; confiee : un backend par
            # entree de la configuration, adresse null pour un nom (Python le resout a chaque connexion).
            "upstreams": (_native_backends(config, zone, resolver or _default_resolver, notes if notes is not None else [])
                          if decision.engine == "native" else
                          [_backend(u, upstream_key(u), normalize_host_address(u.host), None) for u in zone.upstreams]),
        })
    return {
        "engine": settings.engine,
        "budgets": {
            "pending_body_bytes": settings.max_pending_body_bytes,
            "inspections": settings.max_concurrent_inspections,
            "upstream_connections": settings.max_upstream_connections,
        },
        "max_response_body_bytes": int(max_body_mb) * 1024 * 1024,
        "zones": zones,
    }


def build_native_snapshot(config: OmegaServConfig, project_root: Path, generation: int,
                          security_processes: int = 1, resolver: Resolver | None = None,
                          notes: list[str] | None = None) -> dict[str, Any]:
    """`notes` (lot 6) : lignes pour error.log - resolution des noms DNS des backends (C18 : adresses ecrites dans le
    journal), backends hors service."""
    from omega_lib.theme.policies import EXPORT_PALETTES

    from omega_serv.application.server.routing_tables import build_routing_tables
    from omega_serv.application.server.serve_proxy_admin import ADMIN_URL_PREFIX
    from omega_serv.application.server.serve_proxy_load import LOAD_URL_PREFIX
    from omega_serv.core.i18n import page_html_lang
    from omega_serv.domain.http.error_pages import (
        ERROR_CSS_FILENAME,
        ERROR_CSS_URL_PREFIX,
        error_pages_css,
        render_default_error_page,
    )
    from omega_serv.domain.http.response import HttpResponse
    from omega_serv.domain.http.status_codes import HttpStatus, reason_phrase_for
    from omega_serv.domain.routing.dirlisting import CSS_URL_PREFIX, base_css
    from omega_serv.domain.routing.icon_registry import ICON_FILENAMES, ICON_URL_PREFIX
    from omega_serv.domain.routing.proxy_zone import set_sticky_cookie_key
    from omega_serv.domain.security.csp import csp_header_name
    from omega_serv.domain.security.security_headers import apply_security_headers
    from omega_serv.domain.security.tls.cipher_suites import MODERN_CIPHER_SUITES
    from omega_serv.infrastructure.icons.icon_files import read_icon_svg
    from omega_serv.infrastructure.proxy.sticky_cookie_key import load_or_create_sticky_cookie_key
    server = config.server
    security = config.security
    tables = build_routing_tables(config)
    if config.option_enabled("reverse_proxy"):  # scan de securite n° 1 (F41/F42) : meme cle que le moteur Python
        set_sticky_cookie_key(load_or_create_sticky_cookie_key(project_root))

    # En-tetes de securite produits par la VRAIE fonction (politique globale, path=None) ; le natif remplace
    # seulement la valeur de la CSP quand une zone `csp_zones` correspond au chemin (csp_policy_for_path).
    probe = HttpResponse.empty(HttpStatus.OK)
    apply_security_headers(probe, security, config.tls.enabled, None)
    headers: dict[str, Any] | None = None
    if probe.headers:
        headers = {
            "ordered": [[name, value] for name, value in probe.headers.items()],
            "csp_header": csp_header_name(security.csp_mode),
            "csp_zones": [[zone.path_prefix, zone.data] for zone in security.csp_zones],
        }

    trusted = _option_settings(config, "trusted_proxy")
    error_pages = _option_settings(config, "error_pages")
    statuses = _status_codes()
    icons = {}
    for name in sorted(ICON_FILENAMES):
        body = read_icon_svg(name)
        if body is not None:
            icons[name] = _text(body)

    inspect = inspect_section(config, project_root, security_processes)
    waf_filter = waf_filter_section(config, project_root)
    return {
        "format": SNAPSHOT_FORMAT,
        "generation": generation,
        "server": {
            "bind": server.bind,
            "port": server.port,
            "listen_backlog": server.listen_backlog,
            "max_connections": server.max_connections,
            "max_request_size": server.max_request_size,
            "max_header_size": server.max_header_size,
            "max_request_line_size": server.max_request_line_size,
            "read_timeout_seconds": server.read_timeout_seconds,
            "keepalive_timeout_seconds": server.keepalive_timeout_seconds,
            "write_timeout_seconds": server.write_timeout_seconds,  # lot A (D31)
            "max_keepalive_requests": server.max_keepalive_requests,
            "shutdown_grace_period_seconds": server.shutdown_grace_period_seconds,
            "index_files": list(server.index_files),
            # SafePathResolver : webroot resolu une fois, au demarrage du serveur
            "webroot": str((project_root / config.paths.webroot).resolve()),
        },
        "security": {
            "require_valid_host": security.require_valid_host,
            "allowed_methods": list(security.allowed_methods),
            "deny_hidden_files": security.deny_hidden_files,
            "deny_sensitive_extensions": list(security.deny_sensitive_extensions),
            "deny_patterns": list(security.deny_patterns),
            "headers": headers,
        },
        "routes": {
            "trusted_proxy": None if trusted is None else {
                "networks": list(trusted.get("trusted_networks", [])),
                "header_preference": list(trusted.get("header_preference", ["Forwarded", "X-Forwarded-For"])),
            },
            "access_rules": None if tables.access_rules is None else {"list": [
                {"path_prefix": r.path_prefix, "verdict": r.verdict, "extensions": list(r.extensions)}
                for r in tables.access_rules
            ]},
            "redirects": None if tables.redirect_zones is None else {"list": [
                {"url_prefix": z.data.url_prefix, "destination": z.data.destination, "status_code": z.data.status_code}
                for z in tables.redirect_zones
            ]},
            "rewrites": None if tables.rewrite_rules is None else {"list": [
                {"match_prefix": r.match_prefix, "replacement_prefix": r.replacement_prefix} for r in tables.rewrite_rules
            ]},
            # Racine NON resolue : le moteur Python la resout a chaque requete (SafePathResolver par alias)
            "aliases": None if tables.alias_zones is None else {"list": [
                {"url_prefix": z.data.url_prefix, "root": str(project_root / z.data.target_path)}
                for z in tables.alias_zones
            ]},
            "cache": None if tables.cache_policy is None else {
                "default": tables.cache_policy.default,
                "zones": [[z.path_prefix, z.data] for z in tables.cache_policy.zones],
                "extensions": [[ext, value] for ext, value in tables.cache_policy.extensions.items()],
            },
            "dirlisting": None if not tables.dirlisting_zones else {
                "zone_prefixes": [z.path_prefix for z in tables.dirlisting_zones],
            },
        },
        "error_pages": {
            "custom_dir": None if error_pages is None
            else str(project_root / str(error_pages.get("custom_dir", "webroot/.errors"))),
            "page_lang": page_html_lang(),
            "defaults": {str(code): _text(render_default_error_page(code)) for code in statuses if code >= 400},
            "reason_phrases": {str(code): reason_phrase_for(code) for code in statuses},
        },
        "internal": {
            "icon_prefix": ICON_URL_PREFIX,
            "icons": icons,
            "dirlisting_css_prefix": CSS_URL_PREFIX,
            "dirlisting_css": {theme: base_css(theme) for theme in sorted(EXPORT_PALETTES)},
            "dirlisting_css_fallback": base_css(_UNKNOWN_THEME),
            "error_css_prefix": ERROR_CSS_URL_PREFIX,
            "error_css_name": ERROR_CSS_FILENAME,
            "error_css": error_pages_css(),
            "load_prefix": LOAD_URL_PREFIX,
            "admin_prefix": ADMIN_URL_PREFIX,
        },
        "logs": {
            "access": str(project_root / config.logs.access),
            "error": str(project_root / config.logs.error),
        },
        "inspect": inspect,
        "waf_filter": waf_filter,
        # Plan proxy natif v2, lot 3 : null sans reverse proxy.
        "proxy": proxy_section(config, bool(inspect and inspect["security_stage"]), waf_filter, resolver, notes),
        # TLS direct (lot 3b) : memes fichiers et reglages que ssl_context_builder.build_ssl_context ;
        # null si TLS est desactive ou termine en amont (behind_proxy).
        "tls": None if not (config.tls.enabled and config.tls.mode == "direct") else {
            "certificate": str(project_root / config.tls.certificate_path),
            "private_key": str(project_root / config.tls.private_key_path),
            "passphrase_env": config.tls.private_key_passphrase_env,
            "min_version": config.tls.min_version,
            "max_version": config.tls.max_version,
            "ciphers": MODERN_CIPHER_SUITES,
        },
    }


def write_native_snapshot(config: OmegaServConfig, project_root: Path, generation: int, path: Path) -> None:
    path.write_text(json.dumps(build_native_snapshot(config, project_root, generation), ensure_ascii=False), encoding="utf-8")
