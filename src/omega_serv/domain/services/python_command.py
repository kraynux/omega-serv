# Copyright (c) 2026 kraynux - kraynux@proton.me - Licence MIT (voir fichier LICENSE)
"""Relance d'un module omega_serv dans un interpreteur neuf (scan de securite n° 2 du 2026-11-20, F35).

`python -m omega_serv` place le dossier courant en tete de sys.path : lance par root depuis un dossier ou le
compte du service peut ecrire, un `omega_serv.py` pose la s'executait en root. Le mode isole (`-I`) l'evite, mais
il ignore aussi PYTHONPATH : le processus enfant importait alors l'installation du venv au lieu de l'arbre de code
du parent (copie de test, autre instance), et ecrivait dans le var/ de cette autre installation.

Ici : `-I` (ni dossier courant, ni PYTHONPATH, ni site utilisateur) PUIS le dossier `src` du code qui lance,
ajoute explicitement en tete : l'enfant execute toujours le meme code que son parent."""
from __future__ import annotations

from pathlib import Path

_BOOTSTRAP = ("import runpy,sys;sys.argv.pop(0);sys.path.insert(0,sys.argv.pop(0));"
              "runpy.run_module(sys.argv[0],run_name='__main__',alter_sys=True)")


def package_source_root() -> str:
    """Dossier qui contient le paquet omega_serv en cours d'execution (src/)."""
    return str(Path(__file__).resolve().parents[3])


def python_module_argv(python_executable: str, module: str, *arguments: str,
                       source_root: str | None = None) -> list[str]:
    """Equivalent sur de `python -m <module> <arguments...>`, code pris dans `source_root` (par defaut le meme
    arbre que l'appelant)."""
    return [python_executable, "-I", "-c", _BOOTSTRAP, source_root or package_source_root(), module, *arguments]
