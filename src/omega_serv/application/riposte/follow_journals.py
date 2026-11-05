"""Un tour de suivi des journaux par le processus RIPOSTE (OMEGA-SERV_PLAN-DETAILLE_RIPOSTE.md §3.2,
lot 2) : lire les nouvelles lignes, les convertir en evenements normalises, ecarter les doublons,
memoriser la position. Aucune decision ici (lot 3).

Ordre voulu : chaque evenement est marque « vu » AVANT que la position du journal soit enregistree -
un arret brutal entre les deux fait relire quelques lignes au redemarrage, que le dedoublonnage
ecarte ; l'ordre inverse perdrait des evenements."""
from __future__ import annotations

from collections import Counter
from collections.abc import Callable, Sequence
from dataclasses import dataclass, field
from datetime import datetime

from omega_serv.domain.security.riposte.events import ObservedEvent, ParseResult
from omega_serv.ports.clock_port import ClockPort
from omega_serv.ports.log_reader_port import LogReaderPort
from omega_serv.ports.riposte_store_port import RiposteStorePort


@dataclass(frozen=True)
class JournalSource:
    name: str
    """Cle de la position en base (« waf », « security »)."""
    reader: LogReaderPort
    parse: Callable[[str], ParseResult]


@dataclass
class FollowStats:
    """Compteurs depuis le demarrage du processus (ecran Etat, `riposte status`)."""
    lines_read: int = 0
    new_events: int = 0
    duplicates: int = 0
    historical: int = 0
    """Evenements anterieurs au demarrage de RIPOSTE (premier suivi d'un journal) : ecartes."""
    rejected: Counter[str] = field(default_factory=Counter)
    last_event_at: dict[str, datetime] = field(default_factory=dict)


def follow_once(
    sources: Sequence[JournalSource], store: RiposteStorePort, clock: ClockPort, stats: FollowStats,
    not_before: datetime | None = None,
) -> list[ObservedEvent]:
    """`not_before` : un evenement plus ancien est de l'historique (premier suivi, relecture apres
    reecriture d'un vieux journal) - ni transmis ni enregistre, jamais une action sur une attaque passee."""
    now = clock.now()
    new_events: list[ObservedEvent] = []
    for source in sources:
        lines = source.reader.read_new_lines()
        stats.lines_read += len(lines)
        for line in lines:
            result = source.parse(line)
            if result.event is None:
                stats.rejected[result.rejected_reason or "unknown"] += 1
                continue
            if not_before is not None and result.event.timestamp < not_before:
                stats.historical += 1
                continue
            if not store.mark_seen(result.event.event_id, now):
                stats.duplicates += 1
                continue
            stats.new_events += 1
            stats.last_event_at[source.name] = result.event.timestamp
            new_events.append(result.event)
        position = source.reader.position
        if position is not None and position != store.get_position(source.name):
            store.save_position(source.name, position)  # jamais une ecriture par tour sans changement
    return new_events
