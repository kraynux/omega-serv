import unittest

from omega_serv.domain.routing.proxy_health import ProxyHealthState, parse_load_score
from omega_serv.domain.routing.proxy_zone import UpstreamTarget

_UPSTREAM_A = UpstreamTarget(host="10.0.0.1", port=3000)
_UPSTREAM_B = UpstreamTarget(host="10.0.0.2", port=3000)


class TestProxyHealthStateAutomaticTransitions(unittest.TestCase):
    def test_new_upstream_starts_up(self):
        state = ProxyHealthState()
        self.assertEqual(state.status_for("/api/", _UPSTREAM_A), "up")
        self.assertTrue(state.is_eligible("/api/", _UPSTREAM_A))

    def test_stays_up_below_the_failure_threshold(self):
        state = ProxyHealthState()
        state.record_failure("/api/", _UPSTREAM_A, unhealthy_after=3)
        state.record_failure("/api/", _UPSTREAM_A, unhealthy_after=3)
        self.assertEqual(state.status_for("/api/", _UPSTREAM_A), "up")

    def test_goes_down_at_the_failure_threshold(self):
        state = ProxyHealthState()
        for _ in range(3):
            state.record_failure("/api/", _UPSTREAM_A, unhealthy_after=3)
        self.assertEqual(state.status_for("/api/", _UPSTREAM_A), "down")
        self.assertFalse(state.is_eligible("/api/", _UPSTREAM_A))

    def test_single_success_does_not_clear_down_below_rise_threshold(self):
        """fall/rise distincts (§18.3) : un seul succes isole ne suffit
        plus a sortir de DOWN si healthy_after > 1."""
        state = ProxyHealthState()
        for _ in range(3):
            state.record_failure("/api/", _UPSTREAM_A, unhealthy_after=3)
        state.record_success("/api/", _UPSTREAM_A, healthy_after=2)
        self.assertEqual(state.status_for("/api/", _UPSTREAM_A), "down")

    def test_clears_down_after_consecutive_successes_reach_rise_threshold(self):
        state = ProxyHealthState()
        for _ in range(3):
            state.record_failure("/api/", _UPSTREAM_A, unhealthy_after=3)
        state.record_success("/api/", _UPSTREAM_A, healthy_after=2)
        state.record_success("/api/", _UPSTREAM_A, healthy_after=2)
        self.assertEqual(state.status_for("/api/", _UPSTREAM_A), "up")

    def test_a_single_failure_after_partial_successes_does_not_accumulate_across_a_reset(self):
        """Un succes remet le compteur d'echecs a zero (§18.3) : 2
        echecs (sous le seuil de 3) suivis d'un succes, puis a nouveau 2
        echecs ne doivent PAS cumuler a 4 au total et declencher DOWN."""
        state = ProxyHealthState()
        state.record_failure("/api/", _UPSTREAM_A, unhealthy_after=3)
        state.record_failure("/api/", _UPSTREAM_A, unhealthy_after=3)
        state.record_success("/api/", _UPSTREAM_A, healthy_after=1)
        state.record_failure("/api/", _UPSTREAM_A, unhealthy_after=3)
        state.record_failure("/api/", _UPSTREAM_A, unhealthy_after=3)
        self.assertEqual(state.status_for("/api/", _UPSTREAM_A), "up")

    def test_failure_resets_the_success_counter(self):
        state = ProxyHealthState()
        for _ in range(3):
            state.record_failure("/api/", _UPSTREAM_A, unhealthy_after=3)
        state.record_success("/api/", _UPSTREAM_A, healthy_after=2)
        state.record_failure("/api/", _UPSTREAM_A, unhealthy_after=3)
        state.record_success("/api/", _UPSTREAM_A, healthy_after=2)
        # le succes isole precedent a ete efface par l'echec qui a suivi -
        # il faut de nouveau DEUX succes consecutifs pour sortir de DOWN.
        self.assertEqual(state.status_for("/api/", _UPSTREAM_A), "down")

    def test_state_is_independent_per_upstream(self):
        state = ProxyHealthState()
        for _ in range(3):
            state.record_failure("/api/", _UPSTREAM_A, unhealthy_after=3)
        self.assertEqual(state.status_for("/api/", _UPSTREAM_A), "down")
        self.assertEqual(state.status_for("/api/", _UPSTREAM_B), "up")

    def test_state_is_independent_per_zone(self):
        """§27.1 : cle par (zone_key, upstream_key) - le meme host:port
        dans deux zones differentes ne doit jamais partager d'etat."""
        state = ProxyHealthState()
        for _ in range(3):
            state.record_failure("/api/", _UPSTREAM_A, unhealthy_after=3)
        self.assertEqual(state.status_for("/api/", _UPSTREAM_A), "down")
        self.assertEqual(state.status_for("/autre/", _UPSTREAM_A), "up")


class TestProxyHealthStateManualOverrides(unittest.TestCase):
    def test_mark_draining_overrides_up(self):
        state = ProxyHealthState()
        state.mark_draining("/api/", "10.0.0.1:3000")
        self.assertEqual(state.status_for("/api/", _UPSTREAM_A), "draining")
        self.assertFalse(state.is_eligible("/api/", _UPSTREAM_A))

    def test_mark_maintenance_overrides_up(self):
        state = ProxyHealthState()
        state.mark_maintenance("/api/", "10.0.0.1:3000")
        self.assertEqual(state.status_for("/api/", _UPSTREAM_A), "maintenance")
        self.assertFalse(state.is_eligible("/api/", _UPSTREAM_A))

    def test_manual_state_overrides_automatic_down_too(self):
        """DRAINING/MAINTENANCE priment sur DOWN pour l'affichage - mais
        les echecs continuent d'etre comptabilises en arriere-plan
        (verifie par le test suivant)."""
        state = ProxyHealthState()
        for _ in range(3):
            state.record_failure("/api/", _UPSTREAM_A, unhealthy_after=3)
        state.mark_maintenance("/api/", "10.0.0.1:3000")
        self.assertEqual(state.status_for("/api/", _UPSTREAM_A), "maintenance")

    def test_clear_manual_state_reveals_the_real_underlying_health(self):
        """Lever une MAINTENANCE ne force jamais `up` aveuglement - un
        upstream reellement en panne pendant la maintenance reste DOWN
        une fois la maintenance levee (jamais un retour silencieux au
        trafic reel)."""
        state = ProxyHealthState()
        for _ in range(3):
            state.record_failure("/api/", _UPSTREAM_A, unhealthy_after=3)
        state.mark_maintenance("/api/", "10.0.0.1:3000")
        state.clear_manual_state("/api/", "10.0.0.1:3000")
        self.assertEqual(state.status_for("/api/", _UPSTREAM_A), "down")

    def test_clear_manual_state_on_a_healthy_upstream_returns_to_up(self):
        state = ProxyHealthState()
        state.mark_draining("/api/", "10.0.0.1:3000")
        state.clear_manual_state("/api/", "10.0.0.1:3000")
        self.assertEqual(state.status_for("/api/", _UPSTREAM_A), "up")

    def test_clear_manual_state_on_an_upstream_with_no_override_is_a_no_op(self):
        state = ProxyHealthState()
        state.clear_manual_state("/api/", "10.0.0.1:3000")
        self.assertEqual(state.status_for("/api/", _UPSTREAM_A), "up")

    def test_marking_draining_then_maintenance_keeps_the_latest(self):
        state = ProxyHealthState()
        state.mark_draining("/api/", "10.0.0.1:3000")
        state.mark_maintenance("/api/", "10.0.0.1:3000")
        self.assertEqual(state.status_for("/api/", _UPSTREAM_A), "maintenance")


class TestParseLoadScore(unittest.TestCase):
    def test_native_valid_json(self):
        self.assertEqual(parse_load_score("native", b'{"cpu_percent": 42.5}'), 42.5)

    def test_native_missing_key_is_none(self):
        self.assertIsNone(parse_load_score("native", b'{"memory_percent": 10}'))

    def test_native_malformed_json_is_none(self):
        self.assertIsNone(parse_load_score("native", b"not json"))

    def test_native_out_of_range_is_none(self):
        self.assertIsNone(parse_load_score("native", b'{"cpu_percent": 150}'))

    def test_declarative_bare_number(self):
        self.assertEqual(parse_load_score("declarative", b"37"), 37.0)

    def test_declarative_bare_number_with_whitespace(self):
        self.assertEqual(parse_load_score("declarative", b"  12.5  \n"), 12.5)

    def test_declarative_json_object(self):
        self.assertEqual(parse_load_score("declarative", b'{"load_percent": 88}'), 88.0)

    def test_declarative_negative_is_rejected_not_clamped(self):
        self.assertIsNone(parse_load_score("declarative", b"-1"))

    def test_declarative_over_100_is_rejected_not_clamped(self):
        self.assertIsNone(parse_load_score("declarative", b"99999"))

    def test_declarative_garbage_is_none(self):
        self.assertIsNone(parse_load_score("declarative", b"not a number either"))

    def test_boundary_values_are_accepted(self):
        self.assertEqual(parse_load_score("declarative", b"0"), 0.0)
        self.assertEqual(parse_load_score("declarative", b"100"), 100.0)


class TestProxyHealthStateLoadScore(unittest.TestCase):
    def test_no_sample_yet_is_none(self):
        state = ProxyHealthState()
        self.assertIsNone(state.load_score_for("/api/", _UPSTREAM_A, max_age_seconds=60, now=100.0))

    def test_single_sample_is_returned_as_is(self):
        state = ProxyHealthState()
        state.record_load_sample("/api/", _UPSTREAM_A, 40.0, smoothing_samples=3, now=100.0)
        self.assertEqual(state.load_score_for("/api/", _UPSTREAM_A, max_age_seconds=60, now=100.0), 40.0)

    def test_smoothing_averages_recent_samples(self):
        state = ProxyHealthState()
        state.record_load_sample("/api/", _UPSTREAM_A, 10.0, smoothing_samples=3, now=100.0)
        state.record_load_sample("/api/", _UPSTREAM_A, 20.0, smoothing_samples=3, now=101.0)
        state.record_load_sample("/api/", _UPSTREAM_A, 30.0, smoothing_samples=3, now=102.0)
        self.assertEqual(state.load_score_for("/api/", _UPSTREAM_A, max_age_seconds=60, now=102.0), 20.0)

    def test_smoothing_window_drops_oldest_sample_beyond_the_limit(self):
        state = ProxyHealthState()
        state.record_load_sample("/api/", _UPSTREAM_A, 0.0, smoothing_samples=2, now=100.0)
        state.record_load_sample("/api/", _UPSTREAM_A, 10.0, smoothing_samples=2, now=101.0)
        state.record_load_sample("/api/", _UPSTREAM_A, 20.0, smoothing_samples=2, now=102.0)
        # fenetre de 2 : seuls 10.0 et 20.0 comptent, 0.0 est sorti de la fenetre.
        self.assertEqual(state.load_score_for("/api/", _UPSTREAM_A, max_age_seconds=60, now=102.0), 15.0)

    def test_stale_sample_returns_none(self):
        state = ProxyHealthState()
        state.record_load_sample("/api/", _UPSTREAM_A, 40.0, smoothing_samples=3, now=100.0)
        self.assertIsNone(state.load_score_for("/api/", _UPSTREAM_A, max_age_seconds=10, now=200.0))

    def test_sample_exactly_at_the_age_boundary_is_still_fresh(self):
        state = ProxyHealthState()
        state.record_load_sample("/api/", _UPSTREAM_A, 40.0, smoothing_samples=3, now=100.0)
        self.assertEqual(state.load_score_for("/api/", _UPSTREAM_A, max_age_seconds=10, now=110.0), 40.0)

    def test_load_score_is_independent_per_upstream_and_zone(self):
        state = ProxyHealthState()
        state.record_load_sample("/api/", _UPSTREAM_A, 40.0, smoothing_samples=3, now=100.0)
        self.assertIsNone(state.load_score_for("/api/", _UPSTREAM_B, max_age_seconds=60, now=100.0))
        self.assertIsNone(state.load_score_for("/autre/", _UPSTREAM_A, max_age_seconds=60, now=100.0))


if __name__ == "__main__":
    unittest.main()
