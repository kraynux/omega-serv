"""Regles d'audit avec vraie I/O de permissions/fichiers (plan corrige
§5.4) - PERM-002 (fichier de comptes Auth), PERM-003 (fichiers sensibles
sous webroot, contenu reel), PERM-004 (fichiers vides au nom sensible, information)."""
from __future__ import annotations

from pathlib import Path

from omega_serv.core.i18n import _
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
            rule_id="PERM-002", rule_name=_("Fichier de comptes Auth lisible/inscriptible au-delà du propriétaire"),
            severity=Severity.CRITICAL, category="permissions",
            message=_("{users_path} : permissions {value}").format(users_path=users_path, value=oct(mode)),
            recommendation=(
                _("chmod 600 sur ce fichier (déjà fait automatiquement par "
                "JsonUsersRepository.save() - vérifier qu'il n'a pas été edite/copie manuellement depuis).")
            ),
            details={"path": str(users_path), "mode": oct(mode)},
        )]
    return []


_CONTENT_READ_LIMIT = 1024 * 1024
"""Au-dela, le fichier n'est pas lu (classe « contenu present ») : l'audit ne charge jamais un gros fichier."""


def _match_reason(entry: str) -> str | None:
    """Pourquoi ce nom est signale : nom connu ou extension (decision de l'auteur du 2026-11-15 : dire QUOI ne va pas)."""
    if entry in _SENSITIVE_NAMES:
        return _("nom connu {name}").format(name=entry)
    for suffix in _SENSITIVE_SUFFIXES:
        if entry.endswith(suffix):
            return _("extension {suffix}").format(suffix=suffix)
    return None


def _classify_content(filesystem: FilesystemPort, path: Path) -> str:
    """Contenu REEL (comme les fichiers binaires du WAF, constat F2) : « empty » pour un fichier vide ou factice,
    sinon la nature reconnue aux premiers octets. Codes stables, traduits par _CONTENT_LABELS."""
    if filesystem.is_dir(path):
        return "directory"
    try:
        size = filesystem.file_size(path)
        if size == 0:
            return "empty"
        if size > _CONTENT_READ_LIMIT:
            return "content"
        head = filesystem.read_bytes(path)[:4096]
    except OSError:
        return "unreadable"
    if not head.strip():
        return "empty"
    if b"PRIVATE KEY-----" in head:
        return "private_key"
    if b"-----BEGIN CERTIFICATE-----" in head:
        return "certificate"
    if path.name.endswith(".p12") and head[:1] == b"\x30":
        return "pkcs12"
    return "content"


def _content_label(code: str) -> str:
    return {
        "directory": _("dossier"), "empty": _("fichier vide"), "unreadable": _("illisible"),
        "private_key": _("clé privée"), "certificate": _("certificat"), "pkcs12": _("conteneur PKCS#12"),
        "content": _("contenu présent"),
    }[code]


def _scan_sensitive(filesystem: FilesystemPort, root: Path) -> list[tuple[Path, str]]:
    """(chemin, raison). Un dossier au nom sensible (.git) est signale lui-meme, sans y descendre."""
    found: list[tuple[Path, str]] = []
    for entry in sorted(filesystem.list_directory_entries(root)):
        path = root / entry
        reason = _match_reason(entry)
        if filesystem.is_dir(path):
            if reason is not None and entry in _SENSITIVE_NAMES:
                found.append((path, reason))
            else:
                found.extend(_scan_sensitive(filesystem, path))
        elif reason is not None:
            found.append((path, reason))
    return found


def _detail_lines(entries: list[dict[str, str]]) -> tuple[str, ...]:
    lines = [f"{entry['path']} : {entry['reason']}, {entry['content_label']}"
             for entry in entries[:_MAX_SENSITIVE_FILES_REPORTED]]
    if len(entries) > _MAX_SENSITIVE_FILES_REPORTED:
        lines.append(_("... et {count} autre(s) (liste complète : omega-serv audit security --format json)").format(
            count=len(entries) - _MAX_SENSITIVE_FILES_REPORTED))
    return tuple(lines)


def _check_sensitive_files_under_webroot(config: OmegaServConfig, project_root: Path, filesystem: FilesystemPort) -> list[AuditFinding]:
    """PERM-003 (contenu reel present : critique) et PERM-004 (fichier vide ou factice : information).

    Decision de l'auteur du 2026-11-15 : nommer chaque fichier, dire pourquoi (nom connu ou extension) et ce
    qu'il contient vraiment ; un fichier vide (ex. fichier d'exemple pour l'icone du directory listing) n'est
    pas critique."""
    webroot = project_root / config.paths.webroot
    entries: list[dict[str, str]] = []
    for path, reason in _scan_sensitive(filesystem, webroot):
        code = _classify_content(filesystem, path)
        try:
            shown = str(path.relative_to(webroot))
        except ValueError:
            shown = str(path)
        entries.append({"path": shown, "reason": reason, "content": code, "content_label": _content_label(code)})
    real = [entry for entry in entries if entry["content"] != "empty"]
    empty = [entry for entry in entries if entry["content"] == "empty"]
    findings: list[AuditFinding] = []
    if real:
        findings.append(AuditFinding(
            rule_id="PERM-003", rule_name=_("Fichiers sensibles détectés sous webroot"),
            severity=Severity.CRITICAL, category="permissions",
            message=_("{count} fichier(s) sensible(s) sous {webroot}").format(count=len(real), webroot=webroot),
            recommendation=_("Déplacer ces fichiers hors webroot (ex. secure/)."),
            details={"webroot": str(webroot), "files": [str(webroot / entry["path"]) for entry in real],
                     "entries": real},
            detail_lines=_detail_lines(real),
        ))
    if empty:
        findings.append(AuditFinding(
            rule_id="PERM-004", rule_name=_("Fichiers vides au nom sensible sous webroot"),
            severity=Severity.INFO, category="permissions",
            message=_("{count} fichier(s) vide(s) au nom ou à l'extension sensible sous {webroot}").format(
                count=len(empty), webroot=webroot),
            recommendation=_("Sans contenu, rien n'est exposé ; à retirer s'ils ne servent pas (ex. exemples "
                             "d'icônes du directory listing)."),
            details={"webroot": str(webroot), "files": [str(webroot / entry["path"]) for entry in empty],
                     "entries": empty},
            detail_lines=_detail_lines(empty),
        ))
    return findings
