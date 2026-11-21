# Copyright (c) 2026 kraynux - kraynux@proton.me - Licence MIT (voir fichier LICENSE)
"""« Générer le certificat » de l'ecran Configuration distante (lot 8, §9.4) : certificat auto-signe dedie a
l'administration web, au nom de la machine et a ses adresses, cle lisible par le groupe du service (le processus
d'administration tourne sous le compte du service). Remplace l'essai a la main du 2026-11-17 (openssl, chgrp, chmod).

Deux temps, pour que l'ecran ne suspende le terminal (invite sudo) que si c'est necessaire : `generate` sous votre
compte, puis `share` sans privilege ; si votre session n'a pas encore le groupe du service, `share` avec sudo."""
from __future__ import annotations

import ipaddress
from dataclasses import dataclass
from pathlib import Path

from omega_serv.core.i18n import _
from omega_serv.domain.admin_web.settings import AdminWebSettings
from omega_serv.domain.security.tls.entities import SelfSignedCertParams
from omega_serv.ports.admin_web_setup_port import (
    SHARE_NEEDS_PRIVILEGE,
    SHARE_NO_GROUP,
    AdminWebSetupPort,
)
from omega_serv.ports.certificate_tool_port import CertificateToolPort
from omega_serv.ports.filesystem_port import FilesystemPort

VALIDITY_DAYS = 825
OLD_SUFFIX = ".ancien"


@dataclass(frozen=True)
class CertificateSetupOutcome:
    ok: bool
    message: str
    needs_privilege: bool = False


def certificate_params(settings: AdminWebSettings, hostname: str, addresses: tuple[str, ...]) -> SelfSignedCertParams:
    """Noms : la machine et localhost ; adresses : celles de la machine, plus l'adresse d'ecoute si elle est precise
    (adresse Tailscale par exemple)."""
    ips = list(addresses)
    try:
        bind = ipaddress.ip_address(str(settings.bind))
    except ValueError:
        bind = None
    if bind is not None and not bind.is_unspecified and str(bind) not in ips:
        ips.append(str(bind))
    names = [name for name in dict.fromkeys((hostname, "localhost")) if name]
    return SelfSignedCertParams(common_name=hostname or "localhost", san_dns=tuple(names), san_ip=tuple(ips),
                                organizational_unit="administration web", validity_days=VALIDITY_DAYS,
                                key_type="ecdsa-p256")


def _paths(project_root: Path, settings: AdminWebSettings) -> tuple[Path, Path] | None:
    root = project_root.resolve()
    certificate = (root / str(settings.certificate_path)).resolve()
    key = (root / str(settings.private_key_path)).resolve()
    if root not in certificate.parents or root not in key.parents:
        return None
    return certificate, key


def shared_directories(project_root: Path, certificate: Path, key: Path) -> tuple[Path, ...]:
    """Dossiers que le service doit traverser : de secure/certificates jusqu'au dossier des fichiers ; ailleurs, le
    seul dossier des fichiers. Jamais la racine ni secure/ (les autres secrets restent a vous seul)."""
    base = project_root.resolve() / "secure" / "certificates"
    directories: list[Path] = []
    for path in (certificate.parent, key.parent):
        chain = [path]
        if base == path or base in path.parents:
            chain = [base, *(parent for parent in reversed(path.parents) if base in parent.parents), path]
        for directory in chain:
            if directory not in directories:
                directories.append(directory)
    return tuple(directories)


def generate(tool: CertificateToolPort, setup: AdminWebSetupPort, filesystem: FilesystemPort, project_root: Path,
             settings: AdminWebSettings) -> CertificateSetupOutcome:
    paths = _paths(project_root, settings)
    if paths is None:
        return CertificateSetupOutcome(False, _("Chemins du certificat hors du dossier de l'instance : rien n'est "
                                                "généré."))
    certificate, key = paths
    for path in (certificate, key):  # jamais d'ecrasement sans copie (fichier seul, l'autre absent)
        if filesystem.exists(path):
            filesystem.copy_file(path, path.with_name(path.name + OLD_SUFFIX))
            filesystem.delete_file(path)
    hostname, addresses = setup.machine_names()
    try:
        tool.generate_self_signed(certificate_params(settings, hostname, addresses), key, certificate)
    except Exception as error:  # noqa: BLE001 - CertificateToolError ou OSError : message affiche tel quel
        return CertificateSetupOutcome(False, _("Échec de la génération du certificat : {error}").format(error=error))
    return CertificateSetupOutcome(True, _("Certificat généré : {path} (valable {days} jours).").format(
        path=certificate.relative_to(project_root.resolve()), days=VALIDITY_DAYS))


def share(setup: AdminWebSetupPort, project_root: Path, settings: AdminWebSettings, group: str, *,
          privileged: bool) -> CertificateSetupOutcome:
    paths = _paths(project_root, settings)
    if paths is None:
        return CertificateSetupOutcome(False, _("Chemins du certificat hors du dossier de l'instance."))
    certificate, key = paths
    result = setup.share_with_group(shared_directories(project_root, certificate, key), key, certificate, group,
                                    privileged=privileged)
    if result == "" or result == SHARE_NO_GROUP:
        return CertificateSetupOutcome(True, _("Clé lisible par le service."))
    if result == SHARE_NEEDS_PRIVILEGE:
        return CertificateSetupOutcome(False, "", needs_privilege=True)
    return CertificateSetupOutcome(False, _("Droits du certificat non posés ({error}) : le service ne pourra pas le "
                                            "lire.").format(error=result))
