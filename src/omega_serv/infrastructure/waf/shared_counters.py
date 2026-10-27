"""Compteurs de securite partages entre les workers du mode « boost »
(OMEGA-SERV_ETUDE_MODE_BOOST.md, option A, decision utilisateur 2026-10-26).

Sans partage, chaque worker compterait de son cote : une limite de 60/min deviendrait jusqu'a
N x 60, et l'auto-ban arriverait jusqu'a N fois plus tard. Ici, une zone `shared_memory` de
taille fixe (disposition : domain/security/waf/shared_counters.py) et 64 verrous sont crees par
le processus principal AVANT le lancement des workers, qui en heritent tels quels (fork). Seul le
principal la detruit, dans son arret propre.

Meme semantique exacte que InMemoryRateLimitStore / InMemoryReputationTracker (meme seau a
jetons, meme duree de vie des entrees, meme decompte de la recidive) - seul le stockage change.
Table pleine : la case la moins recemment utilisee du voisinage est reprise (compteur
`replacements`, jamais une erreur)."""
from __future__ import annotations

import multiprocessing
import struct
from multiprocessing import shared_memory
from typing import Any

from omega_serv.domain.security.waf.rate_limit import TokenBucketState, consume_token
from omega_serv.domain.security.waf.shared_counters import (
    MAX_PROBES,
    RATE_SLOT,
    RATE_SLOTS_PER_SEGMENT,
    RATE_TABLE_SIZE,
    RECIDIVE_HEADER,
    RECIDIVE_SLOT_SIZE,
    RECIDIVE_SLOTS_PER_SEGMENT,
    SEGMENTS,
    SHARED_RECIDIVE_CAPACITY,
    STATS,
    TOTAL_SIZE,
    first_slot,
    is_empty,
    key_hash,
    segment_of,
)
from omega_serv.ports.clock_port import ClockPort
from omega_serv.ports.rate_limit_port import RateLimitCheckResult

_TTL_SECONDS = 3600.0  # meme duree de vie que les versions en memoire
_KEY_SEPARATOR = "\x00"  # meme forme de cle que InMemoryReputationTracker
_RATE_BASE = STATS.size
_RECIDIVE_BASE = STATS.size + RATE_TABLE_SIZE
_RING = struct.Struct(f"<{SHARED_RECIDIVE_CAPACITY}d")
_TIMESTAMP = struct.Struct("<d")


def _create_segment(name: str) -> shared_memory.SharedMemory:
    """Une zone restee d'un arret brutal precedent (meme nom) est remplacee, jamais reutilisee
    telle quelle (son contenu n'est plus fiable). `track=False` (Python >= 3.13) : le principal
    gere seul la destruction ; avant 3.13, desinscription du gestionnaire de ressources."""
    try:
        stale = shared_memory.SharedMemory(name=name)
    except FileNotFoundError:
        pass
    else:
        stale.close()
        stale.unlink()
    try:
        segment = shared_memory.SharedMemory(name=name, create=True, size=TOTAL_SIZE, track=False)  # type: ignore[call-arg]
    except TypeError:
        segment = shared_memory.SharedMemory(name=name, create=True, size=TOTAL_SIZE)
        try:
            from multiprocessing import resource_tracker
            resource_tracker.unregister(segment._name, "shared_memory")  # type: ignore[attr-defined]
        except Exception:  # noqa: BLE001, S110 - au pire, un avertissement a l'arret
            pass
    buf = segment.buf
    assert buf is not None
    buf[:TOTAL_SIZE] = bytes(TOTAL_SIZE)
    return segment


class SharedCounters:
    """Zone + verrous. `create()` dans le processus principal, avant les workers."""

    def __init__(self, segment: shared_memory.SharedMemory, locks: list[Any]) -> None:
        self._segment = segment
        self._locks = locks
        buf = segment.buf
        assert buf is not None
        self.buf: memoryview = buf

    @classmethod
    def create(cls, name: str) -> SharedCounters:
        # Contexte « fork » : verrous anonymes, herites par les workers, sans le processus
        # gestionnaire de ressources que le contexte par defaut lancerait (Python 3.14 :
        # « forkserver ») et qui se compterait comme un worker de plus.
        context = multiprocessing.get_context("fork")
        return cls(_create_segment(name), [context.Lock() for _ in range(SEGMENTS)])

    def lock(self, segment: int) -> Any:
        return self._locks[segment]

    def add_replacement(self) -> None:
        replacements, occupied = STATS.unpack_from(self.buf, 0)
        STATS.pack_into(self.buf, 0, replacements + 1, occupied)  # approximatif : compteur d'observation

    def replacements(self) -> int:
        return int(STATS.unpack_from(self.buf, 0)[0])

    def rate_limit_store(self, clock: ClockPort) -> SharedRateLimitStore:
        return SharedRateLimitStore(self, clock)

    def reputation_tracker(self, clock: ClockPort) -> SharedReputationTracker:
        return SharedReputationTracker(self, clock)

    def close(self) -> None:
        self._segment.close()

    def destroy(self) -> None:
        """Processus principal uniquement, a son arret."""
        self.close()
        try:
            self._segment.unlink()
        except FileNotFoundError:
            pass


class SharedRateLimitStore:
    def __init__(self, counters: SharedCounters, clock: ClockPort) -> None:
        self._counters = counters
        self._clock = clock

    def _offset(self, segment: int, index: int) -> int:
        return _RATE_BASE + (segment * RATE_SLOTS_PER_SEGMENT + index) * RATE_SLOT.size

    def check(self, key: str, requests: int, window_seconds: int) -> RateLimitCheckResult:
        hashed = key_hash(key)
        segment = segment_of(hashed)
        buf = self._counters.buf
        with self._counters.lock(segment):
            now = self._clock.now().timestamp()
            start = first_slot(hashed, RATE_SLOTS_PER_SEGMENT)
            found: int | None = None
            free: int | None = None
            oldest_offset, oldest_time = -1, float("inf")
            state: TokenBucketState | None = None
            for probe in range(MAX_PROBES):
                offset = self._offset(segment, (start + probe) % RATE_SLOTS_PER_SEGMENT)
                slot_key, tokens, last = RATE_SLOT.unpack_from(buf, offset)
                if slot_key == hashed:
                    found, state = offset, TokenBucketState(tokens=tokens, last_refill=last)
                    break
                if is_empty(slot_key):
                    free = offset if free is None else free
                    break
                if free is None and now - last > _TTL_SECONDS:
                    free = offset
                if last < oldest_time:
                    oldest_offset, oldest_time = offset, last
            if found is None:
                if free is None:
                    free = oldest_offset
                    self._counters.add_replacement()
                found = free
            result = consume_token(state, now, capacity=requests, window_seconds=window_seconds)
            RATE_SLOT.pack_into(buf, found, hashed, result.new_state.tokens, result.new_state.last_refill)
        retry_after = None if result.retry_after_seconds is None else int(result.retry_after_seconds) + 1
        return RateLimitCheckResult(allowed=result.allowed, retry_after_seconds=retry_after)

    def reset(self, key: str | None = None) -> None:
        buf = self._counters.buf
        if key is None:
            for segment in range(SEGMENTS):
                with self._counters.lock(segment):
                    start = self._offset(segment, 0)
                    end = self._offset(segment, RATE_SLOTS_PER_SEGMENT)
                    buf[start:end] = bytes(end - start)
            return
        hashed = key_hash(key)
        segment = segment_of(hashed)
        with self._counters.lock(segment):
            start = first_slot(hashed, RATE_SLOTS_PER_SEGMENT)
            for probe in range(MAX_PROBES):
                offset = self._offset(segment, (start + probe) % RATE_SLOTS_PER_SEGMENT)
                slot_key, _tokens, _last = RATE_SLOT.unpack_from(buf, offset)
                if slot_key == hashed:
                    # Case perimee plutot que videe : la chaine de recherche reste intacte.
                    RATE_SLOT.pack_into(buf, offset, hashed, 0.0, 0.0)
                    return
                if is_empty(slot_key):
                    return


def _counter_key(ip: str, key: str) -> str:
    return ip if key == "global" else f"{key}{_KEY_SEPARATOR}{ip}"


class SharedReputationTracker:
    def __init__(self, counters: SharedCounters, clock: ClockPort) -> None:
        self._counters = counters
        self._clock = clock

    def _offset(self, segment: int, index: int) -> int:
        return _RECIDIVE_BASE + (segment * RECIDIVE_SLOTS_PER_SEGMENT + index) * RECIDIVE_SLOT_SIZE

    def _locate(self, hashed: int, segment: int, now: float, create: bool) -> int | None:
        buf = self._counters.buf
        start = first_slot(hashed, RECIDIVE_SLOTS_PER_SEGMENT)
        free: int | None = None
        oldest_offset, oldest_time = -1, float("inf")
        for probe in range(MAX_PROBES):
            offset = self._offset(segment, (start + probe) % RECIDIVE_SLOTS_PER_SEGMENT)
            slot_key, _ip, _head, count = RECIDIVE_HEADER.unpack_from(buf, offset)
            if slot_key == hashed:
                return offset
            if is_empty(slot_key):
                free = offset if free is None else free
                break
            last = max(_ring(buf, offset)[:count], default=0.0)
            if free is None and now - last > _TTL_SECONDS:
                free = offset
            if last < oldest_time:
                oldest_offset, oldest_time = offset, last
        if not create:
            return None
        if free is None:
            free = oldest_offset
            self._counters.add_replacement()
        return free

    def record_hit(self, ip: str, key: str = "global") -> None:
        hashed = key_hash(_counter_key(ip, key))
        segment = segment_of(hashed)
        buf = self._counters.buf
        with self._counters.lock(segment):
            now = self._clock.now().timestamp()
            offset = self._locate(hashed, segment, now, create=True)
            assert offset is not None
            slot_key, _ip, head, count = RECIDIVE_HEADER.unpack_from(buf, offset)
            if slot_key != hashed:  # nouvelle case (ou reprise) : file remise a zero
                head, count = 0, 0
                buf[offset + RECIDIVE_HEADER.size:offset + RECIDIVE_SLOT_SIZE] = bytes(8 * SHARED_RECIDIVE_CAPACITY)
            ring_offset = offset + RECIDIVE_HEADER.size + 8 * head
            _TIMESTAMP.pack_into(buf, ring_offset, now)
            RECIDIVE_HEADER.pack_into(
                buf, offset, hashed, key_hash(ip),
                (head + 1) % SHARED_RECIDIVE_CAPACITY, min(count + 1, SHARED_RECIDIVE_CAPACITY),
            )

    def count_hits_in_window(self, ip: str, window_seconds: int, key: str = "global") -> int:
        hashed = key_hash(_counter_key(ip, key))
        segment = segment_of(hashed)
        buf = self._counters.buf
        with self._counters.lock(segment):
            now = self._clock.now().timestamp()
            offset = self._locate(hashed, segment, now, create=False)
            if offset is None:
                return 0
            count = RECIDIVE_HEADER.unpack_from(buf, offset)[3]
            cutoff = now - window_seconds
            return sum(1 for timestamp in _ring(buf, offset)[:count] if timestamp >= cutoff)

    def reset(self, ip: str | None = None) -> None:
        buf = self._counters.buf
        ip_hash = None if ip is None else key_hash(ip)
        for segment in range(SEGMENTS):
            with self._counters.lock(segment):
                for index in range(RECIDIVE_SLOTS_PER_SEGMENT):
                    offset = self._offset(segment, index)
                    slot_key, slot_ip, _head, _count = RECIDIVE_HEADER.unpack_from(buf, offset)
                    if is_empty(slot_key) or (ip_hash is not None and slot_ip != ip_hash):
                        continue
                    # Case conservee (chaine de recherche intacte), file videe.
                    RECIDIVE_HEADER.pack_into(buf, offset, slot_key, slot_ip, 0, 0)


def _ring(buf: Any, offset: int) -> tuple[float, ...]:
    """File d'horodatages de la case, dans l'ordre des positions (l'ordre chronologique n'est
    pas necessaire : seul le nombre d'horodatages dans la fenetre compte)."""
    return _RING.unpack_from(buf, offset + RECIDIVE_HEADER.size)
