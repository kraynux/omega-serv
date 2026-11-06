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
import json
from dataclasses import replace
from pathlib import Path
from typing import Any

from omega_lib.theme.policies import EXPORT_PALETTES

from omega_serv.application.server.engine_selection import (
    native_unsupported_features,  # noqa: F401 - reexport
)
from omega_serv.application.server.route_request import build_routing_tables
from omega_serv.application.server.serve_proxy_admin import ADMIN_URL_PREFIX
from omega_serv.application.server.serve_proxy_load import LOAD_URL_PREFIX
from omega_serv.core.i18n import page_html_lang
from omega_serv.domain.config.entities import OmegaServConfig
from omega_serv.domain.http.error_pages import (
    ERROR_CSS_FILENAME,
    ERROR_CSS_PATH,
    ERROR_CSS_URL_PREFIX,
    error_pages_css,
    render_default_error_page,
)
from omega_serv.domain.http.response import HttpResponse
from omega_serv.domain.http.status_codes import HttpStatus, reason_phrase_for
from omega_serv.domain.routing.dirlisting import CSS_URL_PREFIX, base_css
from omega_serv.domain.routing.icon_registry import ICON_FILENAMES, ICON_URL_PREFIX
from omega_serv.domain.security.active_defense.config import parse_active_defense_config
from omega_serv.domain.security.csp import csp_header_name
from omega_serv.domain.security.security_headers import apply_security_headers
from omega_serv.domain.security.tls.cipher_suites import MODERN_CIPHER_SUITES
from omega_serv.domain.security.waf.config import RateLimitConfig, WafConfig, parse_waf_config
from omega_serv.domain.security.waf.exceptions import WafRuleLoadError, WafRuleValidationError
from omega_serv.domain.security.waf.native_rule_export import export_rule_packs
from omega_serv.domain.security.waf.rate_limit_policy import effective_source_policies
from omega_serv.domain.security.waf.signature_engine import CompiledRulePack
from omega_serv.infrastructure.auth.auth_zones_repository import JsonAuthZonesRepository
from omega_serv.infrastructure.filesystem.local_filesystem import LocalFilesystem
from omega_serv.infrastructure.icons.icon_files import read_icon_svg
from omega_serv.infrastructure.waf.keyword_list_loader import load_keyword_lists
from omega_serv.infrastructure.waf.rule_pack_loader import load_rule_packs

SNAPSHOT_FORMAT = 1
_UNKNOWN_THEME = "\x00theme-inconnu"
"""Theme absent de toute palette : base_css() y repond par le theme par defaut - c'est ce repli que le natif
sert pour un theme inconnu, calcule par la vraie fonction plutot que suppose."""


INSPECT_BASE_TIMEOUT_MS = 60_000
"""Le moteur Python n'a AUCUNE limite sur l'etape de securite : celle-ci ne doit jamais se declencher en
fonctionnement normal (processus de securite arrete ou bloque seulement). S'y ajoute le ralentissement maximal du
mode guerre, qui retient volontairement le verdict."""


def inspect_section(config: OmegaServConfig, project_root: Path | None = None) -> dict[str, Any] | None:
    """Lot 4 : null si aucune fonction de l'etape de securite n'est active (zero aller-retour) ; sinon ce que le
    natif doit savoir pour soumettre chaque requete au processus Python. Lu par les VRAIES fonctions de
    configuration (parse_waf_config, parse_active_defense_config), jamais recopie."""
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
    if tables.fastcgi_config is not None:
        handoff_any.append(tables.fastcgi_config.url_prefix)
    for zone in tables.proxy_zones or ():
        handoff_any.append(zone.url_prefix)
    handoff_post = [zone.path_prefix for zone in tables.upload_zones]
    handoff_any = sorted({p for prefix in handoff_any for p in (prefix, prefix.rstrip("/")) if p})
    handoff_post = sorted({p for prefix in handoff_post for p in (prefix, prefix.rstrip("/")) if p})
    if not security_stage and not delegated_routes and not handoff_any and not handoff_post:
        return None
    timeout_ms = INSPECT_BASE_TIMEOUT_MS
    if active_defense is not None:
        slowdown = active_defense.war_mode.slowdown
        timeout_ms += slowdown.maximum_ms + slowdown.jitter_ms
    # Auth : jamais une zone protegee servie sans controle -> toujours fail-closed (decision 2026-11-02, a signaler).
    on_error = "fail-closed" if auth else (waf.on_internal_error if waf is not None else "fail-open")
    return {
        "body_methods": list(waf.inspect.body_methods) if waf is not None else [],
        "body_bytes": waf.inspect.body_max_inspect_bytes if waf is not None else 0,
        "timeout_ms": timeout_ms,
        "on_error": on_error,
        "security_stage": security_stage,
        "handoff_any": handoff_any,
        "handoff_post": handoff_post,
        # Decision utilisateur 2026-11-02 : en fail-open, une adresse deja bannie reste refusee (451) - le natif lit
        # la MEME blocklist que le WAF Python (JsonBlocklistStore), seulement quand le controle est indisponible.
        "blocklist": (str(project_root / waf.blocklist.path)
                      if waf is not None and project_root is not None else None),
    }


def _status_codes() -> list[int]:
    """Tout code d'erreur que le serveur peut produire (HttpStatus) ou relayer (http.HTTPStatus)."""
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
        payload["rate_limit"] = rate_limit_payload(replace(waf.rate_limit, source_policies=effective_source_policies(
            waf.rate_limit.source_policies, config.option_enabled("trusted_proxy"))))
    blocking = [r for r in reasons if r not in ("deception", "rate_limit")]
    payload["native_decides_with_rate_limit"] = not blocking
    # Lot 3 : avec les leurres, le natif decide seul a condition de connaitre les sources suivies (trame WATCH) -
    # champ que seul un natif recent lit ; un natif plus ancien voit `native_decides: false` et envoie tout ici.
    payload["native_decides_with_watch"] = not [reason for reason in reasons if reason != "deception"]
    # Raison affichee : ce qui empeche vraiment le natif de decider seul (leurres et debit ne l'empechent plus).
    payload["python_reason"] = next(iter(blocking or reasons), None)
    return payload


def _auth_zones(config: OmegaServConfig, project_root: Path) -> list[Any]:
    # meme fichier que start_server.build_auth_zones_repository (sans importer tout le demarrage du serveur)
    return list(JsonAuthZonesRepository(LocalFilesystem(), project_root / config.paths.auth_zones).load())


def rate_limit_payload(rate_limit: RateLimitConfig) -> dict[str, Any]:
    """Section `waf_filter.rate_limit` (lot 6) : regles de select_rate_limit, deja filtrees par
    effective_source_policies comme au demarrage (start_server) ; reseaux illisibles transmis tels quels (ignores des
    deux cotes). La feuille de style des pages d'erreur n'est jamais comptee (evaluate_waf_request)."""
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


def build_native_snapshot(config: OmegaServConfig, project_root: Path, generation: int) -> dict[str, Any]:
    server = config.server
    security = config.security
    tables = build_routing_tables(config)

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
        "inspect": inspect_section(config, project_root),
        "waf_filter": waf_filter_section(config, project_root),
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
