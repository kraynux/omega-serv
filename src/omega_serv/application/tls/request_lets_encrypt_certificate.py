"""Cas d'usage "obtenir un certificat Let's Encrypt via Certbot" (etude
OMEGA-SERV_PLAN-DETAILLE_TLS_AUTO.md, Phase 4). Orchestre : ecriture du
script de hook de renouvellement, appel reel a `certbot certonly
--webroot` (`ProcessRunnerPort`, jamais `subprocess` directement - meme
contrat deja utilise par `OpensslCertificateTool`), puis import
IMMEDIAT du certificat obtenu (reutilise `import_certificate.py`, Phase
2) - jamais uniquement dependant du hook pour la toute premiere
emission, deterministe des le premier succes.

Aucune elevation de privileges ici (voir domain/security/tls/acme.py) :
`--config-dir`/`--work-dir`/`--logs-dir` pointes sous `secure/
certificates/letsencrypt/` (jamais `/etc/letsencrypt/`) rendent Certbot
lui-meme non-privilegie de bout en bout pour le mode webroot."""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from omega_serv.application.tls.import_certificate import import_certificate
from omega_serv.domain.security.tls.acme import (
    CertbotRequestParams,
    build_certbot_argv,
    build_deploy_hook_script,
    validate_certbot_request_params,
)
from omega_serv.ports.certificate_tool_port import CertificateToolPort
from omega_serv.ports.clock_port import ClockPort
from omega_serv.ports.filesystem_port import FilesystemPort
from omega_serv.ports.process_runner_port import ProcessRunnerPort

_CERTBOT_TIMEOUT_SECONDS = 180.0


@dataclass(frozen=True)
class RequestLetsEncryptCertificateResult:
    success: bool
    message: str


def request_lets_encrypt_certificate(
    domain: str,
    webroot_path: Path,
    letsencrypt_dir: Path,
    dest_key_path: Path,
    dest_cert_path: Path,
    service_name: str,
    python_executable: str,
    process_runner: ProcessRunnerPort,
    certificate_tool: CertificateToolPort,
    filesystem: FilesystemPort,
    clock: ClockPort,
    backups_dir: Path,
    email: str | None = None,
    staging: bool = True,
) -> RequestLetsEncryptCertificateResult:
    config_dir = letsencrypt_dir / "config"
    work_dir = letsencrypt_dir / "work"
    logs_dir = letsencrypt_dir / "logs"
    hook_script_path = letsencrypt_dir / "hooks" / f"deploy-{domain}.sh"

    params = CertbotRequestParams(
        domain=domain, webroot_path=str(webroot_path),
        config_dir=str(config_dir), work_dir=str(work_dir), logs_dir=str(logs_dir),
        deploy_hook_path=str(hook_script_path), email=email, staging=staging,
    )
    errors = validate_certbot_request_params(params)
    if errors:
        return RequestLetsEncryptCertificateResult(False, "; ".join(errors))

    hook_content = build_deploy_hook_script(
        python_executable=python_executable, config_dir=str(config_dir),
        domain=domain, service_name=service_name,
    )
    filesystem.make_directory(hook_script_path.parent)
    filesystem.write_text(hook_script_path, hook_content)
    filesystem.set_file_mode(hook_script_path, 0o700)

    result = process_runner.run(build_certbot_argv(params), timeout=_CERTBOT_TIMEOUT_SECONDS)
    if not result.ok:
        return RequestLetsEncryptCertificateResult(
            False, f"Certbot a echoue : {(result.stderr or result.stdout).strip()}",
        )

    source_key = config_dir / "live" / domain / "privkey.pem"
    source_cert = config_dir / "live" / domain / "fullchain.pem"
    import_result = import_certificate(
        source_key, source_cert, dest_key_path, dest_cert_path,
        certificate_tool, filesystem, clock, backups_dir,
    )
    if not import_result.success:
        return RequestLetsEncryptCertificateResult(
            False, f"Certificat Let's Encrypt obtenu mais import echoue : {import_result.message}",
        )

    return RequestLetsEncryptCertificateResult(
        True, f"Certificat Let's Encrypt obtenu et installe : {dest_cert_path}. "
        f"Renouvellement automatique via : {hook_script_path}",
    )
