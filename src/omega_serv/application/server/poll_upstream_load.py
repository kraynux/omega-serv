"""Tache de fond (UNE par upstream dont `load_source != "none"` OU
`active_health_check_enabled=True`) qui sonde periodiquement un backend
pour sa charge ET/OU sa sante (OMEGA-SERV_PLAN-DETAILLE_REVERSE_PROXY.md
§19.1/§19.2, Phase 7 ; §18.2 - controle ACTIF, differe depuis la Phase 6,
ferme a la reouverture du §23 angle mort : un upstream SANS `load_source`
peut desormais activer cette meme sonde pour sa seule sante, sans jamais
produire de score de charge).

Un SEUL mecanisme de polling sert les deux besoins, independants l'un de
l'autre (§18.2 n'a jamais besoin de §19 ni l'inverse - un upstream peut
activer la sonde de charge, la sonde de sante active, les deux, ou
aucune) : la reponse HTTP a la sonde (connexion reussie, statut < 400)
alimente TOUJOURS `record_failure`/`record_success` (meme
`ProxyHealthState` que le controle PASSIF de la Phase 6 - un upstream
qui ne repond plus a sa sonde est aussi un upstream dont la sante se
degrade, jamais deux etats paralleles divergents) ; le CORPS de cette
meme reponse, SEULEMENT si `load_source != "none"` et interpretable
(`parse_load_score`), alimente en plus le score de charge lisse - un
upstream purement "sonde de sante" (`load_source="none"`) n'essaie
jamais de parser un score.

Discipline asyncio non negociable (§19.1, ajoutee a la relecture du
2026-10-14) : timeout COURT et DEDIE (`zone.load_poll_timeout_seconds`,
`asyncio.wait_for`), jamais une attente alignee sur le trafic reel
(`read_timeout_seconds`) - un backend qui traine sur sa sonde ne doit
jamais retarder le choix d'upstream pour le trafic reel pendant ce
poll. Boucle infinie tant que la tache n'est pas annulee par l'appelant
(`infrastructure/server/asyncio_server.py` - demarrage/arret du
serveur, §19 angle mort "polling bloquant") - `asyncio.CancelledError`
JAMAIS avale, toujours re-leve pour que l'annulation se propage
normalement."""
from __future__ import annotations

import asyncio
import contextlib
import time
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    import ssl

from omega_serv.domain.routing.proxy_health import ProxyHealthState, parse_load_score
from omega_serv.domain.routing.proxy_zone import ProxyZone, UpstreamTarget
from omega_serv.ports.http_proxy_client_port import HttpProxyClientPort, HttpProxyConnectionError

NATIVE_LOAD_PATH = "/.omega-serv-load/"


async def poll_upstream_load_forever(
    zone: ProxyZone,
    upstream: UpstreamTarget,
    proxy_client: HttpProxyClientPort,
    health_state: ProxyHealthState,
    client_ssl_context_verified: ssl.SSLContext | None,
    client_ssl_context_unverified: ssl.SSLContext | None,
) -> None:
    zone_key = zone.url_prefix
    if upstream.load_source == "native":
        path = NATIVE_LOAD_PATH
    elif upstream.load_source == "declarative":
        path = upstream.load_check_path
    else:
        # §18.2 : upstream sans load_source, sonde de sante active seule - jamais de score.
        path = upstream.active_health_check_path
    ssl_context = None
    if upstream.use_tls:
        ssl_context = client_ssl_context_verified if zone.verify_upstream_tls else client_ssl_context_unverified

    while True:
        await asyncio.sleep(zone.load_poll_interval_seconds)
        try:
            result = await asyncio.wait_for(
                proxy_client.forward_request(
                    upstream.host, upstream.port, "GET", path, (), b"",
                    zone.load_poll_timeout_seconds, zone.load_poll_timeout_seconds, ssl_context,
                ),
                timeout=zone.load_poll_timeout_seconds + 1.0,
            )
        except HttpProxyConnectionError:
            health_state.record_failure(zone_key, upstream, unhealthy_after=zone.unhealthy_after)
            continue
        except TimeoutError:
            health_state.record_failure(zone_key, upstream, unhealthy_after=zone.unhealthy_after)
            continue

        if result.status_code >= 400:
            health_state.record_failure(zone_key, upstream, unhealthy_after=zone.unhealthy_after)
            continue
        health_state.record_success(zone_key, upstream, healthy_after=zone.healthy_after)

        if upstream.load_source == "none":
            continue
        score = parse_load_score(upstream.load_source, result.body)
        if score is not None:
            health_state.record_load_sample(
                zone_key, upstream, score, smoothing_samples=zone.load_smoothing_samples,
                now=time.monotonic(),
            )


async def stop_pollers(tasks: list[asyncio.Task]) -> None:
    """Annule et attend chaque tache - jamais un simple `task.cancel()`
    sans attendre (laisserait une exception d'annulation potentiellement
    non consommee trainer), jamais non plus un `wait_closed()` sans
    limite (meme lecon que `AsyncioHttpServer.shutdown()`, §34) :
    l'annulation elle-meme n'a pas de delai de grace a respecter ici,
    ces taches ne tiennent aucune ressource cote client."""
    for task in tasks:
        task.cancel()
    for task in tasks:
        with contextlib.suppress(asyncio.CancelledError):
            await task
