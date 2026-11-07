"""Sante des logs (Gestion des logs, colonne MAINTENANCE - 2026-11-07, OMEGA-SERV_A_FAIRE_STATS_DEPUIS_
OMEGA_LOG.md, lot 4 ; retour utilisateur : « il faut que ce soit assez complet, avec une fonction d'export »).

Controle en lecture seule de chaque log connu (ceux d'omega-serv et ceux de la Bibliotheque), du disque qui
les porte et des archives. Pur domaine : les constats (`LogFacts`, `DiskFacts`, `ArchiveFacts`) sont
collectes par application/logs/log_health.py ; ici seulement les regles, sans I/O.

Un constat = un code stable + des parametres (`Finding`) : l'export JSON garde les codes (des donnees), les
textes sont produits a l'affichage dans la langue voulue (application/logs/health_presentation.py)."""
from __future__ import annotations

import fnmatch
import re
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import IntEnum


class HealthLevel(IntEnum):
    """Ordonne : le niveau d'un log est celui de son constat le plus grave."""

    OK = 0
    INFO = 1
    WARNING = 2
    PROBLEM = 3

    @property
    def code(self) -> str:
        return self.name.lower()


ORIGIN_OMEGA_SERV = "omega-serv"
ORIGIN_LIBRARY = "library"

SILENT_DAYS = 7
"""Aucune ecriture depuis plus de 7 jours : un service a peut-etre cesse d'ecrire."""
LARGE_EXTERNAL_BYTES = 100 * 1024 * 1024
"""Un log externe de plus de 100 Mo sans regle logrotate grossira sans fin."""
DISK_WARNING_PERCENT = 90.0
DISK_PROBLEM_PERCENT = 95.0
DAYS_TO_FULL_WARNING = 30.0
DAYS_TO_FULL_PROBLEM = 7.0
MIN_SAMPLED_LINES = 20
MIN_DATED_SHARE = 0.5
"""Moins de la moitie des dernieres lignes datees : periodes 24h/7j/30j et statistiques faussees."""
FUTURE_TOLERANCE = timedelta(days=1)
"""Au-dela d'un jour d'avance : horloge ou fuseau faux (les heures sans fuseau sont lues comme UTC)."""
MIN_GROWTH_SPAN = timedelta(days=1)
"""La croissance par jour n'est estimee que sur au moins un jour de lignes datees."""

EVENT_LOG_IDS = frozenset({"waf_alerts", "breakage", "uploads"})
"""Logs d'omega-serv crees au premier evenement : absents ou muets, c'est normal."""


@dataclass(frozen=True)
class Finding:
    code: str
    level: HealthLevel
    params: dict[str, str | int | float] = field(default_factory=dict)


@dataclass(frozen=True)
class LogFacts:
    """Ce que la collecte a vu d'un log (aucune valeur inventee : None = inconnu ou sans objet)."""

    path: str
    origin: str
    log_id: str | None = None
    """access, error, waf_alerts, breakage, uploads pour un log d'omega-serv ; None pour la Bibliotheque."""
    exists: bool = False
    broken_link: bool = False
    regular: bool = True
    size: int = 0
    modified_at: datetime | None = None
    mode: int | None = None
    readable: bool = True
    world_writable: bool = False
    writer: str | None = None
    """Compte qui doit ecrire ce log (compte du service, ou le votre sans service installe)."""
    writer_can_write: bool | None = None
    """None = non verifie (logs de la Bibliotheque : omega-serv n'y ecrit pas)."""
    write_fix_mode: int | None = None
    """Nouveau mode si omega-serv sait corriger les droits lui-meme (bit d'ecriture du groupe)."""
    first_timestamp: datetime | None = None
    last_timestamp: datetime | None = None
    sampled_lines: int = 0
    dated_lines: int = 0
    nul_bytes: bool = False
    detected_source: str | None = None
    device: int | None = None
    logrotate_covered: bool | None = None
    rotation_max_bytes: int | None = None
    """Seuil de rotation d'omega-serv (logs d'omega-serv, rotation active) ; None sinon."""
    duplicate_of: str | None = None


@dataclass(frozen=True)
class DiskFacts:
    device: int
    mount_point: str
    total: int
    free: int


@dataclass(frozen=True)
class ArchiveFacts:
    directory: str
    count: int = 0
    total_bytes: int = 0
    oldest: datetime | None = None
    newest: datetime | None = None
    keep: int | None = None


@dataclass
class LogHealth:
    facts: LogFacts
    findings: list[Finding]
    growth_per_day: float | None = None

    @property
    def level(self) -> HealthLevel:
        return max((finding.level for finding in self.findings), default=HealthLevel.OK)


@dataclass
class DiskHealth:
    facts: DiskFacts
    logs: list[str]
    growth_per_day: float | None
    days_to_full: float | None
    used_percent: float
    findings: list[Finding]

    @property
    def level(self) -> HealthLevel:
        return max((finding.level for finding in self.findings), default=HealthLevel.OK)


@dataclass
class ArchivesHealth:
    facts: ArchiveFacts
    findings: list[Finding]


@dataclass
class AutomationsHealth:
    """Automatisations de rotation (2026-11-07) : nombre, tache planifiee presente ou non, constats."""
    count: int
    scheduled: bool | None
    findings: list[Finding]

    @property
    def level(self) -> HealthLevel:
        return max((finding.level for finding in self.findings), default=HealthLevel.OK)


@dataclass
class HealthReport:
    generated_at: datetime
    logs: list[LogHealth]
    disks: list[DiskHealth]
    archives: ArchivesHealth | None = None
    automations: AutomationsHealth | None = None

    def counts(self) -> dict[HealthLevel, int]:
        counts = dict.fromkeys(HealthLevel, 0)
        for log in self.logs:
            counts[log.level] += 1
        return counts

    @property
    def level(self) -> HealthLevel:
        levels = [log.level for log in self.logs] + [disk.level for disk in self.disks]
        if self.automations is not None:
            levels.append(self.automations.level)
        return max(levels, default=HealthLevel.OK)


def _days(delta: timedelta) -> int:
    return int(delta.total_seconds() // 86400)


def _growth_per_day(facts: LogFacts) -> float | None:
    if facts.first_timestamp is None or facts.last_timestamp is None or facts.size <= 0:
        return None
    span = facts.last_timestamp - facts.first_timestamp
    if span < MIN_GROWTH_SPAN:
        return None
    return facts.size / (span.total_seconds() / 86400)


def evaluate_log(facts: LogFacts, now: datetime) -> LogHealth:
    findings: list[Finding] = []
    if facts.broken_link:
        return LogHealth(facts, [Finding("broken_link", HealthLevel.PROBLEM)])
    if not facts.exists:
        if facts.origin == ORIGIN_LIBRARY:
            level = HealthLevel.PROBLEM
        elif facts.log_id in EVENT_LOG_IDS:
            level = HealthLevel.INFO
        else:
            level = HealthLevel.WARNING
        code = {HealthLevel.PROBLEM: "missing_library", HealthLevel.INFO: "not_created_yet"}.get(level, "missing")
        return LogHealth(facts, [Finding(code, level)])
    if not facts.regular:
        return LogHealth(facts, [Finding("not_regular", HealthLevel.PROBLEM)])

    mode = "" if facts.mode is None else f"{facts.mode:o}"
    if not facts.readable:
        findings.append(Finding("unreadable", HealthLevel.WARNING, {"mode": mode}))
    if facts.writer_can_write is False:
        params: dict[str, str | int | float] = {"account": facts.writer or "", "mode": mode}
        if facts.write_fix_mode is not None:
            params["new_mode"] = f"{facts.write_fix_mode:o}"
        findings.append(Finding("writer_cannot_write", HealthLevel.PROBLEM, params))
    if facts.world_writable:
        findings.append(Finding("world_writable", HealthLevel.WARNING, {"mode": mode}))

    if facts.size == 0:
        findings.append(Finding("empty", HealthLevel.INFO))
    else:
        if facts.modified_at is not None and now - facts.modified_at > timedelta(days=SILENT_DAYS):
            watched = facts.origin == ORIGIN_LIBRARY or facts.log_id == "access"
            findings.append(Finding("silent", HealthLevel.WARNING if watched else HealthLevel.INFO,
                                    {"days": _days(now - facts.modified_at)}))
        if facts.nul_bytes:
            findings.append(Finding("nul_bytes", HealthLevel.WARNING))
        if facts.sampled_lines >= MIN_SAMPLED_LINES and facts.dated_lines / facts.sampled_lines < MIN_DATED_SHARE:
            findings.append(Finding("undated", HealthLevel.WARNING,
                                    {"percent": round(facts.dated_lines / facts.sampled_lines * 100)}))
        if facts.last_timestamp is not None and facts.last_timestamp > now + FUTURE_TOLERANCE:
            findings.append(Finding("future_dates", HealthLevel.WARNING,
                                    {"last": facts.last_timestamp.strftime("%Y-%m-%d %H:%M")}))
        if facts.rotation_max_bytes is not None and facts.size > facts.rotation_max_bytes:
            findings.append(Finding("over_rotation_threshold", HealthLevel.WARNING,
                                    {"size": facts.size, "threshold": facts.rotation_max_bytes}))
        if (facts.origin == ORIGIN_LIBRARY and facts.size > LARGE_EXTERNAL_BYTES
                and facts.logrotate_covered is False):
            findings.append(Finding("no_logrotate", HealthLevel.WARNING, {"size": facts.size}))
    if facts.duplicate_of is not None:
        findings.append(Finding("duplicate", HealthLevel.INFO, {"other": facts.duplicate_of}))
    return LogHealth(facts, findings, _growth_per_day(facts))


def evaluate_disks(disks: list[DiskFacts], logs: list[LogHealth]) -> list[DiskHealth]:
    result: list[DiskHealth] = []
    for disk in disks:
        on_disk = [log for log in logs if log.facts.device == disk.device and log.facts.exists]
        growths = [log.growth_per_day for log in on_disk if log.growth_per_day is not None]
        growth = sum(growths) if growths else None
        used = (disk.total - disk.free) / disk.total * 100 if disk.total else 0.0
        days_to_full = disk.free / growth if growth else None
        findings: list[Finding] = []
        if used >= DISK_PROBLEM_PERCENT:
            findings.append(Finding("disk_almost_full", HealthLevel.PROBLEM, {"percent": round(used, 1)}))
        elif used >= DISK_WARNING_PERCENT:
            findings.append(Finding("disk_almost_full", HealthLevel.WARNING, {"percent": round(used, 1)}))
        if days_to_full is not None and days_to_full < DAYS_TO_FULL_PROBLEM:
            findings.append(Finding("disk_full_soon", HealthLevel.PROBLEM, {"days": round(days_to_full, 1)}))
        elif days_to_full is not None and days_to_full < DAYS_TO_FULL_WARNING:
            findings.append(Finding("disk_full_soon", HealthLevel.WARNING, {"days": round(days_to_full, 1)}))
        result.append(DiskHealth(disk, [log.facts.path for log in on_disk], growth, days_to_full, used, findings))
    return result


def evaluate_archives(facts: ArchiveFacts) -> ArchivesHealth:
    if facts.count == 0:
        return ArchivesHealth(facts, [Finding("no_archives", HealthLevel.INFO)])
    return ArchivesHealth(facts, [])


OVERDUE_GRACE = timedelta(days=2)
"""Une automatisation due depuis plus de 2 jours ne s'execute pas : machine eteinte la nuit sans timer
systemd (cron ne rattrape pas), demon cron arrete, tache planifiee retiree."""


def evaluate_automations(automations: list[dict], scheduled: bool | None, now: datetime) -> AutomationsHealth:
    """`scheduled` : tache planifiee installee (None = inconnu, verification impossible ici)."""
    from omega_serv.domain.logs.rotation_schedule import next_run

    findings: list[Finding] = []
    if automations and scheduled is False:
        findings.append(Finding("schedule_missing", HealthLevel.WARNING, {"count": len(automations)}))
    for automation in automations:
        due = next_run(automation)
        if due is None or now - due <= OVERDUE_GRACE:
            continue
        log_id = str(automation.get("log_id", ""))
        days = _days(now - due)
        if automation.get("last_success") is False:
            findings.append(Finding("automation_failing", HealthLevel.WARNING,
                                    {"log_id": log_id, "days": days, "error": str(automation["last_result"])}))
        else:
            findings.append(Finding("automation_overdue", HealthLevel.WARNING, {"log_id": log_id, "days": days}))
    return AutomationsHealth(len(automations), scheduled, findings)


def build_health_report(
    logs: list[LogFacts], disks: list[DiskFacts], archives: ArchiveFacts | None, now: datetime,
    automations: AutomationsHealth | None = None,
) -> HealthReport:
    log_health = [evaluate_log(facts, now) for facts in logs]
    return HealthReport(
        generated_at=now,
        logs=log_health,
        disks=evaluate_disks(disks, log_health),
        archives=None if archives is None else evaluate_archives(archives),
        automations=automations,
    )


# ---- logrotate -------------------------------------------------------------

_BLOCK_RE = re.compile(r"([^{}]*)\{[^{}]*\}")


def parse_logrotate_patterns(text: str) -> list[str]:
    """Motifs de chemins des blocs `chemin... { ... }` d'un fichier de configuration logrotate. Les
    directives hors bloc (`weekly`, `include /etc/logrotate.d`...) sont ignorees : seule une ligne dont
    tous les mots sont des chemins compte."""
    without_comments = "\n".join(line.split("#", 1)[0] for line in text.splitlines())
    patterns: list[str] = []
    for match in _BLOCK_RE.finditer(without_comments):
        for line in match.group(1).splitlines():
            words = [word.strip('"') for word in line.split()]
            if words and all(word.startswith("/") for word in words):
                patterns.extend(words)
    return patterns


def covered_by_logrotate(path: str, patterns: list[str]) -> bool:
    return any(fnmatch.fnmatch(path, pattern) for pattern in patterns)
