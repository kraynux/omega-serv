"""Route reservee `/.omega-serv-load/` (OMEGA-SERV_PLAN-DETAILLE_
REVERSE_PROXY.md §19.1 : Phase 7, mode natif) - expose les metriques
systeme DEJA calculees par `collect_system_stats()` (infrastructure/
probe/system_stats.py, meme fonction que l'ecran "Etat & Ressources" du
TUI - JAMAIS un second appel psutil) a une AUTRE instance OMEGA-SERV qui
interroge CETTE instance comme backend natif (§19.3).

Meme famille que `/.omega-serv-icons/`/`/.omega-serv-dirlisting-css/`/
`/.omega-serv-error-css/` (verifiee tout en haut de `route_request()`,
avant toute regle utilisateur) - SEULE difference : cette route expose
des metriques systeme internes, donc protegee par `trusted_proxy`
plutot qu'ouverte a tout client (§19.1, securite non negociable) - une
IP source hors des reseaux de confiance configures recoit 403, jamais
les metriques. Fail-CLOSED si `trusted_proxy` est absent/desactive ou
`trusted_networks` vide (`is_trusted_proxy(ip, [])` retourne toujours
False) - pas de repli "ouvert par defaut" possible ici."""
from __future__ import annotations

import json

from omega_serv.domain.http.request import HttpRequest
from omega_serv.domain.http.response import HttpResponse
from omega_serv.domain.http.status_codes import HttpStatus
from omega_serv.domain.security.trusted_proxy import is_trusted_proxy
from omega_serv.infrastructure.probe.system_stats import collect_system_stats

LOAD_URL_PREFIX = "/.omega-serv-load/"


def handle_load_request(request: HttpRequest, trusted_networks: list[str]) -> HttpResponse:
    if not is_trusted_proxy(request.peer_ip, trusted_networks):
        return HttpResponse.empty(HttpStatus.FORBIDDEN)

    stats = collect_system_stats()
    body = json.dumps({
        "cpu_percent": stats.get("cpu_percent", 0.0),
        "load_average_1m": stats.get("load_1", 0.0),
        "memory_percent": stats.get("mem_percent", 0.0),
    }).encode("utf-8")

    response = HttpResponse.empty(HttpStatus.OK)
    response.set_header("Content-Type", "application/json")
    response.body = body
    return response
