"""Construction pure de la commande Certbot et du script de hook de
renouvellement (etude OMEGA-SERV_PLAN-DETAILLE_TLS_AUTO.md, Phase 4).
Aucune I/O ici - `application/tls/request_lets_encrypt_certificate.py`
execute reellement la commande et ecrit le script.

Decision cle de l'etude (§4/§5) : HTTP-01 en mode `--webroot`, jamais
`--standalone` (conflit de port si omega-serv ecoute deja sur le port
80) ni DNS-01 (aucun plugin fiable presuppose). `--config-dir`/`--work-
dir`/`--logs-dir` pointes SOUS `secure/certificates/letsencrypt/` (jamais
`/etc/letsencrypt/`, doc TLS §22 decision 5 : "tous les certificats...
restent sous secure/certificates/") - consequence directe et deliberee :
Certbot lui-meme n'a alors JAMAIS besoin de root/sudo (webroot ne bind
aucun port, et les repertoires d'etat sont dans un dossier que le
processus appelant possede deja) - aucune elevation de privileges a
construire pour cette fonctionnalite, contrairement a `service restart`
(deja gere ailleurs, ServiceManagerPort/SystemdServiceManager)."""
from __future__ import annotations

import shlex
from dataclasses import dataclass


@dataclass(frozen=True)
class CertbotRequestParams:
    domain: str
    webroot_path: str
    config_dir: str
    work_dir: str
    logs_dir: str
    deploy_hook_path: str
    email: str | None = None
    staging: bool = True
    """Par defaut a True (etude §5, ligne "Rate limits Let's Encrypt") :
    Let's Encrypt limite a 5 certificats dupliques/semaine - un premier
    essai part sur l'environnement de test (certificats non fiables pour
    les navigateurs mais illimites), jamais la production par defaut."""


def validate_certbot_request_params(params: CertbotRequestParams) -> list[str]:
    errors: list[str] = []
    if not params.domain:
        errors.append("le domaine ne peut pas etre vide")
    if not params.webroot_path:
        errors.append("le chemin du webroot ne peut pas etre vide")
    if not params.deploy_hook_path:
        errors.append("le chemin du script de hook ne peut pas etre vide")
    return errors


def build_certbot_argv(params: CertbotRequestParams) -> list[str]:
    argv = [
        "certbot", "certonly", "--non-interactive", "--agree-tos",
        "--webroot", "-w", params.webroot_path,
        "-d", params.domain,
        "--config-dir", params.config_dir,
        "--work-dir", params.work_dir,
        "--logs-dir", params.logs_dir,
        "--deploy-hook", params.deploy_hook_path,
    ]
    argv += ["-m", params.email] if params.email else ["--register-unsafely-without-email"]
    if params.staging:
        argv.append("--staging")
    return argv


def build_omega_serv_import_argv(
    python_executable: str, config_dir: str, domain: str,
) -> list[str]:
    return [
        python_executable, "-m", "omega_serv", "certs", "import",
        "--key", f"{config_dir}/live/{domain}/privkey.pem",
        "--cert", f"{config_dir}/live/{domain}/fullchain.pem",
    ]


def build_omega_serv_restart_argv(python_executable: str, service_name: str) -> list[str]:
    return [python_executable, "-m", "omega_serv", "service", "restart", "--service-name", service_name]


def build_deploy_hook_script(
    *, python_executable: str, config_dir: str, domain: str, service_name: str,
) -> str:
    """Script de renouvellement (doc TLS §14.3 "recharge du serveur
    apres renouvellement") - deux lignes, chacune reutilisant une
    commande CLI DEJA existante (import_certificate.py Phase 2, `service
    restart` deja livre) : jamais de logique OS dupliquee ici. Chemin
    absolu vers l'interpreteur Python COURANT (jamais un `omega-serv` nu
    sur le PATH) - garantit d'invoquer la MEME installation/instance qui
    a genere ce script, correct meme en multi-instance (chaque instance
    a son propre venv, PROJECT_ROOT est derive de `__file__` a
    l'interieur de CE venv precis, bootstrap/paths.py)."""
    import_argv = build_omega_serv_import_argv(python_executable, config_dir, domain)
    restart_argv = build_omega_serv_restart_argv(python_executable, service_name)
    lines = [
        "#!/bin/sh",
        "set -e",
        shlex.join(import_argv),
        shlex.join(restart_argv),
        "",
    ]
    return "\n".join(lines)
