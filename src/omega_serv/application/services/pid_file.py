# Copyright (c) 2026 kraynux - kraynux@proton.me - Licence MIT (voir fichier LICENSE)
"""Fichier PID (angle mort §9.1 : "signal SIGHUP vers le PID de
var/run/omega-serv.pid"). Ecriture/lecture/suppression uniquement -
l'envoi effectif du signal est une commande shell externe
(`kill -HUP $(cat var/run/omega-serv.pid)`), pas une responsabilite
d'OMEGA-SERV lui-meme."""
from __future__ import annotations

from pathlib import Path

from omega_serv.ports.filesystem_port import FilesystemPort


def write_pid_file(filesystem: FilesystemPort, path: Path, pid: int) -> None:
    filesystem.make_directory(path.parent)
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
