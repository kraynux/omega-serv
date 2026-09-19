"""Resolution du corps d'une page d'erreur : fichier personnalise si
l'option "error_pages" est active et qu'un fichier `{status}.html`
existe dans le repertoire configure (par defaut `webroot/.errors`,
inaccessible en acces HTTP direct - deny_hidden_files refuse tout
segment commencant par un point), sinon page par defaut (toujours
disponible, meme option desactivee - domain/http/error_pages.py)."""
from __future__ import annotations

from pathlib import Path

from omega_serv.domain.http.error_pages import render_default_error_page
from omega_serv.ports.filesystem_port import FilesystemPort


def resolve_error_page_body(status: int, custom_dir: Path | None, filesystem: FilesystemPort) -> bytes:
    if custom_dir is not None:
        candidate = custom_dir / f"{int(status)}.html"
        if filesystem.is_file(candidate):
            return filesystem.read_bytes(candidate)
    return render_default_error_page(status)
