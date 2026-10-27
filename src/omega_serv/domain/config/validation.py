"""Validation structurelle de la configuration (spec §25.1).

Verifications minimales faisables sans acces au systeme de fichiers ni
au registre de capacites (existence reelle des dossiers, permissions,
disponibilite de PHP-FPM... sont verifiees plus tard, par
application/config/validate_config.py qui a acces aux ports). Ce
module reste pur : aucune I/O, uniquement des regles sur la structure
deja chargee en memoire.

Ne couvre PAS la detection de conflits entre profil/options/exceptions
de zone (spec §6.4, §9.1 "diff avant application") - moteur construit
en Phase 3, une fois le profil/option engine lui-meme existant.
"""
from __future__ import annotations

from omega_serv.core.i18n import _
from omega_serv.domain.config.entities import OmegaServConfig
from omega_serv.domain.config.option import KNOWN_OPTION_NAMES
from omega_serv.domain.routing.access_rule import parse_access_rules, validate_access_rule
from omega_serv.domain.routing.alias import parse_alias_rules, validate_alias_rule
from omega_serv.domain.routing.proxy_zone import parse_proxy_zones, validate_proxy_zone
from omega_serv.domain.routing.redirect import parse_redirect_rules, validate_redirect_rule
from omega_serv.domain.routing.upload_zone import parse_upload_zone_rules, validate_upload_zone_rule
from omega_serv.domain.security.active_defense.config import (
    parse_active_defense_config,
    validate_active_defense_config,
)
from omega_serv.domain.security.tls.validation import validate_tls_config_structure

SUPPORTED_CONFIG_VERSIONS = frozenset({1})

_KNOWN_HTTP_METHOD_TOKENS = frozenset({
    "GET", "HEAD", "POST", "PUT", "DELETE", "OPTIONS", "PATCH",
    "TRACE", "TRACK", "CONNECT",
})

_VALID_CSP_MODES = frozenset({"enforce", "report-only"})
_VALID_COEP_MODES = frozenset({"unsafe-none", "require-corp", "credentialless"})


def is_safe_relative_path(value: str) -> bool:
    """Un chemin de configuration (paths.*) doit rester relatif au
    projet et ne jamais remonter au-dessus de sa racine - regle
    distincte de la resolution de chemin de requete HTTP (voir
    domain/security/path_policy.py), plus simple car lue directement
    depuis un JSON de confiance, pas depuis une URI a decoder."""
    if not value:
        return False
    if value.startswith("/"):
        return False
    if "\x00" in value:
        return False
    segments = value.replace("\\", "/").split("/")
    return ".." not in segments


MAX_WORKERS = 64
"""Borne de surete du mode « boost » ; la vraie limite est le nombre de coeurs de la machine
(core/platform_info.available_cpu_cores), appliquee a l'ecran et au demarrage."""


def validate_config(config: OmegaServConfig) -> list[str]:
    """Valide la structure d'une configuration deja chargee.

    Returns:
        Liste des erreurs (vide si la configuration est valide).
    """
    errors: list[str] = []

    if config.version not in SUPPORTED_CONFIG_VERSIONS:
        errors.append(
            _("version de configuration non supportée : {version} (supportées : {value})").format(version=config.version, value=sorted(SUPPORTED_CONFIG_VERSIONS))
        )

    for field_name, path_value in (
        ("paths.webroot", config.paths.webroot),
        ("paths.logs", config.paths.logs),
        ("paths.uploads", config.paths.uploads),
        ("paths.secure", config.paths.secure),
        ("paths.auth_file", config.paths.auth_file),
        ("paths.auth_zones", config.paths.auth_zones),
        ("paths.waf_script", config.paths.waf_script),
    ):
        if not is_safe_relative_path(path_value):
            errors.append(_("{field_name} doit être un chemin relatif au projet, sans '..' : {path_value!r}").format(field_name=field_name, path_value=path_value))

    if not (1 <= config.server.port <= 65535):
        errors.append(_("server.port hors plage 1-65535 : {port}").format(port=config.server.port))

    if not config.server.bind:
        errors.append(_("server.bind ne peut pas être vide"))

    for field_name, limit_value in (
        ("server.max_connections", config.server.max_connections),
        ("server.max_request_size", config.server.max_request_size),
        ("server.max_header_size", config.server.max_header_size),
        ("server.max_request_line_size", config.server.max_request_line_size),
        ("server.read_timeout_seconds", config.server.read_timeout_seconds),
        ("server.write_timeout_seconds", config.server.write_timeout_seconds),
        ("server.keepalive_timeout_seconds", config.server.keepalive_timeout_seconds),
        ("server.max_keepalive_requests", config.server.max_keepalive_requests),
        ("server.listen_backlog", config.server.listen_backlog),
        ("server.shutdown_grace_period_seconds", config.server.shutdown_grace_period_seconds),
    ):
        if limit_value <= 0:
            errors.append(_("{field_name} doit être strictement positif : {limit_value}").format(field_name=field_name, limit_value=limit_value))

    if not 0 <= config.server.workers <= MAX_WORKERS:
        errors.append(
            _("server.workers doit être compris entre 0 (automatique) et {maximum} : {workers}").format(
                maximum=MAX_WORKERS, workers=config.server.workers,
            )
        )

    unknown_methods = set(config.security.allowed_methods) - _KNOWN_HTTP_METHOD_TOKENS
    if unknown_methods:
        errors.append(_("security.allowed_methods contient des méthodes inconnues : {value}").format(value=sorted(unknown_methods)))

    if config.security.csp_mode not in _VALID_CSP_MODES:
        errors.append(
            _("security.csp_mode invalide : {csp_mode!r} (attendu : {value})").format(csp_mode=config.security.csp_mode, value=sorted(_VALID_CSP_MODES))
        )

    if config.security.coep_mode not in _VALID_COEP_MODES:
        errors.append(
            _("security.coep_mode invalide : {coep_mode!r} (attendu : {value})").format(coep_mode=config.security.coep_mode, value=sorted(_VALID_COEP_MODES))
        )

    for zone in config.security.csp_zones:
        if not zone.path_prefix.startswith("/"):
            errors.append(_("security.csp_zones : path_prefix doit commencer par '/' : {path_prefix!r}").format(path_prefix=zone.path_prefix))
        if not zone.data.strip():
            errors.append(_("security.csp_zones : policy ne peut pas être vide (zone {path_prefix!r})").format(path_prefix=zone.path_prefix))

    unknown_options = set(config.options.keys()) - KNOWN_OPTION_NAMES
    if unknown_options:
        errors.append(_("options inconnues (vérifier l'orthographe ou le périmètre V1) : {value}").format(value=sorted(unknown_options)))

    if config.logs.rotation.max_bytes <= 0:
        errors.append(_("logs.rotation.max_bytes doit être strictement positif"))
    if config.logs.rotation.keep <= 0:
        errors.append(_("logs.rotation.keep doit être strictement positif"))

    aliases_option = config.options.get("aliases")
    if aliases_option is not None and aliases_option.enabled:
        for alias_rule in parse_alias_rules(aliases_option.settings.get("list", [])):
            reason = validate_alias_rule(alias_rule)
            if reason is not None:
                errors.append(_("options.aliases : {reason}").format(reason=reason))

    redirects_option = config.options.get("redirects")
    if redirects_option is not None and redirects_option.enabled:
        for redirect_rule in parse_redirect_rules(redirects_option.settings.get("list", [])):
            reason = validate_redirect_rule(redirect_rule)
            if reason is not None:
                errors.append(_("options.redirects : {reason}").format(reason=reason))

    upload_option = config.options.get("upload")
    if upload_option is not None and upload_option.enabled:
        for upload_rule in parse_upload_zone_rules(upload_option.settings.get("zones", [])):
            reason = validate_upload_zone_rule(upload_rule)
            if reason is not None:
                errors.append(_("options.upload : {reason}").format(reason=reason))
            elif upload_rule.policy.max_file_size_bytes > config.server.max_request_size:
                errors.append(
                    _("options.upload zone {url_prefix!r} : policy.max_file_size_bytes ({max_file_size_bytes}) dépasse server.max_request_size ({max_request_size}) - la zone serait inutilisable pour tout fichier proche de sa propre limite (plan corrigé §9)").format(url_prefix=upload_rule.url_prefix, max_file_size_bytes=upload_rule.policy.max_file_size_bytes, max_request_size=config.server.max_request_size)
                )

    access_control_option = config.options.get("access_control")
    if access_control_option is not None and access_control_option.enabled:
        for access_rule in parse_access_rules(access_control_option.settings.get("list", [])):
            reason = validate_access_rule(access_rule)
            if reason is not None:
                errors.append(_("options.access_control : {reason}").format(reason=reason))

    production_upstreams: set[tuple[str, int]] = set()
    reverse_proxy_option = config.options.get("reverse_proxy")
    if reverse_proxy_option is not None and reverse_proxy_option.enabled:
        for proxy_zone in parse_proxy_zones(reverse_proxy_option.settings.get("zones", [])):
            reason = validate_proxy_zone(proxy_zone)
            if reason is not None:
                errors.append(_("options.reverse_proxy : {reason}").format(reason=reason))
                continue
            for upstream in proxy_zone.upstreams:
                production_upstreams.add((upstream.host, upstream.port))
                if upstream.host in ("127.0.0.1", "localhost", config.server.bind) and upstream.port == config.server.port:
                    errors.append(
                        _("options.reverse_proxy zone {url_prefix!r} : l'upstream ({host}:{port}) pointe vers ce serveur lui-même - boucle de proxy").format(url_prefix=proxy_zone.url_prefix, host=upstream.host, port=upstream.port)
                    )

    active_defense_option = config.options.get("active_defense")
    if active_defense_option is not None and active_defense_option.enabled:
        active_defense_config = parse_active_defense_config(active_defense_option.settings)
        errors.extend(_("options.active_defense : {e}").format(e=e) for e in validate_active_defense_config(active_defense_config))
        for zone_name, decoy_zone in active_defense_config.deception.decoy_zones.items():
            for upstream in decoy_zone.upstreams:
                if (upstream.host, upstream.port) in production_upstreams:
                    errors.append(
                        _("options.active_defense.deception.decoy_zones.{zone_name} : l'upstream ({host}:{port}) est déjà utilisé par une zone options.reverse_proxy de production - un leurre ne doit jamais partager son backend avec la production (plan §\"Routage vers les leurres\")").format(zone_name=zone_name, host=upstream.host, port=upstream.port)
                    )

    errors.extend(
        _("tls : {e}").format(e=e)
        for e in validate_tls_config_structure(
            config.tls.enabled, config.tls.mode, config.tls.min_version, config.tls.max_version,
            config.tls.certificate_path, config.tls.private_key_path,
        )
    )
    if config.security.hsts_enabled and not config.tls.enabled:
        errors.append(_("security.hsts_enabled actif alors que tls.enabled est désactivé (doc TLS §13)"))

    return errors
