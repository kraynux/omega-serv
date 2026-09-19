import unittest
from datetime import datetime, timedelta, timezone

from omega_serv.infrastructure.waf.reputation_tracker import InMemoryReputationTracker


class _FakeClock:
    def __init__(self, now: datetime):
        self._now = now

    def now(self) -> datetime:
        return self._now


class TestInMemoryReputationTracker(unittest.TestCase):
    def setUp(self):
        self.now = datetime(2026, 9, 5, tzinfo=timezone.utc)
        self.clock = _FakeClock(self.now)
        self.tracker = InMemoryReputationTracker(self.clock)

    def test_no_hits_counts_zero(self):
        self.assertEqual(self.tracker.count_hits_in_window("203.0.113.1", 300), 0)

    def test_records_and_counts_hits(self):
        self.tracker.record_hit("203.0.113.1")
        self.tracker.record_hit("203.0.113.1")
        self.assertEqual(self.tracker.count_hits_in_window("203.0.113.1", 300), 2)

    def test_old_hits_fall_out_of_window(self):
        self.tracker.record_hit("203.0.113.1")
        self.clock._now = self.now + timedelta(seconds=400)
        self.assertEqual(self.tracker.count_hits_in_window("203.0.113.1", 300), 0)

    def test_separate_ips_counted_separately(self):
        self.tracker.record_hit("203.0.113.1")
        self.assertEqual(self.tracker.count_hits_in_window("203.0.113.2", 300), 0)

    def test_reset_specific_ip(self):
        self.tracker.record_hit("203.0.113.1")
        self.tracker.reset("203.0.113.1")
        self.assertEqual(self.tracker.count_hits_in_window("203.0.113.1", 300), 0)

    def test_key_is_removed_once_its_hits_all_expire(self):
        self.tracker.record_hit("203.0.113.1")
        self.clock._now = self.now + timedelta(seconds=400)
        self.assertEqual(self.tracker.count_hits_in_window("203.0.113.1", 300), 0)
        self.assertNotIn("203.0.113.1", self.tracker._hits)


class TestInMemoryReputationTrackerSweep(unittest.TestCase):
    """Retour utilisateur (audit memoire) : le vrai bug corrige ici -
    une IP qui ne frappe qu'UNE SEULE FOIS (tres courant, n'importe quel
    scan Internet massif) restait en memoire pour toujours, puisque le
    seul appelant reel enchaine toujours record_hit() puis
    count_hits_in_window() pour la MEME ip (le timestamp fraichement
    ajoute passe donc toujours le filtre, la liste n'est jamais vide a
    cet instant precis - "supprimer si vide" seul ne suffit pas)."""

    def setUp(self):
        self.now = datetime(2026, 9, 5, tzinfo=timezone.utc)
        self.clock = _FakeClock(self.now)
        self.tracker = InMemoryReputationTracker(self.clock, ttl_seconds=100.0)

    def test_a_single_old_hit_is_evicted_by_the_periodic_sweep(self):
        self.tracker.record_hit("203.0.113.1")
        self.assertIn("203.0.113.1", self.tracker._hits)

        self.clock._now = self.now + timedelta(seconds=200)
        self.tracker.record_hit("203.0.113.2")

        self.assertNotIn("203.0.113.1", self.tracker._hits)

    def test_recently_active_ip_survives_a_sweep(self):
        self.tracker.record_hit("203.0.113.1")
        self.clock._now = self.now + timedelta(seconds=65)  # depasse l'intervalle, pas le TTL
        self.tracker.record_hit("203.0.113.2")
        self.assertIn("203.0.113.1", self.tracker._hits)


if __name__ == "__main__":
    unittest.main()
