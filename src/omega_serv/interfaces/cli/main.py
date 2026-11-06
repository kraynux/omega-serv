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
    omitted_history_notice,
)
from omega_serv.application.active_defense.sweep_active_defense import sweep_active_defense
from omega_serv.application.auth.manage_users import add_user, change_password, remove_user
from omega_serv.application.auth.manage_zones import add_zone, remove_zone
from omega_serv.application.config.apply_profile import plan_profile_application
from omega_serv.application.config.generate_config import generate_default_config
from omega_serv.application.config.load_config import load_config
from omega_serv.application.config.manage_option import set_option_enabled, waf_rule_packs_present
from omega_serv.application.config.validate_config import validate_config_environment
from omega_serv.application.security.manage_blocklist import (
    add_blocklist_entry,
    remove_blocklist_entry,
)
from omega_serv.application.security.run_audit import run_audit
from omega_serv.application.security.simulate_waf_request import simulate_waf_request
from omega_serv.application.server.engine_selection import log_reason
from omega_serv.application.server.engine_status import engine_connector_rows, engine_status_rows
from omega_serv.application.server.simulate_request import simulate_request
from omega_serv.application.server.start_server import (
    ActiveDefenseCollaborators,
    build_active_defense_collaborators,
    build_auth_zones_repository,
    build_blocklist_port,
    build_server,
    build_users_repository,
    build_waf_collaborators,
    try_reload_server,
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
from omega_serv.application.terminal.select_language import install_interface_language
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
from omega_serv.bootstrap.early_language import is_server_process
from omega_serv.bootstrap.paths import CONFIG_FILE
from omega_serv.core.i18n import _
from omega_serv.core.platform_info import cpu_info, running_as_root
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
from omega_serv.domain.security.waf.config import parse_waf_config
from omega_serv.domain.security.waf.reputation import effective_never_auto_block
from omega_serv.domain.services.entities import ServiceStatus
from omega_serv.domain.services.systemd_unit import SystemdUnitParams
from omega_serv.infrastructure.exporters.ioc_exporters import build_ioc_exporters
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
from omega_serv.infrastructure.waf.shared_counters import SharedCounters
from omega_serv.interfaces.cli.command_tree import add_command, add_group, cmd_help
from omega_serv.interfaces.cli.declaration_commands import (
    ServeCompanions,
    add_declaration_parser,
    build_declaration_scheduler,
)
from omega_serv.interfaces.cli.riposte_commands import (
    build_riposte_supervisor,
    cmd_riposte_run,
    cmd_riposte_status,
)
from omega_serv.interfaces.cli.riposte_query_commands import register as register_riposte_queries
from omega_serv.interfaces.cli.serve_native import (
    NativeSupervisor,
    current_decision,
    log_error_line,
    python_fallback_decision,
    write_python_engine_state,
)
from omega_serv.interfaces.cli.serve_workers import (
    RiposteChildPort,
    WorkerContext,
    effective_worker_count,
    open_listen_socket,
    run_workers,
)
from omega_serv.ports.service_manager_port import ServiceManagerPort


def _print_errors(errors: list[str], prefix: str = _("Erreur")) -> None:
    for error in errors:
        print(_("{prefix} : {error}").format(prefix=prefix, error=error), file=sys.stderr)


async def run_server_until_stopped(
    config: OmegaServConfig,
    config_path: Path,
    container: DependencyContainer,
    worker: WorkerContext | None = None,
    riposte: RiposteChildPort | None = None,
) -> int:
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
    server = build_server(
        config, container.project_root, container.filesystem, container.logger, container.clock,
        shared_counters=worker.shared_counters if worker else None,
    )

    try:
        await server.start(worker.listen_socket if worker else None)
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

    if worker is None:
        # Mode « boost » : le fichier PID et ce message sont ceux du processus principal.
        write_pid_file(container.filesystem, pid_path, os.getpid())
        print(f"OMEGA-SERV a l'ecoute sur {config.server.bind}:{config.server.port}")
    else:
        print(f"Worker {worker.index} pret (PID {os.getpid()})")

    stop_event = asyncio.Event()
    stopping = False

    async def _graceful_stop() -> None:
        nonlocal stopping
        if stopping:  # SIGTERM recu deux fois (systemd + processus principal) : un seul arret
            return
        stopping = True
        print("Arret demande - drainage des connexions en cours...")
        forced = await server.shutdown(config.server.shutdown_grace_period_seconds)
        if forced:
            print(f"{forced} connexion(s) fermee(s) de force apres le delai de grace.", file=sys.stderr)
        stop_event.set()

    async def _reload() -> None:
        print("Rechargement demande (SIGHUP) - regles WAF et zones Auth uniquement, bind/port/TLS inchanges...")
        if riposte is not None:
            riposte.reload()  # RIPOSTE relit sa propre configuration
        reload_result = load_config(container.configuration, config_path)
        if not reload_result.success:
            _print_errors(reload_result.errors, _("Erreur de rechargement"))
            return
        reloaded_config = reload_result.config
        assert reloaded_config is not None
        if reloaded_config.server.engine != config.server.engine:
            # Garde-fou §16.5 : le moteur ne change jamais a chaud - dit explicitement, jamais ignore en silence.
            engine_message = (f"server.engine passe de {config.server.engine!r} a {reloaded_config.server.engine!r} : "
                              "redemarrage complet necessaire (le reste du rechargement s'applique)")
            print(engine_message, file=sys.stderr)
            log_error_line(container, config, engine_message)
        error = try_reload_server(
            server, reloaded_config, container.project_root, container.filesystem, container.clock,
        )
        if error is not None:
            print(
                f"Rechargement REFUSE - les regles precedentes restent actives : {error}",
                file=sys.stderr,
            )
            return
        print("Rechargement termine.")

    loop = asyncio.get_running_loop()
    loop.add_signal_handler(signal.SIGTERM, lambda: asyncio.ensure_future(_graceful_stop()))
    loop.add_signal_handler(signal.SIGINT, lambda: asyncio.ensure_future(_graceful_stop()))
    loop.add_signal_handler(signal.SIGHUP, lambda: asyncio.ensure_future(_reload()))

    async def _supervise_riposte() -> None:
        assert riposte is not None
        while True:
            await asyncio.sleep(1.0)
            riposte.tick()

    riposte_task: asyncio.Future[None] | None = None
    if riposte is not None:
        riposte.start()
        riposte_task = asyncio.ensure_future(_supervise_riposte())

    try:
        serve_task = asyncio.ensure_future(server.serve_forever())
        await stop_event.wait()
        serve_task.cancel()
        try:
            await serve_task
        except asyncio.CancelledError:
            pass
    finally:
        if riposte_task is not None:
            riposte_task.cancel()
        if riposte is not None:
            await asyncio.to_thread(riposte.stop)
        if worker is None:
            remove_pid_file(container.filesystem, pid_path)
        loop.remove_signal_handler(signal.SIGTERM)
        loop.remove_signal_handler(signal.SIGINT)
        loop.remove_signal_handler(signal.SIGHUP)

    return 0


def _line_buffered_output() -> None:
    """Sous un gestionnaire de service, stdout n'est pas un terminal : Python le
    met en tampon par blocs et les messages du serveur ("a l'ecoute",
    "Rechargement demande/termine"...) n'arrivaient dans journalctl qu'a
    l'arret, tous dates de l'heure d'arret (constate sur craftdark le
    2026-10-26). Une ligne = une ecriture, quel que soit le gestionnaire."""
    for stream in (sys.stdout, sys.stderr):
        reconfigure = getattr(stream, "reconfigure", None)
        if reconfigure is not None:
            reconfigure(line_buffering=True)


def cmd_serve(args: argparse.Namespace, container: DependencyContainer) -> int:
    _line_buffered_output()
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
        _print_errors(env_errors, _("Erreur d'environnement"))
        return 1

    config = result.config
    # Processus accompagnant le serveur : RIPOSTE (None si desactive) et l'envoi quotidien de la
    # declaration anonyme (ne fait rien sans accord en mode quotidien). Pilotes ensemble.
    riposte = ServeCompanions(build_riposte_supervisor(config, args.config),
                              build_declaration_scheduler(container, args.config))

    # Moteur HTTP (plan moteur C++ lot 3, §16.5) : une seule decision, signalee si le moteur demande n'est pas
    # celui qui tournera.
    decision = current_decision(config, container)
    start_failure = ""
    if decision.fallback:
        for reason in decision.reasons:
            message = f"moteur natif demande mais non utilisable : {log_reason(reason)} - moteur Python utilise"
            print(message, file=sys.stderr)
            log_error_line(container, config, message)
    if decision.effective == "native":
        supervisor = NativeSupervisor(config, args.config, container, decision, riposte)
        try:
            start_failure = supervisor.start() or ""
        except PermissionError:
            print(
                f"Erreur : liaison sur {config.server.bind}:{config.server.port} refusee "
                "(privileges insuffisants pour un port < 1024).",
                file=sys.stderr,
            )
            return 1
        except OSError as e:
            print(f"Erreur au demarrage du serveur : {e}", file=sys.stderr)
            return 1
        if not start_failure:
            return supervisor.run()
        message = f"moteur natif indisponible au demarrage ({start_failure}) - repli sur le moteur Python"
        print(message, file=sys.stderr)
        log_error_line(container, config, message)
        decision = python_fallback_decision(decision, start_failure)
    write_python_engine_state(container, decision, start_failure)

    cpu = cpu_info()
    worker_count, capped = effective_worker_count(config.server.workers, "python", cpu.usable_cores)
    if capped:
        print(capped, file=sys.stderr)
        log_error_line(container, config, capped)
    if worker_count > 1:
        return _serve_with_workers(config, args.config, container, worker_count, riposte)

    async def _run() -> int:
        return await run_server_until_stopped(config, args.config, container, riposte=riposte)

    try:
        return asyncio.run(_run())
    except KeyboardInterrupt:
        return 0


def _serve_with_workers(
    config: OmegaServConfig, config_path: Path, container: DependencyContainer, worker_count: int,
    riposte: RiposteChildPort | None = None,
) -> int:
    """Mode « boost » (OMEGA-SERV_ETUDE_MODE_BOOST.md) : port et compteurs partages crees ici,
    dans le processus principal, AVANT le lancement des workers (interfaces/cli/serve_workers.py)."""
    try:
        listen_socket = open_listen_socket(config.server.bind, config.server.port, config.server.listen_backlog)
    except PermissionError:
        print(
            f"Erreur : liaison sur {config.server.bind}:{config.server.port} refusee "
            "(privileges insuffisants pour un port < 1024).",
            file=sys.stderr,
        )
        return 1
    except OSError as e:
        print(f"Erreur au demarrage du serveur : {e}", file=sys.stderr)
        return 1
    counters = SharedCounters.create(f"omega_serv_{config.server.port}")
    pid_path = container.project_root / "var" / "run" / "omega-serv.pid"
    write_pid_file(container.filesystem, pid_path, os.getpid())
    print(f"OMEGA-SERV a l'ecoute sur {config.server.bind}:{config.server.port}")

    def run_worker(worker: WorkerContext) -> int:
        return asyncio.run(run_server_until_stopped(config, config_path, container, worker))

    def read_configured_workers() -> int | None:
        reloaded = load_config(container.configuration, config_path)
        return reloaded.config.server.workers if reloaded.success and reloaded.config else None

    try:
        return run_workers(
            worker_count, listen_socket, counters, run_worker,
            config.server.shutdown_grace_period_seconds, read_configured_workers, riposte,
        )
    finally:
        counters.destroy()
        listen_socket.close()
        remove_pid_file(container.filesystem, pid_path)


def cmd_config_init(args: argparse.Namespace, container: DependencyContainer) -> int:
    result = generate_default_config(container.configuration, container.filesystem, args.config, force=args.force)
    print(result.message)
    return 0 if result.success else 1


def cmd_config_check(args: argparse.Namespace, container: DependencyContainer) -> int:
    result = load_config(container.configuration, args.config)
    if not result.success:
        _print_errors(result.errors, _("Erreur de configuration"))
        return 1
    assert result.config is not None

    env_errors = validate_config_environment(
        result.config, container.filesystem, container.project_root,
        self_signed_public_bind_confirmed=args.confirm_self_signed_public_bind,
        auth_without_tls_confirmed=args.confirm_auth_without_tls,
    )
    if env_errors:
        _print_errors(env_errors, _("Erreur d'environnement"))
        return 1

    print(_("{config} : configuration valide.").format(config=args.config))
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
        _print_errors(result.errors, _("Erreur de configuration"))
        return 1

    if getattr(args, "all", False):
        request = BackupRequest.everything(args.description)  # « Tout sauvegarder » (2026-11-01)
    else:
        request = BackupRequest(
            include_waf_rules=args.include_waf,
            include_auth_zones=args.include_auth,
            include_certificates=args.include_certificates,
            include_active_defense=args.include_active_defense,
            # getattr : options ajoutees le 2026-11-01, absentes d'un Namespace construit a la main.
            include_error_pages=getattr(args, "include_error_pages", False),
            include_preferences=getattr(args, "include_preferences", False),
            include_logs_library=getattr(args, "include_logs_library", False),
            include_riposte=getattr(args, "include_riposte", False),
            description=args.description,
        )
    if (request.include_auth_zones or request.include_certificates) and not args.confirm_secrets:
        print(
            _("Cette sauvegarde inclurait des secrets réels (hash de mot de passe et/ou "
            "clé privée TLS) jamais chiffres par défaut - ajoutez --confirm-secrets pour confirmer."),
            file=sys.stderr,
        )
        return 1

    backup_result = container.create_backup(request, result.config, args.config)
    print(backup_result.message)
    for skipped in backup_result.skipped:
        print("  - " + skipped)
    return 0 if backup_result.success else 1


def cmd_config_restore(args: argparse.Namespace, container: DependencyContainer) -> int:
    restore_result = container.restore_backup(
        args.snapshot_id, stop_and_restart=getattr(args, "stop_and_restart", False),
    )
    print(restore_result.message)
    if restore_result.needs_service_stop:
        print(_("Relancez avec --stop-and-restart pour arrêter le service, restaurer puis le redémarrer."))
    return 0 if restore_result.success else 1


def cmd_config_list_backups(args: argparse.Namespace, container: DependencyContainer) -> int:
    backups = container.list_backups()
    if not backups:
        print(_("Aucune sauvegarde."))
        return 0
    for metadata in backups:
        size_kb = (metadata.file_size_bytes or 0) / 1024
        print(
            _("{snapshot_id}  {value}  {scope:<20}  {size_kb:.1f} Ko  {value2}  {description}").format(snapshot_id=metadata.snapshot_id, value=metadata.created_at.isoformat(), scope=metadata.scope, size_kb=size_kb, value2=metadata.status.value, description=metadata.description)
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
        print(_("Erreur : {e}").format(e=e), file=sys.stderr)
        return 1
    print(_("Profil : {name}").format(name=profile.name))
    print(_(profile.description))
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
        print(_("Erreur : {e}").format(e=e), file=sys.stderr)
        return 1

    plan = plan_profile_application(load_result.config, profile)

    print(_("Profil de base choisi : {name}").format(name=profile.name))
    if not plan.changes:
        print(_("Aucune modification."))
    else:
        print(_("Modifications :"))
        for change in plan.changes:
            print(str(change))

    if plan.conflicts:
        print(_("\nConflits détectés :"))
        for conflict in plan.conflicts:
            print(_("  [{value}] {message}").format(value=conflict.severity.upper(), message=conflict.message))

    if plan.validation_errors:
        _print_errors(plan.validation_errors, _("Erreur de validation"))

    if args.dry_run:
        print(_("\n(--dry-run : aucune écriture effectuée)"))
        return 1 if plan.has_blocking_issues else 0

    if plan.has_blocking_issues and not args.force:
        print(_("\nApplication refusée (problèmes bloquants, voir ci-dessus). Utiliser --force pour outrepasser."), file=sys.stderr)
        return 1

    container.configuration.save(args.config, plan.new_config)
    print(_("\nConfiguration mise à jour dans {config} (profil '{name}' appliqué).").format(config=args.config, name=profile.name))
    return 0


def cmd_option_list(args: argparse.Namespace, container: DependencyContainer) -> int:
    result = load_config(container.configuration, args.config)
    if not result.success:
        _print_errors(result.errors)
        return 1
    assert result.config is not None
    for name, option in sorted(result.config.options.items()):
        state = _("actif") if option.enabled else _("inactif")
        print(_("{name} : {state}").format(name=name, state=state))
    return 0


def _cmd_option_set(args: argparse.Namespace, container: DependencyContainer, enabled: bool) -> int:
    load_result = load_config(container.configuration, args.config)
    if not load_result.success:
        _print_errors(load_result.errors)
        return 1
    assert load_result.config is not None

    result = set_option_enabled(load_result.config, args.name, enabled,
                                waf_rule_packs_present(container.filesystem, container.project_root))
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

    print(_("Méthode          : {method}").format(method=report.method))
    print(_("Chemin demandé   : {raw_path}").format(raw_path=report.raw_path))
    print(_("Chemin normalisé : {normalized_path}").format(normalized_path=report.normalized_path))
    print(_("Méthode autorisée: {method_allowed}").format(method_allowed=report.method_allowed))
    print(_("Refusé (règles)  : {denied_by_access_policy}").format(denied_by_access_policy=report.denied_by_access_policy))
    print(_("Fichier existe   : {file_exists}").format(file_exists=report.file_exists))
    print(_("Statut réponse   : {response_status}").format(response_status=report.response_status))
    if report.rejection_reason:
        print(_("Motif de refus   : {rejection_reason}").format(rejection_reason=report.rejection_reason))
    print(_("En-têtes attendus :"))
    for name, value in report.response_headers.items():
        print(_("  {name}: {value}").format(name=name, value=value))
    return 0


def cmd_waf_never_auto_block(args: argparse.Namespace, container: DependencyContainer) -> int:
    """Affiche, un par ligne, les reseaux REELLEMENT exemptes d'auto-ban
    pour cette configuration (OMEGA-SERV_PLAN-DETAILLE_SENSITIVE_PATHS.md
    §3.13/§3.14-a : `reputation.never_auto_block`, exemption loopback
    retiree sans proxy de confiance). Lu par omega-jail a l'installation
    (lot 10 : `ignoreip` des jails, pont Tailscale) - jamais une copie
    de la liste par defaut dans un autre projet. Ne charge aucune regle :
    fonctionne meme si un pack ou une liste est en erreur."""
    load_result = load_config(container.configuration, args.config)
    if not load_result.success:
        _print_errors(load_result.errors)
        return 1
    config = load_result.config
    assert config is not None
    waf_settings = config.options["waf"].settings if "waf" in config.options else {}
    networks = effective_never_auto_block(
        parse_waf_config(waf_settings).reputation.never_auto_block, config.option_enabled("trusted_proxy"),
    )
    for network in networks:
        print(network)
    return 0


def cmd_waf_test(args: argparse.Namespace, container: DependencyContainer) -> int:
    load_result = load_config(container.configuration, args.config)
    if not load_result.success:
        _print_errors(load_result.errors)
        return 1
    assert load_result.config is not None

    waf = build_waf_collaborators(load_result.config, container.project_root, container.filesystem, container.clock, force=True)
    if waf is None:
        print(_("Erreur : options.waf absent de la configuration (exécuter 'omega-serv config init' ou ajouter la section waf)."), file=sys.stderr)
        return 1

    report = asyncio.run(
        simulate_waf_request(args.method, args.path, args.query or "", args.body or "", args.remote_ip, waf)
    )
    decision = report.decision

    if report.native_decision is not None:
        print(_("Décision native : {value} (score {score})").format(value=report.native_decision.action.upper(), score=report.native_decision.score))
    if report.magnet_decision is not None:
        print(_("Décision magnet : {value} (score {score})").format(value=report.magnet_decision.action.upper(), score=report.magnet_decision.score))
    if report.magnet_error:
        print(_("ATTENTION - le script magnet a levé une erreur sur cette requête : {magnet_error}").format(magnet_error=report.magnet_error))
    if report.magnet_unsupported_members:
        print(
            _("ATTENTION - le script magnet référence lighty.{{{value}}}, non supporte par ce pont (toujours nil - le script peut se comporter différemment qu'en Lighttpd réel)").format(value=', '.join(sorted(report.magnet_unsupported_members)))
        )
    if waf.config.magnet.on_error == "fail-closed" and (report.magnet_error or report.magnet_unsupported_members):
        print(
            _("ATTENTION - options.waf.magnet.on_error='fail-closed' combiné à une incompatibilité détectée : "
            "toute requête future qui déclenche la même erreur sera BLOQUÉE (y compris du trafic légitime). "
            "Passer à 'ignore', ou corriger le script, avant d'activer ce script en production.")
        )
    print(_("Décision finale : {value}").format(value=decision.action.upper()))
    print(_("Statut : {value}").format(value=decision.status_code if decision.status_code is not None else '-'))
    print(_("Score : {score}").format(score=decision.score))
    print(_("Règles : {value}").format(value=', '.join(f'{f.rule_id} ({f.pack})' for f in decision.findings) or '-'))
    print(_("Politique de zone : {zone_id}").format(zone_id=report.zone_id))
    print(_("Mode : {mode}").format(mode=report.mode))
    if decision.blocked_reason:
        print(_("Motif : {blocked_reason}").format(blocked_reason=decision.blocked_reason))
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
        print(_("Aucune entrée."))
        return 0
    for entry in entries:
        expiry = entry.expires_at or _("permanent")
        print(_("{network}\t{source}\t{expiry}\t{reason}").format(network=entry.network, source=entry.source, expiry=expiry, reason=entry.reason))
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
        print(_("Erreur d'accès à la base Active Defense : {exc}.").format(exc=exc), file=sys.stderr)
        print(
            _("Si l'appartenance à un groupe système a changé récemment, une nouvelle "
            "session (deconnexion/reconnexion) peut être nécessaire."),
            file=sys.stderr,
        )
        return None
    if active_defense is None:
        print(_("Erreur : options.active_defense absent ou désactivé de la configuration."), file=sys.stderr)
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
        print(_("Erreur d'accès à la base Active Defense : {exc}.").format(exc=exc), file=sys.stderr)
        return 1
    if active_defense is None:
        print(_("Active Defense : désactivé (options.active_defense.enabled = false ou absent)."))
        return 0
    print(_("Active Defense : activé (mode={mode})").format(mode=active_defense.config.mode))
    print(_("Mode guerre : {value}").format(value=_('activé') if active_defense.config.war_mode.enabled else _('inactif')))
    print(_("Deception : {value}").format(value=_('activé') if active_defense.config.deception.enabled else _('inactive')))
    tracked = active_defense.threat_state_repository.list_all()
    print(_("Sources suivies : {count}").format(count=len(tracked)))
    return 0


def cmd_threats_list(args: argparse.Namespace, container: DependencyContainer) -> int:
    active_defense = _require_active_defense(args, container)
    if active_defense is None:
        return 1

    states = list_threat_states(active_defense.threat_state_repository, level=args.level)
    if not states:
        print(_("Aucune menace suivie."))
        return 0
    for state in states:
        print(_("{subject_id}\t{score}\t{level}\t{value}\t{value2}").format(subject_id=state.subject_id, score=state.score, level=state.level, value=state.updated_at.isoformat(), value2=state.expires_at.isoformat()))
    return 0


def cmd_threats_show(args: argparse.Namespace, container: DependencyContainer) -> int:
    active_defense = _require_active_defense(args, container)
    if active_defense is None:
        return 1

    state = get_threat_state(active_defense.threat_state_repository, args.subject_id)
    if state is None:
        print(_("Aucune menace suivie pour {subject_id!r}.").format(subject_id=args.subject_id), file=sys.stderr)
        return 1
    print(_("Source : {subject_id}").format(subject_id=state.subject_id))
    print(_("Score : {score}").format(score=state.score))
    print(_("Niveau : {level}").format(level=state.level))
    print(_("Mise à jour : {value}").format(value=state.updated_at.isoformat()))
    print(_("Expiration : {value}").format(value=state.expires_at.isoformat()))
    print(_("Actions actives : {value}").format(value=', '.join(state.active_actions) or '-'))
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
        print(_("Aucun incident."))
        return 0
    for incident in incidents:
        closed = incident.closed_at.isoformat() if incident.closed_at else "-"
        print(_("{incident_id}\t{subject_id}\t{status}\t{value}\t{closed}").format(incident_id=incident.incident_id, subject_id=incident.subject_id, status=incident.status, value=incident.opened_at.isoformat(), closed=closed))
    return 0


def cmd_incidents_show(args: argparse.Namespace, container: DependencyContainer) -> int:
    active_defense = _require_active_defense(args, container)
    if active_defense is None:
        return 1

    incident = active_defense.incident_repository.get(args.incident_id)
    if incident is None:
        print(_("Incident introuvable : {incident_id!r}.").format(incident_id=args.incident_id), file=sys.stderr)
        return 1
    print(_("Incident : {incident_id}").format(incident_id=incident.incident_id))
    print(_("Source : {subject_id}").format(subject_id=incident.subject_id))
    print(_("Statut : {status}").format(status=incident.status))
    print(_("Ouvert le : {value}").format(value=incident.opened_at.isoformat()))
    print(_("Fermé le : {value}").format(value=incident.closed_at.isoformat() if incident.closed_at else '-'))
    print(_("Chronologie :"))
    for event in get_incident_timeline(active_defense.incident_repository, args.incident_id):
        print(_("  {value}\t{kind}\t{detail}").format(value=event.occurred_at.isoformat(), kind=event.kind, detail=event.detail))
    if incident.omitted_events:
        print("  " + omitted_history_notice(incident.omitted_events))
    return 0


def cmd_incidents_close(args: argparse.Namespace, container: DependencyContainer) -> int:
    active_defense = _require_active_defense(args, container)
    if active_defense is None:
        return 1

    closed = close_incident(active_defense.incident_repository, container.clock, args.incident_id)
    if closed is None:
        print(_("Incident introuvable ou déjà fermé : {incident_id!r}.").format(incident_id=args.incident_id), file=sys.stderr)
        return 1
    print(_("Incident {incident_id!r} fermé.").format(incident_id=closed.incident_id))
    if active_defense.config.ioc.auto_export_on_close:
        export_dir = container.project_root / active_defense.config.storage.export_dir
        exporters = build_ioc_exporters(container.filesystem, export_dir, active_defense.config.ioc)
        for export_format in active_defense.config.ioc.formats:
            if export_format in exporters:
                result = exporters[export_format].export(closed)
            elif export_format == "markdown":
                result = MarkdownIncidentReportExporter(container.filesystem, export_dir).render(closed)
            else:
                continue
            print(_("Auto-export ({export_format}) : {path}").format(export_format=export_format, path=result.path))
    return 0


def cmd_incidents_export_ioc(args: argparse.Namespace, container: DependencyContainer) -> int:
    active_defense = _require_active_defense(args, container)
    if active_defense is None:
        return 1

    incident = active_defense.incident_repository.get(args.incident_id)
    if incident is None:
        print(_("Incident introuvable : {incident_id!r}.").format(incident_id=args.incident_id), file=sys.stderr)
        return 1

    export_dir = container.project_root / active_defense.config.storage.export_dir
    exporters = build_ioc_exporters(container.filesystem, export_dir, active_defense.config.ioc)
    for export_format in (f.strip() for f in args.format.split(",")):
        exporter = exporters.get(export_format)
        if exporter is None:
            print(_("Format d'export inconnu : {export_format!r} (json, csv, stix ou misp).").format(export_format=export_format), file=sys.stderr)
            return 1
        result = exporter.export(incident)
        print(_("Exporté : {path}").format(path=result.path))
    return 0


def cmd_incidents_generate_report(args: argparse.Namespace, container: DependencyContainer) -> int:
    active_defense = _require_active_defense(args, container)
    if active_defense is None:
        return 1

    incident = active_defense.incident_repository.get(args.incident_id)
    if incident is None:
        print(_("Incident introuvable : {incident_id!r}.").format(incident_id=args.incident_id), file=sys.stderr)
        return 1

    export_dir = container.project_root / active_defense.config.storage.export_dir
    result = MarkdownIncidentReportExporter(container.filesystem, export_dir).render(incident)
    print(_("Rapport généré : {path}").format(path=result.path))
    return 0


def cmd_deception_list(args: argparse.Namespace, container: DependencyContainer) -> int:
    active_defense = _require_active_defense(args, container)
    if active_defense is None:
        return 1

    assignments = active_defense.deception_assignment_repository.list_active()
    if not assignments:
        print(_("Aucune affectation de leurre."))
        return 0
    now = container.clock.now()
    for assignment in assignments:
        status = _("active") if is_assignment_active(assignment, now) else _("expirée")
        print(
            _("{subject_id}\t{profile_name}\t{status}\t{value}\t{value2}").format(subject_id=assignment.subject_id, profile_name=assignment.profile_name, status=status, value=assignment.assigned_at.isoformat(), value2=assignment.expires_at.isoformat())
        )
    return 0


def cmd_deception_release(args: argparse.Namespace, container: DependencyContainer) -> int:
    active_defense = _require_active_defense(args, container)
    if active_defense is None:
        return 1

    release_deception(active_defense.deception_assignment_repository, args.subject_id)
    print(_("Affectation de leurre libérée pour {subject_id!r} (si elle existait).").format(subject_id=args.subject_id))
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
            _("Classe d'attaque inconnue : {attack_class!r} (valeurs possibles : {value}).").format(attack_class=args.attack_class, value=', '.join(sorted(KNOWN_ATTACK_CLASSES))),
            file=sys.stderr,
        )
        return 1
    subject_id = f"{args.ip}:{hash_payload((args.user_agent or '').encode('utf-8'))}"
    preview = preview_playbook_decision(
        active_defense.threat_state_repository, active_defense.incident_repository,
        active_defense.deception_assignment_repository, container.clock, active_defense.config,
        subject_id=subject_id, attack_class=cast("AttackClass", args.attack_class), score_delta=args.score,
    )
    print(_("Source (simulée) : {subject_id}  (chemin observé : {path})").format(subject_id=preview.subject_id, path=args.path))
    print(_("Score : {previous_score} -> {projected_score}").format(previous_score=preview.previous_score, projected_score=preview.projected_score))
    print(_("Niveau : {previous_level} -> {projected_level}").format(previous_level=preview.previous_level, projected_level=preview.projected_level))
    for line in preview.explanation:
        print(_("  - {line}").format(line=line))
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
    print(_("États de menace purgés : {purged_threat_states}").format(purged_threat_states=result.purged_threat_states))
    print(_("Incidents fermés automatiquement : {count}").format(count=len(result.closed_incidents)))
    for incident_id in result.closed_incidents:
        print(_("  - {incident_id}").format(incident_id=incident_id))
    print(_("Incidents fermés depuis plus de 90 jours supprimés : {count}").format(count=result.purged_closed_incidents))
    if result.closed_incidents and active_defense.config.ioc.auto_export_on_close:
        from omega_serv.application.active_defense.auto_export import auto_export_closed_incidents
        from omega_serv.infrastructure.exporters.ioc_exporters import build_ioc_exporters
        from omega_serv.infrastructure.exporters.markdown_incident_report_exporter import (
            MarkdownIncidentReportExporter,
        )

        export_dir = container.project_root / active_defense.config.storage.export_dir
        exporters = build_ioc_exporters(container.filesystem, export_dir, active_defense.config.ioc)
        written = auto_export_closed_incidents(
            result.closed_incidents, active_defense.incident_repository, active_defense.config,
            lambda incident, fmt: exporters[fmt].export(incident) if fmt in exporters else None,
            lambda incident: MarkdownIncidentReportExporter(container.filesystem, export_dir).render(incident),
            lambda message: print(_("Export automatique impossible : {message}").format(message=message), file=sys.stderr),
        )
        print(_("Exports automatiques écrits : {count}").format(count=written))
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
        print(_("Erreur : {e}").format(e=e), file=sys.stderr)
        return 1

    print(result.message)
    return 0 if result.success else 1


def cmd_certs_generate_ca(args: argparse.Namespace, container: DependencyContainer) -> int:
    password = _resolve_ca_password(args)
    if password is None:
        print(_("Erreur : les deux saisies de passphrase ne correspondent pas."), file=sys.stderr)
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
        print(_("Erreur : {e}").format(e=e), file=sys.stderr)
        return 1

    print(result.message)
    if result.success:
        print(_("Importez {value} dans le magasin de confiance des clients (doc TLS §7.4).").format(value=ca_dir / _('root-ca.pem')))
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
        print(_("Erreur : {e}").format(e=e), file=sys.stderr)
        return 1

    print(result.message)
    if result.success:
        print(_("Redémarrage requis pour que le nouveau certificat soit pris en compte (`omega-serv service restart`)."))
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
        print(_("Erreur : {e}").format(e=e), file=sys.stderr)
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
        print(_("Erreur : {e}").format(e=e), file=sys.stderr)
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
        print(_("Erreur : {e}").format(e=e), file=sys.stderr)
        return 1

    print(result.message)
    return 0 if result.success else 1


def _print_certificate_report(report: CertificateReport) -> None:
    info = report.info
    print(_("Sujet : {subject}").format(subject=info.subject))
    print(_("Émetteur : {issuer}").format(issuer=info.issuer))
    print(_("Début de validité : {value}").format(value=info.not_before.isoformat()))
    print(_("Fin de validité : {value}").format(value=info.not_after.isoformat()))
    print(_("Jours restants : {days_remaining}").format(days_remaining=report.days_remaining))
    print(_("Type de clé : {key_type} ({key_bits} bits)").format(key_type=info.key_type, key_bits=info.key_bits) if info.key_bits else _("Type de clé : {key_type}").format(key_type=info.key_type))
    print(_("Algorithme de signature : {signature_algorithm}").format(signature_algorithm=info.signature_algorithm))
    if info.san_dns or info.san_ip:
        print(_("SAN :"))
        for dns in info.san_dns:
            print(_("  - DNS:{dns}").format(dns=dns))
        for ip in info.san_ip:
            print(_("  - IP:{ip}").format(ip=ip))
    print()
    print(_("[{value}] Certificat {value2}").format(value=_('ERREUR') if report.is_expired else _('OK'), value2=_('expiré') if report.is_expired else _('non expiré')))
    if report.key_matches is not None:
        print(_("[{value}] Clé privée {value2}").format(value=_('OK') if report.key_matches else _('ERREUR'), value2=_('correspondante') if report.key_matches else _('NE correspond PAS')))
    if report.key_mode is not None:
        strict = not (report.key_mode & 0o077)
        print(_("[{value}] Permissions clé privée : {value2}").format(value=_('OK') if strict else _('ERREUR'), value2=oct(report.key_mode)))
    if info.is_self_signed:
        print(_("[AVERTISSEMENT] Certificat auto-signé, non approuvé par défaut par les navigateurs"))
    if report.expiring_soon and not report.is_expired:
        print(_("[AVERTISSEMENT] Certificat bientôt expiré ({days_remaining} jours restants)").format(days_remaining=report.days_remaining))


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
        print(_("Erreur : {e}").format(e=e), file=sys.stderr)
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
    print(_("TLS activé (mode {mode}) dans {config}.").format(mode=args.mode, config=args.config))
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
    print(_("TLS désactivé dans {config}.").format(config=args.config))
    return 0


def _resolve_password(args: argparse.Namespace) -> str:
    """N'affiche jamais le mot de passe sur la ligne de commande si
    `--password` est omis (spec §15.4 : "demander le mot de passe sans
    l'afficher") - seule commande de ce CLI par ailleurs non-interactif
    a en avoir besoin, un mot de passe sur la ligne de commande finirait
    dans l'historique du shell."""
    if args.password:
        return str(args.password)
    return getpass.getpass(_("Mot de passe : "))


def _resolve_ca_password(args: argparse.Namespace) -> str | None:
    """Doc TLS §7.3 etape 3 : "demander ET CONFIRMER une passphrase pour
    la cle de CA" - double saisie interactive si `--password` est omis,
    plus stricte que _resolve_password (simple saisie) car la cle de CA
    est la plus sensible du projet (doc TLS §7.2). Retourne None si les
    deux saisies ne correspondent pas (appelant : erreur, jamais de
    nouvelle tentative silencieuse)."""
    if args.password:
        return str(args.password)
    first = getpass.getpass(_("Passphrase de la CA : "))
    second = getpass.getpass(_("Confirmer la passphrase : "))
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

    print(_("Utilisateurs :"))
    for user in users:
        print(_("  - {username}").format(username=user.username))
    print(_("Zones protégées :"))
    for zone in zones:
        methods = ", ".join(zone.allow_methods) or _("toutes")
        print(_("  - {path_prefix} (realm={realm!r}, utilisateurs={value}, methodes={methods})").format(path_prefix=zone.path_prefix, realm=zone.realm, value=list(zone.allowed_users), methods=methods))
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
            print(_("[INFO] {label} absent ({path})").format(label=label, path=path))
            continue
        mode = container.filesystem.file_mode(path)
        strict = not (mode & 0o077)
        print(_("[{value}] {label} permissions : {value2}").format(value=_('OK') if strict else _('AVERTISSEMENT'), label=label, value2=oct(mode)))
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
        print(_("Erreur : aucun gestionnaire de service reconnu (systemd/OpenRC/runit) sur ce système."), file=sys.stderr)
        return None
    return _build_service_manager(manager_type)


def cmd_engine_status(args: argparse.Namespace, container: DependencyContainer) -> int:
    """Moteur HTTP demande / effectif / raisons (plan moteur C++ §16.5) - memes lignes que l'ecran Etat."""
    result = load_config(container.configuration, args.config)
    if not result.success or result.config is None:
        _print_errors(result.errors)
        return 1
    status = container.engine_status(result.config)
    for label, value, _style in engine_status_rows(status):
        print(_("{label} : {value}").format(label=label, value=value))
    connectors = engine_connector_rows(status)
    if connectors:
        print(_("Connecteurs (moteur natif) :"))
        for label, value, _style in connectors:
            print(_("  {label} : {value}").format(label=label, value=value))
    return 0


def cmd_service_status(args: argparse.Namespace, container: DependencyContainer) -> int:
    manager = _detect_or_fail()
    if manager is None:
        return 1
    result = get_service_status(manager, args.service_name)
    if isinstance(result, ServiceStatus):
        print(_("Service : {service_name}").format(service_name=result.service_name))
        print(_("Actif   : {active}").format(active=result.active))
        print(_("Activé au démarrage : {enabled}").format(enabled=result.enabled))
        print(_("État    : {state} ({sub_state})").format(state=result.state, sub_state=result.sub_state))
        if result.description:
            print(_("Description : {description}").format(description=result.description))
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
            _("Erreur : génération d'unité non supportée pour {value} (seul systemd est supporte en V1, voir OMEGA-SERV_PLAN_DEVELOPPEMENT.md §5).").format(value=manager_type or _('aucun gestionnaire détecté')),
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
        print(_("Erreur : désinstallation d'unité non supportée pour {value}.").format(value=manager_type or _('aucun gestionnaire détecté')), file=sys.stderr)
        return 1

    manager = SystemdServiceManager(SubprocessRunner())
    unit_path = Path(args.unit_path) if args.unit_path else Path(f"/etc/systemd/system/{args.service_name}.service")
    result = uninstall_systemd_service(container.filesystem, unit_path, manager)
    print(result.message)
    return 0 if result.success else 1


_SEVERITY_LABELS = {
    Severity.CRITICAL: _("CRITICAL"), Severity.HIGH: _("HIGH"), Severity.MEDIUM: _("MEDIUM"),
    Severity.LOW: _("LOW"), Severity.INFO: _("INFO"),
}


def _print_audit_findings(findings: list[AuditFinding]) -> None:
    if not findings:
        print(_("Aucun problème détecté."))
        return
    for finding in findings:
        label = _SEVERITY_LABELS[finding.severity]
        print(_("[{label}] {rule_id} {rule_name}").format(label=label, rule_id=finding.rule_id, rule_name=finding.rule_name))
        print(f"    {finding.message}")
        print(_("    -> {recommendation}").format(recommendation=finding.recommendation))


def cmd_audit_security(args: argparse.Namespace, container: DependencyContainer) -> int:
    load_result = load_config(container.configuration, args.config)
    if not load_result.success:
        _print_errors(load_result.errors, _("Erreur de configuration"))
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
        print(_("Résumé : {critical} critical, {high} high, {medium} medium, {low} low, {info} info").format(critical=summary['critical'], high=summary['high'], medium=summary['medium'], low=summary['low'], info=summary['info']))
        print(_("État : sécurisé") if result.is_secure else _("État : NON SÉCURISÉ"))

    return result.exit_code


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="omega-serv",
        description=_("Serveur web sécurisé (WAF, TLS, RIPOSTE, Active Defense). Sans argument : interface "
                      "interactive. Avec une commande : ligne de commande, scriptable."),
        epilog=_("Toutes les commandes : omega-serv help. Manuel : man omega-serv."),
    )
    parser.add_argument("--config", type=Path, default=CONFIG_FILE, metavar=_("FICHIER"),
                        help=_("Fichier de configuration (défaut : config/omega-serve.json de l'installation)."))
    subparsers = parser.add_subparsers(dest="command", required=True, title=_("commandes"), metavar=_("COMMANDE"))

    confirm_self_signed = _("Accepte un certificat auto-signé sur une adresse publique.")
    confirm_auth_without_tls = _("Accepte des zones à mot de passe sans TLS (mots de passe lisibles sur le réseau).")
    method_help = _("Méthode HTTP (défaut : GET).")

    serve_parser = add_command(subparsers, "serve", _(
        "Démarre le serveur au premier plan (c'est ce que lance le service système). Refuse de tourner en root."))
    serve_parser.add_argument("--confirm-self-signed-public-bind", action="store_true", help=confirm_self_signed)
    serve_parser.add_argument("--confirm-auth-without-tls", action="store_true", help=confirm_auth_without_tls)
    serve_parser.set_defaults(func=cmd_serve)

    config_sub = add_group(subparsers, "config", _(
        "Fichier de configuration : création, vérification, TLS, sauvegardes."), "config_command")
    init_parser = add_command(config_sub, "init", _("Crée le fichier de configuration par défaut."))
    init_parser.add_argument("--force", action="store_true", help=_("Écrase le fichier existant."))
    init_parser.set_defaults(func=cmd_config_init)
    check_parser = add_command(config_sub, "check", _(
        "Vérifie la configuration et l'environnement (chemins, droits, certificats) sans démarrer."))
    check_parser.add_argument("--confirm-self-signed-public-bind", action="store_true", help=confirm_self_signed)
    check_parser.add_argument("--confirm-auth-without-tls", action="store_true", help=confirm_auth_without_tls)
    check_parser.set_defaults(func=cmd_config_check)
    add_command(config_sub, "show", _("Affiche la configuration chargée, en JSON.")).set_defaults(func=cmd_config_show)
    enable_tls_parser = add_command(config_sub, "enable-tls", _("Active TLS dans la configuration."))
    enable_tls_parser.add_argument("--cert", default="", metavar=_("FICHIER"),
                                   help=_("Certificat à utiliser (sinon celui déjà configuré)."))
    enable_tls_parser.add_argument("--key", default="", metavar=_("FICHIER"),
                                   help=_("Clé privée à utiliser (sinon celle déjà configurée)."))
    enable_tls_parser.add_argument("--mode", choices=("direct", "behind_proxy"), default="direct", help=_(
        "direct : omega-serv chiffre lui-même ; behind_proxy : derrière un reverse proxy (défaut : direct)."))
    enable_tls_parser.set_defaults(func=cmd_config_enable_tls)
    add_command(config_sub, "disable-tls", _("Désactive TLS dans la configuration.")).set_defaults(
        func=cmd_config_disable_tls)
    backup_parser = add_command(config_sub, "backup", _(
        "Crée une sauvegarde : la configuration toujours, le reste selon les options --include-*."))
    backup_parser.add_argument("--include-waf", action="store_true", help=_("Ajoute les règles et listes du WAF."))
    backup_parser.add_argument("--include-auth", action="store_true", help=_(
        "Ajoute les utilisateurs et les zones protégées (secrets : demande --confirm-secrets)."))
    backup_parser.add_argument("--include-certificates", action="store_true", help=_(
        "Ajoute les certificats et les clés TLS (secrets : demande --confirm-secrets)."))
    backup_parser.add_argument("--include-active-defense", action="store_true",
                               help=_("Ajoute la base Active Defense."))
    backup_parser.add_argument("--include-error-pages", action="store_true",
                               help=_("Ajoute les pages d'erreur personnalisées."))
    backup_parser.add_argument("--include-preferences", action="store_true",
                               help=_("Ajoute les préférences de l'interface."))
    backup_parser.add_argument("--include-logs-library", action="store_true",
                               help=_("Ajoute la bibliothèque des journaux."))
    backup_parser.add_argument("--include-riposte", action="store_true", help=_("Ajoute la base RIPOSTE."))
    backup_parser.add_argument("--all", action="store_true", help=_(
        "Tout sauvegarder : toutes les options --include-* (secrets compris : demande --confirm-secrets)."))
    backup_parser.add_argument("--confirm-secrets", action="store_true", help=_(
        "Confirme l'ajout de secrets non chiffrés (hash de mots de passe, clés privées)."))
    backup_parser.add_argument("--description", default="", metavar=_("TEXTE"),
                               help=_("Texte libre enregistré avec la sauvegarde."))
    backup_parser.set_defaults(func=cmd_config_backup)
    restore_parser = add_command(config_sub, "restore", _("Restaure une sauvegarde."))
    restore_parser.add_argument("--snapshot-id", required=True, metavar=_("ID"),
                                help=_("Identifiant de la sauvegarde (voir config list-backups)."))
    restore_parser.add_argument("--stop-and-restart", action="store_true", help=_(
        "Arrête le service, restaure, puis le redémarre (nécessaire si le service tourne)."))
    restore_parser.set_defaults(func=cmd_config_restore)
    add_command(config_sub, "list-backups", _("Liste les sauvegardes.")).set_defaults(func=cmd_config_list_backups)

    profile_sub = add_group(subparsers, "profile", _("Profils de configuration prêts à l'emploi."), "profile_command")
    add_command(profile_sub, "list", _("Liste les profils disponibles.")).set_defaults(func=cmd_profile_list)
    profile_name = _("Nom du profil (voir profile list).")
    show_parser = add_command(profile_sub, "show", _("Affiche un profil et les valeurs qu'il fixe."))
    show_parser.add_argument("name", metavar=_("NOM"), help=profile_name)
    show_parser.set_defaults(func=cmd_profile_show)
    apply_parser = add_command(profile_sub, "apply", _(
        "Applique un profil à la configuration (modifications et conflits affichés d'abord)."))
    apply_parser.add_argument("name", metavar=_("NOM"), help=profile_name)
    apply_parser.add_argument("--dry-run", action="store_true",
                              help=_("Montre seulement ce qui changerait, sans rien écrire."))
    apply_parser.add_argument("--force", action="store_true", help=_("Applique malgré des problèmes bloquants."))
    apply_parser.set_defaults(func=cmd_profile_apply)

    option_sub = add_group(subparsers, "option", _(
        "Modules optionnels (waf, fastcgi, active_defense, riposte...)."), "option_command")
    add_command(option_sub, "list", _("Liste les options et leur état.")).set_defaults(func=cmd_option_list)
    option_name = _("Nom de l'option (voir option list).")
    enable_parser = add_command(option_sub, "enable", _("Active une option."), _(
        "Première activation du WAF : tous les packs de secure/waf/rules/ sont ajoutés, en mode log-only."))
    enable_parser.add_argument("name", metavar=_("NOM"), help=option_name)
    enable_parser.set_defaults(func=cmd_option_enable)
    disable_parser = add_command(option_sub, "disable", _("Désactive une option."))
    disable_parser.add_argument("name", metavar=_("NOM"), help=option_name)
    disable_parser.set_defaults(func=cmd_option_disable)

    simulate_parser = add_command(subparsers, "simulate-request", _(
        "Montre comment le serveur traiterait une requête (chemin, règles, statut, en-têtes), sans l'envoyer."))
    simulate_parser.add_argument("--method", default="GET", help=method_help)
    simulate_parser.add_argument("--url", required=True, metavar=_("CHEMIN"),
                                 help=_("Chemin demandé, par exemple /docs/index.html."))
    simulate_parser.set_defaults(func=cmd_simulate_request)

    waf_sub = add_group(subparsers, "waf", _("Pare-feu applicatif (WAF)."), "waf_command")
    test_parser = add_command(waf_sub, "test", _(
        "Soumet une requête fictive au WAF et affiche sa décision (règles, score, statut)."))
    test_parser.add_argument("--method", default="GET", help=method_help)
    test_parser.add_argument("--path", required=True, metavar=_("CHEMIN"), help=_("Chemin de la requête."))
    test_parser.add_argument("--query", default="", metavar=_("TEXTE"), help=_("Chaîne de requête, sans le « ? »."))
    test_parser.add_argument("--body", default="", metavar=_("TEXTE"), help=_("Corps de la requête."))
    test_parser.add_argument("--remote-ip", default="127.0.0.1", metavar="IP",
                             help=_("Adresse du client simulé (défaut : 127.0.0.1)."))
    test_parser.set_defaults(func=cmd_waf_test)
    add_command(waf_sub, "never-auto-block", _(
        "Affiche les réseaux jamais bannis automatiquement (lu par omega-jail).")).set_defaults(
        func=cmd_waf_never_auto_block)

    blocklist_sub = add_group(subparsers, "blocklist", _("Adresses bannies."), "blocklist_command")
    add_command(blocklist_sub, "list", _("Affiche les bans : réseau, origine, expiration, motif.")).set_defaults(
        func=cmd_blocklist_list)
    add_parser = add_command(blocklist_sub, "add", _("Bannit une adresse ou un réseau."))
    add_parser.add_argument("--network", required=True, metavar=_("RESEAU"),
                            help=_("Adresse IP ou réseau CIDR, par exemple 203.0.113.7 ou 203.0.113.0/24."))
    add_parser.add_argument("--reason", required=True, metavar=_("TEXTE"), help=_("Motif du ban."))
    add_parser.add_argument("--duration-seconds", type=int, default=None, metavar=_("SECONDES"),
                            help=_("Durée du ban. Sans durée, le ban est permanent et demande --confirm-permanent."))
    add_parser.add_argument("--confirm-permanent", action="store_true", help=_("Confirme un ban permanent."))
    add_parser.set_defaults(func=cmd_blocklist_add)
    remove_parser = add_command(blocklist_sub, "remove", _("Lève un ban."))
    remove_parser.add_argument("--network", required=True, metavar=_("RESEAU"),
                               help=_("Adresse ou réseau, tel qu'affiché par blocklist list."))
    remove_parser.set_defaults(func=cmd_blocklist_remove)

    active_defense_sub = add_group(subparsers, "active-defense", _(
        "Active Defense : état, simulation, purge (voir aussi threats, incidents, deception)."),
        "active_defense_command")
    add_command(active_defense_sub, "status", _(
        "Affiche l'état : mode, mode guerre, leurres, nombre de sources suivies.")).set_defaults(
        func=cmd_active_defense_status)
    simulate_ad_parser = add_command(active_defense_sub, "simulate", _(
        "Montre la décision qu'Active Defense prendrait pour une source, sans rien écrire."))
    simulate_ad_parser.add_argument("--ip", required=True, help=_("Adresse de la source simulée."))
    simulate_ad_parser.add_argument("--path", default="/", metavar=_("CHEMIN"),
                                    help=_("Chemin observé (défaut : /)."))
    simulate_ad_parser.add_argument("--user-agent", default="", metavar=_("TEXTE"),
                                    help=_("User-Agent de la source."))
    simulate_ad_parser.add_argument("--attack-class", default="scan", metavar=_("CLASSE"),
                                    help=_("Classe d'attaque (défaut : scan ; liste affichée si inconnue)."))
    simulate_ad_parser.add_argument("--score", type=int, default=10, metavar=_("POINTS"),
                                    help=_("Points ajoutés au score de menace (défaut : 10)."))
    simulate_ad_parser.set_defaults(func=cmd_active_defense_simulate)
    add_command(active_defense_sub, "purge", _(
        "Purge les menaces expirées, ferme les incidents redevenus calmes, supprime les incidents fermés "
        "depuis plus de 90 jours.")).set_defaults(func=cmd_active_defense_purge)

    engine_sub = add_group(subparsers, "engine", _("Moteur HTTP (Python ou natif)."), "engine_command")
    add_command(engine_sub, "status", _(
        "Affiche le moteur demandé, celui qui tourne et la raison d'un éventuel repli.")).set_defaults(
        func=cmd_engine_status)

    riposte_sub = add_group(subparsers, "riposte", _(
        "RIPOSTE : bans de plus en plus longs pour les récidivistes."), "riposte_command")
    add_command(riposte_sub, "run", _(
        "Lance le processus RIPOSTE au premier plan (normalement lancé par serve ; utile au diagnostic).")).set_defaults(
        func=cmd_riposte_run)
    add_command(riposte_sub, "status", _("Affiche l'état de RIPOSTE (lecture seule).")).set_defaults(
        func=cmd_riposte_status)
    register_riposte_queries(riposte_sub)

    threats_sub = add_group(subparsers, "threats", _("Menaces suivies par Active Defense."), "threats_command")
    threats_list_parser = add_command(threats_sub, "list", _("Liste les sources suivies avec leur score et leur niveau."))
    threats_list_parser.add_argument("--level", choices=("normal", "suspicious", "hostile", "contained"), default=None,
                                     help=_("Seulement ce niveau."))
    threats_list_parser.set_defaults(func=cmd_threats_list)
    threats_show_parser = add_command(threats_sub, "show", _("Affiche le détail d'une source suivie."))
    threats_show_parser.add_argument("subject_id", metavar=_("SOURCE"),
                                     help=_("Identifiant de la source, tel qu'affiché par threats list."))
    threats_show_parser.set_defaults(func=cmd_threats_show)

    incidents_sub = add_group(subparsers, "incidents", _("Incidents Active Defense."), "incidents_command")
    incident_id = _("Identifiant de l'incident (voir incidents list).")
    incidents_list_parser = add_command(incidents_sub, "list", _("Liste les incidents."))
    incidents_list_parser.add_argument("--status", choices=("open", "closed"), default=None,
                                       help=_("Seulement les incidents ouverts (open) ou fermés (closed)."))
    incidents_list_parser.add_argument("--since-hours", type=float, default=None, metavar=_("HEURES"),
                                       help=_("Seulement les incidents des N dernières heures."))
    incidents_list_parser.set_defaults(func=cmd_incidents_list)
    incidents_show_parser = add_command(incidents_sub, "show", _("Affiche un incident et sa chronologie."))
    incidents_show_parser.add_argument("incident_id", metavar="ID", help=incident_id)
    incidents_show_parser.set_defaults(func=cmd_incidents_show)
    incidents_close_parser = add_command(incidents_sub, "close", _(
        "Ferme un incident (et l'exporte si l'export automatique est activé)."))
    incidents_close_parser.add_argument("incident_id", metavar="ID", help=incident_id)
    incidents_close_parser.set_defaults(func=cmd_incidents_close)
    incidents_export_ioc_parser = add_command(incidents_sub, "export-ioc", _(
        "Exporte les indicateurs de compromission (IoC) d'un incident."))
    incidents_export_ioc_parser.add_argument("incident_id", metavar="ID", help=incident_id)
    incidents_export_ioc_parser.add_argument("--format", default="json", metavar=_("FORMATS"), help=_(
        "Un ou plusieurs formats séparés par des virgules : json, csv, stix, misp (défaut : json)."))
    incidents_export_ioc_parser.set_defaults(func=cmd_incidents_export_ioc)
    incidents_report_parser = add_command(incidents_sub, "generate-report", _(
        "Écrit le rapport Markdown d'un incident."))
    incidents_report_parser.add_argument("incident_id", metavar="ID", help=incident_id)
    incidents_report_parser.set_defaults(func=cmd_incidents_generate_report)

    deception_sub = add_group(subparsers, "deception", _("Leurres Active Defense."), "deception_command")
    add_command(deception_sub, "list", _("Liste les sources envoyées vers un leurre.")).set_defaults(
        func=cmd_deception_list)
    deception_release_parser = add_command(deception_sub, "release", _("Libère une source de son leurre."))
    deception_release_parser.add_argument("--subject", dest="subject_id", required=True, metavar=_("SOURCE"),
                                          help=_("Identifiant de la source, tel qu'affiché par deception list."))
    deception_release_parser.set_defaults(func=cmd_deception_release)

    certs_sub = add_group(subparsers, "certs", _("Certificats TLS (via OpenSSL)."), "certs_command")
    key_types = ("rsa2048", "rsa4096", "ecdsa-p256", "ecdsa-p384")

    def add_identity(command: argparse.ArgumentParser, cn_help: str) -> None:
        command.add_argument("--cn", required=True, metavar=_("NOM"), help=cn_help)
        command.add_argument("--org", default="OMEGA-SERV", metavar=_("TEXTE"),
                             help=_("Organisation (défaut : OMEGA-SERV)."))
        command.add_argument("--ou", default="", metavar=_("TEXTE"), help=_("Service ou département."))
        command.add_argument("--city", default="", metavar=_("TEXTE"), help=_("Ville."))
        command.add_argument("--region", default="", metavar=_("TEXTE"), help=_("Région."))
        command.add_argument("--country", default="", metavar=_("CODE"), help=_("Pays, code à deux lettres (FR, BE...)."))

    def add_san(command: argparse.ArgumentParser) -> None:
        command.add_argument("--san-dns", nargs="*", default=[], metavar=_("NOM"),
                             help=_("Noms de domaine supplémentaires couverts par le certificat."))
        command.add_argument("--san-ip", nargs="*", default=[], metavar="IP",
                             help=_("Adresses IP couvertes par le certificat."))

    domain_cn = _("Nom commun : le nom de domaine principal.")
    gen_parser = add_command(certs_sub, "generate-self-signed", _(
        "Génère un certificat auto-signé aux chemins de la configuration (l'ancien est sauvegardé)."))
    add_identity(gen_parser, domain_cn)
    add_san(gen_parser)
    gen_parser.add_argument("--days", type=int, default=365, metavar=_("JOURS"),
                            help=_("Validité en jours (défaut : 365)."))
    gen_parser.add_argument("--key-type", choices=key_types, default="rsa2048",
                            help=_("Type de clé (défaut : rsa2048)."))
    gen_parser.add_argument("--password", default=None, metavar=_("MOT-DE-PASSE"),
                            help=_("Chiffre la clé privée avec ce mot de passe (facultatif)."))
    gen_parser.set_defaults(func=cmd_certs_generate_self_signed)

    ca_parser = add_command(certs_sub, "generate-ca", _(
        "Crée une autorité de certification locale dans secure/certificates/ca."))
    add_identity(ca_parser, _("Nom de l'autorité de certification."))
    ca_parser.add_argument("--days", type=int, default=3650, metavar=_("JOURS"),
                           help=_("Validité en jours (défaut : 3650)."))
    ca_parser.add_argument("--key-type", choices=key_types, default="rsa4096",
                           help=_("Type de clé (défaut : rsa4096)."))
    ca_parser.add_argument("--password", default=None, metavar=_("MOT-DE-PASSE"), help=_(
        "Mot de passe de la clé de CA ; sans cette option, il est demandé deux fois au clavier (conseillé)."))
    ca_parser.set_defaults(func=cmd_certs_generate_ca)

    csr_parser = add_command(certs_sub, "generate-csr", _(
        "Génère une clé et une demande de signature (CSR) à faire signer par une CA."))
    add_identity(csr_parser, domain_cn)
    add_san(csr_parser)
    csr_parser.add_argument("--key-type", choices=key_types, default="rsa2048", help=_("Type de clé (défaut : rsa2048)."))
    csr_parser.add_argument("--key-out", required=True, metavar=_("FICHIER"), help=_("Clé privée à créer."))
    csr_parser.add_argument("--csr-out", required=True, metavar=_("FICHIER"), help=_("Demande de signature à créer."))
    csr_parser.set_defaults(func=cmd_certs_generate_csr)

    ca_key_password = _("Mot de passe de la clé de CA (sinon demandé au clavier, conseillé).")
    sign_parser = add_command(certs_sub, "sign-csr", _("Signe une demande de signature (CSR) avec une CA."))
    sign_parser.add_argument("--csr", required=True, metavar=_("FICHIER"), help=_("Demande de signature à signer."))
    sign_parser.add_argument("--ca-key", required=True, metavar=_("FICHIER"), help=_("Clé privée de la CA."))
    sign_parser.add_argument("--ca-cert", required=True, metavar=_("FICHIER"), help=_("Certificat de la CA."))
    sign_parser.add_argument("--ca-key-password", dest="password", default=None, metavar=_("MOT-DE-PASSE"),
                             help=ca_key_password)
    sign_parser.add_argument("--days", type=int, default=365, metavar=_("JOURS"),
                             help=_("Validité en jours (défaut : 365)."))
    sign_parser.add_argument("--out", required=True, metavar=_("FICHIER"), help=_("Certificat signé à écrire."))
    sign_parser.add_argument("--fullchain-out", default=None, metavar=_("FICHIER"),
                             help=_("Écrit aussi la chaîne complète (certificat puis CA)."))
    sign_parser.set_defaults(func=cmd_certs_sign_csr)

    import_parser = add_command(certs_sub, "import", _(
        "Installe un certificat existant aux chemins de la configuration (Let's Encrypt, CA d'entreprise...)."))
    import_parser.add_argument("--key", required=True, metavar=_("FICHIER"), help=_("Clé privée."))
    import_parser.add_argument("--cert", required=True, metavar=_("FICHIER"), help=_("Certificat."))
    import_parser.add_argument("--chain", default=None, metavar=_("FICHIER"),
                               help=_("Chaîne des certificats intermédiaires (facultatif)."))
    import_parser.set_defaults(func=cmd_certs_import)

    revoke_parser = add_command(certs_sub, "revoke", _("Révoque un certificat émis par une CA locale."))
    revoke_parser.add_argument("--cert", required=True, metavar=_("FICHIER"), help=_("Certificat à révoquer."))
    revoke_parser.add_argument("--ca-key", required=True, metavar=_("FICHIER"), help=_("Clé privée de la CA."))
    revoke_parser.add_argument("--ca-cert", required=True, metavar=_("FICHIER"), help=_("Certificat de la CA."))
    revoke_parser.add_argument("--ca-key-password", dest="password", default=None, metavar=_("MOT-DE-PASSE"),
                               help=ca_key_password)
    revoke_parser.set_defaults(func=cmd_certs_revoke)

    inspected_cert = _("Certificat à lire (défaut : celui de la configuration).")
    verify_parser = add_command(certs_sub, "verify", _(
        "Vérifie un certificat : dates, correspondance avec la clé, droits de la clé. Code 1 s'il a expiré."))
    verify_parser.add_argument("--cert", default="", metavar=_("FICHIER"), help=inspected_cert)
    verify_parser.set_defaults(func=cmd_certs_verify)
    show_parser = add_command(certs_sub, "show", _("Affiche le détail d'un certificat (même rapport que verify)."))
    show_parser.add_argument("--cert", default="", metavar=_("FICHIER"), help=inspected_cert)
    show_parser.set_defaults(func=cmd_certs_show)
    expiry_parser = add_command(certs_sub, "check-expiry", _(
        "Même rapport que verify, avec une alerte si l'expiration approche."))
    expiry_parser.add_argument("--cert", default="", metavar=_("FICHIER"), help=inspected_cert)
    expiry_parser.add_argument("--warn-days", type=int, default=30, metavar=_("JOURS"),
                               help=_("Seuil d'alerte en jours (défaut : 30)."))
    expiry_parser.set_defaults(func=cmd_certs_check_expiry)

    auth_sub = add_group(subparsers, "auth", _(
        "Authentification HTTP Basic : utilisateurs et zones protégées."), "auth_command")
    username_help = _("Nom d'utilisateur.")
    password_help = _("Mot de passe (sinon demandé au clavier, conseillé : il resterait dans l'historique).")
    path_prefix_help = _("Début de chemin protégé, par exemple /admin.")

    add_user_parser = add_command(auth_sub, "add-user", _("Crée un utilisateur."))
    add_user_parser.add_argument("--username", required=True, metavar=_("NOM"), help=username_help)
    add_user_parser.add_argument("--password", default=None, metavar=_("MOT-DE-PASSE"), help=password_help)
    add_user_parser.set_defaults(func=cmd_auth_add_user)

    remove_user_parser = add_command(auth_sub, "remove-user", _("Supprime un utilisateur."))
    remove_user_parser.add_argument("--username", required=True, metavar=_("NOM"), help=username_help)
    remove_user_parser.set_defaults(func=cmd_auth_remove_user)

    change_password_parser = add_command(auth_sub, "change-password", _("Change le mot de passe d'un utilisateur."))
    change_password_parser.add_argument("--username", required=True, metavar=_("NOM"), help=username_help)
    change_password_parser.add_argument("--password", default=None, metavar=_("MOT-DE-PASSE"), help=password_help)
    change_password_parser.set_defaults(func=cmd_auth_change_password)

    create_zone_parser = add_command(auth_sub, "create-zone", _("Protège un chemin par mot de passe."))
    create_zone_parser.add_argument("--path-prefix", required=True, metavar=_("CHEMIN"), help=path_prefix_help)
    create_zone_parser.add_argument("--realm", required=True, metavar=_("TEXTE"),
                                    help=_("Nom affiché par le navigateur dans la demande de connexion."))
    create_zone_parser.add_argument("--allowed-users", nargs="+", required=True, metavar=_("NOM"),
                                    help=_("Utilisateurs autorisés dans la zone."))
    create_zone_parser.add_argument("--allow-methods", nargs="*", default=[], metavar=_("METHODE"), help=_(
        "Seules ces méthodes HTTP sont acceptées dans la zone (défaut : toutes celles que le serveur autorise)."))
    create_zone_parser.set_defaults(func=cmd_auth_create_zone)

    remove_zone_parser = add_command(auth_sub, "remove-zone", _("Retire la protection d'un chemin."))
    remove_zone_parser.add_argument("--path-prefix", required=True, metavar=_("CHEMIN"), help=path_prefix_help)
    remove_zone_parser.set_defaults(func=cmd_auth_remove_zone)

    add_command(auth_sub, "list", _("Liste les utilisateurs et les zones protégées.")).set_defaults(func=cmd_auth_list)
    add_command(auth_sub, "check-permissions", _(
        "Vérifie que les fichiers des utilisateurs et des zones ne sont lisibles que par leur propriétaire.")).set_defaults(
        func=cmd_auth_check_permissions)

    service_sub = add_group(subparsers, "service", _(
        "Service système (systemd, OpenRC ou runit)."), "service_command")
    service_name_help = _("Nom du service (défaut : omega-serv).")
    unit_path_help = _("Fichier d'unité (défaut : /etc/systemd/system/<nom>.service).")

    for verb, func, text in (
        ("status", cmd_service_status, _("Affiche l'état du service.")),
        ("start", cmd_service_start, _("Démarre le service.")),
        ("stop", cmd_service_stop, _("Arrête le service.")),
        ("restart", cmd_service_restart, _("Redémarre le service (nécessaire après une mise à jour).")),
        ("reload", cmd_service_reload, _(
            "Recharge sans couper : règles WAF et zones ; bind, port, TLS et moteur demandent un redémarrage.")),
        ("enable", cmd_service_enable, _("Active le démarrage automatique au boot.")),
        ("disable", cmd_service_disable, _("Désactive le démarrage automatique au boot.")),
    ):
        sub = add_command(service_sub, verb, text)
        sub.add_argument("--service-name", default="omega-serv", metavar=_("NOM"), help=service_name_help)
        sub.set_defaults(func=func)

    install_parser = add_command(service_sub, "install", _(
        "Crée l'unité systemd du service (systemd seulement ; demande les droits administrateur)."))
    install_parser.add_argument("--service-name", default="omega-serv", metavar=_("NOM"), help=service_name_help)
    install_parser.add_argument("--description", default="OMEGA-SERV web server", metavar=_("TEXTE"),
                                help=_("Description de l'unité (défaut : OMEGA-SERV web server)."))
    install_parser.add_argument("--python-executable", default=None, metavar=_("FICHIER"),
                                help=_("Python à utiliser (défaut : celui du .venv de l'installation)."))
    install_parser.add_argument("--user", default="omega-serv", metavar=_("NOM"),
                                help=_("Compte système qui fait tourner le service (défaut : omega-serv)."))
    install_parser.add_argument("--group", default="omega-serv", metavar=_("NOM"),
                                help=_("Groupe du service (défaut : omega-serv)."))
    install_parser.add_argument("--stop-timeout-seconds", type=int, default=15, metavar=_("SECONDES"),
                                help=_("Délai laissé à l'arrêt avant de forcer (défaut : 15)."))
    install_parser.add_argument("--unit-path", default=None, metavar=_("FICHIER"), help=unit_path_help)
    install_parser.set_defaults(func=cmd_service_install)

    uninstall_parser = add_command(service_sub, "uninstall", _("Supprime l'unité du service."))
    uninstall_parser.add_argument("--service-name", default="omega-serv", metavar=_("NOM"), help=service_name_help)
    uninstall_parser.add_argument("--unit-path", default=None, metavar=_("FICHIER"), help=unit_path_help)
    uninstall_parser.set_defaults(func=cmd_service_uninstall)

    audit_sub = add_group(subparsers, "audit", _("Audit de sécurité."), "audit_command")
    security_parser = add_command(audit_sub, "security", _(
        "Audite l'installation : configuration, droits, TLS, service. Code 1 si critique, 2 si élevé, "
        "3 si la configuration est illisible."))
    security_parser.add_argument("--format", choices=("text", "json"), default="text",
                                 help=_("Format du rapport (défaut : text)."))
    security_parser.add_argument("--min-severity", choices=("critical", "high", "medium", "low", "info"),
                                 default="info", help=_("N'affiche que ce niveau et les plus graves (défaut : info)."))
    security_parser.add_argument("--service-name", default="omega-serv", metavar=_("NOM"), help=service_name_help)
    security_parser.add_argument("--unit-path", default=None, metavar=_("FICHIER"), help=unit_path_help)
    security_parser.add_argument("--confirm-self-signed-public-bind", action="store_true", help=confirm_self_signed)
    security_parser.add_argument("--confirm-auth-without-tls", action="store_true", help=confirm_auth_without_tls)
    security_parser.set_defaults(func=cmd_audit_security)

    add_declaration_parser(subparsers)

    help_parser = add_command(subparsers, "help", _(
        "Affiche l'arbre de toutes les commandes, ou d'une branche (ex. : omega-serv help riposte)."))
    help_parser.add_argument("branch", nargs="*", metavar=_("COMMANDE"), help=_("Branche à afficher (facultatif)."))
    help_parser.set_defaults(func=lambda args, _container: cmd_help(parser, args))

    return parser


def main(argv: list[str] | None = None) -> int:
    effective_argv = sys.argv[1:] if argv is None else argv
    from omega_serv.infrastructure.persistence.sqlite_snapshot import snapshot_database

    container = DependencyContainer(database_snapshot_fn=snapshot_database)
    if not is_server_process(effective_argv):
        # Avant build_parser() : l'aide (--help) des commandes suivra la langue choisie.
        install_interface_language(
            settings_store=container.settings_store, catalog=container.language_catalog, environ=os.environ,
            terminal_family=container.terminal_detector.detect().family,
        )
    parser = build_parser()
    args = parser.parse_args(effective_argv)
    return cast(int, args.func(args, container))


if __name__ == "__main__":
    sys.exit(main())
