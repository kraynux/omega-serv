"""Lit les octets d'une icone SVG embarquee avec le paquet - meme patron
que `infrastructure/exporters/html_exporter.py::_TEMPLATES_DIR` (chemin
relatif a `__file__`, jamais `project_root` : ce repertoire fait partie
de l'installation d'omega-serv, jamais du site servi ni modifiable par
un utilisateur du serveur, condition de securite posee dans
`domain/routing/icon_registry.py`).

`read_icon_svg()` ne fait AUCUNE validation du nom recu - l'appelant
(`application/server/serve_icon.py`) doit deja avoir verifie que `name`
appartient a `icon_registry.ICON_FILENAMES` (ensemble ferme et connu a
l'avance) avant d'appeler cette fonction ; ce module reste un simple
lecteur de fichier, comme le reste d'`infrastructure/`."""
from __future__ import annotations

from pathlib import Path

_ICONS_DIR = Path(__file__).parent / "svg"


def read_icon_svg(name: str) -> bytes | None:
    path = _ICONS_DIR / name
    if not path.is_file():
        return None
    return path.read_bytes()
