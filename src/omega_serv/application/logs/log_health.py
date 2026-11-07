"""Collecte de la Sante des logs (2026-11-07, OMEGA-SERV_A_FAIRE_STATS_DEPUIS_OMEGA_LOG.md, lot 4) : lit ce
qu'il faut de chaque log (stat, debut et fin du fichier, jamais le fichier entier), le disque qui le porte,
les regles logrotate et les archives, puis laisse les regles de domain/logs/health.py juger.

Lecture seule, jamais de sudo. Seule ecriture possible : `apply_write_fix` (bit d'ecriture du groupe sur
un log d'omega-serv qui vous appartient, apres confirmation a l'ecran)."""
from __future__ import annotations

import os
import stat
from collections.abc import Iterable
from dataclasses import dataclass, replace
from datetime import datetime, timezone
from pathlib import Path
from typing import TYPE_CHECKING, Any

from omega_serv.application.logs.privileged_logs import read_privileged_sample
from omega_serv.domain.logs.health import (
    ORIGIN_LIBRARY,
    ORIGIN_OMEGA_SERV,
    ArchiveFacts,
    DiskFacts,
    HealthReport,
    LogFacts,
    build_health_report,
    covered_by_logrotate,
    parse_logrotate_patterns,
)
from omega_serv.domain.logs.parser import detect_log_source, extract_timestamp
from omega_serv.domain.security.file_access import plan_write_access_fix, service_can_write

if TYPE_CHECKING:
    from omega_serv.domain.config.entities import LogsConfig
    from omega_serv.domain.logs.library import LogFile
    from omega_serv.ports.file_access_port import FileAccessPort
    from omega_serv.ports.process_runner_port import ProcessRunnerPort

OWN_LOG_IDS: tuple[str, ...] = ("access", "error", "waf_alerts", "breakage", "uploads")
SAMPLE_BYTES = 64 * 1024
"""Debut et fin du fichier lus pour les dates et le format : quelques millisecondes meme pour un gros log."""
MAX_SAMPLED_LINES = 200
LOGROTATE_SOURCES: tuple[Path, ...] = (Path("/etc/logrotate.conf"), Path("/etc/logrotate.d"))


@dataclass(frozen=True)
class HealthTarget:
    path: str
    origin: str
    log_id: str | None = None


def health_targets(logs_config: LogsConfig | None, project_root: Path, library: Iterable[LogFile]) -> list[HealthTarget]:
    """Logs d'omega-serv (configuration `logs`) puis ceux de la Bibliotheque. Un log d'omega-serv aussi
    present dans la Bibliotheque n'est controle qu'une fois (comme log d'omega-serv)."""
    targets: list[HealthTarget] = []
    seen: set[str] = set()
    if logs_config is not None:
        for log_id in OWN_LOG_IDS:
            path = os.path.abspath(project_root / getattr(logs_config, log_id))
            targets.append(HealthTarget(path, ORIGIN_OMEGA_SERV, log_id))
            seen.add(path)
    for log_file in library:
        if log_file.access != "file":
            continue  # copie d'une source SSH : verifiee comme un fichier local quand elle existe
        path = os.path.abspath(log_file.path)
        if path not in seen:
            targets.append(HealthTarget(path, ORIGIN_LIBRARY))
            seen.add(path)
    return targets


def _read_samples(path: str, size: int) -> tuple[str, str]:
    """(debut, fin) du fichier, SAMPLE_BYTES octets chacun, decodes."""
    with open(path, "rb") as handle:
        head = handle.read(SAMPLE_BYTES)
        if size > SAMPLE_BYTES:
            handle.seek(max(0, size - SAMPLE_BYTES))
            tail = handle.read(SAMPLE_BYTES)
        else:
            tail = head
    return head.decode("utf-8", errors="replace"), tail.decode("utf-8", errors="replace")


def _split_samples(head: str, tail: str, size: int) -> tuple[list[str], list[str], bool]:
    """(lignes du debut, lignes de la fin, octets nuls dans la fin). Lignes coupees aux bords ecartees."""
    head_lines, tail_lines = head.splitlines(), tail.splitlines()
    if size > SAMPLE_BYTES:
        head_lines = head_lines[:-1]
        tail_lines = tail_lines[1:]
    return head_lines, tail_lines[-MAX_SAMPLED_LINES:], "\x00" in tail


def _first_timestamp(lines: list[str]) -> datetime | None:
    for line in lines:
        moment = extract_timestamp(line)
        if moment is not None:
            return moment
    return None


def _sample_facts(path: str, size: int, runner: ProcessRunnerPort | None = None) -> dict[str, Any]:
    """Dates, format et octets nuls d'apres le debut et la fin du log ; lus avec sudo si `runner`."""
    if runner is not None:
        texts = read_privileged_sample(runner, path, size, SAMPLE_BYTES)
        if texts is None:
            return {}
    else:
        try:
            texts = _read_samples(path, size)
        except OSError:
            return {}
    head, tail, nul_bytes = _split_samples(*texts, size)
    stamps = [extract_timestamp(line) for line in tail if line.strip()]
    dated = [moment for moment in stamps if moment is not None]
    sources = [detect_log_source(line).value for line in tail if line.strip()]
    return {
        "first_timestamp": _first_timestamp(head),
        "last_timestamp": dated[-1] if dated else None,
        "sampled_lines": len(stamps),
        "dated_lines": len(dated),
        "nul_bytes": nul_bytes,
        "detected_source": max(set(sources), key=sources.count) if sources else None,
    }


def _writer_facts(
    path: str, file_access: FileAccessPort | None, service_account: str | None,
) -> tuple[str | None, bool | None, int | None]:
    """(compte qui ecrit, peut-il ecrire, nouveau mode si corrigeable). Sans service installe, le serveur
    tourne sous votre compte : c'est le votre qui doit pouvoir ecrire."""
    if service_account is None or file_access is None:
        return None, os.access(path, os.W_OK), None
    account = file_access.lookup_account(service_account)
    if account is None:
        return service_account, None, None
    try:
        chain = file_access.stat_chain(Path(path))
    except OSError:
        return service_account, None, None
    verdict = service_can_write(chain, account)
    if verdict.readable:
        return service_account, True, None
    fix = plan_write_access_fix(verdict, account, file_access.current_uid())
    return service_account, False, None if fix is None else fix.new_mode


def collect_log_facts(
    target: HealthTarget, *, file_access: FileAccessPort | None, service_account: str | None,
    rotation_max_bytes: int | None, logrotate_patterns: list[str], privileged_runner: ProcessRunnerPort | None = None,
) -> LogFacts:
    path = target.path
    base = LogFacts(path=path, origin=target.origin, log_id=target.log_id)
    try:
        link = os.lstat(path)
    except OSError:
        return base
    try:
        info = os.stat(path)
    except OSError:
        return replace(base, broken_link=stat.S_ISLNK(link.st_mode))
    if not stat.S_ISREG(info.st_mode):
        return replace(base, exists=True, regular=False, device=info.st_dev)
    readable = os.access(path, os.R_OK)
    writer, writer_can_write, fix_mode = (None, None, None)
    if target.origin == ORIGIN_OMEGA_SERV:
        writer, writer_can_write, fix_mode = _writer_facts(path, file_access, service_account)
    facts = replace(
        base,
        exists=True,
        size=info.st_size,
        modified_at=datetime.fromtimestamp(info.st_mtime, tz=timezone.utc),
        mode=stat.S_IMODE(info.st_mode),
        readable=readable,
        world_writable=bool(info.st_mode & stat.S_IWOTH),
        writer=writer,
        writer_can_write=writer_can_write,
        write_fix_mode=fix_mode,
        device=info.st_dev,
        logrotate_covered=covered_by_logrotate(path, logrotate_patterns) if target.origin == ORIGIN_LIBRARY else None,
        rotation_max_bytes=rotation_max_bytes if target.origin == ORIGIN_OMEGA_SERV else None,
    )
    if readable:
        return replace(facts, **_sample_facts(path, info.st_size))
    if privileged_runner is not None:  # illisible par votre compte : constat garde, le reste lu avec sudo
        return replace(facts, **_sample_facts(path, info.st_size, privileged_runner))
    return facts


def read_logrotate_patterns(sources: tuple[Path, ...] = LOGROTATE_SOURCES) -> list[str] | None:
    """Motifs de tous les fichiers logrotate lisibles ; None si logrotate n'est pas installe."""
    files: list[Path] = []
    for source in sources:
        if source.is_dir():
            try:
                files.extend(sorted(entry for entry in source.iterdir() if entry.is_file()))
            except OSError:
                continue
        elif source.is_file():
            files.append(source)
    if not files:
        return None
    patterns: list[str] = []
    for file in files:
        try:
            patterns.extend(parse_logrotate_patterns(file.read_text(encoding="utf-8", errors="replace")))
        except OSError:
            continue
    return patterns


def _mount_point(path: str) -> str:
    current = os.path.abspath(path)
    while not os.path.ismount(current):
        parent = os.path.dirname(current)
        if parent == current:
            break
        current = parent
    return current


def collect_disk_facts(logs: list[LogFacts]) -> list[DiskFacts]:
    disks: dict[int, DiskFacts] = {}
    for facts in logs:
        if facts.device is None or facts.device in disks:
            continue
        try:
            usage = os.statvfs(facts.path)
        except OSError:
            continue
        disks[facts.device] = DiskFacts(
            device=facts.device, mount_point=_mount_point(facts.path),
            total=usage.f_blocks * usage.f_frsize, free=usage.f_bavail * usage.f_frsize,
        )
    return list(disks.values())


def archive_facts(directory: Path, archive_infos: list[dict], keep: int | None) -> ArchiveFacts:
    """`archive_infos` = `ArchiveStore.get_archive_info` de chaque archive."""
    moments = [datetime.fromisoformat(str(info["modified_at"])) for info in archive_infos]
    return ArchiveFacts(
        directory=str(directory),
        count=len(archive_infos),
        total_bytes=sum(int(info["size_bytes"]) for info in archive_infos),
        oldest=min(moments, default=None),
        newest=max(moments, default=None),
        keep=keep,
    )


def collect_log_health(
    targets: list[HealthTarget], *, file_access: FileAccessPort | None, service_account: str | None,
    rotation_max_bytes: int | None, archives: ArchiveFacts | None, now: datetime | None = None,
    logrotate_patterns: list[str] | None = None, privileged_runner: ProcessRunnerPort | None = None,
) -> HealthReport:
    patterns = read_logrotate_patterns() if logrotate_patterns is None else logrotate_patterns
    facts: list[LogFacts] = []
    real_paths: dict[str, str] = {}
    for target in targets:
        item = collect_log_facts(
            target, file_access=file_access, service_account=service_account,
            rotation_max_bytes=rotation_max_bytes, logrotate_patterns=patterns or [],
            privileged_runner=privileged_runner,
        )
        if patterns is None and item.logrotate_covered is False:
            item = replace(item, logrotate_covered=None)  # logrotate absent : rien a reprocher au log
        real = os.path.realpath(target.path)
        if item.exists and real in real_paths:
            item = replace(item, duplicate_of=real_paths[real])
        elif item.exists:
            real_paths[real] = target.path
        facts.append(item)
    return build_health_report(facts, collect_disk_facts(facts), archives, now or datetime.now(timezone.utc))


def apply_write_fix(file_access: FileAccessPort, path: str, new_mode: int) -> None:
    """Ajoute le bit d'ecriture du groupe (mode calcule par `plan_write_access_fix`). OSError remonte."""
    file_access.set_mode(Path(path), new_mode)
