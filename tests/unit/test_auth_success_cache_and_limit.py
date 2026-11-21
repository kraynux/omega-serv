# Copyright (c) 2026 kraynux - kraynux@proton.me - Licence MIT (voir fichier LICENSE)
"""Authentification Basic, retour utilisateur 2026-11-20 : cache des succes (5 min renouvelees, plafond d'une heure,
LRU, purge) et limite des echecs consultee AVANT le hachage."""
import unittest
from unittest import mock

from omega_serv.domain.security.auth import authorize as authorize_module
from omega_serv.domain.security.auth.failure_limit import AuthFailureLimiter


class TestFailureLimiter(unittest.TestCase):
    def test_ip_blocked_after_threshold_until_window_end(self):
        limiter = AuthFailureLimiter(window=300, ip_max=3, user_max=100)
        for _ in range(3):
            self.assertEqual(limiter.retry_after("192.0.2.1", "bob", 10.0), 0)
            limiter.record_failure("192.0.2.1", "bob", 10.0)
        self.assertEqual(limiter.retry_after("192.0.2.1", "alice", 20.0), 290.0)
        self.assertEqual(limiter.retry_after("192.0.2.2", "bob", 20.0), 0)  # autre adresse
        self.assertEqual(limiter.retry_after("192.0.2.1", "bob", 310.0), 0)  # fenetre terminee

    def test_user_blocked_across_addresses(self):
        limiter = AuthFailureLimiter(window=300, ip_max=100, user_max=3)
        for index in range(3):
            limiter.record_failure(f"192.0.2.{index}", "bob", 0.0)
        self.assertGreater(limiter.retry_after("198.51.100.9", "bob", 1.0), 0)
        self.assertEqual(limiter.retry_after("198.51.100.9", "alice", 1.0), 0)

    def test_success_clears_the_address_only(self):
        limiter = AuthFailureLimiter(window=300, ip_max=2, user_max=2)
        limiter.record_failure("192.0.2.1", "bob", 0.0)
        limiter.record_failure("192.0.2.1", "bob", 0.0)
        limiter.record_success("192.0.2.1")
        self.assertEqual(limiter.retry_after("192.0.2.1", None, 1.0), 0)
        self.assertGreater(limiter.retry_after("192.0.2.1", "bob", 1.0), 0)

    def test_memory_is_bounded(self):
        limiter = AuthFailureLimiter(keys_max=50)
        for index in range(500):
            limiter.record_failure(f"10.0.{index // 256}.{index % 256}", None, float(index))
        self.assertLessEqual(len(limiter._counts), 50)


class TestSuccessCache(unittest.TestCase):
    def setUp(self):
        authorize_module.forget_verified_credentials()
        self.addCleanup(authorize_module.forget_verified_credentials)
        self.now = 1000.0
        patcher = mock.patch.object(authorize_module.time, "monotonic", lambda: self.now)
        patcher.start()
        self.addCleanup(patcher.stop)
        verify = mock.patch.object(authorize_module, "verify_password", return_value=True)
        self.verify = verify.start()
        self.addCleanup(verify.stop)

    def test_renewed_on_use_then_capped_at_one_hour(self):
        check = authorize_module._check_password
        self.assertTrue(check("bob", "pw", "hash"))
        self.assertEqual(self.verify.call_count, 1)
        for _ in range(11):  # 11 x 4 min : toujours renouvele, jamais reverifie
            self.now += 240
            self.assertTrue(check("bob", "pw", "hash"))
        self.assertEqual(self.verify.call_count, 1)
        self.now += 240  # 48 min + 4 = 52 min... puis au-dela d'une heure
        check("bob", "pw", "hash")
        self.now += 600
        check("bob", "pw", "hash")
        self.assertEqual(self.verify.call_count, 2)

    def test_expires_without_use(self):
        authorize_module._check_password("bob", "pw", "hash")
        self.now += 301
        authorize_module._check_password("bob", "pw", "hash")
        self.assertEqual(self.verify.call_count, 2)

    def test_lru_eviction_keeps_recent_entries(self):
        with mock.patch.object(authorize_module, "_VERIFIED_MAX", 3):
            for name in ("a", "b", "c"):
                authorize_module._check_password(name, "pw", "hash")
            authorize_module._check_password("a", "pw", "hash")  # « a » devient le plus recent
            authorize_module._check_password("d", "pw", "hash")  # evince « b »
            self.verify.reset_mock()
            authorize_module._check_password("a", "pw", "hash")
            authorize_module._check_password("b", "pw", "hash")
        self.assertEqual(self.verify.call_count, 1)

    def test_forget_on_reload(self):
        authorize_module._check_password("bob", "pw", "hash")
        authorize_module.forget_verified_credentials()
        authorize_module._check_password("bob", "pw", "hash")
        self.assertEqual(self.verify.call_count, 2)



class TestProtectionSettings(unittest.TestCase):
    def test_defaults_bounds_and_order(self):
        from omega_serv.application.auth.password_protection import protection_error_messages
        from omega_serv.domain.security.auth.password_protection import (
            PasswordProtection,
            protection_from_settings,
        )
        self.assertEqual(protection_from_settings({}), PasswordProtection())
        self.assertEqual(protection_from_settings({"password_protection": {"failures_per_ip": 3}}).failures_per_ip, 3)
        self.assertEqual(protection_error_messages({"failures_per_ip": 3, "success_ttl_seconds": 0}), [])
        self.assertEqual(len(protection_error_messages({"failures_per_ip": 0})), 1)
        self.assertEqual(len(protection_error_messages({"pending_checks_max": "dix"})), 1)
        self.assertEqual(len(protection_error_messages({"inconnu": 1})), 1)
        self.assertEqual(len(protection_error_messages({"success_ttl_seconds": 600, "success_max_age_seconds": 300})), 1)

    def test_zero_ttl_disables_the_success_cache(self):
        authorize_module.configure_success_cache(0, 3600, 4096)
        self.addCleanup(authorize_module.configure_success_cache, 300, 3600, 4096)
        with mock.patch.object(authorize_module, "verify_password", return_value=True) as verify:
            authorize_module._check_password("bob", "pw", "hash")
            authorize_module._check_password("bob", "pw", "hash")
        self.assertEqual(verify.call_count, 2)


if __name__ == "__main__":
    unittest.main()
