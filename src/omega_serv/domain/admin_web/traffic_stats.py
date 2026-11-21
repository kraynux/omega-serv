"""Statistiques de trafic du panneau web (etude OMEGA-SERV_ETUDE_MODULES_ADMIN_WEB.md, module 2 ; decisions de
l'auteur du 2026-11-17 : sans pays, aucune base externe ; 5xx comptes dans la meme lecture du journal).

Le journal d'acces (format combined des deux moteurs) est lu au fil de l'eau par la sonde de l'Historique ; chaque
ligne est ajoutee au jour courant : requetes, octets, statuts, pages (sans la query), pages en 404, IP, referents
(nom d'hote seulement), navigateurs et robots (familles), repartition horaire. Plafond de cles par tableau : au-dela,
le reste est compte dans « (autres) » (un afflux d'IP ne fait jamais grossir le fichier du jour). Rien n'est relu en
arriere : les statistiques commencent quand l'administration web demarre."""
from __future__ import annotations

import re
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any
from urllib.parse import urlsplit

LINE = re.compile(rb'^(\S+) \S+ \S+ \[[^\]]*\] "(?:[A-Z]+ )?([^ "]*)[^"]*" (\d{3}) (\d+|-) "([^"]*)" "([^"]*)"')
"""ip, chemin, statut, taille, referent, user-agent ; une ligne qui ne correspond pas compte seulement comme ligne."""
MAX_KEYS = 2000
OTHERS = "(autres)"
ROBOT_PREFIX = "robot : "
"""Cles techniques des fichiers du jour (traduites a l'affichage seulement)."""
TABLES = ("pages", "not_found", "ips", "referrers", "agents")
KEEP_DAYS = 31

_BOTS = re.compile(r"(bot|crawl|spider|slurp|curl|wget|python|go-http|java/|scan|fetch|headless|okhttp|libwww|"
                   r"httpclient|monitor|preview)", re.IGNORECASE)
_BOT_NAME = re.compile(r"([A-Za-z][\w.-]*(?:bot|Bot|crawler|spider|Spider|curl|Wget|wget))")
_BROWSERS = (("Edg/", "Edge"), ("OPR/", "Opera"), ("SamsungBrowser", "Samsung Internet"), ("Firefox/", "Firefox"),
             ("Chrome/", "Chrome"), ("Safari/", "Safari"))


_CACHE_SIZE = 4096
_families: dict[bytes, str] = {}
_hosts: dict[bytes, str] = {}
"""Memes navigateurs et memes referents d'une ligne a l'autre : chaque texte n'est analyse qu'une fois (cout par ligne
divise par plus de 3) ; caches vides des qu'ils depassent 4096 entrees."""


def _cached(cache: dict[bytes, str], raw: bytes, compute: Callable[[str], str]) -> str:
    found = cache.get(raw)
    if found is None:
        if len(cache) >= _CACHE_SIZE:
            cache.clear()
        found = cache[raw] = compute(raw.decode("utf-8", "replace"))
    return found


def agent_family(agent: str) -> str:
    """« robot : Googlebot », « Chrome », « Firefox »... ; vide ou inconnu : « autre »."""
    if not agent or agent == "-":
        return "autre"
    if _BOTS.search(agent):
        named = _BOT_NAME.search(agent)
        return ROBOT_PREFIX + (named.group(1) if named else agent.split("/", 1)[0][:40])
    for marker, name in _BROWSERS:
        if marker in agent:
            return name
    return "autre"


def referrer_host(referrer: str) -> str:
    if not referrer or referrer == "-":
        return ""
    try:
        return (urlsplit(referrer).hostname or "")[:120]
    except ValueError:
        return ""


@dataclass
class StatsDay:
    day: str
    """AAAA-MM-JJ, heure locale du processus d'administration."""
    lines: int = 0
    requests: int = 0
    sent_bytes: int = 0
    statuses: dict[str, int] = field(default_factory=dict)
    hours: list[int] = field(default_factory=lambda: [0] * 24)
    tables: dict[str, dict[str, int]] = field(default_factory=lambda: {name: {} for name in TABLES})

    def _count(self, table: str, key: str) -> None:
        values = self.tables[table]
        if key in values or len(values) < MAX_KEYS:
            values[key] = values.get(key, 0) + 1
        else:
            values[OTHERS] = values.get(OTHERS, 0) + 1

    def add(self, line: bytes, hour: int) -> int | None:
        """Compte une ligne ; rend son statut HTTP (None si la ligne est illisible)."""
        self.lines += 1
        match = LINE.match(line)
        if match is None:
            return None
        raw_ip, raw_path, status, size, raw_referrer, raw_agent = match.groups()
        code = int(status)
        self.requests += 1
        self.sent_bytes += int(size) if size.isdigit() else 0
        key = status.decode()
        self.statuses[key] = self.statuses.get(key, 0) + 1
        self.hours[hour % 24] += 1
        page = raw_path.split(b"?", 1)[0][:200].decode("utf-8", "replace") or "/"
        self._count("pages", page)
        if code == 404:
            self._count("not_found", page)
        self._count("ips", raw_ip[:64].decode("ascii", "replace"))
        host = _cached(_hosts, raw_referrer, referrer_host)
        if host:
            self._count("referrers", host)
        self._count("agents", _cached(_families, raw_agent, agent_family))
        return code

    def to_dict(self) -> dict[str, Any]:
        return {"version": 1, "day": self.day, "lines": self.lines, "requests": self.requests, "bytes": self.sent_bytes,
                "statuses": self.statuses, "hours": self.hours, "tables": self.tables}

    @classmethod
    def from_dict(cls, data: object, day: str) -> StatsDay:
        result = cls(day)
        if not isinstance(data, dict):
            return result
        for name, attribute in (("lines", "lines"), ("requests", "requests"), ("bytes", "sent_bytes")):
            value = data.get(name)
            setattr(result, attribute, value if isinstance(value, int) and value >= 0 else 0)
        statuses = data.get("statuses")
        if isinstance(statuses, dict):
            result.statuses = {str(k): v for k, v in statuses.items() if isinstance(v, int)}
        hours = data.get("hours")
        if isinstance(hours, list) and len(hours) == 24 and all(isinstance(h, int) for h in hours):
            result.hours = list(hours)
        tables = data.get("tables")
        if isinstance(tables, dict):
            for name in TABLES:
                values = tables.get(name)
                if isinstance(values, dict):
                    result.tables[name] = {str(k): v for k, v in list(values.items())[:MAX_KEYS + 1]
                                           if isinstance(v, int)}
        return result


@dataclass(frozen=True)
class StatsSummary:
    days: int
    requests: int
    bytes: int
    statuses: dict[str, int]
    hours: list[int]
    tops: dict[str, list[tuple[str, int]]]

    @property
    def errors_4xx(self) -> int:
        return sum(count for code, count in self.statuses.items() if code.startswith("4"))

    @property
    def errors_5xx(self) -> int:
        return sum(count for code, count in self.statuses.items() if code.startswith("5"))


def summarize(days: list[StatsDay], top: int = 15) -> StatsSummary:
    statuses: dict[str, int] = {}
    hours = [0] * 24
    tables: dict[str, dict[str, int]] = {name: {} for name in TABLES}
    for day in days:
        for code, count in day.statuses.items():
            statuses[code] = statuses.get(code, 0) + count
        hours = [a + b for a, b in zip(hours, day.hours, strict=True)]
        for name in TABLES:
            for key, count in day.tables[name].items():
                tables[name][key] = tables[name].get(key, 0) + count
    tops = {name: sorted(values.items(), key=lambda item: (-item[1], item[0]))[:top]
            for name, values in tables.items()}
    return StatsSummary(len(days), sum(d.requests for d in days), sum(d.sent_bytes for d in days),
                        dict(sorted(statuses.items())), hours, tops)


def mask_ip(ip: str) -> str:
    """IPv4 : dernier octet a 0 ; IPv6 : les 48 premiers bits gardes (comme Matomo et GoAccess)."""
    if ":" in ip:
        groups = ip.split(":")
        return ":".join(groups[:3]) + "::"
    parts = ip.split(".")
    return ".".join(parts[:3] + ["0"]) if len(parts) == 4 else ip
