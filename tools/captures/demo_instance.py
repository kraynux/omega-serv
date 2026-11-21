"""Générateur d'une instance de DÉMONSTRATION d'omega-serv, pour les captures d'écran de la TUI.

Usage :
    .venv/bin/python tools/captures/demo_instance.py <dest>

Recrée <dest> de zéro (supprimé puis reconstruit à chaque passage), avec :
  <dest>/omega-serv/   copie de l'application (src/, config/, secure/, var/, webroot/, bin/, pyproject.toml)
                       - configuration complète et valide, données fictives sur 30 jours ;
  <dest>/staging/, <dest>/docs/   deux instances fictives légères (registre des instances) ;
  <dest>/home/         HOME factice (registre ~/.config/omega-serv/instances.json de la démo).

Rien n'est lu ni écrit dans le vrai var/, config/, secure/ du projet, ni dans le vrai ~/.config. Le script ne
démarre aucun serveur, n'appelle ni sudo, ni systemd, ni pare-feu. Toutes les adresses sont des adresses de
documentation (RFC 5737 / RFC 3849) et tous les noms de domaine sont en exemple.org.

Fonctionnement en deux temps :
  1. ce processus copie l'application et prépare les dossiers ;
  2. il se relance lui-même (`--_populate`) avec HOME=<dest>/home et PYTHONPATH=<dest>/omega-serv/src : la
     génération des données importe alors la COPIE d'omega-serv (PROJECT_ROOT pointe dans <dest>), et utilise
     ses propres dépôts / fonctions de hachage / services pour écrire les fichiers dans leur format exact.
"""
from __future__ import annotations

import argparse
import os
import shutil
import subprocess
import sys
from pathlib import Path

REAL_PROJECT_ROOT = Path(__file__).resolve().parents[2]
DEMO_MARKER = ".omega-serv-demo"
DEMO_VERSION = "3.0.0"
SERVER_PORT = 18080
STAGING_PORT = 18081
DOCS_PORT = 18082
ADMIN_PORT = 19643
BACKEND_PORTS = (18101, 18102, 18103)
SERVICE_NAME = "omega-serv-demo"

_IGNORED = shutil.ignore_patterns("__pycache__", "*.pyc", "*.bak", "*~", "*.orig")


# ---------------------------------------------------------------------------------------------------------------------
# Garde-fous sur la destination


def _check_destination(dest: Path) -> None:
    """Refuse toute destination qui pourrait toucher le vrai projet ou un dossier réel de l'utilisateur."""
    home = Path.home().resolve()
    forbidden_exact = {Path("/"), home, home.parent, REAL_PROJECT_ROOT, REAL_PROJECT_ROOT.parent,
                       REAL_PROJECT_ROOT.parent.parent, home / ".config", Path("/tmp")}
    if dest in forbidden_exact:
        sys.exit(f"Refus : {dest} est un dossier réel, pas une destination de démonstration.")
    if dest == REAL_PROJECT_ROOT or REAL_PROJECT_ROOT in dest.parents:
        sys.exit(f"Refus : {dest} est à l'intérieur du vrai projet omega-serv ({REAL_PROJECT_ROOT}).")
    if dest in REAL_PROJECT_ROOT.parents:
        sys.exit(f"Refus : {dest} contient le vrai projet omega-serv.")
    if (home / ".config") in dest.parents:
        sys.exit(f"Refus : {dest} est sous ~/.config.")
    if dest.exists():
        if not dest.is_dir():
            sys.exit(f"Refus : {dest} existe et n'est pas un dossier.")
        if any(dest.iterdir()) and not (dest / DEMO_MARKER).exists():
            sys.exit(f"Refus : {dest} existe, n'est pas vide et n'a pas été créé par ce script ({DEMO_MARKER} absent).")


# ---------------------------------------------------------------------------------------------------------------------
# Étape 1 : copie de l'application


def _copy_application(root: Path) -> None:
    root.mkdir(parents=True)
    shutil.copytree(REAL_PROJECT_ROOT / "src", root / "src", ignore=_IGNORED)
    # config/ : profils et schéma seulement, le fichier omega-serve.json est écrit par la génération.
    (root / "config").mkdir()
    for sub in ("profiles", "schemas"):
        if (REAL_PROJECT_ROOT / "config" / sub).is_dir():
            shutil.copytree(REAL_PROJECT_ROOT / "config" / sub, root / "config" / sub, ignore=_IGNORED)
    # Base de départ de la configuration : la configuration du projet (chemins relatifs), jamais modifiée.
    shutil.copy2(REAL_PROJECT_ROOT / "config" / "omega-serve.json", root / "config" / "omega-serve.base.json")
    # secure/ : seulement les packs de règles et scripts WAF publiés avec l'application (jamais les comptes, mots de
    # passe, certificats ni la liste de blocage réels).
    (root / "secure").mkdir(mode=0o750)
    rules = REAL_PROJECT_ROOT / "secure" / "waf" / "rules"
    if rules.is_dir():
        shutil.copytree(rules, root / "secure" / "waf" / "rules", ignore=_IGNORED)
    # Seulement le script Magnet publié (waf.lua), jamais un script personnel de l'auteur.
    script = REAL_PROJECT_ROOT / "secure" / "waf" / "scripts" / "waf.lua"
    if script.is_file():
        (root / "secure" / "waf" / "scripts").mkdir(parents=True)
        shutil.copy2(script, root / "secure" / "waf" / "scripts" / "waf.lua")
    # Version de la démo : seulement dans la copie.
    pyproject = (REAL_PROJECT_ROOT / "pyproject.toml").read_text(encoding="utf-8")
    lines = pyproject.splitlines(keepends=True)
    for index, line in enumerate(lines):
        if line.startswith("version = "):
            lines[index] = f'version = "{DEMO_VERSION}"\n'
            break
    (root / "pyproject.toml").write_text("".join(lines), encoding="utf-8")
    for name in ("LICENSE", "HEADER.txt"):
        if (REAL_PROJECT_ROOT / name).is_file():
            shutil.copy2(REAL_PROJECT_ROOT / name, root / name)
    # Moteur natif : le binaire réel (lien bin/ résolu), au chemin relatif attendu par engine_selection.
    binary = (REAL_PROJECT_ROOT / "bin" / "omega-http-core").resolve()
    if binary.is_file():
        (root / "bin").mkdir()
        shutil.copy2(binary, root / "bin" / "omega-http-core")
    (root / "var").mkdir()
    (root / "webroot").mkdir()


# ---------------------------------------------------------------------------------------------------------------------
# Programme principal


def _demo_env(dest: Path) -> dict[str, str]:
    """Environnement de la démo : HOME factice, copie importée (+ masque), zone omega-connect factice."""
    env = {"HOME": str(dest / "home"),
           "PYTHONPATH": f"{dest / 'omega-serv' / 'src'}:{dest / 'masque'}",
           "OMEGA_SYNCHRO_DIR": str(dest / "synchro")}
    return env


def _populate_in_copy(dest: Path, admin_bind: str, tls_mode: str) -> None:
    """Relance ce script avec la copie importée et le HOME factice."""
    env = dict(os.environ)
    env.update(_demo_env(dest))
    env["PYTHONPATH"] = str(dest / "omega-serv" / "src")  # le masque n'existe pas encore
    env.pop("XDG_CONFIG_HOME", None)
    env.pop("OMEGA_SERV_LANG", None)
    env["LANG"] = "fr_FR.UTF-8"
    command = [sys.executable, str(Path(__file__).resolve()), "--_populate", str(dest),
               "--admin-bind", admin_bind, "--tls-mode", tls_mode]
    subprocess.run(command, env=env, check=True, cwd=str(dest))


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Génère une instance de démonstration d'omega-serv (captures).")
    parser.add_argument("dest", help="dossier de destination (recréé de zéro)")
    parser.add_argument("--admin-bind", default="127.0.0.1",
                        help="adresse d'écoute de l'administration web (défaut 127.0.0.1 ; le bouton « Ouvrir le "
                             "port » n'apparaît que hors boucle locale, ex. 0.0.0.0)")
    parser.add_argument("--tls-mode", choices=("direct", "behind_proxy"), default="direct",
                        help="direct (défaut : TLS par omega-serv ; le natif se replie alors sur Python à cause de "
                             "FastCGI/envoi de fichiers) ou behind_proxy (le moteur natif reste effectif)")
    parser.add_argument("--_populate", action="store_true", help=argparse.SUPPRESS)
    args = parser.parse_args(argv)
    dest = Path(args.dest).expanduser().resolve()
    if args._populate:
        from demo_populate import (
            populate,
        )

        populate(dest, REAL_PROJECT_ROOT, args.admin_bind, args.tls_mode)
        return 0

    _check_destination(dest)
    if dest.exists():
        shutil.rmtree(dest)
    dest.mkdir(parents=True)
    (dest / DEMO_MARKER).write_text("Instance de démonstration omega-serv (tools/captures/demo_instance.py).\n",
                                    encoding="utf-8")
    root = dest / "omega-serv"
    print(f"Copie de l'application vers {root} ...")
    _copy_application(root)
    (dest / "home").mkdir()
    _populate_in_copy(dest, args.admin_bind, args.tls_mode)
    python = REAL_PROJECT_ROOT / ".venv" / "bin" / "python"
    env = " ".join(f"{key}={value}" for key, value in _demo_env(dest).items())
    print()
    print("Instance de démonstration prête (rien n'a été démarré).")
    print(f"  Interface (TUI)      : cd {root} && {env} {python} -m omega_serv")
    print(f"  Serveur (1er plan)   : cd {root} && {env} {python} -m omega_serv serve")
    print(f"  Admin web seule      : cd {root} && {env} {python} -m omega_serv "
          f"--config {root / 'config' / 'omega-serve.json'} admin-web run")
    print(f"  Vérification (TUI)   : {env} {python} {Path(__file__).with_name('verify_demo.py')} {dest}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
