"""Emplacement des blocklists sous var/lib/waf/ (OMEGA-SERV_PLAN-DETAILLE_
SENSITIVE_PATHS.md, apres l'incident craftdark du 2026-10-18) : creation du
dossier avec des droits EXPLICITES et reprise unique des anciens fichiers de
secure/waf/.

- Dossier en 2770 quel que soit l'umask : cree depuis la TUI/CLI sous umask 022,
  il serait sinon en 2750, donc NON inscriptible par le groupe du service.
  Le setgid fait heriter le groupe de var/lib/ (partage avec le service).
- Migration : seulement si le chemin configure est le NOUVEAU defaut, que le
  nouveau fichier n'existe pas encore et que l'ancien existe - jamais un
  ecrasement, jamais un chemin personnalise touche, l'ancien fichier conserve
  tel quel (copie, pas deplacement) comme sauvegarde."""
from __future__ import annotations

import sys
from pathlib import Path

from omega_serv.ports.filesystem_port import FilesystemPort

SHARED_DIRECTORY_MODE = 0o2770


def ensure_shared_directory(filesystem: FilesystemPort, directory: Path) -> None:
    if filesystem.is_dir(directory):
        return
    filesystem.make_directory(directory, mode=SHARED_DIRECTORY_MODE)
    try:
        filesystem.set_file_mode(directory, SHARED_DIRECTORY_MODE)
    except OSError:
        pass  # dossier cree par un autre compte entre-temps : ses droits priment


def prepare_blocklist_location(
    filesystem: FilesystemPort, project_root: Path, configured: str, default: str, legacy: str,
) -> str | None:
    """Renvoie un message si une migration a eu lieu (ou a echoue), sinon None."""
    if configured != default:
        return None
    target = project_root / default
    try:
        ensure_shared_directory(filesystem, target.parent)
    except OSError as e:
        return f"dossier {target.parent} impossible à créer : {e}"
    source = project_root / legacy
    if filesystem.exists(target) or not filesystem.exists(source):
        return None
    try:
        filesystem.atomic_write_text(target, filesystem.read_text(source))
    except OSError as e:
        message = f"ancienne blocklist {source} non reprise ({e}) - le fichier reste en place, à recopier à la main"
        print(f"ERREUR {message}", file=sys.stderr)
        return message
    message = f"blocklist reprise depuis {source} vers {target} (l'ancien fichier est conservé)"
    print(message, file=sys.stderr)
    return message
