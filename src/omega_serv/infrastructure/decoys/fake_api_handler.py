"""Leurre `fake_api` (plan_active_defense_omega_serv.md, §"Honeypots
V1"/Phase 5) - fixture STATIQUE et deterministe, Niveau 1 (in-process).
Simule une API minimale (`/api/v1/*`, routes de diagnostic) - reponses
JSON plausibles mais toujours fixes, jamais de traitement reel d'un
parametre ou d'un token soumis au-dela de sa capture pour le journal
(deja faite en amont par Active Defense)."""
from __future__ import annotations

import json

from omega_serv.domain.http.request import HttpRequest
from omega_serv.domain.http.response import HttpResponse
from omega_serv.domain.http.status_codes import HttpStatus


def handle_fake_api(request: HttpRequest) -> HttpResponse:
    if request.path.rstrip("/").endswith(("/health", "/status", "/diagnostic")):
        payload = {"status": "ok", "version": "1.4.2"}
    elif request.method == "POST":
        payload = {"error": "unauthorized", "message": "Jeton invalide ou expire."}
    else:
        payload = {"error": "not_found", "path": request.path}
    body = json.dumps(payload).encode("utf-8")
    status = HttpStatus.UNAUTHORIZED if request.method == "POST" else HttpStatus.OK
    response = HttpResponse.empty(status)
    response.set_header("Content-Type", "application/json")
    response.set_header("Content-Length", str(len(body)))
    response.body = body
    return response
