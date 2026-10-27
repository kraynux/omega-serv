"""Compteurs de securite partages entre workers (OMEGA-SERV_ETUDE_MODE_BOOST.md, option A) -
partie pure : disposition de la zone, hachage stable, choix du segment.

Disposition : deux tables (seaux de rate limit, files de recidive), chacune decoupee en
SEGMENTS segments independants. Une cle ne cherche sa case QUE dans son segment, protege par
le verrou du meme numero : deux cles de verrous differents ne peuvent jamais toucher la meme
case (un decoupage par verrou sur une table unique, avec adressage ouvert, le permettrait).
"""
from __future__ import annotations

import hashlib
import struct
from typing import TYPE_CHECKING

from omega_serv.core.i18n import _
from omega_serv.domain.security.waf.config import WafConfig, parse_waf_config

if TYPE_CHECKING:
    from omega_serv.domain.config.entities import OmegaServConfig

SEGMENTS = 64
MAX_PROBES = 16
"""Cases examinees au plus pour une cle (adressage ouvert lineaire, dans son segment)."""

RATE_SLOTS_PER_SEGMENT = 1024
RATE_SLOT = struct.Struct("<Qdd")  # cle (64 bits), jetons, derniere mise a jour (horodatage)

SHARED_RECIDIVE_CAPACITY = 32
"""Taille de la file d'horodatages par (IP, liste) : un seuil de recidive plus grand est refuse
a la validation de la config quand plusieurs workers sont configures."""
RECIDIVE_SLOTS_PER_SEGMENT = 128
RECIDIVE_HEADER = struct.Struct("<QQII")  # cle, empreinte de l'IP seule, position suivante, nombre
RECIDIVE_SLOT_SIZE = RECIDIVE_HEADER.size + 8 * SHARED_RECIDIVE_CAPACITY

STATS = struct.Struct("<QQ")  # cases remplacees (table pleine), cases occupees (approximatif)

RATE_TABLE_SIZE = SEGMENTS * RATE_SLOTS_PER_SEGMENT * RATE_SLOT.size
RECIDIVE_TABLE_SIZE = SEGMENTS * RECIDIVE_SLOTS_PER_SEGMENT * RECIDIVE_SLOT_SIZE
TOTAL_SIZE = STATS.size + RATE_TABLE_SIZE + RECIDIVE_TABLE_SIZE

_EMPTY = 0


def key_hash(key: str) -> int:
    """Empreinte stable sur 64 bits (jamais `hash()`, different a chaque lancement ; jamais
    32 bits : deux visiteurs finiraient par partager un compteur). 0 est reserve aux cases vides."""
    value = int.from_bytes(hashlib.blake2b(key.encode("utf-8"), digest_size=8).digest(), "little")
    return value or 1


def segment_of(hashed: int) -> int:
    return hashed % SEGMENTS


def first_slot(hashed: int, slots_per_segment: int) -> int:
    """Case de depart dans le segment : bits differents de ceux du choix du segment."""
    return (hashed >> 6) % slots_per_segment


def is_empty(hashed: int) -> bool:
    return hashed == _EMPTY


def shared_recidive_errors(waf_config: WafConfig) -> list[str]:
    """Plusieurs workers : la recidive est comptee dans une file partagee de taille fixe
    (SHARED_RECIDIVE_CAPACITY) - un seuil plus grand ne pourrait jamais etre atteint."""
    thresholds = [("options.waf.reputation.suspicious_threshold", waf_config.reputation.suspicious_threshold)]
    thresholds += [
        (f"options.waf.rules.keyword_lists[{definition.id}].escalation_threshold", definition.escalation_threshold)
        for definition in waf_config.keyword_lists
    ]
    return [
        _("{field} = {value} : avec plusieurs workers, un seuil de récidive ne peut pas dépasser {maximum}").format(
            field=field, value=value, maximum=SHARED_RECIDIVE_CAPACITY,
        )
        for field, value in thresholds
        if value > SHARED_RECIDIVE_CAPACITY
    ]


def boost_errors(config: OmegaServConfig) -> list[str]:
    """Contraintes du mode « boost » verifiables sans le disque (ecran Resistance et limites)."""
    if config.server.workers == 1 or "waf" not in config.options:
        return []
    return shared_recidive_errors(parse_waf_config(config.options["waf"].settings))
