# Copyright (c) 2026 kraynux - kraynux@proton.me - Licence MIT (voir fichier LICENSE)
"""Regles d'audit avec vraie I/O de permissions/fichiers (plan corrige
§5.4) - PERM-002 (fichier de comptes Auth), PERM-003 (fichiers sensibles
sous webroot)."""
from __future__ import annotations

from pathlib import Path

from omega_serv.domain.config.entities import OmegaServConfig
from omega_serv.domain.security.audit.entities import AuditFinding, Severity
from omega_serv.ports.filesystem_port import FilesystemPort

_SENSITIVE_NAMES = frozenset({
    ".env", ".git", ".htpasswd", ".htaccess", "config.php", "wp-config.php", "settings.py",
})
_SENSITIVE_SUFFIXES = (".key", ".pem", ".crt", ".p12")
_MAX_SENSITIVE_FILES_REPORTED = 10


def check_permissions(config: OmegaServConfig, project_root: Path, filesystem: FilesystemPort) -> list[AuditFinding]:
    findings: list[AuditFinding] = []
    findings.extend(_check_auth_file_permissions(config, project_root, filesystem))
    findings.extend(_check_sensitive_files_under_webroot(config, project_root, filesystem))
    return findings


def _check_auth_file_permissions(config: OmegaServConfig, project_root: Path, filesystem: FilesystemPort) -> list[AuditFinding]:
    """PERM-002 : le vrai fichier de comptes est paths.auth_file
    (secure/auth/users.json, JSON+scrypt) - jamais de htpasswd dans ce
    projet."""
    auth_option = config.options.get("auth")
    if auth_option is None or not auth_option.enabled:
        return []

    users_path = project_root / config.paths.auth_file
    if not filesystem.exists(users_path):
        return []

    mode = filesystem.file_mode(users_path)
    if mode & 0o077:
        return [AuditFinding(
            rule_id="PERM-002", rule_name="Fichier de comptes Auth lisible/inscriptible au-dela du proprietaire",
            severity=Severity.CRITICAL, category="permissions",
            message=f"{users_path} : permissions {oct(mode)}",
            recommendation=(
                "chmod 600 sur ce fichier (deja fait automatiquement par "
                "JsonUsersRepository.save() - verifier qu'il n'a pas ete edite/copie manuellement depuis)."
            ),
            details={"path": str(users_path), "mode": oct(mode)},
        )]
    return []


def _scan_sensitive(filesystem: FilesystemPort, root: Path) -> list[str]:
    found: list[str] = []
    for entry in filesystem.list_directory_entries(root):
        path = root / entry
        if filesystem.is_dir(path):
            found.extend(_scan_sensitive(filesystem, path))
        elif entry in _SENSITIVE_NAMES or entry.endswith(_SENSITIVE_SUFFIXES):
            found.append(str(path))
    return found


def _check_sensitive_files_under_webroot(config: OmegaServConfig, project_root: Path, filesystem: FilesystemPort) -> list[AuditFinding]:
    """PERM-003."""
    webroot = project_root / config.paths.webroot
    found = _scan_sensitive(filesystem, webroot)
    if found:
        return [AuditFinding(
            rule_id="PERM-003", rule_name="Fichiers sensibles detectes sous webroot",
            severity=Severity.CRITICAL, category="permissions",
            message=f"{len(found)} fichier(s) sensible(s) sous {webroot}",
            recommendation="Deplacer ces fichiers hors webroot (ex. secure/).",
            details={"webroot": str(webroot), "files": found[:_MAX_SENSITIVE_FILES_REPORTED]},
        )]
    return []
