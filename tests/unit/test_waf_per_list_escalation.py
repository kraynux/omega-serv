"""Recidive par liste et reseaux jamais bannis automatiquement -
OMEGA-SERV_PLAN-DETAILLE_SENSITIVE_PATHS.md §3.12/§3.13. Utilise le VRAI
compteur (InMemoryReputationTracker) avec une horloge controlee."""
import ipaddress
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path

from omega_serv.application.security.evaluate_waf_request import evaluate_waf_request
from omega_serv.application.server.start_server import build_waf_collaborators
from omega_serv.domain.config.entities import OmegaServConfig
from omega_serv.domain.http.headers import HttpHeaders
from omega_serv.domain.http.request import HttpRequest
from omega_serv.domain.security.waf.config import parse_waf_config
from omega_serv.domain.security.waf.entities import Severity, WafDecision, WafFinding
from omega_serv.infrastructure.filesystem.local_filesystem import LocalFilesystem
from omega_serv.infrastructure.waf.reputation_tracker import InMemoryReputationTracker
from omega_serv.ports.rate_limit_port import RateLimitCheckResult

_HOSTILE = "sensitive-paths-hostile"
_PROBE = "sensitive-paths-probe"
_OBSERVED = "sensitive-paths-essai"


class _Clock:
    def __init__(self):
        self.current = datetime(2026, 10, 18, tzinfo=timezone.utc)

    def now(self) -> datetime:
        return self.current


class _Blocklist:
    """Comme la vraie blocklist : une IP deja bannie est refusee en tete
    de pipeline, donc ne peut plus provoquer de nouvelle entree."""
    def __init__(self):
        self.entries = []

    def is_blocked(self, ip):
        addr = ipaddress.ip_address(ip)
        for entry in self.entries:
            network = ipaddress.ip_network(entry.network, strict=False)
            if addr.version == network.version and addr in network:
                return entry
        return None

    def list_entries(self):
        return tuple(self.entries)

    def add_entry(self, entry):
        self.entries.append(entry)

    def remove_entry(self, network):
        return False

    def purge_expired(self):
        return 0

    def count_auto_entries(self):
        return len(self.entries)


class _RateLimit:
    def check(self, key, requests, window_seconds):
        return RateLimitCheckResult(allowed=True, retry_after_seconds=None)

    def reset(self, key=None):
        pass


class _WafPort:
    def __init__(self, *packs: str):
        self._decision = WafDecision(
            action="log", status_code=None, score=3,
            findings=tuple(
                WafFinding(rule_id=p, pack=p, description="", severity=Severity.MEDIUM, weight=3, scope="path")
                for p in packs
            ),
        )

    def inspect(self, request):
        return self._decision


def _list(list_id: str, **overrides) -> dict:
    data = {"id": list_id, "scope": ["path"], "file": f"secure/waf/rules/keywords/{list_id}.txt", "match": "path"}
    data.update(overrides)
    return data


def _config(**reputation_overrides):
    reputation = {"enabled": True, "auto_block": True, "suspicious_threshold": 3, "window_seconds": 300,
                  "auto_block_duration_seconds": 3600}
    reputation.update(reputation_overrides)
    return parse_waf_config({
        "mode": "block",
        "reputation": reputation,
        "rules": {"keyword_lists": [
            _list(_HOSTILE, weight=6, escalation_threshold=2, escalation_window_seconds=600,
                  auto_block_duration_seconds=86400),
            _list(_PROBE, weight=3, anchor="root", escalation_threshold=5, escalation_window_seconds=600),
            _list(_OBSERVED, weight=6, observe_only=True, escalation_threshold=1),
        ]},
    })


def _request(ip: str = "198.51.100.7") -> HttpRequest:
    return HttpRequest(
        request_id="r1", remote_ip=ip, peer_ip=ip, method="GET", path="/x", raw_path="/x", query="",
        headers=HttpHeaders.from_pairs([]), body=None, content_length=None, is_tls=False,
    )


class TestPerListEscalation(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.clock = _Clock()
        self.tracker = InMemoryReputationTracker(self.clock)
        self.blocklist = _Blocklist()

    async def _hit(self, *packs: str, ip: str = "198.51.100.7", config=None, times: int = 1):
        for _ in range(times):
            await evaluate_waf_request(
                _request(ip), config or _config(), _WafPort(*packs), self.blocklist, _RateLimit(), self.tracker,
            )
            self.clock.current += timedelta(seconds=10)

    def _expires_in(self, entry) -> float:
        created = datetime.fromisoformat(entry.created_at)
        return (datetime.fromisoformat(entry.expires_at) - created).total_seconds()

    async def test_hostile_list_bans_at_its_own_threshold(self):
        await self._hit(_HOSTILE)
        self.assertEqual(self.blocklist.entries, [])
        await self._hit(_HOSTILE)
        self.assertEqual(len(self.blocklist.entries), 1)
        entry = self.blocklist.entries[0]
        self.assertEqual(entry.network, "198.51.100.7/32")
        self.assertEqual(entry.source, "auto")
        self.assertIn(_HOSTILE, entry.reason)
        self.assertEqual(self._expires_in(entry), 86400)

    async def test_probe_list_ignores_the_lower_common_threshold(self):
        await self._hit(_PROBE, times=4)
        self.assertEqual(self.blocklist.entries, [], "le seuil commun (3) ne doit pas s'appliquer a une liste a seuil propre")
        await self._hit(_PROBE)
        self.assertEqual(len(self.blocklist.entries), 1)
        self.assertEqual(self._expires_in(self.blocklist.entries[0]), 3600, "duree commune si la liste n'en fixe pas")

    async def test_list_window_is_respected(self):
        await self._hit(_HOSTILE)
        self.clock.current += timedelta(seconds=601)
        await self._hit(_HOSTILE)
        self.assertEqual(self.blocklist.entries, [])

    async def test_json_pack_keeps_the_common_counter(self):
        await self._hit("body-sqli", times=2)
        self.assertEqual(self.blocklist.entries, [])
        await self._hit("body-sqli")
        self.assertEqual(len(self.blocklist.entries), 1)
        self.assertNotIn("recidive", self.blocklist.entries[0].reason)

    async def test_list_hits_do_not_feed_the_common_counter(self):
        await self._hit(_PROBE, times=2)
        await self._hit("body-sqli", times=2)
        self.assertEqual(self.blocklist.entries, [], "2 hits de pack JSON seulement : sous le seuil commun de 3")

    async def test_observe_only_list_never_counts(self):
        await self._hit(_OBSERVED, times=10)
        self.assertEqual(self.blocklist.entries, [])
        self.assertEqual(self.tracker.count_hits_in_window("198.51.100.7", 300), 0)
        self.assertEqual(self.tracker.count_hits_in_window("198.51.100.7", 600, key=_OBSERVED), 0)

    async def test_several_thresholds_one_entry_longest_duration(self):
        await self._hit(_HOSTILE, "body-sqli")  # hostile 1/2, commun 1/3
        await self._hit("body-sqli")            # commun 2/3
        self.assertEqual(self.blocklist.entries, [])
        await self._hit(_HOSTILE, "body-sqli")  # hostile 2/2 ET commun 3/3 dans la meme requete
        self.assertEqual(len(self.blocklist.entries), 1)
        self.assertEqual(self._expires_in(self.blocklist.entries[0]), 86400, "la duree la plus longue l'emporte")

    async def test_banned_ip_is_refused_before_inspection(self):
        await self._hit(_HOSTILE, times=2)
        decision = await evaluate_waf_request(
            _request(), _config(), _WafPort(_HOSTILE), self.blocklist, _RateLimit(), self.tracker,
        )
        self.assertEqual(decision.action, "block")
        self.assertIn(_HOSTILE, decision.blocked_reason)

    async def test_ipv6_is_banned_as_single_address(self):
        await self._hit(_HOSTILE, ip="2001:db8::7", times=2)
        self.assertEqual(self.blocklist.entries[0].network, "2001:db8::7/128")

    async def test_auto_block_disabled_never_bans(self):
        await self._hit(_HOSTILE, config=_config(auto_block=False), times=5)
        self.assertEqual(self.blocklist.entries, [])


class TestNeverAutoBlock(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.clock = _Clock()
        self.tracker = InMemoryReputationTracker(self.clock)
        self.blocklist = _Blocklist()

    async def _hammer(self, ip: str, config=None):
        for _ in range(5):
            await evaluate_waf_request(
                _request(ip), config or _config(), _WafPort(_HOSTILE), self.blocklist, _RateLimit(), self.tracker,
            )

    async def test_local_tailscale_and_lan_are_never_auto_banned(self):
        for ip in ("127.0.0.1", "::1", "100.106.10.47", "fd7a:115c:a1e0::5", "192.168.1.20", "10.0.0.3",
                   "172.20.1.1", "fe80::1", "::ffff:127.0.0.1"):
            with self.subTest(ip=ip):
                await self._hammer(ip)
                self.assertEqual(self.blocklist.entries, [])

    async def test_public_addresses_are_banned(self):
        for ip in ("198.51.100.7", "100.12.196.99", "2001:db8::9"):
            with self.subTest(ip=ip):
                self.blocklist.entries.clear()
                await self._hammer(ip)
                self.assertEqual(len(self.blocklist.entries), 1)

    async def test_custom_list_replaces_defaults(self):
        await self._hammer("192.168.1.20", config=_config(never_auto_block=["127.0.0.0/8"]))
        self.assertEqual(len(self.blocklist.entries), 1)


class TestBuildAppliesLoopbackGuard(unittest.TestCase):
    """§3.14-a : l'exemption loopback n'est effective qu'avec trusted_proxy actif."""
    def _effective(self, trusted_proxy_enabled: bool) -> tuple[str, ...]:
        with tempfile.TemporaryDirectory() as tmp:
            config = OmegaServConfig.from_dict({
                "server": {"bind": "127.0.0.1", "port": 8080},
                "options": {
                    "waf": {"enabled": True, "rules": {"paths": []}},
                    "trusted_proxy": {"enabled": trusted_proxy_enabled, "trusted_networks": ["127.0.0.1"]},
                },
            })
            waf = build_waf_collaborators(config, Path(tmp), LocalFilesystem(), _Clock())
            assert waf is not None
            return waf.config.reputation.never_auto_block

    def test_loopback_exempt_behind_trusted_proxy(self):
        self.assertIn("127.0.0.0/8", self._effective(True))

    def test_loopback_not_exempt_without_trusted_proxy(self):
        effective = self._effective(False)
        self.assertNotIn("127.0.0.0/8", effective)
        self.assertNotIn("::1/128", effective)
        self.assertIn("100.64.0.0/10", effective)


if __name__ == "__main__":
    unittest.main()
