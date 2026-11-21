"""Construction des variables d'environnement CGI/1.1 (spec §21) pour
une requete FastCGI. Fonction pure : ne sait rien du transport
(socket Unix) ni de la resolution de chemin - recoit deja les chemins
absolus resolus par l'appelant (infrastructure/filesystem/,
SafePathResolver)."""
from __future__ import annotations

import re

from omega_serv.domain.http.admin_cookies import without_admin_cookies
from omega_serv.domain.http.request import HttpRequest

_SKIPPED_HTTP_HEADERS = frozenset({"content-type", "content-length"})
_TOKEN_NAME = re.compile(r"[A-Za-z0-9!#$%&'*+.^`|~-]+")


def build_cgi_env(
    request: HttpRequest,
    script_filename: str,
    script_name: str,
    document_root: str,
    server_name: str,
    server_port: int,
) -> dict[str, str]:
    env: dict[str, str] = {
        "GATEWAY_INTERFACE": "CGI/1.1",
        "SERVER_SOFTWARE": "OMEGA-SERV",
        "SERVER_PROTOCOL": "HTTP/1.1",
        "SERVER_NAME": server_name,
        "SERVER_PORT": str(server_port),
        "REQUEST_METHOD": request.method,
        "SCRIPT_FILENAME": script_filename,
        "SCRIPT_NAME": script_name,
        "REQUEST_URI": request.raw_path,
        "QUERY_STRING": request.query,
        "REMOTE_ADDR": request.remote_ip,
        "DOCUMENT_ROOT": document_root,
        "REDIRECT_STATUS": "200",
    }

    if request.is_tls:
        env["HTTPS"] = "on"

    content_type = request.header("content-type")
    if content_type:
        env["CONTENT_TYPE"] = content_type
    if request.body:
        env["CONTENT_LENGTH"] = str(len(request.body))

    for name, value in request.headers:
        if name.lower() in _SKIPPED_HTTP_HEADERS:
            continue
        # Scan de securite n° 1 (2026-11-20, F40) : `Proxy:` du client devenait HTTP_PROXY (« httpoxy »), lu par
        # les bibliotheques HTTP du script comme proxy sortant ; un nom avec « _ » ou hors jeton (RFC 9110 §5.6.2)
        # pouvait se faire passer pour un en-tete pose par un composant de confiance (X_Forwarded_For). Ignores,
        # comme Apache, lighttpd et nginx.
        if name.lower() == "proxy" or not _TOKEN_NAME.fullmatch(name):
            continue
        if name.lower() == "cookie":
            value = without_admin_cookies(value)  # scan n° 2 (F16) : jamais la session de l'administration web
            if not value:
                continue
        env["HTTP_" + name.upper().replace("-", "_")] = value

    return env
