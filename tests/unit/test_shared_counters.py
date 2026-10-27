"""Compteurs de securite partages du mode « boost » (OMEGA-SERV_ETUDE_MODE_BOOST.md, option A).

1. Meme comportement exact que les versions en memoire (memes sequences, memes reponses).
2. Plusieurs processus sur la meme cle : JAMAIS plus de passages que la limite au total, et la
   recidive compte exactement chaque detection - c'est la propriete qui justifie l'option A.
3. Table pleine, entrees perimees, remise a zero."""
import multiprocessing
import os
import unittest
from datetime import datetime, timedelta, timezone
from unittest import mock

from omega_serv.domain.security.waf.shared_counters import (
    MAX_PROBES,
    RATE_SLOTS_PER_SEGMENT,
    SEGMENTS,
    SHARED_RECIDIVE_CAPACITY,
    first_slot,
    key_hash,
    segment_of,
)
from omega_serv.infrastructure.waf.rate_limit_store import InMemoryRateLimitStore
from omega_serv.infrastructure.waf.reputation_tracker import InMemoryReputationTracker
from omega_serv.infrastructure.waf.shared_counters import SharedCounters


class _Clock:
    def __init__(self):
        self.current = datetime(2026, 10, 26, tzinfo=timezone.utc)

    def now(self):
        return self.current

    def advance(self, seconds):
        self.current += timedelta(seconds=seconds)


class _SharedCase(unittest.TestCase):
    def setUp(self):
        self.counters = SharedCounters.create(f"omega_serv_test_{os.getpid()}_{id(self)}")
        self.clock = _Clock()

    def tearDown(self):
        self.counters.destroy()


class TestSameBehaviourAsInMemory(_SharedCase):
    def test_rate_limit_sequence_is_identical(self):
        shared = self.counters.rate_limit_store(self.clock)
        memory = InMemoryRateLimitStore(self.clock)
        for step in range(200):
            key = f"203.0.113.{step % 3}"
            requests, window = (5, 10) if step % 2 else (3, 60)
            self.assertEqual(shared.check(key, requests, window), memory.check(key, requests, window), step)
            self.clock.advance(0.7 if step % 5 else 4)

    def test_recidive_sequence_is_identical(self):
        shared = self.counters.reputation_tracker(self.clock)
        memory = InMemoryReputationTracker(self.clock)
        for step in range(120):
            ip, key = f"198.51.100.{step % 4}", ("global", "liste-a")[step % 2]
            shared.record_hit(ip, key)
            memory.record_hit(ip, key)
            # Une fenetre par compteur, comme en production : la version en memoire efface les
            # horodatages hors fenetre a chaque decompte (melanger les fenetres fausserait la reference).
            window = 30 if key == "global" else 300
            self.assertEqual(
                shared.count_hits_in_window(ip, window, key),
                min(memory.count_hits_in_window(ip, window, key), SHARED_RECIDIVE_CAPACITY), step,
            )
            self.clock.advance(3 if step % 7 else 40)

    def test_reset_one_ip_or_everything(self):
        store = self.counters.rate_limit_store(self.clock)
        tracker = self.counters.reputation_tracker(self.clock)
        for _ in range(3):
            store.check("203.0.113.1", 3, 60)
            tracker.record_hit("203.0.113.1")
            tracker.record_hit("203.0.113.1", "liste-a")
            tracker.record_hit("203.0.113.2")
        self.assertFalse(store.check("203.0.113.1", 3, 60).allowed)
        store.reset("203.0.113.1")
        self.assertTrue(store.check("203.0.113.1", 3, 60).allowed)
        tracker.reset("203.0.113.1")
        self.assertEqual(tracker.count_hits_in_window("203.0.113.1", 60), 0)
        self.assertEqual(tracker.count_hits_in_window("203.0.113.1", 60, "liste-a"), 0)
        self.assertEqual(tracker.count_hits_in_window("203.0.113.2", 60), 3)
        tracker.reset()
        self.assertEqual(tracker.count_hits_in_window("203.0.113.2", 60), 0)


def _hammer_rate_limit(counters, key, attempts, results):
    store = counters.rate_limit_store(_Clock())
    results.put(sum(store.check(key, 50, 10**9).allowed for _ in range(attempts)))


def _hammer_recidive(counters, ip, hits):
    tracker = counters.reputation_tracker(_Clock())
    for _ in range(hits):
        tracker.record_hit(ip)


class TestSharedBetweenProcesses(_SharedCase):
    """Le cas qui justifie tout : 4 processus en parallele sur la meme cle."""

    def _run(self, target, *args):
        context = multiprocessing.get_context("fork")
        workers = [context.Process(target=target, args=(self.counters, *args)) for _ in range(4)]
        for worker in workers:
            worker.start()
        for worker in workers:
            worker.join(30)
            self.assertEqual(worker.exitcode, 0)

    def test_never_more_passes_than_the_limit_in_total(self):
        results = multiprocessing.get_context("fork").Queue()
        self._run(_hammer_rate_limit, "203.0.113.9", 200, results)
        allowed = sum(results.get(timeout=10) for _ in range(4))
        self.assertEqual(allowed, 50)  # sans partage : jusqu'a 4 x 50 = 200

    def test_recidive_counts_every_detection_exactly(self):
        self._run(_hammer_recidive, "203.0.113.7", 7)
        self.assertEqual(self.counters.reputation_tracker(self.clock).count_hits_in_window("203.0.113.7", 600), 28)


class TestTableLimits(_SharedCase):
    def setUp(self):
        super().setUp()
        # Empreintes choisies : meme segment (h % 64) ET meme case de depart ((h >> 6) % 1024),
        # au lieu d'une recherche par force brute d'environ un million de cles.
        self.keys = [f"cle-{k}" for k in range(MAX_PROBES + 1)]
        forced = {key: 5 + k * SEGMENTS * RATE_SLOTS_PER_SEGMENT for k, key in enumerate(self.keys)}
        for hashed in forced.values():
            assert segment_of(hashed) == 5 and first_slot(hashed, RATE_SLOTS_PER_SEGMENT) == 0
        patcher = mock.patch(
            "omega_serv.infrastructure.waf.shared_counters.key_hash",
            side_effect=lambda key: forced.get(key) or key_hash(key),
        )
        patcher.start()
        self.addCleanup(patcher.stop)

    def _colliding_keys(self, count):
        return self.keys[:count]

    def test_full_neighbourhood_replaces_the_least_recently_used(self):
        store = self.counters.rate_limit_store(self.clock)
        keys = self._colliding_keys(MAX_PROBES + 1)
        for key in keys[:MAX_PROBES]:
            store.check(key, 1, 3600)  # chaque cle epuise son seau
            self.clock.advance(1)
        self.assertEqual(self.counters.replacements(), 0)
        store.check(keys[MAX_PROBES], 1, 3600)
        self.assertEqual(self.counters.replacements(), 1)
        for key in keys[1:]:
            self.assertFalse(store.check(key, 1, 3600).allowed, key)  # intactes, retrouvees sans remplacement
        self.assertEqual(self.counters.replacements(), 1)
        self.assertTrue(store.check(keys[0], 1, 3600).allowed)  # la plus ancienne avait ete reprise : seau neuf
        self.assertEqual(self.counters.replacements(), 2)

    def test_stale_entries_are_reused_without_counting_a_replacement(self):
        store = self.counters.rate_limit_store(self.clock)
        keys = self._colliding_keys(MAX_PROBES + 1)
        for key in keys[:MAX_PROBES]:
            store.check(key, 1, 60)
        self.clock.advance(3601)
        store.check(keys[MAX_PROBES], 1, 60)
        self.assertEqual(self.counters.replacements(), 0)


if __name__ == "__main__":
    unittest.main()
