# Copyright (c) 2026 kraynux - kraynux@proton.me - Licence MIT (voir fichier LICENSE)
"""Plan proxy natif v2, lot 6 (P6, Q5, Q7) : etat de sante des backends dans le processus de securite n° 0 du moteur
natif, pour les zones que le natif relaie.

Le natif tient la sante de ces zones (controle passif, coupe-circuit, compteurs, communs a tous ses fils). Le
processus n° 0 seul :
- lance les sondes actives et de charge de ces zones (les autres processus ne les sondent pas) - chaque resultat part
  au natif ;
- recoit `/.omega-serv-admin/` (le natif l'y aiguille, lot 3) : un etat manuel (draining, maintenance) part au natif,
  qui l'applique a tous ses fils ;
- lit l'etat des backends que le natif lui envoie environ une fois par seconde, pour repondre a l'administration
  (ecran Reverse proxy du TUI) avec l'etat reel.

Pour les zones confiees a Python, rien ne change : ce processus les sert lui-meme, avec l'etat herite de
`ProxyHealthState`. Un nom DNS designe plusieurs backends dans le natif (une adresse = un backend, decision de l'auteur
du 2026-11-13) : l'etat d'un nom est un etat manuel commun, sinon « down » seulement si toutes ses adresses le sont."""
from __future__ import annotations

from collections.abc import Callable, Sequence
from dataclasses import replace

from omega_serv.domain.routing.proxy_backend_traffic import BackendTraffic
from omega_serv.domain.routing.proxy_health import ProxyHealthState, ProxyUpstreamStatus
from omega_serv.domain.routing.proxy_zone import UpstreamTarget, upstream_key

BackendEntry = tuple[str, str, str, str]
Sender = Callable[[list[BackendEntry]], None]


class RelayedHealthState(ProxyHealthState):
    def __init__(self, send: Sender, native_zones: Callable[[], frozenset[str]]) -> None:
        super().__init__()
        self._send = send
        self._native_zones = native_zones
        self._reported: dict[str, dict[str, list[tuple[str, str]]]] = {}  # zone -> nom -> [(cle, etat)]
        self._traffic_report: dict[str, list[BackendTraffic]] = {}        # tableau de bord : zone -> mesures

    def _relayed(self, zone_key: str) -> bool:
        return zone_key in self._native_zones()

    # ------------------------------------------------------------------ vers le natif
    def record_failure(self, zone_key: str, upstream: UpstreamTarget, *, unhealthy_after: int,
                       now: float | None = None) -> None:
        super().record_failure(zone_key, upstream, unhealthy_after=unhealthy_after, now=now)
        if self._relayed(zone_key):
            self._send([(zone_key, upstream_key(upstream), "probe", "fail")])

    def record_success(self, zone_key: str, upstream: UpstreamTarget, *, healthy_after: int) -> None:
        super().record_success(zone_key, upstream, healthy_after=healthy_after)
        if self._relayed(zone_key):
            self._send([(zone_key, upstream_key(upstream), "probe", "ok")])

    def record_load_sample(self, zone_key: str, upstream: UpstreamTarget, raw_score: float, *, smoothing_samples: int,
                           now: float) -> None:
        super().record_load_sample(zone_key, upstream, raw_score, smoothing_samples=smoothing_samples, now=now)
        if self._relayed(zone_key):
            score = self.load_score_for(zone_key, upstream, max_age_seconds=float("inf"), now=now)
            if score is not None:  # Q5 : score lisse, la fraicheur est comptee par le natif a la reception
                self._send([(zone_key, upstream_key(upstream), "load", repr(float(score)))])

    def mark_draining(self, zone_key: str, target_upstream_key: str) -> None:
        super().mark_draining(zone_key, target_upstream_key)
        self._manual(zone_key, target_upstream_key, "draining")

    def mark_maintenance(self, zone_key: str, target_upstream_key: str) -> None:
        super().mark_maintenance(zone_key, target_upstream_key)
        self._manual(zone_key, target_upstream_key, "maintenance")

    def clear_manual_state(self, zone_key: str, target_upstream_key: str) -> None:
        super().clear_manual_state(zone_key, target_upstream_key)
        self._manual(zone_key, target_upstream_key, "clear")

    def _manual(self, zone_key: str, name: str, value: str) -> None:
        if self._relayed(zone_key):
            self._send([(zone_key, name, "manual", value)])

    def resend_manual_states(self) -> None:
        """Natif (re)demarre : il ne connait aucun etat manuel - ceux poses par l'administration lui sont renvoyes."""
        entries: list[tuple[str, str, str, str]] = [(zone, name, "manual", status) for zone, states in self._manual_state.items()
                   for name, status in states.items() if self._relayed(zone)]
        if entries:
            self._send(entries)

    # ------------------------------------------------------------------ depuis le natif
    def apply_report(self, states: Sequence[tuple]) -> None:
        """Entrees de `native_ipc.backend_states` : 5 champs (zone, cle, nom, etat, en cours), ou 9 avec requetes,
        502, 504 et temps moyen en microsecondes (-1 : jamais sollicite), tableau de bord du 2026-11-16."""
        reported: dict[str, dict[str, list[tuple[str, str]]]] = {}
        traffic: dict[str, list[BackendTraffic]] = {}
        for entry in states:
            zone, key, name, status, active = entry[:5]
            requests, errors_502, errors_504, avg_us = (*entry[5:9], 0, 0, 0, -1)[:4]
            reported.setdefault(zone, {}).setdefault(name, []).append((key, status))
            traffic.setdefault(zone, []).append(BackendTraffic(
                zone=zone, name=name, address=key, engine="natif", status=status, requests=requests,
                errors_502=errors_502, errors_504=errors_504, avg_ms=None if avg_us < 0 else avg_us / 1000.0,
                active=active))
        self._reported = reported
        self._traffic_report = traffic

    def relayed_traffic(self, zone_key: str) -> list[BackendTraffic] | None:
        """Mesures envoyees par le natif pour une zone qu'il relaie (une ligne par adresse) ; None pour une zone
        confiee a Python, que ce processus compte lui-meme."""
        if not self._relayed(zone_key):
            return None
        # Etat pose a la main ici (DRAINING, MAINTENANCE) : vrai tout de suite, comme status_for, sans attendre le
        # prochain etat du natif (environ 1 fois/s) - la page d'administration le montre des le clic (lot 5).
        manual = self._manual_state.get(zone_key, {})
        return [replace(row, status=manual[row.name]) if row.name in manual else row
                for row in self._traffic_report.get(zone_key, [])]

    def status_for(self, zone_key: str, upstream: UpstreamTarget) -> ProxyUpstreamStatus:
        addresses = self._reported.get(zone_key, {}).get(upstream_key(upstream)) if self._relayed(zone_key) else None
        if not addresses:
            return super().status_for(zone_key, upstream)
        manual = self._manual_state.get(zone_key, {}).get(upstream_key(upstream))
        if manual is not None:  # pose ici : vrai tout de suite, avant le prochain etat du natif
            return manual
        statuses = {status for _key, status in addresses}
        for status in ("maintenance", "draining"):
            if status in statuses:
                return status
        return "down" if statuses == {"down"} else "up"

    def backend_statuses(self, zone_key: str) -> dict[str, str] | None:
        """Etat de chaque adresse (« nom (adresse):port ») d'une zone relayee ; None pour une zone confiee."""
        if not self._relayed(zone_key) or zone_key not in self._reported:
            return None
        return {key: status for addresses in self._reported[zone_key].values() for key, status in addresses}
