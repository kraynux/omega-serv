"""Point d'entree `python -m omega_serv` / script console `omega-serv`
(voir [project.scripts] dans pyproject.toml). Dispatche vers la TUI
(aucun argument) ou la CLI non-interactive (au moins un argument) -
meme patron que le reste de la suite omega- (plan interface §0/§4,
Phase I). `python -m omega_serv serve` demarre le serveur en CLI comme
avant ; `python -m omega_serv` seul lance desormais l'interface
interactive plutot que d'echouer sur "command requis" (comportement
argparse par defaut avant ce chantier).

Les fonctions `_run_*` ci-dessous cablent les cas d'usage application/
qui touchent infrastructure/ (WAF, TLS, FastCGI...) et sont injectees
dans DependencyContainer plutot qu'importees depuis bootstrap/ ou
interfaces.tui/ : ces deux couches sont exclues de infrastructure/ et/ou
subprocess/ssl par les contrats import-linter (transitivement, voir
bootstrap/container.py), et ce module est le seul point neutre non
liste dans aucun de ces contrats (plan interface §3.6/§12, Phase II)."""
from __future__ import annotations

import sys
from collections.abc import MutableMapping
from typing import TYPE_CHECKING

from omega_serv.core.i18n import _

if TYPE_CHECKING:
    from collections.abc import Callable, Sequence
    from pathlib import Path

    from omega_lib.theme.policies import Palette

    from omega_serv.application.security.check_magnet_compatibility import MagnetCompatibilityCheck
    from omega_serv.application.security.simulate_waf_request import WafSimulationReport
    from omega_serv.application.server.simulate_request import SimulationReport
    from omega_serv.application.server.start_server import ActiveDefenseCollaborators
    from omega_serv.bootstrap.container import DependencyContainer
    from omega_serv.core.capability import Capability
    from omega_serv.domain.config.entities import OmegaServConfig
    from omega_serv.domain.security.active_defense.config import IoCConfig
    from omega_serv.domain.security.active_defense.entities import ExportResult, Incident
    from omega_serv.domain.security.audit.entities import AuditResult
    from omega_serv.domain.security.waf.config import MagnetConfig
    from omega_serv.ports.blocklist_port import BlocklistPort
    from omega_serv.ports.certificate_tool_port import CertificateToolPort
    from omega_serv.ports.clock_port import ClockPort
    from omega_serv.ports.filesystem_port import FilesystemPort
    from omega_serv.ports.instance_registry_port import InstanceRegistryPort
    from omega_serv.ports.process_runner_port import ProcessResult, ProcessRunnerPort


def _run_config_check(
    config: OmegaServConfig,
    filesystem: FilesystemPort,
    project_root: Path,
    self_signed_public_bind_confirmed: bool,
    auth_without_tls_confirmed: bool,
) -> list[str]:
    from omega_serv.application.config.validate_config import validate_config_environment

    return validate_config_environment(
        config, filesystem, project_root,
        self_signed_public_bind_confirmed=self_signed_public_bind_confirmed,
        auth_without_tls_confirmed=auth_without_tls_confirmed,
    )


def _run_audit(
    config: OmegaServConfig,
    config_path: Path,
    project_root: Path,
    filesystem: FilesystemPort,
    clock: ClockPort,
    service_name: str,
    self_signed_public_bind_confirmed: bool,
    auth_without_tls_confirmed: bool,
) -> AuditResult:
    from pathlib import Path

    from omega_serv.application.security.run_audit import run_audit
    from omega_serv.infrastructure.process.subprocess_runner import SubprocessRunner
    from omega_serv.infrastructure.tls.openssl_certificate_tool import OpensslCertificateTool

    unit_path = Path(f"/etc/systemd/system/{service_name}.service")
    certificate_tool = OpensslCertificateTool(SubprocessRunner())
    return run_audit(
        config, config_path, project_root, filesystem, certificate_tool,
        clock, service_unit_path=unit_path,
        self_signed_public_bind_confirmed=self_signed_public_bind_confirmed,
        auth_without_tls_confirmed=auth_without_tls_confirmed,
    )


async def _call_admin_endpoint(port: int, method: str, path_and_query: str) -> tuple[int, dict | None] | None:
    from omega_serv.infrastructure.proxy_admin.http_admin_client import call_admin_endpoint

    return await call_admin_endpoint(port, method, path_and_query)


async def _run_simulate_request(
    method: str,
    path: str,
    config: OmegaServConfig,
    filesystem: FilesystemPort,
    project_root: Path,
) -> SimulationReport:
    from omega_serv.application.server.simulate_request import simulate_request
    from omega_serv.infrastructure.fastcgi.asyncio_fastcgi_client import AsyncioFastCgiClient
    from omega_serv.infrastructure.filesystem.safe_path_resolver import SafePathResolver

    webroot = project_root / config.paths.webroot
    path_resolver = SafePathResolver(filesystem, webroot)
    fastcgi_client = AsyncioFastCgiClient() if config.option_enabled("fastcgi") else None
    return await simulate_request(method, path, config, path_resolver, filesystem, project_root, fastcgi_client)


async def _run_waf_test(
    method: str,
    path: str,
    query: str,
    body: str,
    remote_ip: str,
    config: OmegaServConfig,
    filesystem: FilesystemPort,
    project_root: Path,
    clock: ClockPort,
) -> WafSimulationReport | None:
    from omega_serv.application.security.simulate_waf_request import simulate_waf_request
    from omega_serv.application.server.start_server import build_waf_collaborators

    waf = build_waf_collaborators(config, project_root, filesystem, clock, force=True)
    if waf is None:
        return None
    return await simulate_waf_request(method, path, query, body, remote_ip, waf)


def _service_runs_older_code(service_name: str) -> bool:
    from pathlib import Path

    import omega_serv
    from omega_serv.application.services.build_service_manager import build_service_manager
    from omega_serv.application.services.check_stale_service import service_runs_older_code
    from omega_serv.infrastructure.process.process_info import newest_code_time, process_start_time

    manager = build_service_manager()
    if manager is None:
        return False
    code_time = newest_code_time(Path(omega_serv.__file__).resolve().parent)
    return service_runs_older_code(manager, service_name, process_start_time, code_time)


async def _check_magnet_compatibility(
    magnet: MagnetConfig, project_root: Path, filesystem: FilesystemPort,
) -> MagnetCompatibilityCheck:
    from omega_serv.application.security.check_magnet_compatibility import (
        check_magnet_compatibility,
    )

    return await check_magnet_compatibility(magnet, project_root, filesystem)


def _build_blocklist_port(
    config: OmegaServConfig,
    filesystem: FilesystemPort,
    project_root: Path,
    clock: ClockPort,
) -> BlocklistPort:
    from omega_serv.application.server.start_server import build_blocklist_port

    return build_blocklist_port(config, project_root, filesystem, clock)


def _build_active_defense_collaborators(
    config: OmegaServConfig, project_root: Path,
) -> ActiveDefenseCollaborators | None:
    from omega_serv.application.server.start_server import build_active_defense_collaborators

    return build_active_defense_collaborators(config, project_root)


def _run_ioc_export(
    incident: Incident, export_format: str, export_dir: Path, filesystem: FilesystemPort, ioc: IoCConfig,
) -> ExportResult | None:
    from omega_serv.infrastructure.exporters.ioc_exporters import build_ioc_exporters

    exporter = build_ioc_exporters(filesystem, export_dir, ioc).get(export_format)
    return None if exporter is None else exporter.export(incident)


def _run_incident_report_export(incident: Incident, export_dir: Path, filesystem: FilesystemPort) -> ExportResult:
    from omega_serv.infrastructure.exporters.markdown_incident_report_exporter import (
        MarkdownIncidentReportExporter,
    )

    return MarkdownIncidentReportExporter(filesystem, export_dir).render(incident)


def _build_certificate_tool() -> CertificateToolPort:
    from omega_serv.infrastructure.process.subprocess_runner import SubprocessRunner
    from omega_serv.infrastructure.tls.openssl_certificate_tool import OpensslCertificateTool

    return OpensslCertificateTool(SubprocessRunner())


def _build_acme_client() -> ProcessRunnerPort:
    from omega_serv.infrastructure.process.subprocess_runner import SubprocessRunner

    return SubprocessRunner()


def _build_remote_log_fetch_runner() -> ProcessRunnerPort:
    from omega_serv.infrastructure.process.subprocess_runner import SubprocessRunner

    return SubprocessRunner()


async def _run_serve_foreground(config_path: Path, container: DependencyContainer) -> int:
    from omega_serv.application.config.load_config import load_config
    from omega_serv.application.config.validate_config import validate_config_environment
    from omega_serv.core.platform_info import running_as_root
    from omega_serv.interfaces.cli.main import run_server_until_stopped

    if running_as_root():
        print("Erreur : OMEGA-SERV refuse de demarrer en tant que root (voir plan de developpement §6).")
        return 1

    result = load_config(container.configuration, config_path)
    if not result.success:
        print("Erreur de configuration : " + "; ".join(result.errors))
        return 1
    assert result.config is not None

    env_errors = validate_config_environment(
        result.config, container.filesystem, container.project_root,
        self_signed_public_bind_confirmed=False, auth_without_tls_confirmed=False,
    )
    if env_errors:
        print("Erreur d'environnement : " + "; ".join(env_errors))
        return 1

    return await run_server_until_stopped(result.config, config_path, container)


def _run_lnav(log_paths: tuple[Path, ...], palette: Palette, title: str, menu_label: str) -> str | None:
    from omega_serv.infrastructure.lnav.live_renderer import render_lnav_live

    try:
        render_lnav_live(list(log_paths), palette, title, menu_label)
    except FileNotFoundError:
        return _("L'exécutable 'lnav' est introuvable (non installé ou absent du PATH).")
    except OSError as exc:
        return _("Échec du lancement de lnav : {exc}").format(exc=exc)
    return None


def _run_create_instance(
    source_root: Path,
    name: str,
    target_parent_dir: Path,
    bind: str,
    port: int,
    service_name: str,
    filesystem: FilesystemPort,
    registry: InstanceRegistryPort,
    clock: ClockPort,
    on_step: Callable[[int, int, str], None] | None,
) -> str | None:
    from omega_serv.application.instances.create_instance import create_instance
    from omega_serv.infrastructure.process.subprocess_runner import SubprocessRunner

    return create_instance(
        filesystem, SubprocessRunner(), registry, clock,
        source_root=source_root, name=name, target_parent_dir=target_parent_dir,
        bind=bind, port=port, service_name=service_name, on_step=on_step,
    )


def _build_execv_invocation(python_executable: Path) -> tuple[str, list[str]]:
    """Isole dans une fonction pure/testable ce qui SERAIT passe a
    os.execv() (OMEGA-SERV_PLAN-DETAILLE_MULTI_INSTANCE.md §9 Phase D) -
    l'appel reel lui-meme (dans main() ci-dessous) ne peut jamais etre
    exerce par un test automatise : il remplacerait le processus de
    test en cours, aucun moyen sur de l'observer de l'exterieur (meme
    limite que le `exec` final d'omega-serv.sh, jamais unit-teste non
    plus)."""
    path = str(python_executable)
    return path, [path, "-m", "omega_serv"]


def _prepare_language_restart_environment(environ: MutableMapping[str, str], language_code: str) -> None:
    """Environnement transmis au processus relance par os.execv() apres un changement de
    langue (OMEGA-SERV_PLAN-DETAILLE_I18N.md §5.4) : le splash de confirmation est demande,
    et une eventuelle surcharge OMEGA_SERV_LANG (voie de secours, une fois) est retiree -
    sinon elle masquerait la langue que l'utilisateur vient de choisir."""
    from omega_serv.application.terminal.select_language import (
        LANGUAGE_CHANGED_ENV_VAR,
        LANGUAGE_ENV_VAR,
    )

    environ[LANGUAGE_CHANGED_ENV_VAR] = language_code
    environ.pop(LANGUAGE_ENV_VAR, None)


def _export_capabilities_html(capabilities: Sequence[Capability], theme_name: str) -> str:
    from omega_serv.infrastructure.exporters.html_exporter import export_capabilities_html

    return export_capabilities_html(capabilities, theme_name)


def _export_log_archives_html(archives: Sequence[dict], theme_name: str) -> str:
    from omega_serv.infrastructure.exporters.html_exporter import export_log_archives_html

    return export_log_archives_html(archives, theme_name)


def _export_guide_html(screen_guides: Sequence[dict], faq_entries: Sequence[dict], theme_name: str) -> str:
    from omega_serv.infrastructure.exporters.html_exporter import export_guide_html

    return export_guide_html(screen_guides, faq_entries, theme_name)


# Lot « langue des exports » (decision utilisateur 2026-10-23) : un export dans une autre langue
# que l'interface est genere par un processus enfant lance dans cette langue. Le guide et les
# raisons du registre des capacites sont traduits a leur creation (import, scan) : seul un
# processus demarre dans la langue voulue les produit sans melange de langues.
EXPORT_HTML_CHILD_COMMAND = "_export-html"
EXPORT_REPORT_CHILD_COMMAND = "_export-report"
# Code de sortie convenu avec DependencyContainer : le message est traduit par le parent,
# dans la langue de l'interface (l'enfant parle la langue des exports).
EXPORT_CHILD_INCIDENT_NOT_FOUND = 3


def _run_export_in_language(command: list[str], language_code: str) -> ProcessResult:
    from omega_serv.bootstrap.early_language import EXPORT_CHILD_ENV_VAR
    from omega_serv.infrastructure.process.subprocess_runner import SubprocessRunner

    return SubprocessRunner().run(
        ["env", f"OMEGA_SERV_LANG={language_code}", f"{EXPORT_CHILD_ENV_VAR}=1",
         sys.executable, "-m", "omega_serv", *command],
        timeout=180,
    )


def _render_html_export_here(kind: str, theme_name: str) -> str | None:
    """Rendu HTML dans la langue de CE processus (enfant d'export)."""
    from dataclasses import asdict

    from omega_serv.application.config.load_config import load_config
    from omega_serv.bootstrap.container import DependencyContainer
    from omega_serv.core.capability_registry import CapabilityRegistry

    container = DependencyContainer()
    if kind == "guide":
        from omega_serv.interfaces.tui.guide.menu_tree import GUIDE_MENU_ENTRIES
        from omega_serv.interfaces.tui.guide.registry import ALL_FAQ_ENTRIES, SCREEN_GUIDES

        guides = [asdict(SCREEN_GUIDES[e.screen_class_name]) for e in GUIDE_MENU_ENTRIES if e.screen_class_name in SCREEN_GUIDES]
        return _export_guide_html(guides, [asdict(f) for f in ALL_FAQ_ENTRIES], theme_name)
    if kind == "log-archives":
        store = container.build_archive_store(container.project_root / "var" / "backups" / "logs")
        return _export_log_archives_html([store.get_archive_info(p) for p in store.list_archives()], theme_name)
    if kind == "capabilities":
        load_result = load_config(container.configuration, container.config_file)
        if not load_result.success or load_result.config is None:
            sys.stderr.write("; ".join(load_result.errors))
            return None
        config = load_result.config
        fastcgi_socket = None
        fastcgi_option = config.options.get("fastcgi")
        if fastcgi_option is not None and fastcgi_option.enabled:
            fastcgi_socket = container.project_root / fastcgi_option.settings.get("socket_path", "var/run/php-fpm.sock")
        scanner = container.build_capability_scanner(config.server.port, fastcgi_socket)
        return _export_capabilities_html(CapabilityRegistry(scanner.scan()).list_all(), theme_name)
    return None


def _write_report_here(incident_id: str) -> Path | None:
    """Rapport d'incident Markdown dans la langue de CE processus (enfant d'export)."""
    from omega_serv.application.config.load_config import load_config
    from omega_serv.bootstrap.container import DependencyContainer

    container = DependencyContainer()
    load_result = load_config(container.configuration, container.config_file)
    if not load_result.success or load_result.config is None:
        sys.stderr.write("; ".join(load_result.errors))
        return None
    active_defense = _build_active_defense_collaborators(load_result.config, container.project_root)
    incident = None if active_defense is None else active_defense.incident_repository.get(incident_id)
    if active_defense is None or incident is None:
        raise LookupError(incident_id)
    export_dir = container.project_root / active_defense.config.storage.export_dir
    return _run_incident_report_export(incident, export_dir, container.filesystem).path


def _run_export_child_command(argv: list[str]) -> int:
    """`_export-html <guide|capabilities|log-archives> <theme>` : HTML sur stdout.
    `_export-report <incident_id>` : chemin du rapport ecrit sur stdout. Commandes internes,
    lancees uniquement par `_run_export_in_language` (absentes de --help)."""
    if argv[0] == EXPORT_HTML_CHILD_COMMAND and len(argv) == 3:
        content = _render_html_export_here(argv[1], argv[2])
        if content is None:
            return 1
        sys.stdout.write(content)
        return 0
    if argv[0] == EXPORT_REPORT_CHILD_COMMAND and len(argv) == 2:
        try:
            path = _write_report_here(argv[1])
        except LookupError:
            return EXPORT_CHILD_INCIDENT_NOT_FOUND
        if path is None:
            return 1
        sys.stdout.write(f"{path}\n")
        return 0
    return 2


def _run_with_text_direction(app) -> None:  # type: ignore[no-untyped-def]
    """Arabe (plan i18n lot 11, option C) : omega-serv ordonne lui-meme le texte droite-a-gauche,
    le terminal passe en mode bidi explicite le temps de la TUI pour ne plus rien deplacer."""
    from omega_lib.i18n.policies import text_direction

    from omega_serv.core.i18n import STATE
    from omega_serv.interfaces.tui.terminal_bidi import (
        ENTER_EXPLICIT_MODE,
        LEAVE_EXPLICIT_MODE,
        install_visual_reordering,
    )

    if text_direction(STATE.language.code) != "rtl" or not install_visual_reordering():
        app.run()
        return
    sys.stdout.write(ENTER_EXPLICIT_MODE)
    sys.stdout.flush()
    try:
        app.run()
    finally:
        sys.stdout.write(LEAVE_EXPLICIT_MODE)
        sys.stdout.flush()


def main(argv: list[str] | None = None) -> int:
    effective_argv = sys.argv[1:] if argv is None else argv

    import os

    from omega_serv.bootstrap.early_language import (
        install_language_early,
        install_page_language_early,
        is_server_process,
    )

    # Langue installee AVANT tout autre import du programme (plan i18n, lot 4) : une phrase
    # traduite au chargement d'un module est ainsi deja dans la bonne langue. Jamais pour
    # `serve` (D18b : journalctl reste en francais).
    if not is_server_process(effective_argv):
        install_language_early(os.environ)
    install_page_language_early(os.environ)  # pages visiteurs (D19), y compris pour `serve`

    # Hindi (plan i18n, lots 10-11) : Rich compte les voyelles devanagari espacantes pour 0
    # colonne, le terminal pour 1 - aligne avant tout rendu, sans effet sur les autres langues.
    from omega_serv.infrastructure.i18n.terminal_cell_widths import (
        align_spacing_marks_with_terminal,
    )

    align_spacing_marks_with_terminal()

    if effective_argv and effective_argv[0] in (EXPORT_HTML_CHILD_COMMAND, EXPORT_REPORT_CHILD_COMMAND):
        return _run_export_child_command(effective_argv)

    if not effective_argv:

        os.environ.setdefault("TEXTUAL_DISABLE_KITTY_KEY", "1")

        # Diagnostic de gel (retour utilisateur 2026-09-27, gel reproduit a
        # 3 reprises sur Archcraft malgre plusieurs correctifs deja
        # appliques, py-spy indisponible sur cette machine) : faulthandler
        # est stdlib, ne demande rien a installer. `kill -USR1 <pid>`
        # ecrit la pile d'appels de TOUS les threads dans
        # /tmp/omega-serv-freeze-<pid>.txt, y compris pendant un vrai gel
        # (le handler de signal s'execute meme si la boucle asyncio est
        # bloquee dans un appel synchrone - c'est exactement le scenario a
        # diagnostiquer). Fichier ouvert ici et jamais ferme explicitement
        # (garde une reference via _freeze_dump_file pour eviter le GC) -
        # nettoye par l'OS a la fin du processus, cout negligeable.
        import faulthandler
        import signal
        from pathlib import Path

        _freeze_dump_path = Path(f"/tmp/omega-serv-freeze-{os.getpid()}.txt")
        _freeze_dump_file = _freeze_dump_path.open("w", encoding="utf-8")
        faulthandler.register(signal.SIGUSR1, file=_freeze_dump_file, all_threads=True)

        from omega_serv.application.services.build_service_manager import build_service_manager
        from omega_serv.bootstrap.container import DependencyContainer

        container = DependencyContainer(
            service_manager_factory=build_service_manager,
            config_check_runner=_run_config_check,
            audit_runner=_run_audit,
            simulate_request_runner=_run_simulate_request,
            admin_request_runner=_call_admin_endpoint,
            waf_test_runner=_run_waf_test,
            magnet_compat_check_runner=_check_magnet_compatibility,
            stale_service_checker=_service_runs_older_code,
            blocklist_port_factory=_build_blocklist_port,
            active_defense_collaborators_factory=_build_active_defense_collaborators,
            ioc_export_runner=_run_ioc_export,
            incident_report_export_runner=_run_incident_report_export,
            certificate_tool_factory=_build_certificate_tool,
            acme_client_factory=_build_acme_client,
            remote_log_fetch_runner_factory=_build_remote_log_fetch_runner,
            lnav_runner=_run_lnav,
            create_instance_runner=_run_create_instance,
            export_capabilities_html_fn=_export_capabilities_html,
            export_log_archives_html_fn=_export_log_archives_html,
            export_guide_html_fn=_export_guide_html,
            export_in_language_runner=_run_export_in_language,
            serve_foreground_runner=_run_serve_foreground,
        )
        from omega_serv.interfaces.tui.app import OmegaServApp

        app = OmegaServApp(container)
        _run_with_text_direction(app)
        if app.pending_switch is not None:
            os.environ["OMEGA_SERV_SWITCHED_FROM"] = app.pending_switch.source_name
            path, exec_argv = _build_execv_invocation(app.pending_switch.python_executable)
            os.execv(path, exec_argv)  # pragma: no cover - remplace le processus, jamais testable pour de vrai
        if app.pending_restart is not None:
            # Meme Python, meme installation : seule l'interface redemarre, jamais le service.
            _prepare_language_restart_environment(os.environ, app.pending_restart.language_code)
            path, exec_argv = _build_execv_invocation(Path(sys.executable))
            os.execv(path, exec_argv)  # pragma: no cover - remplace le processus, jamais testable pour de vrai
        return 0

    from omega_serv.interfaces.cli.main import main as run_cli

    return run_cli(effective_argv)


if __name__ == "__main__":
    sys.exit(main())
