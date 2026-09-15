# Copyright (c) 2026 kraynux - kraynux@proton.me - Licence MIT (voir fichier LICENSE)
"""Endpoint /healthz minimal (voir OMEGA-SERV_PLAN_DEVELOPPEMENT.md §9.6).

Pas seulement une liveness pour un reverse proxy : premiere instance
reelle du mecanisme d'exemption WAF concu pour des modules/services
ayant deja leurs propres regles (waf_service_policies, Phase 5) - ce
chemin rejoindra par defaut les exclusions WAF des que le moteur existe.
Volontairement minimal : aucune authentification, aucune information
sensible (version, uptime, etat interne) exposee publiquement."""
from __future__ import annotations

from omega_serv.domain.http.request import HttpRequest
from omega_serv.domain.http.response import HttpResponse
from omega_serv.domain.http.status_codes import HttpStatus

HEALTHZ_PATH = "/healthz"
_ALLOWED_METHODS = ("GET", "HEAD")
_BODY = b"OK"


def handle_healthz(request: HttpRequest) -> HttpResponse:
    if request.method not in _ALLOWED_METHODS:
        response = HttpResponse.empty(HttpStatus.METHOD_NOT_ALLOWED)
        response.set_header("Allow", ", ".join(_ALLOWED_METHODS))
        return response

    response = HttpResponse.empty(HttpStatus.OK)
    response.set_header("Content-Type", "text/plain; charset=utf-8")
    response.set_header("Content-Length", str(len(_BODY)))
    if request.method == "GET":
        response.body = _BODY
    return response
