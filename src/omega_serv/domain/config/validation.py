# Copyright (c) 2026 kraynux - kraynux@proton.me - Licence MIT (voir fichier LICENSE)
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


def validate_config(config: OmegaServConfig) -> list[str]:
    """Valide la structure d'une configuration deja chargee.

    Returns:
        Liste des erreurs (vide si la configuration est valide).
    """
    errors: list[str] = []

    if config.version not in SUPPORTED_CONFIG_VERSIONS:
        errors.append(
            f"version de configuration non supportee : {config.version} "
            f"(supportees : {sorted(SUPPORTED_CONFIG_VERSIONS)})"
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
            errors.append(f"{field_name} doit etre un chemin relatif au projet, sans '..' : {path_value!r}")

    if not (1 <= config.server.port <= 65535):
        errors.append(f"server.port hors plage 1-65535 : {config.server.port}")

    if not config.server.bind:
        errors.append("server.bind ne peut pas etre vide")

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
            errors.append(f"{field_name} doit etre strictement positif : {limit_value}")

    unknown_methods = set(config.security.allowed_methods) - _KNOWN_HTTP_METHOD_TOKENS
    if unknown_methods:
        errors.append(f"security.allowed_methods contient des methodes inconnues : {sorted(unknown_methods)}")

    if config.security.csp_mode not in _VALID_CSP_MODES:
        errors.append(
            f"security.csp_mode invalide : {config.security.csp_mode!r} "
            f"(attendu : {sorted(_VALID_CSP_MODES)})"
        )

    unknown_options = set(config.options.keys()) - KNOWN_OPTION_NAMES
    if unknown_options:
        errors.append(f"options inconnues (verifier l'orthographe ou le perimetre V1) : {sorted(unknown_options)}")

    if config.logs.rotation.max_bytes <= 0:
        errors.append("logs.rotation.max_bytes doit etre strictement positif")
    if config.logs.rotation.keep <= 0:
        errors.append("logs.rotation.keep doit etre strictement positif")

    aliases_option = config.options.get("aliases")
    if aliases_option is not None and aliases_option.enabled:
        for alias_rule in parse_alias_rules(aliases_option.settings.get("list", [])):
            reason = validate_alias_rule(alias_rule)
            if reason is not None:
                errors.append(f"options.aliases : {reason}")

    redirects_option = config.options.get("redirects")
    if redirects_option is not None and redirects_option.enabled:
        for redirect_rule in parse_redirect_rules(redirects_option.settings.get("list", [])):
            reason = validate_redirect_rule(redirect_rule)
            if reason is not None:
                errors.append(f"options.redirects : {reason}")

    upload_option = config.options.get("upload")
    if upload_option is not None and upload_option.enabled:
        for upload_rule in parse_upload_zone_rules(upload_option.settings.get("zones", [])):
            reason = validate_upload_zone_rule(upload_rule)
            if reason is not None:
                errors.append(f"options.upload : {reason}")
            elif upload_rule.policy.max_file_size_bytes > config.server.max_request_size:
                errors.append(
                    f"options.upload zone {upload_rule.url_prefix!r} : policy.max_file_size_bytes "
                    f"({upload_rule.policy.max_file_size_bytes}) depasse server.max_request_size "
                    f"({config.server.max_request_size}) - la zone serait inutilisable pour "
                    "tout fichier proche de sa propre limite (plan corrige §9)"
                )

    access_control_option = config.options.get("access_control")
    if access_control_option is not None and access_control_option.enabled:
        for access_rule in parse_access_rules(access_control_option.settings.get("list", [])):
            reason = validate_access_rule(access_rule)
            if reason is not None:
                errors.append(f"options.access_control : {reason}")

    production_upstreams: set[tuple[str, int]] = set()
    reverse_proxy_option = config.options.get("reverse_proxy")
    if reverse_proxy_option is not None and reverse_proxy_option.enabled:
        for proxy_zone in parse_proxy_zones(reverse_proxy_option.settings.get("zones", [])):
            reason = validate_proxy_zone(proxy_zone)
            if reason is not None:
                errors.append(f"options.reverse_proxy : {reason}")
                continue
            for upstream in proxy_zone.upstreams:
                production_upstreams.add((upstream.host, upstream.port))
                if upstream.host in ("127.0.0.1", "localhost", config.server.bind) and upstream.port == config.server.port:
                    # Retour utilisateur 2026-09-11 (OMEGA-SERV_PLAN-DETAILLE_
                    # REVERSE_PROXY.md §5.4) : une zone pointant vers le
                    # serveur lui-meme creerait une boucle infinie/
                    # amplification - detectee ici, jamais decouverte
                    # seulement au runtime. Verifie sur CHAQUE upstream
                    # (phase 2, repartition de charge) - un seul upstream
                    # en boucle suffit a etre bloquant, pas seulement le
                    # premier de la liste.
                    errors.append(
                        f"options.reverse_proxy zone {proxy_zone.url_prefix!r} : l'upstream "
                        f"({upstream.host}:{upstream.port}) pointe vers ce serveur lui-meme - boucle de proxy"
                    )

    active_defense_option = config.options.get("active_defense")
    if active_defense_option is not None and active_defense_option.enabled:
        active_defense_config = parse_active_defense_config(active_defense_option.settings)
        errors.extend(f"options.active_defense : {e}" for e in validate_active_defense_config(active_defense_config))
        # plan_active_defense_omega_serv.md, Phase 5, "Routage vers les
        # leurres" : "ajouter une verification empechant qu'une zone
        # reverse_proxy de production soit accidentellement reutilisee
        # comme cible de deception" - les zones leurres (Niveau 2) vivent
        # deja dans un espace de configuration separe (jamais lues
        # depuis options.reverse_proxy, voir DeceptionConfig.decoy_zones),
        # donc aucune collision de NOM n'est possible par construction ;
        # le risque reel qui reste est de pointer un leurre vers le MEME
        # backend physique (host:port) qu'une zone de production deja
        # declaree - verifie ici, le seul endroit qui voit les deux
        # configurations a la fois.
        for zone_name, decoy_zone in active_defense_config.deception.decoy_zones.items():
            for upstream in decoy_zone.upstreams:
                if (upstream.host, upstream.port) in production_upstreams:
                    errors.append(
                        f"options.active_defense.deception.decoy_zones.{zone_name} : l'upstream "
                        f"({upstream.host}:{upstream.port}) est deja utilise par une zone "
                        "options.reverse_proxy de production - un leurre ne doit jamais partager "
                        "son backend avec la production (plan §\"Routage vers les leurres\")"
                    )

    errors.extend(
        f"tls : {e}"
        for e in validate_tls_config_structure(
            config.tls.enabled, config.tls.mode, config.tls.min_version, config.tls.max_version,
            config.tls.certificate_path, config.tls.private_key_path,
        )
    )
    if config.security.hsts_enabled and not config.tls.enabled:
        errors.append("security.hsts_enabled actif alors que tls.enabled est desactive (doc TLS §13)")

    return errors
