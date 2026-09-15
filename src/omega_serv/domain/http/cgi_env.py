# Copyright (c) 2026 kraynux - kraynux@proton.me - Licence MIT (voir fichier LICENSE)
"""Construction des variables d'environnement CGI/1.1 (spec §21) pour
une requete FastCGI. Fonction pure : ne sait rien du transport
(socket Unix) ni de la resolution de chemin - recoit deja les chemins
absolus resolus par l'appelant (infrastructure/filesystem/,
SafePathResolver)."""
from __future__ import annotations

from omega_serv.domain.http.request import HttpRequest

_SKIPPED_HTTP_HEADERS = frozenset({"content-type", "content-length"})


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
        # Exige par la plupart des configurations PHP-FPM durcies
        # (verification anti path-info-exploit) - sans cette variable,
        # certains pools refusent silencieusement d'executer le script.
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
        env["HTTP_" + name.upper().replace("-", "_")] = value

    return env
