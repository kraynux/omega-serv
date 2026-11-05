"""Lecture complete des journaux pour « Mesurer » (OMEGA-SERV_PLAN-DETAILLE_RIPOSTE.md §3.10) : du debut
de chaque fichier, avec le meme lecteur que le processus (lignes trop longues sautees, ligne en cours
ignoree) et les memes analyseurs. Lecture seule ; un journal absent ne donne aucun evenement."""
from __future__ import annotations

from collections.abc import Callable
from pathlib import Path

from omega_serv.domain.security.riposte.events import (
    ObservedEvent,
    ParseResult,
    parse_security_event_line,
    parse_waf_alert_line,
)
from omega_serv.infrastructure.riposte.log_follower import LogFollower


def _read_journal(path: Path, parse: Callable[[str], ParseResult]) -> list[ObservedEvent]:
    follower = LogFollower(path, None, start_at_end=False)
    events: list[ObservedEvent] = []
    while True:
        lines = follower.read_new_lines()
        if not lines:
            return events
        for line in lines:
            result = parse(line)
            if result.event is not None:
                events.append(result.event)


def read_journal_events(waf_log: Path, security_log: Path) -> list[ObservedEvent]:
    return _read_journal(waf_log, parse_waf_alert_line) + _read_journal(security_log, parse_security_event_line)
