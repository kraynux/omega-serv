import unittest

from omega_serv.domain.security.waf.reputation import (
    DEFAULT_NEVER_AUTO_BLOCK,
    effective_never_auto_block,
    evaluate_escalation,
    is_exempt_from_auto_block,
    validate_never_auto_block,
)


class TestEvaluateEscalation(unittest.TestCase):
    def test_below_threshold_does_not_escalate(self):
        decision = evaluate_escalation(hit_count_in_window=2, suspicious_threshold=3)
        self.assertFalse(decision.should_escalate)

    def test_at_threshold_escalates(self):
        decision = evaluate_escalation(hit_count_in_window=3, suspicious_threshold=3)
        self.assertTrue(decision.should_escalate)

    def test_above_threshold_escalates(self):
        decision = evaluate_escalation(hit_count_in_window=10, suspicious_threshold=3)
        self.assertTrue(decision.should_escalate)

    def test_disabled_threshold_never_escalates(self):
        decision = evaluate_escalation(hit_count_in_window=999, suspicious_threshold=0)
        self.assertFalse(decision.should_escalate)


class TestNeverAutoBlockNetworks(unittest.TestCase):
    """OMEGA-SERV_PLAN-DETAILLE_SENSITIVE_PATHS.md §3.13/§3.14-a."""
    def test_defaults_cover_local_tailscale_and_lan(self):
        for ip in ("127.0.0.1", "::1", "100.64.0.1", "100.127.255.254", "fd7a:115c:a1e0::1",
                   "10.1.2.3", "172.31.0.1", "192.168.0.10", "169.254.1.1", "fc00::1", "fe80::1"):
            with self.subTest(ip=ip):
                self.assertTrue(is_exempt_from_auto_block(ip, DEFAULT_NEVER_AUTO_BLOCK))

    def test_public_addresses_are_not_exempt(self):
        for ip in ("198.51.100.7", "100.12.196.99", "100.128.0.1", "8.8.8.8", "2001:db8::1", "172.32.0.1"):
            with self.subTest(ip=ip):
                self.assertFalse(is_exempt_from_auto_block(ip, DEFAULT_NEVER_AUTO_BLOCK))

    def test_ipv4_mapped_ipv6_is_normalized(self):
        self.assertTrue(is_exempt_from_auto_block("::ffff:127.0.0.1", DEFAULT_NEVER_AUTO_BLOCK))
        self.assertFalse(is_exempt_from_auto_block("::ffff:198.51.100.7", DEFAULT_NEVER_AUTO_BLOCK))

    def test_unparseable_ip_is_not_exempt(self):
        self.assertFalse(is_exempt_from_auto_block("not-an-ip", DEFAULT_NEVER_AUTO_BLOCK))

    def test_loopback_kept_when_trusted_proxy_enabled(self):
        self.assertEqual(effective_never_auto_block(DEFAULT_NEVER_AUTO_BLOCK, True), DEFAULT_NEVER_AUTO_BLOCK)

    def test_loopback_dropped_without_trusted_proxy(self):
        effective = effective_never_auto_block(DEFAULT_NEVER_AUTO_BLOCK, False)
        self.assertFalse(is_exempt_from_auto_block("127.0.0.1", effective))
        self.assertFalse(is_exempt_from_auto_block("::1", effective))
        self.assertTrue(is_exempt_from_auto_block("100.106.10.47", effective))
        self.assertTrue(is_exempt_from_auto_block("192.168.1.20", effective))

    def test_invalid_network_reported(self):
        self.assertEqual(validate_never_auto_block(("10.0.0.0/8",)), [])
        self.assertEqual(len(validate_never_auto_block(("10.0.0.0/33", "pas-un-reseau"))), 2)


if __name__ == "__main__":
    unittest.main()
