import ipaddress
import random
import unittest
from datetime import datetime, timedelta, timezone
from unittest.mock import patch

from omega_serv.domain.security.waf import blocklist as blocklist_module
from omega_serv.domain.security.waf.blocklist import (
    BlocklistIndex,
    find_matching_entry,
    parse_blocklist,
    purge_expired,
    serialize_blocklist,
    validate_blocklist_entry,
)
from omega_serv.domain.security.waf.entities import BlocklistEntry

_NOW = datetime(2026, 9, 5, tzinfo=timezone.utc)


def _entry(network="203.0.113.25/32", expires_at=None, source="manual"):
    return BlocklistEntry(network=network, reason="test", created_at=_NOW.isoformat(), expires_at=expires_at, source=source)


class TestParseSerializeRoundTrip(unittest.TestCase):
    def test_round_trip(self):
        entries = [_entry()]
        data = serialize_blocklist(entries)
        parsed = parse_blocklist(data)
        self.assertEqual(parsed, entries)


class TestValidateBlocklistEntry(unittest.TestCase):
    def test_valid_ip_passes(self):
        self.assertIsNone(validate_blocklist_entry(_entry()))

    def test_valid_cidr_passes(self):
        self.assertIsNone(validate_blocklist_entry(_entry(network="203.0.113.0/24")))

    def test_invalid_network_rejected(self):
        self.assertIsNotNone(validate_blocklist_entry(_entry(network="not-an-ip")))

    def test_empty_reason_rejected(self):
        entry = BlocklistEntry(network="203.0.113.25/32", reason="", created_at=_NOW.isoformat())
        self.assertIsNotNone(validate_blocklist_entry(entry))


class TestFindMatchingEntry(unittest.TestCase):
    def test_matches_exact_ip(self):
        entries = [_entry()]
        found = find_matching_entry("203.0.113.25", entries, _NOW)
        self.assertIsNotNone(found)

    def test_matches_cidr_range(self):
        entries = [_entry(network="203.0.113.0/24")]
        found = find_matching_entry("203.0.113.99", entries, _NOW)
        self.assertIsNotNone(found)

    def test_no_match_outside_range(self):
        entries = [_entry(network="203.0.113.0/24")]
        found = find_matching_entry("198.51.100.1", entries, _NOW)
        self.assertIsNone(found)

    def test_expired_entry_does_not_match(self):
        expired = (_NOW - timedelta(hours=1)).isoformat()
        entries = [_entry(expires_at=expired)]
        found = find_matching_entry("203.0.113.25", entries, _NOW)
        self.assertIsNone(found)

    def test_future_expiry_still_matches(self):
        future = (_NOW + timedelta(hours=1)).isoformat()
        entries = [_entry(expires_at=future)]
        found = find_matching_entry("203.0.113.25", entries, _NOW)
        self.assertIsNotNone(found)

    def test_invalid_client_ip_never_raises(self):
        entries = [_entry()]
        found = find_matching_entry("not-an-ip", entries, _NOW)
        self.assertIsNone(found)


class TestBlocklistIndex(unittest.TestCase):
    """L'index (OMEGA-SERV_ANALYSE_OPTIMISATION.md §1) doit rendre EXACTEMENT
    l'entree que rend find_matching_entry : meme objet, meme ordre de priorite."""

    def test_same_result_as_linear_search_on_random_lists(self):
        rng = random.Random(20261029)
        past, future = (_NOW - timedelta(hours=1)).isoformat(), (_NOW + timedelta(hours=1)).isoformat()
        naive_future = (_NOW + timedelta(hours=1)).replace(tzinfo=None).isoformat()
        networks = [
            "203.0.113.25/32", "203.0.113.25", "203.0.113.0/24", "203.0.0.0/16", "203.0.113.26/31",
            "198.51.100.7/32", "198.51.100.0/25", "2001:db8::1/128", "2001:db8::1", "2001:db8::/64",
            "2001:db8::/32", "::ffff:203.0.113.25/128", "203.0.113.25/24", "not-a-network", "0.0.0.0/0",
        ]
        ips = ["203.0.113.25", "203.0.113.26", "203.0.113.99", "203.0.5.1", "198.51.100.7", "198.51.100.200",
               "2001:db8::1", "2001:db8::2", "2001:db8:1::1", "::ffff:203.0.113.25", "192.0.2.1", "bad-ip"]
        for _ in range(3000):
            entries = [
                _entry(network=rng.choice(networks), expires_at=rng.choice([None, past, future, naive_future]))
                for _ in range(rng.randint(0, 12))
            ]
            index = BlocklistIndex(entries)
            for ip in ips:
                self.assertIs(index.find(ip, _NOW), find_matching_entry(ip, entries, _NOW), (ip, entries))

    def test_first_matching_entry_in_file_order_wins(self):
        network_first = _entry(network="203.0.113.0/24")
        exact_after = _entry(network="203.0.113.25/32")
        self.assertIs(BlocklistIndex([network_first, exact_after]).find("203.0.113.25", _NOW), network_first)
        self.assertIs(BlocklistIndex([exact_after, network_first]).find("203.0.113.25", _NOW), exact_after)

    def test_expired_exact_entry_falls_back_to_a_later_network(self):
        expired = _entry(expires_at=(_NOW - timedelta(hours=1)).isoformat())
        network = _entry(network="203.0.113.0/24")
        self.assertIs(BlocklistIndex([expired, network]).find("203.0.113.25", _NOW), network)

    def test_unreadable_expiry_raises_like_before(self):
        entries = [_entry(expires_at="pas une date")]
        with self.assertRaises(ValueError):
            find_matching_entry("203.0.113.25", entries, _NOW)
        index = BlocklistIndex(entries)  # jamais d'erreur a la construction
        with self.assertRaises(ValueError):
            index.find("203.0.113.25", _NOW)

    def test_entries_are_parsed_once_not_per_lookup(self):
        entries = [_entry(network=f"198.51.{i // 250}.{i % 250}/32") for i in range(100)]
        index = BlocklistIndex(entries)
        with patch.object(blocklist_module.ipaddress, "ip_network", wraps=ipaddress.ip_network) as spy:
            for _ in range(50):
                self.assertIsNone(index.find("203.0.113.9", _NOW))
        self.assertEqual(spy.call_count, 0)


class TestPurgeExpired(unittest.TestCase):
    def test_removes_only_expired(self):
        expired = (_NOW - timedelta(hours=1)).isoformat()
        future = (_NOW + timedelta(hours=1)).isoformat()
        entries = [_entry(network="203.0.113.1/32", expires_at=expired), _entry(network="203.0.113.2/32", expires_at=future)]
        kept, removed_count = purge_expired(entries, _NOW)
        self.assertEqual(removed_count, 1)
        self.assertEqual(len(kept), 1)
        self.assertEqual(kept[0].network, "203.0.113.2/32")

    def test_permanent_entries_never_purged(self):
        entries = [_entry(expires_at=None)]
        kept, removed_count = purge_expired(entries, _NOW)
        self.assertEqual(removed_count, 0)
        self.assertEqual(len(kept), 1)


if __name__ == "__main__":
    unittest.main()
