"""Sert une icone SVG du directory listing (retour utilisateur :
"incorporer des vrais icones svg" + recommandation OWASP citee) - meme
patron que `healthz.py` (chemin reserve, verifie tout en haut de
`route_request()`, avant toute regle utilisateur : redirections,
reecritures, alias, controle d'acces - une icone integree a l'application
n'a jamais a etre soumise aux regles du site servi).

`ICON_FILENAMES` (domain/routing/icon_registry.py) est un ensemble FERME,
connu a l'avance - la requete est rejetee (404) si le nom demande n'en
fait pas partie, jamais une resolution de chemin sur le nom recu. C'est
la seule verification de securite necessaire ici : `read_icon_svg()`
(infrastructure/icons/icon_files.py) ne lit ensuite QUE dans le
repertoire d'icones du paquet, jamais l'arborescence du site servi."""
from __future__ import annotations

from omega_serv.domain.http.request import HttpRequest
from omega_serv.domain.http.response import HttpResponse
from omega_serv.domain.http.status_codes import HttpStatus
from omega_serv.domain.routing.icon_registry import ICON_FILENAMES, ICON_URL_PREFIX
from omega_serv.infrastructure.icons.icon_files import read_icon_svg

_ALLOWED_METHODS = ("GET", "HEAD")
_CACHE_CONTROL = "public, max-age=86400"


def handle_icon_request(request: HttpRequest) -> HttpResponse:
    if request.method not in _ALLOWED_METHODS:
        response = HttpResponse.empty(HttpStatus.METHOD_NOT_ALLOWED)
        response.set_header("Allow", ", ".join(_ALLOWED_METHODS))
        return response

    name = request.path[len(ICON_URL_PREFIX):]
    if name not in ICON_FILENAMES:
        return HttpResponse.empty(HttpStatus.NOT_FOUND)

    body = read_icon_svg(name)
    if body is None:
        return HttpResponse.empty(HttpStatus.NOT_FOUND)

    response = HttpResponse.empty(HttpStatus.OK)
    response.set_header("Content-Type", "image/svg+xml")
    response.set_header("Cache-Control", _CACHE_CONTROL)
    if request.method == "GET":
        response.body = body
        response.set_header("Content-Length", str(len(body)))
    else:
        response.set_header("Content-Length", str(len(body)))

    return response
