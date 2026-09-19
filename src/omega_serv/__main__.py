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
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Callable, Sequence
    from pathlib import Path

    from omega_lib.theme.policies import Palette

    from omega_serv.application.security.simulate_waf_request import WafSimulationReport
    from omega_serv.application.server.simulate_request import SimulationReport
    from omega_serv.application.server.start_server import ActiveDefenseCollaborators
    from omega_serv.bootstrap.container import DependencyContainer
    from omega_serv.core.capability import Capability
    from omega_serv.domain.config.entities import OmegaServConfig
    from omega_serv.domain.security.active_defense.entities import ExportResult, Incident
    from omega_serv.domain.security.audit.entities import AuditResult
    from omega_serv.ports.blocklist_port import BlocklistPort
    from omega_serv.ports.certificate_tool_port import CertificateToolPort
    from omega_serv.ports.clock_port import ClockPort
    from omega_serv.ports.filesystem_port import FilesystemPort
    from omega_serv.ports.instance_registry_port import InstanceRegistryPort
    from omega_serv.ports.ioc_exporter_port import IoCExporterPort
    from omega_serv.ports.process_runner_port import ProcessRunnerPort


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


def _run_waf_test(
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
    return simulate_waf_request(method, path, query, body, remote_ip, waf)


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
    incident: Incident, export_format: str, export_dir: Path, filesystem: FilesystemPort,
) -> ExportResult | None:
    from omega_serv.infrastructure.exporters.csv_ioc_exporter import CsvIoCExporter
    from omega_serv.infrastructure.exporters.json_ioc_exporter import JsonIoCExporter

    exporters: dict[str, IoCExporterPort] = {
        "json": JsonIoCExporter(filesystem, export_dir), "csv": CsvIoCExporter(filesystem, export_dir),
    }
    exporter = exporters.get(export_format)
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
        return "L'executable 'lnav' est introuvable (non installe ou absent du PATH)."
    except OSError as exc:
        return f"Echec du lancement de lnav : {exc}"
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


def _export_capabilities_html(capabilities: Sequence[Capability], theme_name: str) -> str:
    from omega_serv.infrastructure.exporters.html_exporter import export_capabilities_html

    return export_capabilities_html(capabilities, theme_name)


def _export_log_archives_html(archives: Sequence[dict], theme_name: str) -> str:
    from omega_serv.infrastructure.exporters.html_exporter import export_log_archives_html

    return export_log_archives_html(archives, theme_name)


def _export_guide_html(screen_guides: Sequence[dict], faq_entries: Sequence[dict], theme_name: str) -> str:
    from omega_serv.infrastructure.exporters.html_exporter import export_guide_html

    return export_guide_html(screen_guides, faq_entries, theme_name)


def main(argv: list[str] | None = None) -> int:
    effective_argv = sys.argv[1:] if argv is None else argv

    if not effective_argv:
        import os

        os.environ.setdefault("TEXTUAL_DISABLE_KITTY_KEY", "1")

        from omega_serv.application.services.build_service_manager import build_service_manager
        from omega_serv.bootstrap.container import DependencyContainer
        from omega_serv.interfaces.tui.app import OmegaServApp

        container = DependencyContainer(
            service_manager_factory=build_service_manager,
            config_check_runner=_run_config_check,
            audit_runner=_run_audit,
            simulate_request_runner=_run_simulate_request,
            waf_test_runner=_run_waf_test,
            blocklist_port_factory=_build_blocklist_port,
            active_defense_collaborators_factory=_build_active_defense_collaborators,
            ioc_export_runner=_run_ioc_export,
            incident_report_export_runner=_run_incident_report_export,
            certificate_tool_factory=_build_certificate_tool,
            acme_client_factory=_build_acme_client,
            lnav_runner=_run_lnav,
            create_instance_runner=_run_create_instance,
            export_capabilities_html_fn=_export_capabilities_html,
            export_log_archives_html_fn=_export_log_archives_html,
            export_guide_html_fn=_export_guide_html,
            serve_foreground_runner=_run_serve_foreground,
        )
        app = OmegaServApp(container)
        app.run()
        if app.pending_switch is not None:
            import os

            os.environ["OMEGA_SERV_SWITCHED_FROM"] = app.pending_switch.source_name
            path, exec_argv = _build_execv_invocation(app.pending_switch.python_executable)
            os.execv(path, exec_argv)  # pragma: no cover - remplace le processus, jamais testable pour de vrai
        return 0

    from omega_serv.interfaces.cli.main import main as run_cli

    return run_cli(effective_argv)


if __name__ == "__main__":
    sys.exit(main())
