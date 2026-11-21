"""Historique du tableau de bord web : lot 7 (OMEGA-SERV_PLAN-DETAILLE_TABLEAU_DE_BORD_WEB.md §8 ; Q7 de l'auteur du
2026-11-16 : 1 h et 24 h), etendu au lot 9 (§9.5, demande de l'auteur du 2026-11-17) : plages 1 h, 3 h, 12 h, 24 h,
7 jours et 30 jours, chacune en « Moyenne » ou en « Max 1 min » (la pire minute de chaque tranche).

Un releve toutes les 10 s alimente cinq paliers de taille fixe :

| Palier | Pas | Points | Plages |
|---|---|---|---|
| s10 | 10 s | 360 | 1 h |
| m1 | 1 min | 720 | 3 h, 12 h |
| m5 | 5 min | 288 | 24 h |
| m30 | 30 min | 336 | 7 jours |
| h2 | 2 h | 360 | 30 jours |

Le palier minute est la moyenne des releves de chaque minute ; au-dessus, chaque point garde la moyenne des minutes de
sa tranche ET la plus forte d'entre elles (`<serie>_max`). Regles pures : la sonde et le fichier sont ailleurs."""
from __future__ import annotations

import math
from collections import deque
from dataclasses import dataclass
from typing import Any

SHORT_STEP = 10
MINUTE = 60
SERIES = ("cpu", "mem", "swap", "load1", "load5", "load15", "net_in", "net_out", "rps", "site_in", "site_out",
          "tcp", "sockets", "disk_read", "disk_write", "disk_used", "procs", "serv_cpu", "serv_mem", "temp",
          "battery")


@dataclass(frozen=True)
class Tier:
    name: str
    step: int
    size: int
    keeps_max: bool


TIERS = (Tier("s10", SHORT_STEP, 360, False), Tier("m1", MINUTE, 720, False), Tier("m5", 300, 288, True),
         Tier("m30", 1800, 336, True), Tier("h2", 7200, 360, True))
_TIER = {tier.name: tier for tier in TIERS}
RANGES = {"1h": ("s10", 3600), "3h": ("m1", 3 * 3600), "12h": ("m1", 12 * 3600), "24h": ("m5", 86400),
          "7j": ("m30", 7 * 86400), "30j": ("h2", 30 * 86400)}
MODES = ("avg", "max")
FORMAT = 2


@dataclass(frozen=True)
class Counters:
    """Releve brut de la sonde. Compteurs cumules (le debit se calcule entre deux releves) ou valeurs instantanees ;
    None : mesure absente sur cette machine (pas de swap, pas de capteur, pas de batterie...)."""

    at: float
    """Heure (secondes depuis l'epoque)."""
    cpu_busy: float
    cpu_total: float
    mem_percent: float
    net_recv: int
    net_sent: int
    requests: int | None
    """Lignes du journal d'acces comptees depuis le demarrage de la sonde ; None si le journal est illisible."""
    swap_percent: float | None = None
    load: tuple[float, float, float] | None = None
    site_recv: int | None = None
    """Octets recus des visiteurs par les processus du serveur (cumul, lot 9b)."""
    site_sent: int | None = None
    tcp: int | None = None
    """Connexions TCP en cours de la machine (IPv4 + IPv6)."""
    sockets: int | None = None
    disk_read: int | None = None
    disk_write: int | None = None
    disk_used: float | None = None
    """Pourcentage utilise de la partition de l'instance."""
    procs: int | None = None
    serv_cpu: float | None = None
    """Temps processeur cumule des processus d'omega-serv (secondes, ne fait que croitre)."""
    serv_mem: int | None = None
    """Memoire residente des processus d'omega-serv (octets)."""
    cpu_count: int = 1
    temp: float | None = None
    battery: float | None = None
    errors_5xx: int | None = None
    """Reponses 5xx comptees dans le journal d'acces depuis le demarrage (etude modules, module 2) ; alertes."""


def _rate(previous: float | None, current: float | None, elapsed: float) -> float | None:
    """Debit entre deux cumuls ; None si l'un manque ou si le compteur est reparti de zero (redemarrage, rotation)."""
    if previous is None or current is None or current < previous:
        return None
    return (current - previous) / elapsed


def point_between(previous: Counters, current: Counters) -> dict[str, float | None] | None:
    """Point d'historique entre deux releves ; None si l'horloge a recule ou si le releve est le meme."""
    elapsed = current.at - previous.at
    if elapsed <= 0:
        return None
    total = current.cpu_total - previous.cpu_total
    cpu = (current.cpu_busy - previous.cpu_busy) / total * 100 if total > 0 else None
    serv_cpu = _rate(previous.serv_cpu, current.serv_cpu, elapsed)
    load = current.load or (None, None, None)
    return {
        "t": round(current.at),
        "cpu": _clamp(cpu, 0, 100),
        "mem": _clamp(current.mem_percent, 0, 100),
        "swap": _clamp(current.swap_percent, 0, 100),
        "load1": _clamp(load[0], 0, math.inf),
        "load5": _clamp(load[1], 0, math.inf),
        "load15": _clamp(load[2], 0, math.inf),
        "net_in": max(0.0, (current.net_recv - previous.net_recv) / elapsed),
        "net_out": max(0.0, (current.net_sent - previous.net_sent) / elapsed),
        "rps": _rate(previous.requests, current.requests, elapsed),
        "site_in": _rate(previous.site_recv, current.site_recv, elapsed),
        "site_out": _rate(previous.site_sent, current.site_sent, elapsed),
        "tcp": _clamp(current.tcp, 0, math.inf),
        "sockets": _clamp(current.sockets, 0, math.inf),
        "disk_read": _rate(previous.disk_read, current.disk_read, elapsed),
        "disk_write": _rate(previous.disk_write, current.disk_write, elapsed),
        "disk_used": _clamp(current.disk_used, 0, 100),
        "procs": _clamp(current.procs, 0, math.inf),
        "serv_cpu": _clamp(serv_cpu / max(1, current.cpu_count) * 100 if serv_cpu is not None else None, 0, 100),
        "serv_mem": _clamp(current.serv_mem, 0, math.inf),
        "temp": _clamp(current.temp, -50, 200),
        "battery": _clamp(current.battery, 0, 100),
        "e5xx": _rate(previous.errors_5xx, current.errors_5xx, elapsed),
    }


def _clamp(value: float | None, low: float, high: float) -> float | None:
    if value is None or not math.isfinite(value):
        return None
    return min(high, max(low, float(value)))


def _round(value: float | None) -> float | None:
    """2 decimales pour les petites valeurs, entier au-dessus de 100 (debits en octets/s : le fichier reste petit)."""
    if value is None:
        return None
    return float(round(value)) if abs(value) >= 100 else round(value, 2)


def _rounded(point: dict[str, Any]) -> dict[str, Any]:
    return {"t": int(point["t"]), **{key: _round(point.get(key)) for key in SERIES}}


def _aggregate(points: list[dict[str, Any]], t: int, keep_max: bool) -> dict[str, Any]:
    """Moyenne de chaque serie (valeurs absentes ignorees) ; avec `keep_max`, la plus forte valeur aussi."""
    out: dict[str, Any] = {"t": t}
    for key in SERIES:
        values = [p[key] for p in points if p.get(key) is not None]
        out[key] = _round(sum(values) / len(values)) if values else None
        if keep_max:
            out[key + "_max"] = _round(max(values)) if values else None
    return out


class _Ring:
    """Un palier : points finis, plus la tranche en cours (les points du palier inferieur qui la composent)."""

    def __init__(self, tier: Tier) -> None:
        self.tier = tier
        self.points: deque[dict[str, Any]] = deque(maxlen=tier.size)
        self.bucket: int | None = None
        self.pending: list[dict[str, Any]] = []

    def feed(self, point: dict[str, Any], start: int) -> dict[str, Any] | None:
        """`start` : debut de l'intervalle que represente `point`. Rend le point fini quand une tranche se ferme."""
        bucket = start // self.tier.step
        closed = None
        if self.bucket is not None and bucket != self.bucket and self.pending:
            closed = _aggregate(self.pending, self.bucket * self.tier.step + self.tier.step, self.tier.keeps_max)
            self.points.append(closed)
            self.pending = []
        self.bucket = bucket
        self.pending.append(point)
        return closed

    def current(self) -> dict[str, Any] | None:
        if not self.pending or self.bucket is None:
            return None
        return _aggregate(self.pending, self.bucket * self.tier.step + self.tier.step, self.tier.keeps_max)


class HistoryRings:
    def __init__(self) -> None:
        self.rings = {tier.name: _Ring(tier) for tier in TIERS}

    @property
    def short(self) -> deque[dict[str, Any]]:
        return self.rings["s10"].points

    def add(self, point: dict[str, Any]) -> None:
        point = _rounded(point)
        short = self.rings["s10"]
        if short.points and point["t"] <= short.points[-1]["t"]:
            return  # jamais deux points au meme instant ni en arriere
        short.points.append(point)
        minute = self.rings["m1"].feed(point, point["t"] - SHORT_STEP)
        if minute is not None:
            for name in ("m5", "m30", "h2"):
                self.rings[name].feed(minute, minute["t"] - MINUTE)

    def series(self, range_name: str, now: float, mode: str = "avg") -> dict[str, Any] | None:
        """Points de la plage encore dans la fenetre, tranche en cours comprise. `max` : la plus forte minute de chaque
        tranche (paliers 5 min et plus ; en dessous, la courbe est la meme et `has_max` le dit)."""
        if range_name not in RANGES or mode not in MODES:
            return None
        name, span = RANGES[range_name]
        ring = self.rings[name]
        points = list(ring.points)
        if name == "m1":
            current = ring.current()
            points += [current] if current is not None else []
        else:
            minutes = list(ring.pending)
            open_minute = self.rings["m1"].current()
            if open_minute is not None:
                minutes.append(open_minute)
            if minutes and ring.bucket is not None:
                points.append(_aggregate(minutes, ring.bucket * ring.tier.step + ring.tier.step, True))
        oldest = now - span
        use_max = mode == "max" and ring.tier.keeps_max
        shown = [{"t": p["t"], **{key: p.get(key + "_max", p.get(key)) if use_max else p.get(key)
                                  for key in SERIES}} for p in points if p["t"] > oldest]
        return {"range": range_name, "mode": mode, "step": ring.tier.step, "has_max": ring.tier.keeps_max,
                "now": round(now), "from": round(oldest), "points": shown}

    def to_dict(self) -> dict[str, Any]:
        """Fichier a colonnes : une liste par serie, bien plus court qu'un objet par point (environ 350 Ko plein)."""
        return {"format": FORMAT,
                "tiers": {name: {"points": _columns(ring.points, ring.tier.keeps_max),
                                 "bucket": ring.bucket, "pending": _columns(ring.pending, False)}
                          for name, ring in self.rings.items()}}

    @classmethod
    def from_dict(cls, data: object, now: float) -> HistoryRings:
        """Fichier relu au demarrage : tout ce qui est invalide ou sorti de son palier est ignore. Le format 1 (lot 7 :
        1 h a 10 s et 24 h a 5 min) est repris ; le palier minute est refait depuis l'heure gardee."""
        rings = cls()
        if not isinstance(data, dict):
            return rings
        if data.get("format") == 1:
            return cls._from_format_1(data, now)
        tiers = data.get("tiers")
        if data.get("format") != FORMAT or not isinstance(tiers, dict):
            return rings
        for name, ring in rings.rings.items():
            saved = tiers.get(name)
            if not isinstance(saved, dict):
                continue
            keep = ring.tier.step * ring.tier.size
            ring.points.extend(_points(saved.get("points"), now - keep, ring.tier.keeps_max))
            bucket = saved.get("bucket")
            pending = _points(saved.get("pending"), now - ring.tier.step * 2, False)  # releves ou minutes, sans max
            if name != "s10" and isinstance(bucket, int) and not isinstance(bucket, bool) and pending:
                ring.bucket, ring.pending = bucket, pending
        return rings

    @classmethod
    def _from_format_1(cls, data: dict[str, Any], now: float) -> HistoryRings:
        rings = cls()
        for point in _rows(data.get("short"), now - 3600):
            rings.rings["s10"].points.append(point)
            rings.rings["m1"].feed(point, point["t"] - SHORT_STEP)
        for point in _rows(data.get("long"), now - 86400):
            rings.rings["m5"].points.append({**point, **{key + "_max": point[key] for key in SERIES}})
        return rings


def _columns(points: Any, keep_max: bool) -> dict[str, list[Any]]:
    keys = ["t", *SERIES, *((key + "_max" for key in SERIES) if keep_max else ())]
    return {key: [p.get(key) for p in points] for key in keys}


def _number(value: object) -> bool:
    return value is None or (isinstance(value, int | float) and not isinstance(value, bool) and math.isfinite(value))


def _points(raw: object, oldest: float, keep_max: bool) -> list[dict[str, Any]]:
    """Colonnes relues : toutes de meme longueur, sinon le palier entier est ignore ; point par point ensuite."""
    if not isinstance(raw, dict) or not isinstance(raw.get("t"), list):
        return []
    times = raw["t"]
    keys = [*SERIES, *((key + "_max" for key in SERIES) if keep_max else ())]
    columns = {key: raw.get(key, [None] * len(times)) for key in keys}
    if any(not isinstance(column, list) or len(column) != len(times) for column in columns.values()):
        return []
    points: list[dict[str, Any]] = []
    for index, t in enumerate(times):
        if not isinstance(t, int) or isinstance(t, bool) or t <= oldest:
            continue
        values = {key: column[index] for key, column in columns.items()}
        if not all(_number(v) for v in values.values()) or (points and t <= points[-1]["t"]):
            continue
        points.append({"t": t, **values})
    return points


def _rows(raw: object, oldest: float) -> list[dict[str, Any]]:
    """Points du format 1 (un objet par point, 5 series) ; les series nouvelles y sont absentes."""
    if not isinstance(raw, list):
        return []
    points: list[dict[str, Any]] = []
    for item in raw:
        if not isinstance(item, dict):
            continue
        t = item.get("t")
        if not isinstance(t, int) or isinstance(t, bool) or t <= oldest or (points and t <= points[-1]["t"]):
            continue
        values = {key: item.get(key) for key in SERIES}
        if all(_number(v) for v in values.values()):
            points.append({"t": t, **values})
    return points
