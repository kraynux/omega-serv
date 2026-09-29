"""Fichier PID (angle mort §9.1 : "signal SIGHUP vers le PID de
var/run/omega-serv.pid"). Ecriture/lecture/suppression uniquement -
l'envoi effectif du signal est une commande shell externe
(`kill -HUP $(cat var/run/omega-serv.pid)`), pas une responsabilite
d'OMEGA-SERV lui-meme."""
from __future__ import annotations

from pathlib import Path

from omega_serv.ports.filesystem_port import FilesystemPort


_SHARED_RUN_DIR_MODE = 0o770
"""Retour utilisateur reel (2026-09-27, boucle de crash systemd -
`PermissionError` sur var/run/omega-serv.pid.tmp, ~65 tentatives de
redemarrage) : `make_directory()` par defaut (0o750, voir
FilesystemPort) ne donne au groupe QUE lecture+traversee, jamais
ecriture - le compte systeme dedie (grant_directory_access,
systemd_service_manager.py, membre du groupe mais jamais proprietaire)
ne peut alors plus jamais y ecrire des que ce dossier a ete cree par
l'UTILISATEUR interactif (ou l'inverse), meme bug de fond que celui
deja corrige pour les fichiers de log (FileLineLogger, retour
utilisateur 2026-09-14) - jamais reproduit la-bas pour var/run/
specifiquement jusqu'ici. `set_file_mode` reapplique le mode a CHAQUE
demarrage (jamais seulement a la creation, contrairement au parametre
`mode=` de make_directory qui ne s'applique qu'une fois) - auto-guerit
un dossier deja mal permissionne par une execution anterieure, sans
exiger d'intervention manuelle DANS LE CAS COURANT (dossier deja
possede par le compte qui ecrit maintenant). `chmod` exige neanmoins
d'etre le PROPRIETAIRE du dossier (ou root) - si l'inverse s'est deja
produit (dossier cree par l'AUTRE compte, celui-ci simple membre du
groupe), ce chmod echoue lui-meme avec la meme PermissionError : jamais
aggraver la panne d'origine avec une seconde levee d'exception ici,
l'ecriture reelle juste apres restera la source d'erreur faisant foi
(message clair, deja adapte a ce cas - voir sa propre gestion)."""


def write_pid_file(filesystem: FilesystemPort, path: Path, pid: int) -> None:
    filesystem.make_directory(path.parent, mode=_SHARED_RUN_DIR_MODE)
    try:
        filesystem.set_file_mode(path.parent, _SHARED_RUN_DIR_MODE)
    except OSError:
        pass
    filesystem.atomic_write_text(path, f"{pid}\n")


def remove_pid_file(filesystem: FilesystemPort, path: Path) -> None:
    if filesystem.exists(path):
        filesystem.delete_file(path)


def read_pid_file(filesystem: FilesystemPort, path: Path) -> int | None:
    pid, _unreadable = pid_file_status(filesystem, path)
    return pid


def pid_file_status(filesystem: FilesystemPort, path: Path) -> tuple[int | None, bool]:
    """Retourne (pid, illisible). `pid` est None si le fichier est
    absent, malforme OU illisible (`read_pid_file` s'en contente).
    `illisible` distingue precisement "fichier present mais refuse en
    lecture" de "aucun fichier" - retour utilisateur 2026-09-10 : le
    message generique "Arrete (aucun fichier PID)" affiche par l'ecran
    Etat & Ressources s'est revele trompeur pendant la fenetre exacte
    entre l'installation du service systemd (partage de var/ avec le
    compte dedie, infrastructure/services/systemd_service_manager.py::
    grant_directory_access) et la reconnexion de session necessaire a
    la prise en compte du nouveau groupe Unix - le serveur peut etre
    reellement actif via systemd malgre ce message, l'ecran doit
    pouvoir afficher "INCONNU" plutot qu'affirmer a tort "ARRETE"."""
    if not filesystem.exists(path):
        return None, False
    try:
        return int(filesystem.read_text(path).strip()), False
    except ValueError:
        return None, False
    except OSError:
        return None, True
