# Copyright (c) 2026 kraynux - kraynux@proton.me - Licence MIT (voir fichier LICENSE)
import unittest
from datetime import datetime, timedelta, timezone

from omega_serv.infrastructure.waf.rate_limit_store import InMemoryRateLimitStore


class _FakeClock:
    def __init__(self, now: datetime):
        self._now = now

    def now(self) -> datetime:
        return self._now


class TestInMemoryRateLimitStore(unittest.TestCase):
    def setUp(self):
        self.now = datetime(2026, 9, 5, tzinfo=timezone.utc)
        self.clock = _FakeClock(self.now)
        self.store = InMemoryRateLimitStore(self.clock)

    def test_allows_within_quota(self):
        result = self.store.check("203.0.113.1", requests=2, window_seconds=60)
        self.assertTrue(result.allowed)

    def test_rejects_beyond_quota(self):
        self.store.check("203.0.113.1", requests=1, window_seconds=60)
        result = self.store.check("203.0.113.1", requests=1, window_seconds=60)
        self.assertFalse(result.allowed)
        self.assertIsNotNone(result.retry_after_seconds)

    def test_separate_keys_have_separate_quotas(self):
        self.store.check("203.0.113.1", requests=1, window_seconds=60)
        result = self.store.check("203.0.113.2", requests=1, window_seconds=60)
        self.assertTrue(result.allowed)

    def test_refills_after_time_passes(self):
        self.store.check("203.0.113.1", requests=1, window_seconds=10)
        self.clock._now = self.now + timedelta(seconds=10)
        result = self.store.check("203.0.113.1", requests=1, window_seconds=10)
        self.assertTrue(result.allowed)

    def test_reset_specific_key(self):
        self.store.check("203.0.113.1", requests=1, window_seconds=60)
        self.store.reset("203.0.113.1")
        result = self.store.check("203.0.113.1", requests=1, window_seconds=60)
        self.assertTrue(result.allowed)

    def test_reset_all(self):
        self.store.check("203.0.113.1", requests=1, window_seconds=60)
        self.store.check("203.0.113.2", requests=1, window_seconds=60)
        self.store.reset()
        self.assertTrue(self.store.check("203.0.113.1", requests=1, window_seconds=60).allowed)
        self.assertTrue(self.store.check("203.0.113.2", requests=1, window_seconds=60).allowed)


class TestInMemoryRateLimitStoreSweep(unittest.TestCase):
    """Retour utilisateur (audit memoire) : `_buckets` n'etait jamais
    purge - une entree par IP unique s'accumulait pour toujours sur un
    serveur qui tourne des mois. Le balayage periodique ne doit changer
    AUCUN comportement observable (une entree stale se comporte deja
    comme une entree absente, le bucket ayant necessairement regagne sa
    capacite pleine)."""

    def setUp(self):
        self.now = datetime(2026, 9, 5, tzinfo=timezone.utc)
        self.clock = _FakeClock(self.now)
        # TTL et intervalle de balayage courts, pour tester sans devoir
        # simuler des heures d'ecart.
        self.store = InMemoryRateLimitStore(self.clock, ttl_seconds=100.0)

    def test_stale_entry_is_evicted_after_ttl_and_sweep_interval(self):
        self.store.check("203.0.113.1", requests=1, window_seconds=10)
        self.assertIn("203.0.113.1", self.store._buckets)

        # Depasse a la fois le TTL (100s) et l'intervalle de balayage
        # (60s, constante du module) en un seul bond.
        self.clock._now = self.now + timedelta(seconds=200)
        self.store.check("203.0.113.2", requests=1, window_seconds=10)  # declenche le balayage

        self.assertNotIn("203.0.113.1", self.store._buckets)

    def test_eviction_never_changes_the_allow_decision(self):
        # Meme sequence, mais on verifie que le comportement observable
        # (autorise/refuse) est identique avec ou sans l'entree balayee -
        # une IP inactive depuis longtemps redemarre de toute facon a
        # pleine capacite, balayee ou non.
        self.store.check("203.0.113.1", requests=1, window_seconds=10)
        self.clock._now = self.now + timedelta(seconds=200)
        self.store.check("203.0.113.2", requests=1, window_seconds=10)  # declenche le balayage
        self.assertNotIn("203.0.113.1", self.store._buckets)

        result = self.store.check("203.0.113.1", requests=1, window_seconds=10)
        self.assertTrue(result.allowed)

    def test_recently_active_entries_survive_a_sweep(self):
        self.clock._now = self.now
        self.store.check("203.0.113.1", requests=5, window_seconds=10)
        self.clock._now = self.now + timedelta(seconds=65)  # depasse l'intervalle, pas le TTL
        self.store.check("203.0.113.2", requests=1, window_seconds=10)  # declenche le balayage
        self.assertIn("203.0.113.1", self.store._buckets)


if __name__ == "__main__":
    unittest.main()
