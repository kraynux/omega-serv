import unittest
from datetime import datetime, timedelta, timezone

from omega_serv.domain.security.waf.blocklist import (
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
