# Copyright (c) 2026 kraynux - kraynux@proton.me - Licence MIT (voir fichier LICENSE)
import unittest

from omega_serv.domain.security.waf.rate_limit import consume_token


class TestConsumeToken(unittest.TestCase):
    def test_first_request_always_allowed(self):
        result = consume_token(None, now=1000.0, capacity=2, window_seconds=60)
        self.assertTrue(result.allowed)

    def test_exhausts_capacity_then_rejects(self):
        state = None
        now = 1000.0
        for _ in range(2):
            result = consume_token(state, now, capacity=2, window_seconds=60)
            self.assertTrue(result.allowed)
            state = result.new_state
        result = consume_token(state, now, capacity=2, window_seconds=60)
        self.assertFalse(result.allowed)
        self.assertIsNotNone(result.retry_after_seconds)

    def test_refills_over_time(self):
        state = None
        result = consume_token(state, now=1000.0, capacity=1, window_seconds=10)
        self.assertTrue(result.allowed)
        state = result.new_state
        # immediat : plus de jeton
        result = consume_token(state, now=1000.0, capacity=1, window_seconds=10)
        self.assertFalse(result.allowed)
        # 10s plus tard : jeton entierement reconstitue
        result = consume_token(state, now=1010.0, capacity=1, window_seconds=10)
        self.assertTrue(result.allowed)

    def test_never_exceeds_capacity(self):
        state = None
        result = consume_token(state, now=1000.0, capacity=3, window_seconds=10)
        state = result.new_state
        result = consume_token(state, now=100000.0, capacity=3, window_seconds=10)  # tres loin dans le temps
        self.assertLessEqual(result.new_state.tokens, 3.0)


if __name__ == "__main__":
    unittest.main()
