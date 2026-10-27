"""Cas d'usage "fichier de liste edite depuis la TUI, lu par le service"
(OMEGA-SERV_PLAN-DETAILLE_SENSITIVE_PATHS.md §3.7, regles R1 a R7) - appele
par l'editeur integre (lot 4) et l'assistant WAF Custom (lot 6), jamais
contourne : aucun ecran n'ecrit un fichier de liste autrement.

Regles appliquees :
- R6 : le fichier doit etre un `.txt` DIRECTEMENT dans
  `secure/waf/rules/keywords/` du projet, sans aucun lien symbolique entre la
  racine du projet et lui (une verification lexicale ne suffit pas) ;
- R5 : non modifiable par l'utilisateur -> lecture seule, jamais via sudo ;
- R7 : modification exterieure pendant l'edition -> enregistrement refuse ;
- R1/R2 : ecriture atomique conservant mode et groupe, `0644` pour un
  nouveau fichier (comme les regles existantes, decision A10) ;
- R3/R4 : lisibilite par le compte du service verifiee apres chaque
  enregistrement, corrections proposees seulement sur ce que l'utilisateur
  possede."""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Literal

from omega_serv.core.i18n import _
from omega_serv.domain.config.validation import is_safe_relative_path
from omega_serv.domain.security.file_access import (
    AccessFix,
    PathNode,
    ReadabilityVerdict,
    plan_read_access_fixes,
    service_can_read,
)
from omega_serv.ports.file_access_port import FileAccessPort, WriteOutcome

KEYWORDS_DIR = "secure/waf/rules/keywords"
NEW_LIST_FILE_MODE = 0o644

ServiceCheck = Literal["readable", "unreadable", "no_service", "missing_file"]


@dataclass(frozen=True)
class ListFileStatus:
    path: Path
    location_error: str | None
    exists: bool
    writable: bool
    service_account: str | None
    service_check: ServiceCheck
    readability: ReadabilityVerdict | None = None
    fixes: tuple[AccessFix, ...] = field(default_factory=tuple)
    not_fixable: tuple[PathNode, ...] = field(default_factory=tuple)

    @property
    def editable(self) -> bool:
        return self.location_error is None and self.writable

    def service_message(self) -> str:
        if self.service_check == "no_service":
            return _("aucun service installé : le serveur lancé à la main lit le fichier sous votre compte")
        if self.service_check == "missing_file":
            return _("fichier pas encore créé")
        assert self.readability is not None and self.service_account is not None
        return self.readability.explain(self.service_account)


@dataclass(frozen=True)
class SaveResult:
    saved: bool
    refused_reason: str | None
    status: ListFileStatus
    outcome: WriteOutcome | None = None


def _location_error(file_access: FileAccessPort, project_root: Path, relative: str) -> str | None:
    if not is_safe_relative_path(relative):
        return _("chemin refusé (absolu ou contenant '..') : {relative!r}").format(relative=relative)
    path = project_root / relative
    if path.parent != project_root / KEYWORDS_DIR or path.suffix != ".txt":
        return _("une liste doit être un fichier .txt directement dans {KEYWORDS_DIR}/ : {relative!r}").format(KEYWORDS_DIR=KEYWORDS_DIR, relative=relative)
    if file_access.has_symlink_between(project_root, path):
        return _("lien symbolique refusé entre le projet et {relative!r} (il pourrait écrire hors du projet)").format(relative=relative)
    return None


def inspect_list_file(
    file_access: FileAccessPort, project_root: Path, relative: str, service_account: str | None,
) -> ListFileStatus:
    path = project_root / relative
    location_error = _location_error(file_access, project_root, relative)
    exists = location_error is None and file_access.fingerprint(path) is not None
    writable = location_error is None and file_access.can_write(path)

    identity = file_access.lookup_account(service_account) if service_account else None
    if identity is None:
        return ListFileStatus(path, location_error, exists, writable, None, "no_service")
    if not exists:
        return ListFileStatus(path, location_error, exists, writable, service_account, "missing_file")

    verdict = service_can_read(file_access.stat_chain(path), identity)
    fixes, not_fixable = plan_read_access_fixes(verdict, identity, file_access.current_uid())
    return ListFileStatus(
        path, location_error, exists, writable, service_account,
        "readable" if verdict.readable else "unreadable", verdict, fixes, not_fixable,
    )


def save_list_file(
    file_access: FileAccessPort,
    project_root: Path,
    relative: str,
    content: str,
    service_account: str | None,
    expected_fingerprint: tuple[int, int] | None,
) -> SaveResult:
    """`expected_fingerprint` = celui releve a l'ouverture (None si le
    fichier n'existait pas encore). Ne valide PAS la syntaxe de la liste :
    c'est le role de l'appelant (validateur unique, keyword_list.py), qui
    ne doit jamais appeler cette fonction sur un texte en erreur."""
    before = inspect_list_file(file_access, project_root, relative, service_account)
    if before.location_error is not None:
        return SaveResult(False, before.location_error, before)
    if not before.writable:
        return SaveResult(False, _("fichier ou dossier non modifiable par votre compte (lecture seule)"), before)
    if file_access.fingerprint(before.path) != expected_fingerprint:
        return SaveResult(False, _("le fichier a été modifié en dehors de l'éditeur depuis son ouverture"), before)

    outcome = file_access.atomic_write_preserving(before.path, content, NEW_LIST_FILE_MODE)
    after = inspect_list_file(file_access, project_root, relative, service_account)
    return SaveResult(True, None, after, outcome)


def apply_read_fixes(file_access: FileAccessPort, fixes: tuple[AccessFix, ...]) -> None:
    """Bouton "Corriger les droits" (R4) : seulement les corrections
    calculees par plan_read_access_fixes, donc sur des elements possedes."""
    for fix in fixes:
        file_access.set_mode(Path(fix.path), fix.new_mode)
