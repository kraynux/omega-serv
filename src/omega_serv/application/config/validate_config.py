"""Validations d'environnement (spec §25.1) qui exigent un acces
filesystem reel - distinctes de domain/config/validation.py (purement
structurel, sans I/O). Ces deux validateurs sont complementaires et
executes l'un apres l'autre par les futures commandes CLI
(`omega-serv config check`, Phase 3) : structurel d'abord (rapide,
sans effet de bord), environnement ensuite (necessite le disque)."""
from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

from omega_serv.application.server.start_server import resolve_magnet_paths
from omega_serv.core.i18n import _
from omega_serv.domain.config.entities import OmegaServConfig
from omega_serv.domain.routing.alias import parse_alias_rules
from omega_serv.domain.routing.fastcgi_zone import (
    parse_fastcgi_config,
    validate_fastcgi_config_structure,
)
from omega_serv.domain.routing.proxy_zone import parse_proxy_zones
from omega_serv.domain.routing.redirect import parse_redirect_rules
from omega_serv.domain.routing.rewrite import parse_rewrite_rules
from omega_serv.domain.routing.upload_zone import parse_upload_zone_rules
from omega_serv.domain.security.auth.exceptions import AuthZonesFileError, UsersFileError
from omega_serv.domain.security.auth.zones import validate_auth_zone
from omega_serv.domain.security.tls.exceptions import CertificateToolError
from omega_serv.domain.security.tls.validation import TlsStartupFacts, validate_tls_startup
from omega_serv.domain.security.waf.config import parse_waf_config, validate_waf_config
from omega_serv.domain.security.waf.exceptions import WafRuleLoadError, WafRuleValidationError
from omega_serv.domain.security.waf.keyword_list import (
    analyze_path_list_text,
    find_route_conflicts,
    is_excepted,
    is_suffix_entry,
)
from omega_serv.domain.security.waf.shared_counters import shared_recidive_errors
from omega_serv.infrastructure.waf.keyword_list_loader import load_keyword_list
from omega_serv.infrastructure.waf.lua_waf_adapter import WafMagnetScriptError, load_lua_waf_adapter
from omega_serv.infrastructure.waf.rule_pack_loader import load_rule_pack
from omega_serv.ports.certificate_tool_port import CertificateToolPort
from omega_serv.ports.filesystem_port import FilesystemPort

_LOCAL_BIND_HOSTS = frozenset({"127.0.0.1", "::1", "localhost"})


def validate_config_environment(
    config: OmegaServConfig,
    filesystem: FilesystemPort,
    project_root: Path,
    certificate_tool: CertificateToolPort | None = None,
    self_signed_public_bind_confirmed: bool = False,
    auth_without_tls_confirmed: bool = False,
) -> list[str]:
    """Verifie que les chemins declares existent ou sont creables, et
    que webroot ne contient pas accidentellement les repertoires
    sensibles (spec §4.2 : secure/, config/, var/log/, var/run/,
    var/backups/, src/ jamais accessibles depuis HTTP)."""
    errors: list[str] = []

    webroot = (project_root / config.paths.webroot).resolve()
    if not filesystem.is_dir(webroot):
        errors.append(_("paths.webroot n'est pas un dossier existant : {webroot}").format(webroot=webroot))

    secure_dir = (project_root / config.paths.secure).resolve()
    try:
        secure_dir.relative_to(webroot)
        errors.append(
            _("paths.secure ({secure_dir}) est à l'intérieur de paths.webroot ({webroot}) - ne doit jamais être accessible depuis HTTP (spec §4.2)").format(secure_dir=secure_dir, webroot=webroot)
        )
    except ValueError:
        pass  # secure_dir hors webroot, c'est la situation attendue

    auth_file = (project_root / config.paths.auth_file).resolve()
    try:
        auth_file.relative_to(webroot)
        errors.append(_("paths.auth_file ({auth_file}) est à l'intérieur de paths.webroot - interdit (spec §4.2)").format(auth_file=auth_file))
    except ValueError:
        pass

    waf_option = config.options.get("waf")
    if waf_option is not None and waf_option.enabled:
        errors.extend(
            _validate_waf_environment(waf_option.settings, filesystem, project_root, config.paths.waf_script, config)
        )

    if config.tls.enabled and config.tls.mode == "direct":
        errors.extend(_validate_tls_environment(config, filesystem, project_root, certificate_tool, self_signed_public_bind_confirmed))

    auth_option = config.options.get("auth")
    if auth_option is not None and auth_option.enabled:
        errors.extend(_validate_auth_environment(config, filesystem, project_root, auth_without_tls_confirmed))

    fastcgi_option = config.options.get("fastcgi")
    if fastcgi_option is not None and fastcgi_option.enabled:
        errors.extend(_validate_fastcgi_environment(fastcgi_option.settings, filesystem, project_root, config.paths.webroot))

    upload_option = config.options.get("upload")
    if upload_option is not None and upload_option.enabled:
        errors.extend(_validate_upload_environment(upload_option.settings, filesystem, project_root))

    return errors


def _validate_upload_environment(settings: dict, filesystem: FilesystemPort, project_root: Path) -> list[str]:
    """Verifie que chaque storage_path declare ne collisionne pas avec
    un fichier existant - le repertoire lui-meme est cree a la volee au
    premier upload (infrastructure/upload/filesystem_upload_storage.py),
    pas une precondition bloquante comme fastcgi.script_root (qui doit
    deja exister car il contient du code source a executer)."""
    errors: list[str] = []
    for rule in parse_upload_zone_rules(settings.get("zones", [])):
        storage_dir = project_root / rule.storage_path
        if filesystem.exists(storage_dir) and not filesystem.is_dir(storage_dir):
            errors.append(
                _("options.upload zone {url_prefix!r} : storage_path existe déjà et n'est pas un dossier : {storage_dir}").format(url_prefix=rule.url_prefix, storage_dir=storage_dir)
            )
    return errors


def _validate_fastcgi_environment(
    settings: dict,
    filesystem: FilesystemPort,
    project_root: Path,
    webroot_relative: str,
) -> list[str]:
    """Porte bloquante (plan de developpement §6) : script_root doit
    resoudre HORS webroot - propriete de securite structurelle : le
    handler statique ne peut alors jamais divulguer le code source PHP,
    meme si FastCGI est mal configure ou indisponible."""
    errors: list[str] = []
    fastcgi_config = parse_fastcgi_config(settings)
    errors.extend(_("options.fastcgi : {e}").format(e=e) for e in validate_fastcgi_config_structure(fastcgi_config))
    if not fastcgi_config.script_root:
        return errors

    webroot = (project_root / webroot_relative).resolve()
    script_root = (project_root / fastcgi_config.script_root).resolve()
    try:
        script_root.relative_to(webroot)
        errors.append(
            _("options.fastcgi.script_root ({script_root}) est à l'intérieur de paths.webroot ({webroot}) - interdit structurellement (spec §21, plan de développement §6)").format(script_root=script_root, webroot=webroot)
        )
    except ValueError:
        pass

    if not filesystem.is_dir(script_root):
        errors.append(_("options.fastcgi.script_root n'est pas un dossier existant : {script_root}").format(script_root=script_root))

    socket_path = project_root / fastcgi_config.socket_path
    if not filesystem.exists(socket_path):
        errors.append(_("options.fastcgi.socket_path introuvable : {socket_path} (PHP-FPM démarré ?)").format(socket_path=socket_path))

    return errors


def _validate_auth_environment(
    config: OmegaServConfig,
    filesystem: FilesystemPort,
    project_root: Path,
    auth_without_tls_confirmed: bool,
) -> list[str]:
    """Verifie l'environnement Auth (spec §15) : structure des zones
    deja ecrites sur disque (validate_auth_zone ne peut etre appele
    qu'apres lecture du fichier reel), et la porte bloquante "Basic Auth
    expose sans TLS ni reverse-proxy declare" (spec §15.6 : "en acces
    distant, Basic Auth doit etre utilisee uniquement sous HTTPS")."""
    errors: list[str] = []

    tls_effectively_covered = config.tls.enabled or config.tls.mode == "behind_proxy"
    if config.server.bind not in _LOCAL_BIND_HOSTS and not tls_effectively_covered and not auth_without_tls_confirmed:
        errors.append(
            _("options.auth actif avec un bind non local, sans TLS direct actif ni mode 'behind_proxy' déclaré "
            "- Basic Auth transmettrait des identifiants en clair (spec §15.6, doc TLS §22)")
        )

    zones_path = project_root / config.paths.auth_zones
    if not filesystem.exists(zones_path):
        return errors

    from omega_serv.infrastructure.auth.auth_zones_repository import JsonAuthZonesRepository
    try:
        zones = JsonAuthZonesRepository(filesystem, zones_path).load()
    except AuthZonesFileError as e:
        errors.append(_("paths.auth_zones : {e}").format(e=e))
        return errors

    for zone in zones:
        reason = validate_auth_zone(zone)
        if reason is not None:
            errors.append(_("paths.auth_zones : {reason}").format(reason=reason))

    users_path = project_root / config.paths.auth_file
    if filesystem.exists(users_path):
        from omega_serv.infrastructure.auth.users_repository import JsonUsersRepository
        try:
            users = JsonUsersRepository(filesystem, users_path).load()
        except UsersFileError as e:
            errors.append(_("paths.auth_file : {e}").format(e=e))
            return errors
        known_usernames = {u.username for u in users}
        for zone in zones:
            unknown = set(zone.allowed_users) - known_usernames
            if unknown:
                errors.append(_("paths.auth_zones : zone {path_prefix!r} référence des utilisateurs inconnus : {value}").format(path_prefix=zone.path_prefix, value=sorted(unknown)))

    return errors


def _validate_tls_environment(
    config: OmegaServConfig,
    filesystem: FilesystemPort,
    project_root: Path,
    certificate_tool: CertificateToolPort | None,
    self_signed_public_bind_confirmed: bool,
) -> list[str]:
    """Verifie les portes de demarrage TLS bloquantes (plan de
    developpement §6) qui exigent des fichiers reels : permissions de
    la cle, correspondance cle/certificat, expiration, auto-signe+bind
    public. La validation structurelle pure (mode/versions/chemins non
    vides) est deja faite par domain/config/validation.py::validate_config."""
    cert_path = project_root / config.tls.certificate_path
    key_path = project_root / config.tls.private_key_path

    if not filesystem.exists(cert_path):
        return [_("tls.certificate.certificate_path introuvable : {cert_path}").format(cert_path=cert_path)]
    if not filesystem.exists(key_path):
        return [_("tls.certificate.private_key_path introuvable : {key_path}").format(key_path=key_path)]

    webroot = (project_root / config.paths.webroot).resolve()
    for label, path in (("certificate_path", cert_path.resolve()), ("private_key_path", key_path.resolve())):
        try:
            path.relative_to(webroot)
            return [_("tls.certificate.{label} ({path}) est à l'intérieur de paths.webroot - interdit (doc TLS §9.1)").format(label=label, path=path)]
        except ValueError:
            pass

    if certificate_tool is None:
        from omega_serv.infrastructure.process.subprocess_runner import SubprocessRunner
        from omega_serv.infrastructure.tls.openssl_certificate_tool import OpensslCertificateTool
        certificate_tool = OpensslCertificateTool(SubprocessRunner())

    try:
        certificate_info = certificate_tool.inspect_certificate(cert_path)
        keys_match = certificate_tool.keys_match(key_path, cert_path)
    except CertificateToolError as e:
        return [_("tls : {e}").format(e=e)]

    facts = TlsStartupFacts(
        tls_enabled=config.tls.enabled,
        tls_mode=config.tls.mode,
        bind_host=config.server.bind,
        private_key_mode=filesystem.file_mode(key_path),
        certificate_info=certificate_info,
        keys_match=keys_match,
        hsts_enabled=config.security.hsts_enabled,
        self_signed_public_bind_confirmed=self_signed_public_bind_confirmed,
        now=datetime.now(timezone.utc),
    )
    return validate_tls_startup(facts)


def _collect_site_routes(
    config: OmegaServConfig, filesystem: FilesystemPort, project_root: Path,
) -> tuple[tuple[str, str], ...]:
    """Toutes les routes que le site sert reellement, hors fichiers du
    webroot (OMEGA-SERV_PLAN-DETAILLE_SENSITIVE_PATHS.md, recensement 1.0) :
    aliases, redirections, reecritures, zones de reverse proxy, zones
    d'upload, FastCGI, zones Auth. Seules les options ACTIVES comptent."""
    routes: list[tuple[str, str]] = []

    def settings_of(name: str) -> dict | None:
        option = config.options.get(name)
        return option.settings if option is not None and option.enabled else None

    if (aliases := settings_of("aliases")) is not None:
        routes += [("aliases", r.url_prefix) for r in parse_alias_rules(aliases.get("list", []))]
    if (redirects := settings_of("redirects")) is not None:
        routes += [("redirects", r.url_prefix) for r in parse_redirect_rules(redirects.get("list", []))]
    if (rewrites := settings_of("rewrites")) is not None:
        routes += [("rewrites", r.match_prefix) for r in parse_rewrite_rules(rewrites.get("list", []))]
    if (proxy := settings_of("reverse_proxy")) is not None:
        routes += [("reverse_proxy", z.url_prefix) for z in parse_proxy_zones(proxy.get("zones", []))]
    if (upload := settings_of("upload")) is not None:
        routes += [("upload", z.url_prefix) for z in parse_upload_zone_rules(upload.get("zones", []))]
    if (fastcgi := settings_of("fastcgi")) is not None:
        routes.append(("fastcgi", parse_fastcgi_config(fastcgi).url_prefix))
    if settings_of("auth") is not None:
        zones_path = project_root / config.paths.auth_zones
        if filesystem.exists(zones_path):
            from omega_serv.infrastructure.auth.auth_zones_repository import JsonAuthZonesRepository
            try:
                routes += [("auth", z.path_prefix) for z in JsonAuthZonesRepository(filesystem, zones_path).load()]
            except AuthZonesFileError:
                pass  # deja signale par _validate_auth_environment
    return tuple(routes)


def _route_conflict_errors(
    list_id: str, anchor: str, text: str, config: OmegaServConfig, filesystem: FilesystemPort, project_root: Path,
) -> list[str]:
    """Garde-fou §3.10-2 : une liste qui BLOQUE seule (poids >= seuil, hors
    observation) ne doit jamais toucher une route reellement servie. Pour
    le webroot, seul le chemin exact de l'entree est verifie (un parcours
    complet serait trop lent sur un gros site) - le rejeu des logs reels
    de l'editeur integre couvre les cas plus profonds."""
    analysis = analyze_path_list_text(text, anchor)
    entries, exceptions = analysis.entries, analysis.exceptions
    prefix = f"options.waf.rules.keyword_lists[{list_id!r}]"
    errors = [
        _("{prefix} : l'entrée {entry!r} bloquerait la route {route!r} ({source}) - ajouter une exception '!' ou passer la liste en observation").format(prefix=prefix, entry=c.entry, route=c.route, source=c.source)
        for c in find_route_conflicts(
            entries, anchor, _collect_site_routes(config, filesystem, project_root), exceptions,
        )
    ]
    webroot = project_root / config.paths.webroot
    for entry in entries:
        relative = entry.strip("/")
        if (
            relative and not is_suffix_entry(entry) and filesystem.exists(webroot / relative)
            and not is_excepted("/" + relative, exceptions, anchor)
        ):
            errors.append(
                _("{prefix} : l'entrée {entry!r} bloquerait {relative!r}, qui existe dans le webroot - ajouter une exception '!' ou retirer l'entrée").format(prefix=prefix, entry=entry, relative=relative)
            )
    return errors


def _validate_waf_environment(
    settings: dict,
    filesystem: FilesystemPort,
    project_root: Path,
    default_waf_script: str,
    config: OmegaServConfig | None = None,
) -> list[str]:
    """Verifie que les packs de regles configures existent reellement
    et sont chargeables - la validation structurelle pure
    (domain/security/waf/config.py::validate_waf_config) ne peut pas le
    savoir, elle n'a pas acces au disque."""
    errors: list[str] = []
    waf_config = parse_waf_config(settings)
    errors.extend(_("options.waf : {e}").format(e=e) for e in validate_waf_config(waf_config))
    if config is not None and config.server.workers != 1:
        errors.extend(shared_recidive_errors(waf_config))

    for relative_path in waf_config.rule_paths:
        path = project_root / relative_path
        try:
            load_rule_pack(filesystem, path)
        except (WafRuleLoadError, WafRuleValidationError) as e:
            errors.append(_("options.waf.rules.paths : {e}").format(e=e))

    for definition in waf_config.keyword_lists:
        path = project_root / definition.file
        try:
            load_keyword_list(filesystem, definition, path)
        except WafRuleLoadError as e:
            errors.append(_("options.waf.rules.keyword_lists[{id!r}] : {e}").format(id=definition.id, e=e))
            continue
        blocks_on_its_own = (
            definition.enabled and not definition.observe_only
            and definition.weight >= waf_config.scoring.block_threshold
        )
        if config is not None and definition.match == "path" and blocks_on_its_own:
            errors.extend(_route_conflict_errors(definition.id, definition.anchor, filesystem.read_text(path),
                                                 config, filesystem, project_root))

    if waf_config.magnet.enabled:
        script_path = project_root / (waf_config.magnet.script or default_waf_script)
        resolved_paths = resolve_magnet_paths(project_root, waf_config.magnet.paths)
        try:
            load_lua_waf_adapter(filesystem, script_path, waf_config, resolved_paths)
        except WafMagnetScriptError as e:
            errors.append(_("options.waf.magnet : {e}").format(e=e))
        except ImportError:
            errors.append(
                _("options.waf.magnet : dépendance 'lupa' absente - installer l'extra optionnel "
                "avec `pip install -e \".[magnet]\"` (jamais installé par défaut, voir pyproject.toml)")
            )

    return errors
