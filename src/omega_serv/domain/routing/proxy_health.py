"""Etat de sante ET de charge des upstreams de reverse proxy (OMEGA-SERV_
PLAN-DETAILLE_REVERSE_PROXY.md §18 : Phase 6, passif + etats
operationnels ; §19 : Phase 7, score de charge reelle lisse/frais).

**Phase 6** : controle PASSIF (§18.1, base sur les echecs deja observes
par `serve_proxy()`/`serve_websocket_proxy()` lui-meme) et les quatre
etats operationnels (§18.3). Le controle ACTIF (§18.2, tache de fond
interrogeant periodiquement chaque upstream) a ete differe a la Phase 7
- c'est desormais cette meme tache de fond (`application/server/
poll_upstream_load.py`) qui alimente `record_failure`/`record_success`
EN PLUS de `record_load_sample` : un seul mecanisme de polling sert les
deux besoins (sante active ET charge), jamais deux taches paralleles
distinctes pour le meme upstream.

**Phase 7** : `record_load_sample`/`load_score_for` ajoutent un score de
charge LISSE (moyenne glissante, §19.4) et FRAIS (horodatage, §19.5 -
distinct d'un upstream mort, §18 : un upstream peut repondre sain au
sens §18 tout en ayant une charge perimee). `parse_load_score` (fonction
pure, aucune I/O) valide/borne la valeur recue en mode declaratif (§19.2)
- rejette plutot que tronque une valeur hors `[0, 100]`, jamais une
confiance aveugle dans un script tiers non controle par OMEGA-SERV.

Tout l'etat est cle par identite STABLE d'upstream (`host:port` via
`upstream_key()`), jamais par position dans un tuple (§27.1 - meme regle
que `ProxyLoadBalancerState`)."""
from __future__ import annotations

import json
from typing import Literal

from omega_serv.domain.routing.proxy_zone import UpstreamTarget, upstream_key

ProxyUpstreamStatus = Literal["up", "down", "draining", "maintenance"]


def parse_load_score(load_source: str, body: bytes) -> float | None:
    """`None` signale un corps non interpretable OU hors plage - traite
    partout en appelant comme "pas d'echantillon cette fois", jamais une
    erreur bloquante (§19.2 : repli silencieux). Mode "native" attend
    EXACTEMENT le JSON produit par `serve_proxy_load.py` (`cpu_percent`
    comme score) ; mode "declarative" tolere soit un nombre nu, soit
    `{"load_percent": ..}` (contrat minimal documente, §19.2 - OMEGA-SERV
    reste agnostique du script qui le produit)."""
    try:
        text = body.decode("utf-8").strip()
    except UnicodeDecodeError:
        return None
    value: float
    if load_source == "native":
        try:
            data = json.loads(text)
            value = float(data["cpu_percent"])
        except (json.JSONDecodeError, KeyError, TypeError, ValueError):
            return None
    else:
        try:
            value = float(text)
        except ValueError:
            try:
                data = json.loads(text)
                value = float(data["load_percent"])
            except (json.JSONDecodeError, KeyError, TypeError, ValueError):
                return None
    if not (0 <= value <= 100):
        return None
    return value


class ProxyHealthState:
    """Une seule instance par serveur (meme convention que
    `ProxyLoadBalancerState`, jamais recreee par requete). `DOWN` est
    TOUJOURS automatique, derive des echecs/succes consecutifs observes
    (`record_failure`/`record_success`) - `DRAINING`/`MAINTENANCE` sont
    TOUJOURS manuels (`mark_draining`/`mark_maintenance`, declenches par
    le TUI), jamais l'un ne declenche l'autre implicitement (§25).

    `DRAINING`/`MAINTENANCE` sont de l'etat d'execution EPHEMERE
    (§18.3, decision explicite) : jamais ecrits dans la configuration
    de zone, jamais rechargues par SIGHUP, effet immediat des l'action
    TUI, jamais survivants a un redemarrage complet (reconstruits a
    `UP` par defaut comme tout le reste de cet etat)."""

    def __init__(self) -> None:
        self._consecutive_failures: dict[str, dict[str, int]] = {}
        self._consecutive_successes: dict[str, dict[str, int]] = {}
        self._down: dict[str, set[str]] = {}
        self._manual_state: dict[str, dict[str, Literal["draining", "maintenance"]]] = {}
        self._load_samples: dict[str, dict[str, list[float]]] = {}
        self._last_load_sample_at: dict[str, dict[str, float]] = {}

    def record_failure(self, zone_key: str, upstream: UpstreamTarget, *, unhealthy_after: int) -> None:
        key = upstream_key(upstream)
        self._consecutive_successes.setdefault(zone_key, {})[key] = 0
        failures = self._consecutive_failures.setdefault(zone_key, {})
        failures[key] = failures.get(key, 0) + 1
        if failures[key] >= unhealthy_after:
            self._down.setdefault(zone_key, set()).add(key)

    def record_success(self, zone_key: str, upstream: UpstreamTarget, *, healthy_after: int) -> None:
        """Un succes remet TOUJOURS le compteur d'echecs a zero (§18.3 :
        une instabilite recente ne doit pas s'accumuler indefiniment
        derriere des succes isoles), mais ne fait sortir de `DOWN` qu'au
        bout de `healthy_after` succes CONSECUTIFS (fall/rise distincts,
        reduit le risque de flapping par rapport a un seuil unique)."""
        key = upstream_key(upstream)
        self._consecutive_failures.setdefault(zone_key, {})[key] = 0
        successes = self._consecutive_successes.setdefault(zone_key, {})
        successes[key] = successes.get(key, 0) + 1
        if successes[key] >= healthy_after:
            self._down.get(zone_key, set()).discard(key)

    def mark_draining(self, zone_key: str, target_upstream_key: str) -> None:
        self._manual_state.setdefault(zone_key, {})[target_upstream_key] = "draining"

    def mark_maintenance(self, zone_key: str, target_upstream_key: str) -> None:
        self._manual_state.setdefault(zone_key, {})[target_upstream_key] = "maintenance"

    def clear_manual_state(self, zone_key: str, target_upstream_key: str) -> None:
        """Retour a l'etat derive automatiquement (`up`/`down` selon
        l'historique reel de sante) - jamais force a `up` aveuglement,
        un upstream reellement en panne pendant la MAINTENANCE reste
        `down` une fois la MAINTENANCE levee."""
        self._manual_state.get(zone_key, {}).pop(target_upstream_key, None)

    def status_for(self, zone_key: str, upstream: UpstreamTarget) -> ProxyUpstreamStatus:
        key = upstream_key(upstream)
        manual = self._manual_state.get(zone_key, {}).get(key)
        if manual is not None:
            return manual
        return "down" if key in self._down.get(zone_key, set()) else "up"

    def is_eligible(self, zone_key: str, upstream: UpstreamTarget) -> bool:
        """`True` seulement pour `up` - `down`/`draining`/`maintenance`
        excluent tous les trois des NOUVEAUX choix (§18.3) - un tube
        WebSocket deja etabli n'est lui jamais affecte retroactivement
        (§18.3 : "les connexions/tubes deja etablis continuent
        normalement jusqu'a leur terme naturel"), cette fonction n'est
        consultee qu'au moment du CHOIX, jamais pendant un tube ouvert."""
        return self.status_for(zone_key, upstream) == "up"

    def record_load_sample(
        self, zone_key: str, upstream: UpstreamTarget, raw_score: float, *, smoothing_samples: int, now: float,
    ) -> None:
        """`raw_score` deja valide/borne par `parse_load_score` avant
        d'arriver ici - cette methode ne fait QUE lisser (moyenne
        glissante sur `smoothing_samples` echantillons, §19.4) et
        horodater (§19.5, `now` = `time.monotonic()` fourni par
        l'appelant, jamais recalcule ici - simplifie les tests)."""
        key = upstream_key(upstream)
        samples = self._load_samples.setdefault(zone_key, {}).setdefault(key, [])
        samples.append(raw_score)
        del samples[:-smoothing_samples]
        self._last_load_sample_at.setdefault(zone_key, {})[key] = now

    def load_score_for(
        self, zone_key: str, upstream: UpstreamTarget, *, max_age_seconds: float, now: float,
    ) -> float | None:
        """`None` si jamais echantillonne OU si l'echantillon le plus
        recent est perime (§19.5, distinct d'un upstream `DOWN` - §18 :
        la fraicheur des METRIQUES DE CHARGE est une notion separee de
        la SANTE de l'upstream). Sinon, moyenne glissante des derniers
        `load_smoothing_samples` echantillons."""
        key = upstream_key(upstream)
        last_sample_at = self._last_load_sample_at.get(zone_key, {}).get(key)
        if last_sample_at is None or (now - last_sample_at) > max_age_seconds:
            return None
        samples = self._load_samples.get(zone_key, {}).get(key)
        if not samples:
            return None
        return sum(samples) / len(samples)
