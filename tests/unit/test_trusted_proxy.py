# Copyright (c) 2026 kraynux - kraynux@proton.me - Licence MIT (voir fichier LICENSE)
import unittest

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
        # L'angle mort explicitement identifie avant la Phase 0 : sans
        # normalisation, cette forme IPv6-mappee d'une IP NON fiable
        # pourrait passer les filtres bases sur la forme IPv4 pure.
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


if __name__ == "__main__":
    unittest.main()
