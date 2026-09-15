# Copyright (c) 2026 kraynux - kraynux@proton.me - Licence MIT (voir fichier LICENSE)
"""Racine du projet et chemins internes fixes.

Deduite de l'emplacement reel de ce fichier source, jamais du
repertoire courant du processus (os.getcwd()) : un chemin relatif au
cwd depend de la maniere dont le lanceur a ete invoque et casse selon
le contexte de demarrage - lecon deja tiree sur un bug reel similaire
dans omega-fire (interfaces/tui/screens/lnav_screen.py, chemins epingles
resolus depuis un cwd non garanti). Meme principe applique ici des le
depart plutot que redecouvert plus tard."""
from __future__ import annotations

from pathlib import Path


def _resolve_project_root() -> Path:
    # Ce fichier vit sous src/omega_serv/bootstrap/paths.py : remonter
    # 3 niveaux (bootstrap -> omega_serv -> src) atteint la racine.
    return Path(__file__).resolve().parents[3]


PROJECT_ROOT: Path = _resolve_project_root()
CONFIG_DIR: Path = PROJECT_ROOT / "config"
CONFIG_FILE: Path = CONFIG_DIR / "omega-serve.json"
VAR_DIR: Path = PROJECT_ROOT / "var"
LOG_DIR: Path = VAR_DIR / "log"
BACKUPS_DIR: Path = VAR_DIR / "backups"
RUN_DIR: Path = VAR_DIR / "run"
WEBROOT_DIR: Path = PROJECT_ROOT / "webroot"
SECURE_DIR: Path = PROJECT_ROOT / "secure"

# Registre multi-instance (OMEGA-SERV_PLAN-DETAILLE_MULTI_INSTANCE.md §3) -
# SEUL chemin de tout le projet qui vit deliberement HORS de
# PROJECT_ROOT : c'est justement sa raison d'etre, connaitre TOUTES les
# installations a la fois, jamais une seule. Convention XDG standard
# (~/.config/), jamais derive de PROJECT_ROOT (le seul fichier qui ne
# doit surtout pas etre par-instance).
INSTANCE_REGISTRY_PATH: Path = Path.home() / ".config" / "omega-serv" / "instances.json"
