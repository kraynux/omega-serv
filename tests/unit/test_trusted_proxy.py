import unittest
from typing import ClassVar

from omega_serv.domain.http.headers import HttpHeaders
from omega_serv.domain.security.trusted_proxy import (
    is_trusted_proxy,
    normalize_ip,
    resolve_client_ip,
)


class TestNormalizeIp(unittest.TestCase):
    def test_plain_ipv4_unchanged(self):
        self.assertEqual(normalize_ip("203.0.113.10"), "203.0.113.10")

    def test_ipv4_mapped_ipv6_normalized(self):
        self.assertEqual(normalize_ip("::ffff:203.0.113.10"), "203.0.113.10")

    def test_plain_ipv6_unchanged(self):
        self.assertEqual(normalize_ip("2001:db8::1"), "2001:db8::1")

    def test_invalid_ip_returned_as_is(self):
        self.assertEqual(normalize_ip("not-an-ip"), "not-an-ip")


class TestIsTrustedProxy(unittest.TestCase):
    def test_ip_in_trusted_network(self):
        self.assertTrue(is_trusted_proxy("127.0.0.1", ["127.0.0.1/32"]))

    def test_ip_not_in_any_network(self):
        self.assertFalse(is_trusted_proxy("203.0.113.10", ["127.0.0.1/32"]))

    def test_ipv4_mapped_ipv6_bypass_is_prevented(self):
        self.assertFalse(is_trusted_proxy("::ffff:203.0.113.10", ["127.0.0.1/32"]))
        self.assertTrue(is_trusted_proxy("::ffff:127.0.0.1", ["127.0.0.1/32"]))

    def test_invalid_network_string_is_ignored_not_crashed(self):
        self.assertFalse(is_trusted_proxy("127.0.0.1", ["not-a-network"]))


class TestResolveClientIp(unittest.TestCase):
    def test_untrusted_peer_ip_returned_verbatim(self):
        headers = HttpHeaders.from_pairs([("X-Forwarded-For", "9.9.9.9")])
        result = resolve_client_ip("203.0.113.10", headers, trusted_networks=["127.0.0.1/32"], header_preference=["X-Forwarded-For"])
        self.assertEqual(result, "203.0.113.10")  # jamais confiance en l'en-tete d'un pair non fiable

    def test_trusted_peer_uses_x_forwarded_for(self):
        headers = HttpHeaders.from_pairs([("X-Forwarded-For", "9.9.9.9, 127.0.0.1")])
        result = resolve_client_ip("127.0.0.1", headers, trusted_networks=["127.0.0.1/32"], header_preference=["X-Forwarded-For"])
        self.assertEqual(result, "9.9.9.9")

    def test_trusted_peer_uses_forwarded_header(self):
        headers = HttpHeaders.from_pairs([("Forwarded", 'for="9.9.9.9";proto=https')])
        result = resolve_client_ip("127.0.0.1", headers, trusted_networks=["127.0.0.1/32"], header_preference=["Forwarded"])
        self.assertEqual(result, "9.9.9.9")

    def test_forwarded_header_ipv6_bracket_form(self):
        headers = HttpHeaders.from_pairs([("Forwarded", 'for="[2001:db8::1]:1234"')])
        result = resolve_client_ip("127.0.0.1", headers, trusted_networks=["127.0.0.1/32"], header_preference=["Forwarded"])
        self.assertEqual(result, "2001:db8::1")

    def test_no_header_present_falls_back_to_peer(self):
        headers = HttpHeaders.from_pairs([])
        result = resolve_client_ip("127.0.0.1", headers, trusted_networks=["127.0.0.1/32"], header_preference=["X-Forwarded-For"])
        self.assertEqual(result, "127.0.0.1")


class TestRightmostUntrustedResolution(unittest.TestCase):
    """OMEGA-SERV_PLAN-DETAILLE_SENSITIVE_PATHS.md §3.14-b (Q11) : la valeur
    la plus a gauche est choisie par le client - jamais retenue si une
    adresse non fiable se trouve a sa droite."""
    _TRUSTED: ClassVar[list[str]] = ["127.0.0.1/32", "::1/128"]

    def _resolve(self, header: str, value: str) -> str:
        headers = HttpHeaders.from_pairs([(header, value)])
        return resolve_client_ip("127.0.0.1", headers, trusted_networks=self._TRUSTED, header_preference=[header])

    def test_spoofed_loopback_on_the_left_is_ignored(self):
        self.assertEqual(self._resolve("X-Forwarded-For", "127.0.0.1, 203.0.113.9"), "203.0.113.9")

    def test_spoofed_tailscale_address_is_ignored(self):
        self.assertEqual(self._resolve("X-Forwarded-For", "100.106.10.47, 203.0.113.9"), "203.0.113.9")

    def test_single_value_unchanged(self):
        self.assertEqual(self._resolve("X-Forwarded-For", "203.0.113.9"), "203.0.113.9")

    def test_chain_of_trusted_proxies_is_skipped(self):
        self.assertEqual(self._resolve("X-Forwarded-For", "203.0.113.9, 127.0.0.1, ::1"), "203.0.113.9")

    def test_all_trusted_falls_back_to_leftmost(self):
        self.assertEqual(self._resolve("X-Forwarded-For", "127.0.0.1, ::1"), "127.0.0.1")

    def test_forwarded_header_multi_hop(self):
        self.assertEqual(self._resolve("Forwarded", 'for=127.0.0.1, for="[2001:db8::1]:443"'), "2001:db8::1")


if __name__ == "__main__":
    unittest.main()
