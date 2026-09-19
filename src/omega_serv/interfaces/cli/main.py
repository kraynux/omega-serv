"""CLI non-interactive OMEGA-SERV (spec §31).

Chaque commande appelle directement un cas d'usage d'application/ via
le conteneur de dependances - n'appelle jamais subprocess/filesystem
directement (charte §2.3 : "interfaces/ ne doit jamais appeler
directement subprocess", etendu ici a toute I/O reelle). Un futur menu
interactif (Textual) pourra habiller ces memes commandes sans dupliquer
leur logique (spec §31 : "toute action TUI reste scriptable et
testable via CLI non interactive").
"""
from __future__ import annotations

import argparse
import asyncio
import getpass
import json
import os
import signal
import sys
from collections.abc import Callable
from datetime import timedelta
from pathlib import Path
from typing import cast

from omega_serv.application.active_defense.manage_deception import release_deception
from omega_serv.application.active_defense.manage_incidents import close_incident
from omega_serv.application.active_defense.preview_playbook_decision import (
    preview_playbook_decision,
)
from omega_serv.application.active_defense.queries import (
    get_incident_timeline,
    get_threat_state,
    list_incidents,
    list_threat_states,
)
from omega_serv.application.active_defense.sweep_active_defense import sweep_active_defense
from omega_serv.application.auth.manage_users import add_user, change_password, remove_user
from omega_serv.application.auth.manage_zones import add_zone, remove_zone
from omega_serv.application.config.apply_profile import plan_profile_application
from omega_serv.application.config.generate_config import generate_default_config
from omega_serv.application.config.load_config import load_config
from omega_serv.application.config.manage_option import set_option_enabled
from omega_serv.application.config.validate_config import validate_config_environment
from omega_serv.application.security.manage_blocklist import (
    add_blocklist_entry,
    remove_blocklist_entry,
)
from omega_serv.application.security.run_audit import run_audit
from omega_serv.application.security.simulate_waf_request import simulate_waf_request
from omega_serv.application.server.simulate_request import simulate_request
from omega_serv.application.server.start_server import (
    ActiveDefenseCollaborators,
    build_active_defense_collaborators,
    build_auth_zones_repository,
    build_blocklist_port,
    build_server,
    build_users_repository,
    build_waf_collaborators,
    reload_server,
)
from omega_serv.application.services.install_service import (
    install_systemd_service,
    uninstall_systemd_service,
)
from omega_serv.application.services.manage_service import (
    ManageServiceResult,
    disable_service,
    enable_service,
    get_service_status,
    reload_service,
    restart_service,
    start_service,
    stop_service,
)
from omega_serv.application.services.pid_file import remove_pid_file, write_pid_file
from omega_serv.application.tls.generate_ca_certificate import generate_ca_certificate
from omega_serv.application.tls.generate_certificate_signing_request import (
    generate_certificate_signing_request,
)
from omega_serv.application.tls.generate_self_signed import generate_self_signed_certificate
from omega_serv.application.tls.import_certificate import import_certificate
from omega_serv.application.tls.inspect_certificate import (
    CertificateReport,
    inspect_certificate_report,
)
from omega_serv.application.tls.revoke_certificate import revoke_certificate
from omega_serv.application.tls.sign_certificate_signing_request import (
    sign_certificate_signing_request,
)
from omega_serv.bootstrap.container import DependencyContainer
from omega_serv.bootstrap.paths import CONFIG_FILE
from omega_serv.core.platform_info import running_as_root
from omega_serv.domain.config.entities import OmegaServConfig
from omega_serv.domain.config.exceptions import ProfileLoadError, ProfileNotFoundError
from omega_serv.domain.persistence.backup import BackupRequest
from omega_serv.domain.security.active_defense.entities import IncidentFilters
from omega_serv.domain.security.active_defense.policies import hash_payload, is_assignment_active
from omega_serv.domain.security.active_defense.value_objects import (
    KNOWN_ATTACK_CLASSES,
    AttackClass,
)
from omega_serv.domain.security.audit.entities import AuditFinding, Severity, severity_at_least
from omega_serv.domain.security.auth.entities import AuthZone
from omega_serv.domain.security.tls.entities import CaParams, CsrParams, SelfSignedCertParams
from omega_serv.domain.security.tls.exceptions import CertificateToolError
from omega_serv.domain.services.entities import ServiceStatus
from omega_serv.domain.services.systemd_unit import SystemdUnitParams
from omega_serv.infrastructure.exporters.csv_ioc_exporter import CsvIoCExporter
from omega_serv.infrastructure.exporters.json_ioc_exporter import JsonIoCExporter
from omega_serv.infrastructure.exporters.markdown_incident_report_exporter import (
    MarkdownIncidentReportExporter,
)
from omega_serv.infrastructure.fastcgi.asyncio_fastcgi_client import AsyncioFastCgiClient
from omega_serv.infrastructure.filesystem.safe_path_resolver import SafePathResolver
from omega_serv.infrastructure.process.subprocess_runner import SubprocessRunner
from omega_serv.infrastructure.services.detector import detect_service_manager_type
from omega_serv.infrastructure.services.openrc_service_manager import OpenRCServiceManager
from omega_serv.infrastructure.services.runit_service_manager import RunitServiceManager
from omega_serv.infrastructure.services.systemd_service_manager import SystemdServiceManager
from omega_serv.infrastructure.tls.openssl_certificate_tool import OpensslCertificateTool
from omega_serv.ports.ioc_exporter_port import IoCExporterPort
from omega_serv.ports.service_manager_port import ServiceManagerPort


def _print_errors(errors: list[str], prefix: str = "Erreur") -> None:
    for error in errors:
        print(f"{prefix} : {error}", file=sys.stderr)


async def run_server_until_stopped(config: OmegaServConfig, config_path: Path, container: DependencyContainer) -> int:
    """Coeur bloquant partage entre `cmd_serve` (CLI) et le bouton
    "Lancer maintenant" de l'assistant premier lancement
    (interfaces/tui/screens/wizard_service_screen.py, retour utilisateur
    2026-09-09) - jamais duplique. `cmd_serve` enveloppe cet appel dans
    `asyncio.run()` (nouvelle boucle dediee, comportement CLI habituel) ;
    la TUI l'attend directement sur SA PROPRE boucle deja active,
    puisque `App.suspend()` ne suspend jamais la boucle asyncio de
    Textual elle-meme (seulement le pilote du terminal) - imbriquer un
    second `asyncio.run()` a l'interieur d'un gestionnaire Textual leve
    `RuntimeError: asyncio.run() cannot be called from a running event
    loop`, verifie empiriquement en testant ce bouton avant d'ecrire ce
    commentaire."""
    pid_path = container.project_root / "var" / "run" / "omega-serv.pid"
    server = build_server(config, container.project_root, container.filesystem, container.logger, container.clock)

    try:
        await server.start()
    except PermissionError:
        print(
            f"Erreur : liaison sur {config.server.bind}:{config.server.port} refusee "
            "(privileges insuffisants pour un port < 1024). Solutions : choisir un port >= 1024 "
            "(un reverse proxy peut ensuite exposer le 80/443), ou accorder CAP_NET_BIND_SERVICE "
            "au service systeme (voir Service dans l'interface / plan de developpement §6).",
            file=sys.stderr,
        )
        return 1
    except OSError as e:
        print(f"Erreur au demarrage du serveur : {e}", file=sys.stderr)
        return 1

    write_pid_file(container.filesystem, pid_path, os.getpid())
    print(f"OMEGA-SERV a l'ecoute sur {config.server.bind}:{config.server.port}")

    stop_event = asyncio.Event()

    async def _graceful_stop() -> None:
        print("Arret demande - drainage des connexions en cours...")
        forced = await server.shutdown(config.server.shutdown_grace_period_seconds)
        if forced:
            print(f"{forced} connexion(s) fermee(s) de force apres le delai de grace.", file=sys.stderr)
        stop_event.set()

    async def _reload() -> None:
        print("Rechargement demande (SIGHUP) - regles WAF et zones Auth uniquement, bind/port/TLS inchanges...")
        reload_result = load_config(container.configuration, config_path)
        if not reload_result.success:
            _print_errors(reload_result.errors, "Erreur de rechargement")
            return
        reloaded_config = reload_result.config
        assert reloaded_config is not None
        reload_server(server, reloaded_config, container.project_root, container.filesystem, container.clock)
        print("Rechargement termine.")

    loop = asyncio.get_running_loop()
    loop.add_signal_handler(signal.SIGTERM, lambda: asyncio.ensure_future(_graceful_stop()))
    loop.add_signal_handler(signal.SIGINT, lambda: asyncio.ensure_future(_graceful_stop()))
    loop.add_signal_handler(signal.SIGHUP, lambda: asyncio.ensure_future(_reload()))

    try:
        serve_task = asyncio.ensure_future(server.serve_forever())
        await stop_event.wait()
        serve_task.cancel()
        try:
            await serve_task
        except asyncio.CancelledError:
            pass
    finally:
        remove_pid_file(container.filesystem, pid_path)
        loop.remove_signal_handler(signal.SIGTERM)
        loop.remove_signal_handler(signal.SIGINT)
        loop.remove_signal_handler(signal.SIGHUP)

    return 0


def cmd_serve(args: argparse.Namespace, container: DependencyContainer) -> int:
    if running_as_root():
        print("Erreur : OMEGA-SERV refuse de demarrer en tant que root (voir plan de developpement §6).", file=sys.stderr)
        return 1

    result = load_config(container.configuration, args.config)
    if not result.success:
        _print_errors(result.errors)
        return 1
    assert result.config is not None

    env_errors = validate_config_environment(
        result.config, container.filesystem, container.project_root,
        self_signed_public_bind_confirmed=args.confirm_self_signed_public_bind,
        auth_without_tls_confirmed=args.confirm_auth_without_tls,
    )
    if env_errors:
        _print_errors(env_errors, "Erreur d'environnement")
        return 1

    async def _run() -> int:
        config = result.config
        assert config is not None
        return await run_server_until_stopped(config, args.config, container)

    try:
        return asyncio.run(_run())
    except KeyboardInterrupt:
        return 0


def cmd_config_init(args: argparse.Namespace, container: DependencyContainer) -> int:
    result = generate_default_config(container.configuration, container.filesystem, args.config, force=args.force)
    print(result.message)
    return 0 if result.success else 1


def cmd_config_check(args: argparse.Namespace, container: DependencyContainer) -> int:
    result = load_config(container.configuration, args.config)
    if not result.success:
        _print_errors(result.errors, "Erreur de configuration")
        return 1
    assert result.config is not None

    env_errors = validate_config_environment(
        result.config, container.filesystem, container.project_root,
        self_signed_public_bind_confirmed=args.confirm_self_signed_public_bind,
        auth_without_tls_confirmed=args.confirm_auth_without_tls,
    )
    if env_errors:
        _print_errors(env_errors, "Erreur d'environnement")
        return 1

    print(f"{args.config} : configuration valide.")
    return 0


def cmd_config_show(args: argparse.Namespace, container: DependencyContainer) -> int:
    result = load_config(container.configuration, args.config)
    if not result.success:
        _print_errors(result.errors)
        return 1
    assert result.config is not None
    print(json.dumps(result.config.to_dict(), indent=2, ensure_ascii=False))
    return 0


def cmd_config_backup(args: argparse.Namespace, container: DependencyContainer) -> int:
    result = load_config(container.configuration, args.config)
    if not result.success or result.config is None:
        _print_errors(result.errors, "Erreur de configuration")
        return 1

    request = BackupRequest(
        include_waf_rules=args.include_waf,
        include_auth_zones=args.include_auth,
        include_certificates=args.include_certificates,
        include_active_defense=args.include_active_defense,
        description=args.description,
    )
    if (request.include_auth_zones or request.include_certificates) and not args.confirm_secrets:
        print(
            "Cette sauvegarde inclurait des secrets reels (hash de mot de passe et/ou "
            "cle privee TLS) jamais chiffres par defaut - ajoutez --confirm-secrets pour confirmer.",
            file=sys.stderr,
        )
        return 1

    backup_result = container.create_backup(request, result.config, args.config)
    print(backup_result.message)
    return 0 if backup_result.success else 1


def cmd_config_restore(args: argparse.Namespace, container: DependencyContainer) -> int:
    restore_result = container.restore_backup(args.snapshot_id)
    print(restore_result.message)
    return 0 if restore_result.success else 1


def cmd_config_list_backups(args: argparse.Namespace, container: DependencyContainer) -> int:
    backups = container.list_backups()
    if not backups:
        print("Aucune sauvegarde.")
        return 0
    for metadata in backups:
        size_kb = (metadata.file_size_bytes or 0) / 1024
        print(
            f"{metadata.snapshot_id}  {metadata.created_at.isoformat()}  "
            f"{metadata.scope:<20}  {size_kb:.1f} Ko  {metadata.status.value}  {metadata.description}"
        )
    return 0


def cmd_profile_list(args: argparse.Namespace, container: DependencyContainer) -> int:
    for name in container.profiles.list_profile_names():
        print(name)
    return 0


def cmd_profile_show(args: argparse.Namespace, container: DependencyContainer) -> int:
    try:
        profile = container.profiles.load_profile(args.name)
    except (ProfileNotFoundError, ProfileLoadError) as e:
        print(f"Erreur : {e}", file=sys.stderr)
        return 1
    print(f"Profil : {profile.name}")
    print(profile.description)
    print(json.dumps(profile.values, indent=2, ensure_ascii=False))
    return 0


def cmd_profile_apply(args: argparse.Namespace, container: DependencyContainer) -> int:
    load_result = load_config(container.configuration, args.config)
    if not load_result.success:
        _print_errors(load_result.errors)
        return 1
    assert load_result.config is not None

    try:
        profile = container.profiles.load_profile(args.name)
    except (ProfileNotFoundError, ProfileLoadError) as e:
        print(f"Erreur : {e}", file=sys.stderr)
        return 1

    plan = plan_profile_application(load_result.config, profile)

    print(f"Profil de base choisi : {profile.name}")
    if not plan.changes:
        print("Aucune modification.")
    else:
        print("Modifications :")
        for change in plan.changes:
            print(str(change))

    if plan.conflicts:
        print("\nConflits detectes :")
        for conflict in plan.conflicts:
            print(f"  [{conflict.severity.upper()}] {conflict.message}")

    if plan.validation_errors:
        _print_errors(plan.validation_errors, "Erreur de validation")

    if args.dry_run:
        print("\n(--dry-run : aucune ecriture effectuee)")
        return 1 if plan.has_blocking_issues else 0

    if plan.has_blocking_issues and not args.force:
        print("\nApplication refusee (problemes bloquants, voir ci-dessus). Utiliser --force pour outrepasser.", file=sys.stderr)
        return 1

    container.configuration.save(args.config, plan.new_config)
    print(f"\nConfiguration mise a jour dans {args.config} (profil '{profile.name}' applique).")
    return 0


def cmd_option_list(args: argparse.Namespace, container: DependencyContainer) -> int:
    result = load_config(container.configuration, args.config)
    if not result.success:
        _print_errors(result.errors)
        return 1
    assert result.config is not None
    for name, option in sorted(result.config.options.items()):
        state = "actif" if option.enabled else "inactif"
        print(f"{name} : {state}")
    return 0


def _cmd_option_set(args: argparse.Namespace, container: DependencyContainer, enabled: bool) -> int:
    load_result = load_config(container.configuration, args.config)
    if not load_result.success:
        _print_errors(load_result.errors)
        return 1
    assert load_result.config is not None

    result = set_option_enabled(load_result.config, args.name, enabled)
    print(result.message)
    if not result.success:
        return 1

    assert result.new_config is not None
    container.configuration.save(args.config, result.new_config)
    return 0


def cmd_option_enable(args: argparse.Namespace, container: DependencyContainer) -> int:
    return _cmd_option_set(args, container, enabled=True)


def cmd_option_disable(args: argparse.Namespace, container: DependencyContainer) -> int:
    return _cmd_option_set(args, container, enabled=False)


def cmd_simulate_request(args: argparse.Namespace, container: DependencyContainer) -> int:
    load_result = load_config(container.configuration, args.config)
    if not load_result.success:
        _print_errors(load_result.errors)
        return 1
    assert load_result.config is not None

    webroot = container.project_root / load_result.config.paths.webroot
    path_resolver = SafePathResolver(container.filesystem, webroot)
    fastcgi_client = AsyncioFastCgiClient() if load_result.config.option_enabled("fastcgi") else None

    report = asyncio.run(simulate_request(
        args.method.upper(), args.url, load_result.config, path_resolver, container.filesystem, container.project_root,
        fastcgi_client,
    ))

    print(f"Methode          : {report.method}")
    print(f"Chemin demande   : {report.raw_path}")
    print(f"Chemin normalise : {report.normalized_path}")
    print(f"Methode autorisee: {report.method_allowed}")
    print(f"Refuse (regles)  : {report.denied_by_access_policy}")
    print(f"Fichier existe   : {report.file_exists}")
    print(f"Statut reponse   : {report.response_status}")
    if report.rejection_reason:
        print(f"Motif de refus   : {report.rejection_reason}")
    print("En-tetes attendus :")
    for name, value in report.response_headers.items():
        print(f"  {name}: {value}")
    return 0


def cmd_waf_test(args: argparse.Namespace, container: DependencyContainer) -> int:
    load_result = load_config(container.configuration, args.config)
    if not load_result.success:
        _print_errors(load_result.errors)
        return 1
    assert load_result.config is not None

    waf = build_waf_collaborators(load_result.config, container.project_root, container.filesystem, container.clock, force=True)
    if waf is None:
        print("Erreur : options.waf absent de la configuration (executer 'omega-serv config init' ou ajouter la section waf).", file=sys.stderr)
        return 1

    report = simulate_waf_request(args.method, args.path, args.query or "", args.body or "", args.remote_ip, waf)
    decision = report.decision

    print(f"Decision : {decision.action.upper()}")
    print(f"Statut : {decision.status_code if decision.status_code is not None else '-'}")
    print(f"Score : {decision.score}")
    print(f"Regles : {', '.join(f.rule_id for f in decision.findings) or '-'}")
    print(f"Politique de zone : {report.zone_id}")
    print(f"Mode : {report.mode}")
    if decision.blocked_reason:
        print(f"Motif : {decision.blocked_reason}")
    return 0


def cmd_blocklist_list(args: argparse.Namespace, container: DependencyContainer) -> int:
    load_result = load_config(container.configuration, args.config)
    if not load_result.success:
        _print_errors(load_result.errors)
        return 1
    assert load_result.config is not None

    blocklist_port = build_blocklist_port(load_result.config, container.project_root, container.filesystem, container.clock)
    entries = blocklist_port.list_entries()
    if not entries:
        print("Aucune entree.")
        return 0
    for entry in entries:
        expiry = entry.expires_at or "permanent"
        print(f"{entry.network}\t{entry.source}\t{expiry}\t{entry.reason}")
    return 0


def cmd_blocklist_add(args: argparse.Namespace, container: DependencyContainer) -> int:
    load_result = load_config(container.configuration, args.config)
    if not load_result.success:
        _print_errors(load_result.errors)
        return 1
    assert load_result.config is not None

    blocklist_port = build_blocklist_port(load_result.config, container.project_root, container.filesystem, container.clock)
    result = add_blocklist_entry(
        blocklist_port, args.network, args.reason, args.duration_seconds, confirm_permanent=args.confirm_permanent,
    )
    print(result.message)
    return 0 if result.success else 1


def cmd_blocklist_remove(args: argparse.Namespace, container: DependencyContainer) -> int:
    load_result = load_config(container.configuration, args.config)
    if not load_result.success:
        _print_errors(load_result.errors)
        return 1
    assert load_result.config is not None

    blocklist_port = build_blocklist_port(load_result.config, container.project_root, container.filesystem, container.clock)
    result = remove_blocklist_entry(blocklist_port, args.network)
    print(result.message)
    return 0 if result.success else 1


def _require_active_defense(
    args: argparse.Namespace, container: DependencyContainer,
) -> ActiveDefenseCollaborators | None:
    """Factorise le chargement de config + construction des
    collaborateurs Active Defense, deja duplique 7 fois (seuil depasse -
    voir la charte "pas d'abstraction avant 3 repetitions reelles").
    Retourne None (et affiche l'erreur) si la config est invalide ou si
    l'option est desactivee - `cmd_active_defense_status` reste seul a
    ne PAS traiter la desactivation comme une erreur (c'est son role
    precis), donc n'utilise pas ce helper."""
    load_result = load_config(container.configuration, args.config)
    if not load_result.success:
        _print_errors(load_result.errors)
        return None
    assert load_result.config is not None
    try:
        active_defense = build_active_defense_collaborators(load_result.config, container.project_root)
    except OSError as exc:
        print(f"Erreur d'acces a la base Active Defense : {exc}.", file=sys.stderr)
        print(
            "Si l'appartenance a un groupe systeme a change recemment, une nouvelle "
            "session (deconnexion/reconnexion) peut etre necessaire.",
            file=sys.stderr,
        )
        return None
    if active_defense is None:
        print("Erreur : options.active_defense absent ou desactive de la configuration.", file=sys.stderr)
        return None
    return active_defense


def cmd_active_defense_status(args: argparse.Namespace, container: DependencyContainer) -> int:
    load_result = load_config(container.configuration, args.config)
    if not load_result.success:
        _print_errors(load_result.errors)
        return 1
    assert load_result.config is not None

    try:
        active_defense = build_active_defense_collaborators(load_result.config, container.project_root)
    except OSError as exc:
        print(f"Erreur d'acces a la base Active Defense : {exc}.", file=sys.stderr)
        return 1
    if active_defense is None:
        print("Active Defense : desactive (options.active_defense.enabled = false ou absent).")
        return 0
    print(f"Active Defense : active (mode={active_defense.config.mode})")
    print(f"Mode guerre : {'active' if active_defense.config.war_mode.enabled else 'inactif'}")
    print(f"Deception : {'active' if active_defense.config.deception.enabled else 'inactive'}")
    tracked = active_defense.threat_state_repository.list_all()
    print(f"Sources suivies : {len(tracked)}")
    return 0


def cmd_threats_list(args: argparse.Namespace, container: DependencyContainer) -> int:
    active_defense = _require_active_defense(args, container)
    if active_defense is None:
        return 1

    states = list_threat_states(active_defense.threat_state_repository, level=args.level)
    if not states:
        print("Aucune menace suivie.")
        return 0
    for state in states:
        print(f"{state.subject_id}\t{state.score}\t{state.level}\t{state.updated_at.isoformat()}\t{state.expires_at.isoformat()}")
    return 0


def cmd_threats_show(args: argparse.Namespace, container: DependencyContainer) -> int:
    active_defense = _require_active_defense(args, container)
    if active_defense is None:
        return 1

    state = get_threat_state(active_defense.threat_state_repository, args.subject_id)
    if state is None:
        print(f"Aucune menace suivie pour {args.subject_id!r}.", file=sys.stderr)
        return 1
    print(f"Source : {state.subject_id}")
    print(f"Score : {state.score}")
    print(f"Niveau : {state.level}")
    print(f"Mise a jour : {state.updated_at.isoformat()}")
    print(f"Expiration : {state.expires_at.isoformat()}")
    print(f"Actions actives : {', '.join(state.active_actions) or '-'}")
    return 0


def cmd_incidents_list(args: argparse.Namespace, container: DependencyContainer) -> int:
    active_defense = _require_active_defense(args, container)
    if active_defense is None:
        return 1

    since = None
    if args.since_hours is not None:
        since = container.clock.now() - timedelta(hours=args.since_hours)
    filters = IncidentFilters(status=args.status, since=since)
    incidents = list_incidents(active_defense.incident_repository, filters)
    if not incidents:
        print("Aucun incident.")
        return 0
    for incident in incidents:
        closed = incident.closed_at.isoformat() if incident.closed_at else "-"
        print(f"{incident.incident_id}\t{incident.subject_id}\t{incident.status}\t{incident.opened_at.isoformat()}\t{closed}")
    return 0


def cmd_incidents_show(args: argparse.Namespace, container: DependencyContainer) -> int:
    active_defense = _require_active_defense(args, container)
    if active_defense is None:
        return 1

    incident = active_defense.incident_repository.get(args.incident_id)
    if incident is None:
        print(f"Incident introuvable : {args.incident_id!r}.", file=sys.stderr)
        return 1
    print(f"Incident : {incident.incident_id}")
    print(f"Source : {incident.subject_id}")
    print(f"Statut : {incident.status}")
    print(f"Ouvert le : {incident.opened_at.isoformat()}")
    print(f"Ferme le : {incident.closed_at.isoformat() if incident.closed_at else '-'}")
    print("Chronologie :")
    for event in get_incident_timeline(active_defense.incident_repository, args.incident_id):
        print(f"  {event.occurred_at.isoformat()}\t{event.kind}\t{event.detail}")
    return 0


def cmd_incidents_close(args: argparse.Namespace, container: DependencyContainer) -> int:
    active_defense = _require_active_defense(args, container)
    if active_defense is None:
        return 1

    closed = close_incident(active_defense.incident_repository, container.clock, args.incident_id)
    if closed is None:
        print(f"Incident introuvable ou deja ferme : {args.incident_id!r}.", file=sys.stderr)
        return 1
    print(f"Incident {closed.incident_id!r} ferme.")
    if active_defense.config.ioc.auto_export_on_close:
        export_dir = container.project_root / active_defense.config.storage.export_dir
        exporters: dict[str, IoCExporterPort] = {
            "json": JsonIoCExporter(container.filesystem, export_dir),
            "csv": CsvIoCExporter(container.filesystem, export_dir),
        }
        for export_format in active_defense.config.ioc.formats:
            if export_format in exporters:
                result = exporters[export_format].export(closed)
            elif export_format == "markdown":
                result = MarkdownIncidentReportExporter(container.filesystem, export_dir).render(closed)
            else:
                continue
            print(f"Auto-export ({export_format}) : {result.path}")
    return 0


def cmd_incidents_export_ioc(args: argparse.Namespace, container: DependencyContainer) -> int:
    active_defense = _require_active_defense(args, container)
    if active_defense is None:
        return 1

    incident = active_defense.incident_repository.get(args.incident_id)
    if incident is None:
        print(f"Incident introuvable : {args.incident_id!r}.", file=sys.stderr)
        return 1

    export_dir = container.project_root / active_defense.config.storage.export_dir
    exporters: dict[str, IoCExporterPort] = {
        "json": JsonIoCExporter(container.filesystem, export_dir),
        "csv": CsvIoCExporter(container.filesystem, export_dir),
    }
    for export_format in (f.strip() for f in args.format.split(",")):
        exporter = exporters.get(export_format)
        if exporter is None:
            print(f"Format d'export inconnu : {export_format!r} (json ou csv).", file=sys.stderr)
            return 1
        result = exporter.export(incident)
        print(f"Exporte : {result.path}")
    return 0


def cmd_incidents_generate_report(args: argparse.Namespace, container: DependencyContainer) -> int:
    active_defense = _require_active_defense(args, container)
    if active_defense is None:
        return 1

    incident = active_defense.incident_repository.get(args.incident_id)
    if incident is None:
        print(f"Incident introuvable : {args.incident_id!r}.", file=sys.stderr)
        return 1

    export_dir = container.project_root / active_defense.config.storage.export_dir
    result = MarkdownIncidentReportExporter(container.filesystem, export_dir).render(incident)
    print(f"Rapport genere : {result.path}")
    return 0


def cmd_deception_list(args: argparse.Namespace, container: DependencyContainer) -> int:
    active_defense = _require_active_defense(args, container)
    if active_defense is None:
        return 1

    assignments = active_defense.deception_assignment_repository.list_active()
    if not assignments:
        print("Aucune affectation de leurre.")
        return 0
    now = container.clock.now()
    for assignment in assignments:
        status = "active" if is_assignment_active(assignment, now) else "expiree"
        print(
            f"{assignment.subject_id}\t{assignment.profile_name}\t{status}\t"
            f"{assignment.assigned_at.isoformat()}\t{assignment.expires_at.isoformat()}"
        )
    return 0


def cmd_deception_release(args: argparse.Namespace, container: DependencyContainer) -> int:
    active_defense = _require_active_defense(args, container)
    if active_defense is None:
        return 1

    release_deception(active_defense.deception_assignment_repository, args.subject_id)
    print(f"Affectation de leurre liberee pour {args.subject_id!r} (si elle existait).")
    return 0


def cmd_active_defense_simulate(args: argparse.Namespace, container: DependencyContainer) -> int:
    """Simulation/dry-run (plan §"Mode guerre", Phase 4 : "ajouter
    simulation, dry-run et explication de la decision") - AUCUNE
    ecriture (voir preview_playbook_decision.py), jamais d'impact sur
    l'etat reel ni sur le reseau."""
    active_defense = _require_active_defense(args, container)
    if active_defense is None:
        return 1
    if args.attack_class not in KNOWN_ATTACK_CLASSES:
        print(
            f"Classe d'attaque inconnue : {args.attack_class!r} "
            f"(valeurs possibles : {', '.join(sorted(KNOWN_ATTACK_CLASSES))}).",
            file=sys.stderr,
        )
        return 1
    subject_id = f"{args.ip}:{hash_payload((args.user_agent or '').encode('utf-8'))}"
    preview = preview_playbook_decision(
        active_defense.threat_state_repository, active_defense.incident_repository,
        active_defense.deception_assignment_repository, container.clock, active_defense.config,
        subject_id=subject_id, attack_class=cast("AttackClass", args.attack_class), score_delta=args.score,
    )
    print(f"Source (simulee) : {preview.subject_id}  (chemin observe : {args.path})")
    print(f"Score : {preview.previous_score} -> {preview.projected_score}")
    print(f"Niveau : {preview.previous_level} -> {preview.projected_level}")
    for line in preview.explanation:
        print(f"  - {line}")
    return 0


def cmd_active_defense_purge(args: argparse.Namespace, container: DependencyContainer) -> int:
    """Balayage manuel (plan §"CLI et TUI a parite" : "active-defense
    purge" ; §"Mode guerre"/Phase 6 "retention, purge") - purge les
    ThreatState expires et ferme les incidents redevenus silencieux
    (voir sweep_active_defense.py pour le pourquoi d'un balayage manuel
    plutot qu'un scheduler)."""
    active_defense = _require_active_defense(args, container)
    if active_defense is None:
        return 1
    result = sweep_active_defense(
        active_defense.threat_state_repository, active_defense.incident_repository,
        container.clock, active_defense.config,
    )
    print(f"Etats de menace purges : {result.purged_threat_states}")
    print(f"Incidents fermes automatiquement : {len(result.closed_incidents)}")
    for incident_id in result.closed_incidents:
        print(f"  - {incident_id}")
    return 0


def cmd_certs_generate_self_signed(args: argparse.Namespace, container: DependencyContainer) -> int:
    load_result = load_config(container.configuration, args.config)
    if not load_result.success:
        _print_errors(load_result.errors)
        return 1
    assert load_result.config is not None

    params = SelfSignedCertParams(
        common_name=args.cn,
        san_dns=tuple(args.san_dns),
        san_ip=tuple(args.san_ip),
        organization=args.org,
        organizational_unit=args.ou,
        city=args.city,
        region=args.region,
        country=args.country,
        validity_days=args.days,
        key_type=args.key_type,
        key_password=args.password,
    )
    key_path = container.project_root / load_result.config.tls.private_key_path
    cert_path = container.project_root / load_result.config.tls.certificate_path
    backups_dir = container.project_root / "var" / "backups" / "certificates"

    tool = OpensslCertificateTool(SubprocessRunner())
    try:
        result = generate_self_signed_certificate(params, key_path, cert_path, tool, container.filesystem, container.clock, backups_dir)
    except CertificateToolError as e:
        print(f"Erreur : {e}", file=sys.stderr)
        return 1

    print(result.message)
    return 0 if result.success else 1


def cmd_certs_generate_ca(args: argparse.Namespace, container: DependencyContainer) -> int:
    password = _resolve_ca_password(args)
    if password is None:
        print("Erreur : les deux saisies de passphrase ne correspondent pas.", file=sys.stderr)
        return 1

    params = CaParams(
        common_name=args.cn, organization=args.org, organizational_unit=args.ou,
        city=args.city, region=args.region, country=args.country,
        validity_days=args.days, key_type=args.key_type, key_password=password,
    )
    ca_dir = container.project_root / "secure" / "certificates" / "ca"
    backups_dir = container.project_root / "var" / "backups" / "certificates"

    tool = OpensslCertificateTool(SubprocessRunner())
    try:
        result = generate_ca_certificate(
            params, ca_dir / "root-ca.key", ca_dir / "root-ca.pem", ca_dir / "serial.txt", ca_dir / "index.txt",
            tool, container.filesystem, container.clock, backups_dir,
        )
    except CertificateToolError as e:
        print(f"Erreur : {e}", file=sys.stderr)
        return 1

    print(result.message)
    if result.success:
        print(f"Importez {ca_dir / 'root-ca.pem'} dans le magasin de confiance des clients (doc TLS §7.4).")
    return 0 if result.success else 1


def cmd_certs_import(args: argparse.Namespace, container: DependencyContainer) -> int:
    """`omega-serv certs import` (doc TLS §9, §20) - comble le seul point
    du perimetre TLS documente depuis le debut mais jamais implemente
    (voir OMEGA-SERV_PLAN-DETAILLE_TLS_AUTO.md). Copie vers les chemins
    DEJA CONFIGURES (`tls.certificate_path`/`private_key_path`), jamais
    un chemin arbitraire choisi ici - meme convention que `generate-self-
    signed`/`generate-ca` ci-dessus. Premier vrai consommateur vise : un
    hook de renouvellement Certbot (`--cert`/`--key` pointant vers
    `/etc/letsencrypt/live/<domaine>/`), mais generique - n'importe quelle
    source (CA d'entreprise, certificat achete) fonctionne a l'identique."""
    load_result = load_config(container.configuration, args.config)
    if not load_result.success:
        _print_errors(load_result.errors)
        return 1
    assert load_result.config is not None

    dest_key_path = container.project_root / load_result.config.tls.private_key_path
    dest_cert_path = container.project_root / load_result.config.tls.certificate_path
    backups_dir = container.project_root / "var" / "backups" / "certificates"

    tool = OpensslCertificateTool(SubprocessRunner())
    try:
        result = import_certificate(
            Path(args.key), Path(args.cert), dest_key_path, dest_cert_path,
            tool, container.filesystem, container.clock, backups_dir,
            source_chain_path=Path(args.chain) if args.chain else None,
        )
    except CertificateToolError as e:
        print(f"Erreur : {e}", file=sys.stderr)
        return 1

    print(result.message)
    if result.success:
        print("Redemarrage requis pour que le nouveau certificat soit pris en compte (`omega-serv service restart`).")
    return 0 if result.success else 1


def cmd_certs_generate_csr(args: argparse.Namespace, container: DependencyContainer) -> int:
    params = CsrParams(
        common_name=args.cn, san_dns=tuple(args.san_dns), san_ip=tuple(args.san_ip),
        organization=args.org, organizational_unit=args.ou, city=args.city, region=args.region,
        country=args.country, key_type=args.key_type,
    )
    key_path = Path(args.key_out)
    csr_path = Path(args.csr_out)
    backups_dir = container.project_root / "var" / "backups" / "certificates"

    tool = OpensslCertificateTool(SubprocessRunner())
    try:
        result = generate_certificate_signing_request(
            params, key_path, csr_path, tool, container.filesystem, container.clock, backups_dir,
        )
    except CertificateToolError as e:
        print(f"Erreur : {e}", file=sys.stderr)
        return 1

    print(result.message)
    return 0 if result.success else 1


def cmd_certs_sign_csr(args: argparse.Namespace, container: DependencyContainer) -> int:
    ca_key_password = _resolve_password(args)
    ca_dir = Path(args.ca_key).parent
    backups_dir = container.project_root / "var" / "backups" / "certificates"

    tool = OpensslCertificateTool(SubprocessRunner())
    try:
        result = sign_certificate_signing_request(
            Path(args.csr), Path(args.ca_key), Path(args.ca_cert), ca_key_password,
            ca_dir / "serial.txt", ca_dir / "index.txt", args.days, Path(args.out),
            tool, container.filesystem, container.clock, backups_dir,
            out_fullchain_path=Path(args.fullchain_out) if args.fullchain_out else None,
        )
    except CertificateToolError as e:
        print(f"Erreur : {e}", file=sys.stderr)
        return 1

    print(result.message)
    return 0 if result.success else 1


def cmd_certs_revoke(args: argparse.Namespace, container: DependencyContainer) -> int:
    ca_key_password = _resolve_password(args)
    ca_dir = Path(args.ca_key).parent

    tool = OpensslCertificateTool(SubprocessRunner())
    try:
        result = revoke_certificate(
            Path(args.cert), Path(args.ca_key), Path(args.ca_cert), ca_key_password,
            ca_dir / "index.txt", tool, container.filesystem,
        )
    except CertificateToolError as e:
        print(f"Erreur : {e}", file=sys.stderr)
        return 1

    print(result.message)
    return 0 if result.success else 1


def _print_certificate_report(report: CertificateReport) -> None:
    info = report.info
    print(f"Sujet : {info.subject}")
    print(f"Emetteur : {info.issuer}")
    print(f"Debut de validite : {info.not_before.isoformat()}")
    print(f"Fin de validite : {info.not_after.isoformat()}")
    print(f"Jours restants : {report.days_remaining}")
    print(f"Type de cle : {info.key_type} ({info.key_bits} bits)" if info.key_bits else f"Type de cle : {info.key_type}")
    print(f"Algorithme de signature : {info.signature_algorithm}")
    if info.san_dns or info.san_ip:
        print("SAN :")
        for dns in info.san_dns:
            print(f"  - DNS:{dns}")
        for ip in info.san_ip:
            print(f"  - IP:{ip}")
    print()
    print(f"[{'ERREUR' if report.is_expired else 'OK'}] Certificat {'expire' if report.is_expired else 'non expire'}")
    if report.key_matches is not None:
        print(f"[{'OK' if report.key_matches else 'ERREUR'}] Cle privee {'correspondante' if report.key_matches else 'NE correspond PAS'}")
    if report.key_mode is not None:
        strict = not (report.key_mode & 0o077)
        print(f"[{'OK' if strict else 'ERREUR'}] Permissions cle privee : {oct(report.key_mode)}")
    if info.is_self_signed:
        print("[AVERTISSEMENT] Certificat auto-signe, non approuve par defaut par les navigateurs")
    if report.expiring_soon and not report.is_expired:
        print(f"[AVERTISSEMENT] Certificat bientot expire ({report.days_remaining} jours restants)")


def _cmd_certs_inspect(args: argparse.Namespace, container: DependencyContainer, warn_days: int = 30) -> int:
    load_result = load_config(container.configuration, args.config)
    if not load_result.success:
        _print_errors(load_result.errors)
        return 1
    assert load_result.config is not None

    cert_path = Path(args.cert) if args.cert else container.project_root / load_result.config.tls.certificate_path
    key_path = container.project_root / load_result.config.tls.private_key_path

    tool = OpensslCertificateTool(SubprocessRunner())
    try:
        report = inspect_certificate_report(cert_path, key_path, tool, container.filesystem, container.clock, warn_days)
    except CertificateToolError as e:
        print(f"Erreur : {e}", file=sys.stderr)
        return 1

    _print_certificate_report(report)
    return 1 if report.is_expired else 0


def cmd_certs_verify(args: argparse.Namespace, container: DependencyContainer) -> int:
    return _cmd_certs_inspect(args, container)


def cmd_certs_show(args: argparse.Namespace, container: DependencyContainer) -> int:
    return _cmd_certs_inspect(args, container)


def cmd_certs_check_expiry(args: argparse.Namespace, container: DependencyContainer) -> int:
    return _cmd_certs_inspect(args, container, warn_days=args.warn_days)


def cmd_config_enable_tls(args: argparse.Namespace, container: DependencyContainer) -> int:
    load_result = load_config(container.configuration, args.config)
    if not load_result.success:
        _print_errors(load_result.errors)
        return 1
    assert load_result.config is not None

    data = load_result.config.to_dict()
    data["tls"]["enabled"] = True
    data["tls"]["mode"] = args.mode
    if args.cert:
        data["tls"]["certificate"]["certificate_path"] = args.cert
    if args.key:
        data["tls"]["certificate"]["private_key_path"] = args.key
    new_config = OmegaServConfig.from_dict(data)

    container.configuration.save(args.config, new_config)
    print(f"TLS active (mode {args.mode}) dans {args.config}.")
    return 0


def cmd_config_disable_tls(args: argparse.Namespace, container: DependencyContainer) -> int:
    load_result = load_config(container.configuration, args.config)
    if not load_result.success:
        _print_errors(load_result.errors)
        return 1
    assert load_result.config is not None

    data = load_result.config.to_dict()
    data["tls"]["enabled"] = False
    new_config = OmegaServConfig.from_dict(data)

    container.configuration.save(args.config, new_config)
    print(f"TLS desactive dans {args.config}.")
    return 0


def _resolve_password(args: argparse.Namespace) -> str:
    """N'affiche jamais le mot de passe sur la ligne de commande si
    `--password` est omis (spec §15.4 : "demander le mot de passe sans
    l'afficher") - seule commande de ce CLI par ailleurs non-interactif
    a en avoir besoin, un mot de passe sur la ligne de commande finirait
    dans l'historique du shell."""
    if args.password:
        return str(args.password)
    return getpass.getpass("Mot de passe : ")


def _resolve_ca_password(args: argparse.Namespace) -> str | None:
    """Doc TLS §7.3 etape 3 : "demander ET CONFIRMER une passphrase pour
    la cle de CA" - double saisie interactive si `--password` est omis,
    plus stricte que _resolve_password (simple saisie) car la cle de CA
    est la plus sensible du projet (doc TLS §7.2). Retourne None si les
    deux saisies ne correspondent pas (appelant : erreur, jamais de
    nouvelle tentative silencieuse)."""
    if args.password:
        return str(args.password)
    first = getpass.getpass("Passphrase de la CA : ")
    second = getpass.getpass("Confirmer la passphrase : ")
    if first != second:
        return None
    return first


def cmd_auth_add_user(args: argparse.Namespace, container: DependencyContainer) -> int:
    load_result = load_config(container.configuration, args.config)
    if not load_result.success:
        _print_errors(load_result.errors)
        return 1
    assert load_result.config is not None

    repo = build_users_repository(load_result.config, container.project_root, container.filesystem)
    result = add_user(repo, args.username, _resolve_password(args))
    print(result.message)
    return 0 if result.success else 1


def cmd_auth_remove_user(args: argparse.Namespace, container: DependencyContainer) -> int:
    load_result = load_config(container.configuration, args.config)
    if not load_result.success:
        _print_errors(load_result.errors)
        return 1
    assert load_result.config is not None

    repo = build_users_repository(load_result.config, container.project_root, container.filesystem)
    result = remove_user(repo, args.username)
    print(result.message)
    return 0 if result.success else 1


def cmd_auth_change_password(args: argparse.Namespace, container: DependencyContainer) -> int:
    load_result = load_config(container.configuration, args.config)
    if not load_result.success:
        _print_errors(load_result.errors)
        return 1
    assert load_result.config is not None

    repo = build_users_repository(load_result.config, container.project_root, container.filesystem)
    result = change_password(repo, args.username, _resolve_password(args))
    print(result.message)
    return 0 if result.success else 1


def cmd_auth_create_zone(args: argparse.Namespace, container: DependencyContainer) -> int:
    load_result = load_config(container.configuration, args.config)
    if not load_result.success:
        _print_errors(load_result.errors)
        return 1
    assert load_result.config is not None

    repo = build_auth_zones_repository(load_result.config, container.project_root, container.filesystem)
    zone = AuthZone(
        path_prefix=args.path_prefix, realm=args.realm,
        allowed_users=tuple(args.allowed_users), allow_methods=tuple(args.allow_methods),
    )
    result = add_zone(repo, zone)
    print(result.message)
    return 0 if result.success else 1


def cmd_auth_remove_zone(args: argparse.Namespace, container: DependencyContainer) -> int:
    load_result = load_config(container.configuration, args.config)
    if not load_result.success:
        _print_errors(load_result.errors)
        return 1
    assert load_result.config is not None

    repo = build_auth_zones_repository(load_result.config, container.project_root, container.filesystem)
    result = remove_zone(repo, args.path_prefix)
    print(result.message)
    return 0 if result.success else 1


def cmd_auth_list(args: argparse.Namespace, container: DependencyContainer) -> int:
    load_result = load_config(container.configuration, args.config)
    if not load_result.success:
        _print_errors(load_result.errors)
        return 1
    assert load_result.config is not None

    users = build_users_repository(load_result.config, container.project_root, container.filesystem).load()
    zones = build_auth_zones_repository(load_result.config, container.project_root, container.filesystem).load()

    print("Utilisateurs :")
    for user in users:
        print(f"  - {user.username}")
    print("Zones protegees :")
    for zone in zones:
        methods = ", ".join(zone.allow_methods) or "toutes"
        print(f"  - {zone.path_prefix} (realm={zone.realm!r}, utilisateurs={list(zone.allowed_users)}, methodes={methods})")
    return 0


def cmd_auth_check_permissions(args: argparse.Namespace, container: DependencyContainer) -> int:
    load_result = load_config(container.configuration, args.config)
    if not load_result.success:
        _print_errors(load_result.errors)
        return 1
    assert load_result.config is not None

    ok = True
    for label, relative_path in (("users.json", load_result.config.paths.auth_file), ("zones.json", load_result.config.paths.auth_zones)):
        path = container.project_root / relative_path
        if not container.filesystem.exists(path):
            print(f"[INFO] {label} absent ({path})")
            continue
        mode = container.filesystem.file_mode(path)
        strict = not (mode & 0o077)
        print(f"[{'OK' if strict else 'AVERTISSEMENT'}] {label} permissions : {oct(mode)}")
        if not strict:
            ok = False
    return 0 if ok else 1


def _build_service_manager(manager_type: str) -> ServiceManagerPort:
    runner = SubprocessRunner()
    if manager_type == "systemd":
        return SystemdServiceManager(runner)
    if manager_type == "openrc":
        return OpenRCServiceManager(runner)
    return RunitServiceManager(runner)


def _detect_or_fail() -> ServiceManagerPort | None:
    manager_type = detect_service_manager_type()
    if manager_type is None:
        print("Erreur : aucun gestionnaire de service reconnu (systemd/OpenRC/runit) sur ce systeme.", file=sys.stderr)
        return None
    return _build_service_manager(manager_type)


def cmd_service_status(args: argparse.Namespace, container: DependencyContainer) -> int:
    manager = _detect_or_fail()
    if manager is None:
        return 1
    result = get_service_status(manager, args.service_name)
    if isinstance(result, ServiceStatus):
        print(f"Service : {result.service_name}")
        print(f"Actif   : {result.active}")
        print(f"Active au demarrage : {result.enabled}")
        print(f"Etat    : {result.state} ({result.sub_state})")
        if result.description:
            print(f"Description : {result.description}")
        return 0
    print(result.message, file=sys.stderr)
    return 1


def _cmd_service_control(
    args: argparse.Namespace,
    container: DependencyContainer,
    action: Callable[[ServiceManagerPort, str], ManageServiceResult],
) -> int:
    manager = _detect_or_fail()
    if manager is None:
        return 1
    result = action(manager, args.service_name)
    print(result.message)
    return 0 if result.success else 1


def cmd_service_start(args: argparse.Namespace, container: DependencyContainer) -> int:
    return _cmd_service_control(args, container, start_service)


def cmd_service_stop(args: argparse.Namespace, container: DependencyContainer) -> int:
    return _cmd_service_control(args, container, stop_service)


def cmd_service_restart(args: argparse.Namespace, container: DependencyContainer) -> int:
    return _cmd_service_control(args, container, restart_service)


def cmd_service_reload(args: argparse.Namespace, container: DependencyContainer) -> int:
    return _cmd_service_control(args, container, reload_service)


def cmd_service_enable(args: argparse.Namespace, container: DependencyContainer) -> int:
    return _cmd_service_control(args, container, enable_service)


def cmd_service_disable(args: argparse.Namespace, container: DependencyContainer) -> int:
    return _cmd_service_control(args, container, disable_service)


def _default_python_executable(container: DependencyContainer) -> Path:
    venv_python = container.project_root / ".venv" / "bin" / "python"
    if container.filesystem.exists(venv_python):
        return venv_python
    return Path(sys.executable)


def cmd_service_install(args: argparse.Namespace, container: DependencyContainer) -> int:
    manager_type = detect_service_manager_type()
    if manager_type != "systemd":
        print(
            f"Erreur : generation d'unite non supportee pour {manager_type or 'aucun gestionnaire detecte'} "
            "(seul systemd est supporte en V1, voir OMEGA-SERV_PLAN_DEVELOPPEMENT.md §5).",
            file=sys.stderr,
        )
        return 1

    manager = SystemdServiceManager(SubprocessRunner())
    params = SystemdUnitParams(
        service_name=args.service_name,
        description=args.description,
        python_executable=Path(args.python_executable) if args.python_executable else _default_python_executable(container),
        project_root=container.project_root,
        config_path=args.config,
        user=args.user,
        group=args.group,
        stop_timeout_seconds=args.stop_timeout_seconds,
    )
    unit_path = Path(args.unit_path) if args.unit_path else Path(f"/etc/systemd/system/{args.service_name}.service")

    result = install_systemd_service(container.filesystem, params, unit_path, manager)
    print(result.message)
    return 0 if result.success else 1


def cmd_service_uninstall(args: argparse.Namespace, container: DependencyContainer) -> int:
    manager_type = detect_service_manager_type()
    if manager_type != "systemd":
        print(f"Erreur : desinstallation d'unite non supportee pour {manager_type or 'aucun gestionnaire detecte'}.", file=sys.stderr)
        return 1

    manager = SystemdServiceManager(SubprocessRunner())
    unit_path = Path(args.unit_path) if args.unit_path else Path(f"/etc/systemd/system/{args.service_name}.service")
    result = uninstall_systemd_service(container.filesystem, unit_path, manager)
    print(result.message)
    return 0 if result.success else 1


_SEVERITY_LABELS = {
    Severity.CRITICAL: "CRITICAL", Severity.HIGH: "HIGH", Severity.MEDIUM: "MEDIUM",
    Severity.LOW: "LOW", Severity.INFO: "INFO",
}


def _print_audit_findings(findings: list[AuditFinding]) -> None:
    if not findings:
        print("Aucun probleme detecte.")
        return
    for finding in findings:
        label = _SEVERITY_LABELS[finding.severity]
        print(f"[{label}] {finding.rule_id} {finding.rule_name}")
        print(f"    {finding.message}")
        print(f"    -> {finding.recommendation}")


def cmd_audit_security(args: argparse.Namespace, container: DependencyContainer) -> int:
    load_result = load_config(container.configuration, args.config)
    if not load_result.success:
        _print_errors(load_result.errors, "Erreur de configuration")
        return 3
    assert load_result.config is not None

    certificate_tool = OpensslCertificateTool(SubprocessRunner())
    unit_path = Path(args.unit_path) if args.unit_path else Path(f"/etc/systemd/system/{args.service_name}.service")

    result = run_audit(
        load_result.config, args.config, container.project_root, container.filesystem,
        certificate_tool, container.clock, service_unit_path=unit_path,
        self_signed_public_bind_confirmed=args.confirm_self_signed_public_bind,
        auth_without_tls_confirmed=args.confirm_auth_without_tls,
    )

    min_severity = Severity(args.min_severity)
    displayed = [f for f in result.findings if severity_at_least(f.severity, min_severity)]

    if args.format == "json":
        payload = result.to_dict()
        payload["findings"] = [f.to_dict() for f in displayed]
        print(json.dumps(payload, indent=2, ensure_ascii=False))
    else:
        _print_audit_findings(displayed)
        summary = result.summary
        print(f"Resume : {summary['critical']} critical, {summary['high']} high, "
              f"{summary['medium']} medium, {summary['low']} low, {summary['info']} info")
        print("Etat : securise" if result.is_secure else "Etat : NON SECURISE")

    return result.exit_code


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="omega-serv")
    parser.add_argument("--config", type=Path, default=CONFIG_FILE)
    subparsers = parser.add_subparsers(dest="command", required=True)

    serve_parser = subparsers.add_parser("serve")
    serve_parser.add_argument("--confirm-self-signed-public-bind", action="store_true")
    serve_parser.add_argument("--confirm-auth-without-tls", action="store_true")
    serve_parser.set_defaults(func=cmd_serve)

    config_parser = subparsers.add_parser("config")
    config_sub = config_parser.add_subparsers(dest="config_command", required=True)
    init_parser = config_sub.add_parser("init")
    init_parser.add_argument("--force", action="store_true")
    init_parser.set_defaults(func=cmd_config_init)
    check_parser = config_sub.add_parser("check")
    check_parser.add_argument("--confirm-self-signed-public-bind", action="store_true")
    check_parser.add_argument("--confirm-auth-without-tls", action="store_true")
    check_parser.set_defaults(func=cmd_config_check)
    config_sub.add_parser("show").set_defaults(func=cmd_config_show)
    enable_tls_parser = config_sub.add_parser("enable-tls")
    enable_tls_parser.add_argument("--cert", default="")
    enable_tls_parser.add_argument("--key", default="")
    enable_tls_parser.add_argument("--mode", choices=("direct", "behind_proxy"), default="direct")
    enable_tls_parser.set_defaults(func=cmd_config_enable_tls)
    config_sub.add_parser("disable-tls").set_defaults(func=cmd_config_disable_tls)
    backup_parser = config_sub.add_parser("backup")
    backup_parser.add_argument("--include-waf", action="store_true")
    backup_parser.add_argument("--include-auth", action="store_true")
    backup_parser.add_argument("--include-certificates", action="store_true")
    backup_parser.add_argument("--include-active-defense", action="store_true")
    backup_parser.add_argument("--confirm-secrets", action="store_true")
    backup_parser.add_argument("--description", default="")
    backup_parser.set_defaults(func=cmd_config_backup)
    restore_parser = config_sub.add_parser("restore")
    restore_parser.add_argument("--snapshot-id", required=True)
    restore_parser.set_defaults(func=cmd_config_restore)
    config_sub.add_parser("list-backups").set_defaults(func=cmd_config_list_backups)

    profile_parser = subparsers.add_parser("profile")
    profile_sub = profile_parser.add_subparsers(dest="profile_command", required=True)
    profile_sub.add_parser("list").set_defaults(func=cmd_profile_list)
    show_parser = profile_sub.add_parser("show")
    show_parser.add_argument("name")
    show_parser.set_defaults(func=cmd_profile_show)
    apply_parser = profile_sub.add_parser("apply")
    apply_parser.add_argument("name")
    apply_parser.add_argument("--dry-run", action="store_true")
    apply_parser.add_argument("--force", action="store_true")
    apply_parser.set_defaults(func=cmd_profile_apply)

    option_parser = subparsers.add_parser("option")
    option_sub = option_parser.add_subparsers(dest="option_command", required=True)
    option_sub.add_parser("list").set_defaults(func=cmd_option_list)
    enable_parser = option_sub.add_parser("enable")
    enable_parser.add_argument("name")
    enable_parser.set_defaults(func=cmd_option_enable)
    disable_parser = option_sub.add_parser("disable")
    disable_parser.add_argument("name")
    disable_parser.set_defaults(func=cmd_option_disable)

    simulate_parser = subparsers.add_parser("simulate-request")
    simulate_parser.add_argument("--method", default="GET")
    simulate_parser.add_argument("--url", required=True)
    simulate_parser.set_defaults(func=cmd_simulate_request)

    waf_parser = subparsers.add_parser("waf")
    waf_sub = waf_parser.add_subparsers(dest="waf_command", required=True)
    test_parser = waf_sub.add_parser("test")
    test_parser.add_argument("--method", default="GET")
    test_parser.add_argument("--path", required=True)
    test_parser.add_argument("--query", default="")
    test_parser.add_argument("--body", default="")
    test_parser.add_argument("--remote-ip", default="127.0.0.1")
    test_parser.set_defaults(func=cmd_waf_test)

    blocklist_parser = subparsers.add_parser("blocklist")
    blocklist_sub = blocklist_parser.add_subparsers(dest="blocklist_command", required=True)
    blocklist_sub.add_parser("list").set_defaults(func=cmd_blocklist_list)
    add_parser = blocklist_sub.add_parser("add")
    add_parser.add_argument("--network", required=True)
    add_parser.add_argument("--reason", required=True)
    add_parser.add_argument("--duration-seconds", type=int, default=None)
    add_parser.add_argument("--confirm-permanent", action="store_true")
    add_parser.set_defaults(func=cmd_blocklist_add)
    remove_parser = blocklist_sub.add_parser("remove")
    remove_parser.add_argument("--network", required=True)
    remove_parser.set_defaults(func=cmd_blocklist_remove)

    active_defense_parser = subparsers.add_parser("active-defense")
    active_defense_sub = active_defense_parser.add_subparsers(dest="active_defense_command", required=True)
    active_defense_sub.add_parser("status").set_defaults(func=cmd_active_defense_status)
    simulate_ad_parser = active_defense_sub.add_parser("simulate")
    simulate_ad_parser.add_argument("--ip", required=True)
    simulate_ad_parser.add_argument("--path", default="/")
    simulate_ad_parser.add_argument("--user-agent", default="")
    simulate_ad_parser.add_argument("--attack-class", default="scan")
    simulate_ad_parser.add_argument("--score", type=int, default=10)
    simulate_ad_parser.set_defaults(func=cmd_active_defense_simulate)
    active_defense_sub.add_parser("purge").set_defaults(func=cmd_active_defense_purge)

    threats_parser = subparsers.add_parser("threats")
    threats_sub = threats_parser.add_subparsers(dest="threats_command", required=True)
    threats_list_parser = threats_sub.add_parser("list")
    threats_list_parser.add_argument("--level", choices=("normal", "suspicious", "hostile", "contained"), default=None)
    threats_list_parser.set_defaults(func=cmd_threats_list)
    threats_show_parser = threats_sub.add_parser("show")
    threats_show_parser.add_argument("subject_id")
    threats_show_parser.set_defaults(func=cmd_threats_show)

    incidents_parser = subparsers.add_parser("incidents")
    incidents_sub = incidents_parser.add_subparsers(dest="incidents_command", required=True)
    incidents_list_parser = incidents_sub.add_parser("list")
    incidents_list_parser.add_argument("--status", choices=("open", "closed"), default=None)
    incidents_list_parser.add_argument("--since-hours", type=float, default=None)
    incidents_list_parser.set_defaults(func=cmd_incidents_list)
    incidents_show_parser = incidents_sub.add_parser("show")
    incidents_show_parser.add_argument("incident_id")
    incidents_show_parser.set_defaults(func=cmd_incidents_show)
    incidents_close_parser = incidents_sub.add_parser("close")
    incidents_close_parser.add_argument("incident_id")
    incidents_close_parser.set_defaults(func=cmd_incidents_close)
    incidents_export_ioc_parser = incidents_sub.add_parser("export-ioc")
    incidents_export_ioc_parser.add_argument("incident_id")
    incidents_export_ioc_parser.add_argument("--format", default="json")
    incidents_export_ioc_parser.set_defaults(func=cmd_incidents_export_ioc)
    incidents_report_parser = incidents_sub.add_parser("generate-report")
    incidents_report_parser.add_argument("incident_id")
    incidents_report_parser.set_defaults(func=cmd_incidents_generate_report)

    deception_parser = subparsers.add_parser("deception")
    deception_sub = deception_parser.add_subparsers(dest="deception_command", required=True)
    deception_sub.add_parser("list").set_defaults(func=cmd_deception_list)
    deception_release_parser = deception_sub.add_parser("release")
    deception_release_parser.add_argument("--subject", dest="subject_id", required=True)
    deception_release_parser.set_defaults(func=cmd_deception_release)

    certs_parser = subparsers.add_parser("certs")
    certs_sub = certs_parser.add_subparsers(dest="certs_command", required=True)

    gen_parser = certs_sub.add_parser("generate-self-signed")
    gen_parser.add_argument("--cn", required=True)
    gen_parser.add_argument("--san-dns", nargs="*", default=[])
    gen_parser.add_argument("--san-ip", nargs="*", default=[])
    gen_parser.add_argument("--org", default="OMEGA-SERV")
    gen_parser.add_argument("--ou", default="")
    gen_parser.add_argument("--city", default="")
    gen_parser.add_argument("--region", default="")
    gen_parser.add_argument("--country", default="")
    gen_parser.add_argument("--days", type=int, default=365)
    gen_parser.add_argument("--key-type", choices=("rsa2048", "rsa4096", "ecdsa-p256", "ecdsa-p384"), default="rsa2048")
    gen_parser.add_argument("--password", default=None)
    gen_parser.set_defaults(func=cmd_certs_generate_self_signed)

    ca_parser = certs_sub.add_parser("generate-ca")
    ca_parser.add_argument("--cn", required=True)
    ca_parser.add_argument("--org", default="OMEGA-SERV")
    ca_parser.add_argument("--ou", default="")
    ca_parser.add_argument("--city", default="")
    ca_parser.add_argument("--region", default="")
    ca_parser.add_argument("--country", default="")
    ca_parser.add_argument("--days", type=int, default=3650)
    ca_parser.add_argument("--key-type", choices=("rsa2048", "rsa4096", "ecdsa-p256", "ecdsa-p384"), default="rsa4096")
    ca_parser.add_argument("--password", default=None)
    ca_parser.set_defaults(func=cmd_certs_generate_ca)

    csr_parser = certs_sub.add_parser("generate-csr")
    csr_parser.add_argument("--cn", required=True)
    csr_parser.add_argument("--san-dns", nargs="*", default=[])
    csr_parser.add_argument("--san-ip", nargs="*", default=[])
    csr_parser.add_argument("--org", default="OMEGA-SERV")
    csr_parser.add_argument("--ou", default="")
    csr_parser.add_argument("--city", default="")
    csr_parser.add_argument("--region", default="")
    csr_parser.add_argument("--country", default="")
    csr_parser.add_argument("--key-type", choices=("rsa2048", "rsa4096", "ecdsa-p256", "ecdsa-p384"), default="rsa2048")
    csr_parser.add_argument("--key-out", required=True)
    csr_parser.add_argument("--csr-out", required=True)
    csr_parser.set_defaults(func=cmd_certs_generate_csr)

    sign_parser = certs_sub.add_parser("sign-csr")
    sign_parser.add_argument("--csr", required=True)
    sign_parser.add_argument("--ca-key", required=True)
    sign_parser.add_argument("--ca-cert", required=True)
    sign_parser.add_argument("--ca-key-password", dest="password", default=None)
    sign_parser.add_argument("--days", type=int, default=365)
    sign_parser.add_argument("--out", required=True)
    sign_parser.add_argument("--fullchain-out", default=None)
    sign_parser.set_defaults(func=cmd_certs_sign_csr)

    import_parser = certs_sub.add_parser("import")
    import_parser.add_argument("--key", required=True)
    import_parser.add_argument("--cert", required=True)
    import_parser.add_argument("--chain", default=None)
    import_parser.set_defaults(func=cmd_certs_import)

    revoke_parser = certs_sub.add_parser("revoke")
    revoke_parser.add_argument("--cert", required=True)
    revoke_parser.add_argument("--ca-key", required=True)
    revoke_parser.add_argument("--ca-cert", required=True)
    revoke_parser.add_argument("--ca-key-password", dest="password", default=None)
    revoke_parser.set_defaults(func=cmd_certs_revoke)

    verify_parser = certs_sub.add_parser("verify")
    verify_parser.add_argument("--cert", default="")
    verify_parser.set_defaults(func=cmd_certs_verify)

    show_parser = certs_sub.add_parser("show")
    show_parser.add_argument("--cert", default="")
    show_parser.set_defaults(func=cmd_certs_show)

    expiry_parser = certs_sub.add_parser("check-expiry")
    expiry_parser.add_argument("--cert", default="")
    expiry_parser.add_argument("--warn-days", type=int, default=30)
    expiry_parser.set_defaults(func=cmd_certs_check_expiry)

    auth_parser = subparsers.add_parser("auth")
    auth_sub = auth_parser.add_subparsers(dest="auth_command", required=True)

    add_user_parser = auth_sub.add_parser("add-user")
    add_user_parser.add_argument("--username", required=True)
    add_user_parser.add_argument("--password", default=None)
    add_user_parser.set_defaults(func=cmd_auth_add_user)

    remove_user_parser = auth_sub.add_parser("remove-user")
    remove_user_parser.add_argument("--username", required=True)
    remove_user_parser.set_defaults(func=cmd_auth_remove_user)

    change_password_parser = auth_sub.add_parser("change-password")
    change_password_parser.add_argument("--username", required=True)
    change_password_parser.add_argument("--password", default=None)
    change_password_parser.set_defaults(func=cmd_auth_change_password)

    create_zone_parser = auth_sub.add_parser("create-zone")
    create_zone_parser.add_argument("--path-prefix", required=True)
    create_zone_parser.add_argument("--realm", required=True)
    create_zone_parser.add_argument("--allowed-users", nargs="+", required=True)
    create_zone_parser.add_argument("--allow-methods", nargs="*", default=[])
    create_zone_parser.set_defaults(func=cmd_auth_create_zone)

    remove_zone_parser = auth_sub.add_parser("remove-zone")
    remove_zone_parser.add_argument("--path-prefix", required=True)
    remove_zone_parser.set_defaults(func=cmd_auth_remove_zone)

    auth_sub.add_parser("list").set_defaults(func=cmd_auth_list)
    auth_sub.add_parser("check-permissions").set_defaults(func=cmd_auth_check_permissions)

    service_parser = subparsers.add_parser("service")
    service_sub = service_parser.add_subparsers(dest="service_command", required=True)

    for verb, func in (
        ("status", cmd_service_status), ("start", cmd_service_start), ("stop", cmd_service_stop),
        ("restart", cmd_service_restart), ("reload", cmd_service_reload),
        ("enable", cmd_service_enable), ("disable", cmd_service_disable),
    ):
        sub = service_sub.add_parser(verb)
        sub.add_argument("--service-name", default="omega-serv")
        sub.set_defaults(func=func)

    install_parser = service_sub.add_parser("install")
    install_parser.add_argument("--service-name", default="omega-serv")
    install_parser.add_argument("--description", default="OMEGA-SERV web server")
    install_parser.add_argument("--python-executable", default=None)
    install_parser.add_argument("--user", default="omega-serv")
    install_parser.add_argument("--group", default="omega-serv")
    install_parser.add_argument("--stop-timeout-seconds", type=int, default=15)
    install_parser.add_argument("--unit-path", default=None)
    install_parser.set_defaults(func=cmd_service_install)

    uninstall_parser = service_sub.add_parser("uninstall")
    uninstall_parser.add_argument("--service-name", default="omega-serv")
    uninstall_parser.add_argument("--unit-path", default=None)
    uninstall_parser.set_defaults(func=cmd_service_uninstall)

    audit_parser = subparsers.add_parser("audit")
    audit_sub = audit_parser.add_subparsers(dest="audit_command", required=True)
    security_parser = audit_sub.add_parser("security")
    security_parser.add_argument("--format", choices=("text", "json"), default="text")
    security_parser.add_argument("--min-severity", choices=("critical", "high", "medium", "low", "info"), default="info")
    security_parser.add_argument("--service-name", default="omega-serv")
    security_parser.add_argument("--unit-path", default=None)
    security_parser.add_argument("--confirm-self-signed-public-bind", action="store_true")
    security_parser.add_argument("--confirm-auth-without-tls", action="store_true")
    security_parser.set_defaults(func=cmd_audit_security)

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    container = DependencyContainer()
    return cast(int, args.func(args, container))


if __name__ == "__main__":
    sys.exit(main())
