"""Sert le CSS de base du directory listing comme fichier EXTERNE
reserve (retour utilisateur 2026-10-10 : "la thematique CSS casse sur
les profils autres que minimal") - meme patron que `serve_icon.py`
(chemin reserve, verifie tout en haut de `route_request()`, avant toute
regle utilisateur : redirections, reecritures, alias, controle d'acces -
ce CSS fait partie de l'application elle-meme, jamais du site servi).

Le contenu est genere dynamiquement depuis le theme demande
(`domain/routing/dirlisting.py::base_css`) - aucune I/O, jamais de
lecture disque, donc aucun risque de parcours de chemin : un theme
inconnu degrade simplement vers le theme par defaut (meme comportement
qu'avant ce correctif, quand ce CSS etait genere inline avec le meme
fallback)."""
from __future__ import annotations

from omega_serv.domain.http.request import HttpRequest
from omega_serv.domain.http.response import HttpResponse
from omega_serv.domain.http.status_codes import HttpStatus
from omega_serv.domain.routing.dirlisting import CSS_URL_PREFIX, base_css

_ALLOWED_METHODS = ("GET", "HEAD")
_CACHE_CONTROL = "public, max-age=86400"


def handle_dirlisting_css_request(request: HttpRequest) -> HttpResponse:
    if request.method not in _ALLOWED_METHODS:
        response = HttpResponse.empty(HttpStatus.METHOD_NOT_ALLOWED)
        response.set_header("Allow", ", ".join(_ALLOWED_METHODS))
        return response

    theme = request.path[len(CSS_URL_PREFIX):].removesuffix(".css")
    body = base_css(theme).encode("utf-8")

    response = HttpResponse.empty(HttpStatus.OK)
    response.set_header("Content-Type", "text/css; charset=utf-8")
    response.set_header("Cache-Control", _CACHE_CONTROL)
    response.set_header("Content-Length", str(len(body)))
    if request.method == "GET":
        response.body = body

    return response
