"""Certificats de l'instance et leurs echeances (etude OMEGA-SERV_ETUDE_MODULES_ADMIN_WEB.md, module 3 ; cadre de
l'auteur du 2026-11-17 : aucun risque, aucune surface d'attaque).

Certificats LOCAUX seulement, lus par openssl (deja utilise par omega-serv) : jamais de connexion vers un backend,
jamais de decodeur maison. Sources : certificat du site (tls.certificate_path), certificat du panneau web, et tout
fichier de secure/certificates/ qui contient un certificat (CA locale, pont Certbot...). Les cles privees ne sont
jamais lues : un fichier sans « BEGIN CERTIFICATE » est ignore. Partage par la TUI (TLS -> Echeances) et par le
processus d'administration (vue Certificats, alertes)."""
from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

from omega_serv.core.i18n import _
from omega_serv.domain.config.entities import OmegaServConfig
from omega_serv.ports.certificate_tool_port import CertificateToolPort
from omega_serv.ports.filesystem_port import FilesystemPort

SCAN_DIRECTORY = Path("secure") / "certificates"
MAX_FILES = 60
"""Au plus autant de fichiers examines (un dossier rempli par erreur ne fige jamais l'ecran)."""
CERTIFICATE_SUFFIXES = (".pem", ".crt", ".cer")
SOON_DAYS = 30
URGENT_DAYS = 7
ALERT_DAYS = (30, 14, 7, 1)
"""Paliers d'alerte (module 2) : une alerte par palier franchi."""
_MARKER = b"-----BEGIN CERTIFICATE-----"


@dataclass(frozen=True)
class CertificateLine:
    label: str
    path: str
    """Relatif a la racine de l'instance quand il y est."""
    state: str
    """ok, soon (< 30 j), urgent (< 7 j), expired, unreadable, missing, no_tool."""
    days: int | None = None
    not_after: str = ""
    subject: str = ""
    issuer: str = ""
    names: tuple[str, ...] = ()
    detail: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {"label": self.label, "path": self.path, "state": self.state, "days": self.days,
                "not_after": self.not_after, "subject": self.subject, "issuer": self.issuer,
                "names": list(self.names), "detail": self.detail}

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> CertificateLine:
        return cls(str(data.get("label", "")), str(data.get("path", "")), str(data.get("state", "unreadable")),
                   data.get("days") if isinstance(data.get("days"), int) else None, str(data.get("not_after", "")),
                   str(data.get("subject", "")), str(data.get("issuer", "")),
                   tuple(str(n) for n in data.get("names", []) if isinstance(n, str)), str(data.get("detail", "")))


def certificate_sources(config: OmegaServConfig, project_root: Path, filesystem: FilesystemPort,
                        admin_certificate: Path | None = None) -> list[tuple[str, Path]]:
    """(libelle, chemin absolu) : site, panneau web, puis les autres fichiers de secure/certificates/ (tries)."""
    root = project_root.resolve()
    found: list[tuple[str, Path]] = []
    seen: set[Path] = set()

    def add(label: str, path: Path) -> None:
        absolute = path if path.is_absolute() else root / path
        if absolute not in seen and len(found) < MAX_FILES:
            seen.add(absolute)
            found.append((label, absolute))

    if config.tls.enabled or filesystem.exists(root / config.tls.certificate_path):
        add(_("Site"), Path(config.tls.certificate_path))
    if admin_certificate is not None:
        add(_("Panneau web"), admin_certificate)
    for path in _scan(filesystem, root / SCAN_DIRECTORY):
        add(_("Autre certificat"), path)
    return found


def _scan(filesystem: FilesystemPort, directory: Path, depth: int = 0) -> list[Path]:
    if depth > 3 or not filesystem.is_dir(directory):
        return []
    try:
        names = sorted(filesystem.list_directory_entries(directory))
    except OSError:
        return []
    files: list[Path] = []
    for name in names:
        path = directory / name
        if filesystem.is_dir(path):
            files += _scan(filesystem, path, depth + 1)
        elif name.endswith(CERTIFICATE_SUFFIXES) and not name.endswith(".old"):
            files.append(path)
        if len(files) >= MAX_FILES:
            break
    return files


def _state(days: int) -> str:
    if days < 0:
        return "expired"
    if days < URGENT_DAYS:
        return "urgent"
    if days < SOON_DAYS:
        return "soon"
    return "ok"


def inspect_all(sources: list[tuple[str, Path]], project_root: Path, filesystem: FilesystemPort,
                tool_factory: Callable[[], CertificateToolPort] | None, now: datetime) -> list[CertificateLine]:
    """Une ligne par source. Jamais d'exception : fichier absent, illisible ou openssl absent = etat dedie."""
    root = project_root.resolve()
    lines: list[CertificateLine] = []
    tool = tool_factory() if tool_factory is not None else None
    for label, path in sources:
        shown = str(path.relative_to(root)) if root in path.parents else str(path)
        if not filesystem.is_file(path):
            lines.append(CertificateLine(label, shown, "missing"))
            continue
        try:
            head = filesystem.read_bytes(path)[:65536]
        except OSError as error:
            lines.append(CertificateLine(label, shown, "unreadable", detail=error.strerror or str(error)))
            continue
        if _MARKER not in head:
            continue  # cle privee, CSR, fichier vide : pas un certificat
        if tool is None:
            lines.append(CertificateLine(label, shown, "no_tool"))
            continue
        try:
            info = tool.inspect_certificate(path)
        except Exception as error:  # noqa: BLE001 - openssl absent ou fichier abime : etat « illisible », jamais d'arret
            lines.append(CertificateLine(label, shown, "unreadable", detail=str(error)[:200]))
            continue
        days = info.days_remaining(now)
        lines.append(CertificateLine(
            label, shown, _state(days), days, info.not_after.date().isoformat(), info.subject, info.issuer,
            tuple(info.san_dns) + tuple(info.san_ip)))
    return lines


def state_text(line: CertificateLine) -> str:
    texts = {
        "ok": _("valable encore {days} jours"), "soon": _("expire dans {days} jours"),
        "urgent": _("expire dans {days} jours"), "expired": _("expiré depuis {days} jours"),
        "unreadable": _("illisible"), "missing": _("fichier absent"),
        "no_tool": _("échéance inconnue (openssl absent)"),
    }
    text = texts.get(line.state, line.state).format(days=abs(line.days) if line.days is not None else "?")
    return f"{text} ({line.detail})" if line.detail else text


def tone(line: CertificateLine) -> str:
    return {"ok": "ok", "soon": "warn", "urgent": "error", "expired": "error", "unreadable": "error",
            "missing": "dim", "no_tool": "dim"}.get(line.state, "dim")
