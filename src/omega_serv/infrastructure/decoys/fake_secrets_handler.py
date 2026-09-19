"""Leurre `fake_secrets` (plan_active_defense_omega_serv.md,
§"Honeypots V1"/Phase 5) - fixture STATIQUE et deterministe, Niveau 1
(in-process). Simule des fichiers sensibles souvent scannes
(`/.env`, `/config.*`, `/backup.*`) - contenu toujours FACTICE (jamais
une vraie variable d'environnement ou un vrai secret), jamais de
lecture reelle du filesystem."""
from __future__ import annotations

from omega_serv.domain.http.request import HttpRequest
from omega_serv.domain.http.response import HttpResponse
from omega_serv.domain.http.status_codes import HttpStatus

_FAKE_ENV = (
    "APP_ENV=production\n"
    "APP_DEBUG=false\n"
    "DB_HOST=127.0.0.1\n"
    "DB_DATABASE=app\n"
    "DB_USERNAME=app\n"
    "DB_PASSWORD=change-me\n"
)


def handle_fake_secrets(request: HttpRequest) -> HttpResponse:
    """Toujours 200 avec un contenu texte factice et stable, quel que
    soit le chemin exact scanne (`.env`, `config.php.bak`, `backup.sql`...) -
    plausible mais jamais un vrai secret ni une vraie configuration."""
    body = _FAKE_ENV.encode("utf-8")
    response = HttpResponse.empty(HttpStatus.OK)
    response.set_header("Content-Type", "text/plain; charset=utf-8")
    response.set_header("Content-Length", str(len(body)))
    response.body = body
    return response
