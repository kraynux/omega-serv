# Copyright (c) 2026 kraynux - kraynux@proton.me - Licence MIT (voir fichier LICENSE)
"""Lecture du journal des bans de la zone omega-synchro pour Active Defense (plan omega-connect, phase 3,
2026-11-21). Ecrivains : omega-fire (`omega-fire:manual`) et l'action fail2ban d'omega-jail (`fail2ban:<jail>`).

- Etat initial : `bans/actifs.json`, puis suivi de `bans/journal.jsonl` depuis sa position (omega-lib) ; une
  rotation ratee fait relire l'etat initial. La position du journal est notee AVANT de lire l'instantane : un
  evenement ecrit entre les deux est simplement rejoue (ban ou levee : sans effet la seconde fois).
- Relu sans redemarrage : au plus toutes les REFRESH_SECONDS, au moment d'une consultation (aucun fil).
- Jails RIPOSTE ignores (`is_riposte_origin`) : un ban qu'omega-serv a lui-meme provoque ne doit jamais faire
  remonter le score de la meme adresse (boucle, plan §10).
- Zone absente ou illisible (service hors du groupe omega-synchro) : aucune adresse connue, jamais une erreur."""
from __future__ import annotations

import ipaddress
import os
import threading
import time
from collections.abc import Callable
from datetime import datetime, timezone
from pathlib import Path

from omega_lib.infrastructure.synchro.ban_journal import (
    JournalPosition,
    read_active_bans,
    read_ban_journal,
)
from omega_lib.infrastructure.synchro.files import zone_dir
from omega_lib.synchro.constants import ACTIVE_BANS, BAN_JOURNAL, ZONE_BANS_DIR
from omega_lib.synchro.models import BanAction, BanEvent, ReadStatus
from omega_lib.synchro.policies import is_riposte_origin, parse_utc

REFRESH_SECONDS = 5.0

_Network = ipaddress.IPv4Network | ipaddress.IPv6Network


class JournalKnownBans:
    def __init__(self, zone: Path | None = None, *, monotonic: Callable[[], float] = time.monotonic,
                 now: Callable[[], datetime] | None = None) -> None:
        self._bans_dir = (zone or zone_dir()) / ZONE_BANS_DIR
        self._monotonic = monotonic
        self._now = now or (lambda: datetime.now(timezone.utc))
        self._lock = threading.Lock()
        self._next_refresh = 0.0
        self._position: JournalPosition | None = None
        self._active: dict[tuple[str, str], datetime | None] = {}
        """(reseau, origine) -> echeance (None = permanent)."""
        self._hosts: dict[str, datetime | None] = {}
        self._wide: list[tuple[_Network, datetime | None]] = []

    def is_banned(self, ip: str) -> bool:
        try:
            address = ipaddress.ip_address(ip)
        except ValueError:
            return False
        if isinstance(address, ipaddress.IPv6Address) and address.ipv4_mapped is not None:
            address = address.ipv4_mapped
        self._refresh_if_due()
        moment = self._now()
        if _alive(self._hosts.get(str(address), _ABSENT), moment):
            return True
        return any(address in network and _alive(end, moment) for network, end in self._wide)

    # ---- interne ---------------------------------------------------------------------------------

    def _refresh_if_due(self) -> None:
        if self._monotonic() < self._next_refresh or not self._lock.acquire(blocking=False):
            return
        try:
            self._next_refresh = self._monotonic() + REFRESH_SECONDS
            self._refresh()
        except Exception:  # noqa: BLE001, S110 - une lecture ratee ne doit jamais toucher une requete
            pass
        finally:
            self._lock.release()

    def _refresh(self) -> None:
        if self._position is None:
            self._load_snapshot()
        read = read_ban_journal(self._bans_dir / BAN_JOURNAL, self._position)
        if read.restarted:
            self._position = None
            self._load_snapshot()
            read = read_ban_journal(self._bans_dir / BAN_JOURNAL, self._position)
        if read.status is ReadStatus.OK:
            for event in read.events:
                self._apply(event)
            self._position = read.position
        self._rebuild()

    def _load_snapshot(self) -> None:
        # Position de fin du journal prise AVANT l'instantane : ce qui s'ecrit entre les deux est rejoue.
        try:
            info = os.stat(self._bans_dir / BAN_JOURNAL)
            start = JournalPosition(info.st_ino, info.st_size)
        except OSError:
            start = JournalPosition()  # pas encore de journal : lu depuis le debut quand il apparaitra
        snapshot = read_active_bans(self._bans_dir / ACTIVE_BANS)
        self._active = {}
        if snapshot.status is ReadStatus.OK and snapshot.value is not None:
            for entry in snapshot.value.entries:
                self._apply(entry)
        self._position = start

    def _apply(self, event: BanEvent) -> None:
        if is_riposte_origin(event.origin, event.jail):
            return
        key = (event.network, event.origin)
        if event.action is BanAction.BAN:
            self._active[key] = parse_utc(event.expires_at)
        else:
            self._active.pop(key, None)

    def _rebuild(self) -> None:
        moment = self._now()
        hosts: dict[str, datetime | None] = {}
        wide: list[tuple[_Network, datetime | None]] = []
        for (network_text, _origin), end in self._active.items():
            if not _alive(end, moment):
                continue
            network = ipaddress.ip_network(network_text, strict=False)
            if network.num_addresses == 1:
                previous = hosts.get(str(network.network_address), _ABSENT)
                hosts[str(network.network_address)] = _later(previous, end)
            else:
                wide.append((network, end))
        self._hosts, self._wide = hosts, wide


_ABSENT = datetime.min.replace(tzinfo=timezone.utc)
"""Marqueur « pas de ban » (echeance depassee depuis toujours)."""


def _alive(end: datetime | None, moment: datetime) -> bool:
    return end is None or end > moment


def _later(first: datetime | None, second: datetime | None) -> datetime | None:
    if first is None or second is None:
        return None
    return max(first, second)
