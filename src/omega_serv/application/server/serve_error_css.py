"""Sert le CSS des pages d'erreur par defaut (401/403/404/451) comme
fichier EXTERNE reserve (retour utilisateur 2026-10-12 : "le css ne
s'applique pas sur le profil hardene") - meme patron que
`serve_dirlisting_css.py`/`serve_icon.py` (chemin reserve, verifie tout
en haut de `route_request()`, avant toute regle utilisateur :
redirections, reecritures, alias, controle d'acces - ce CSS fait partie
de l'application elle-meme, jamais du site servi. Crucial ici : une
page d'erreur peut etre justement declenchee PAR une regle d'acces qui
bloquerait sinon le CSS lui-meme si celui-ci passait par le routage
normal).

Contenu 100% statique (pas de personnalisation par theme comme le
dirlisting) - `domain/http/error_pages.py::error_pages_css()` ne fait
aucune I/O."""
from __future__ import annotations

from omega_serv.domain.http.error_pages import ERROR_CSS_URL_PREFIX, error_pages_css
from omega_serv.domain.http.request import HttpRequest
from omega_serv.domain.http.response import HttpResponse
from omega_serv.domain.http.status_codes import HttpStatus

_ALLOWED_METHODS = ("GET", "HEAD")
_CACHE_CONTROL = "public, max-age=86400"
_CSS_FILENAME = "error-pages.css"


def handle_error_css_request(request: HttpRequest) -> HttpResponse:
    if request.path[len(ERROR_CSS_URL_PREFIX):] != _CSS_FILENAME:
        return HttpResponse.empty(HttpStatus.NOT_FOUND)

    if request.method not in _ALLOWED_METHODS:
        response = HttpResponse.empty(HttpStatus.METHOD_NOT_ALLOWED)
        response.set_header("Allow", ", ".join(_ALLOWED_METHODS))
        return response

    body = error_pages_css().encode("utf-8")

    response = HttpResponse.empty(HttpStatus.OK)
    response.set_header("Content-Type", "text/css; charset=utf-8")
    response.set_header("Cache-Control", _CACHE_CONTROL)
    response.set_header("Content-Length", str(len(body)))
    if request.method == "GET":
        response.body = body

    return response
