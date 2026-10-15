"""Client HTTP local pour `/.omega-serv-admin/` (OMEGA-SERV_PLAN-DETAILLE_
REVERSE_PROXY.md §22, reouverture) - DISTINCT de `infrastructure/proxy/`
(le client HTTP SORTANT vers les UPSTREAMS du reverse proxy) : celui-ci
parle au PROCESSUS SERVEUR OMEGA-SERV LUI-MEME, en local (`127.0.0.1`),
exactement comme le ferait n'importe quel autre client de cette route
(§19.1/§19.3 : meme garde `trusted_proxy`, cote serveur, que le mode
natif de charge).

Injecte dans `bootstrap/container.py` (meme regime que
`simulate_request_runner` - property brute, le `None`-check et la
gestion d'erreur restent la responsabilite de l'ecran appelant) plutot
que construit directement par un ecran TUI : `interfaces.tui` ne peut
jamais importer `infrastructure` (contrat import-linter), et ce module
touche un vrai socket TCP."""
from __future__ import annotations

import asyncio
import http.client
import json


def _call_sync(port: int, method: str, path_and_query: str, *, timeout: float) -> tuple[int, dict | None]:
    conn = http.client.HTTPConnection("127.0.0.1", port, timeout=timeout)
    try:
        conn.request(method, path_and_query)
        response = conn.getresponse()
        raw = response.read()
        try:
            parsed = json.loads(raw) if raw else None
        except json.JSONDecodeError:
            parsed = None
        return response.status, parsed
    finally:
        conn.close()


async def call_admin_endpoint(
    port: int, method: str, path_and_query: str, *, timeout: float = 3.0,
) -> tuple[int, dict | None] | None:
    """`None` si la connexion elle-meme echoue (serveur eteint,
    mauvais port, refus de connexion) - DISTINCT d'un statut HTTP
    d'erreur (403/404/400), qui lui EST une reponse valide du serveur.
    L'appelant doit donc distinguer "pas de reponse du tout" de "une
    reponse qui dit non"."""
    try:
        return await asyncio.to_thread(_call_sync, port, method, path_and_query, timeout=timeout)
    except OSError:
        return None
