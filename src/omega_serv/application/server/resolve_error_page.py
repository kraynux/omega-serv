"""Resolution du corps d'une page d'erreur : fichier personnalise si
l'option "error_pages" est active et qu'un fichier `{status}.html`
existe dans le repertoire configure (par defaut `webroot/.errors`,
inaccessible en acces HTTP direct - deny_hidden_files refuse tout
segment commencant par un point), sinon page par defaut (toujours
disponible, meme option desactivee - domain/http/error_pages.py).

Langue (OMEGA-SERV_PLAN-DETAILLE_I18N.md D19) : `{status}-{langue}.html` (ex. 404-en.html,
404-zh-CN.html) est servi en priorite dans la langue des pages visiteurs, sinon `{status}.html`
- une installation existante sans fichiers par langue ne change donc pas."""
from __future__ import annotations

from pathlib import Path

from omega_serv.core.i18n import page_html_lang
from omega_serv.domain.http.error_pages import render_default_error_page
from omega_serv.ports.filesystem_port import FilesystemPort


def resolve_error_page_body(status: int, custom_dir: Path | None, filesystem: FilesystemPort) -> bytes:
    if custom_dir is not None:
        code = int(status)
        for name in (f"{code}-{page_html_lang()}.html", f"{code}.html"):
            candidate = custom_dir / name
            if filesystem.is_file(candidate):
                return filesystem.read_bytes(candidate)
    return render_default_error_page(status)
