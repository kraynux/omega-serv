"""Table MIME explicite et fermee.

Decision issue de la revue des angles morts avant Phase 0
(OMEGA-SERV_PLAN_DEVELOPPEMENT.md §9.5) : mimetypes.guess_type() varie
selon l'OS et la version Python installee - non deterministe pour un
serveur qui doit se comporter identiquement partout. Cette table est
volontairement fermee : une extension absente retombe sur
'application/octet-stream' (spec §28.4, jamais un type devine)."""
from __future__ import annotations

DEFAULT_MIME_TYPE = "application/octet-stream"

_EXTENSION_TO_MIME: dict[str, str] = {
    ".html": "text/html; charset=utf-8",
    ".htm": "text/html; charset=utf-8",
    ".txt": "text/plain; charset=utf-8",
    ".css": "text/css; charset=utf-8",
    ".js": "text/javascript; charset=utf-8",
    ".mjs": "text/javascript; charset=utf-8",
    ".json": "application/json",
    ".xml": "application/xml",
    ".svg": "image/svg+xml",
    ".png": "image/png",
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".gif": "image/gif",
    ".webp": "image/webp",
    ".ico": "image/x-icon",
    ".woff": "font/woff",
    ".woff2": "font/woff2",
    ".ttf": "font/ttf",
    ".pdf": "application/pdf",
}


def guess_mime_type(filename: str) -> str:
    dot_index = filename.rfind(".")
    if dot_index == -1:
        return DEFAULT_MIME_TYPE
    extension = filename[dot_index:].lower()
    return _EXTENSION_TO_MIME.get(extension, DEFAULT_MIME_TYPE)
