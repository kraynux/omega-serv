"""RIPOSTE lot 6 (OMEGA-SERV_PLAN-DETAILLE_RIPOSTE.md §3.6) : ban reseau = ligne dans riposte-decisions.jsonl lue
par les jails omega-jail a duree fixe. Decision utilisateur 2026-11-02 : jail la plus longue qui ne depasse pas
le palier (au moins 1 h). Le format de ligne est un contrat avec les filtres fail2ban (catalog.yaml d'omega-jail)."""
import json
import re
import tempfile
import unittest
from datetime import timedelta
from pathlib import Path

from omega_serv.application.riposte.actuator import ActionTargets, RiposteActuator
from omega_serv.bootstrap.container import DependencyContainer
from omega_serv.domain.config.entities import OmegaServConfig
from omega_serv.domain.config.option import Option
from omega_serv.domain.security.riposte.config import DAY, HOUR
from omega_serv.domain.security.riposte.network_ban import jail_for, jail_name, network_ban_line
from omega_serv.domain.security.waf.entities import BlocklistEntry
from omega_serv.interfaces.cli.riposte_commands import _Targets
from omega_serv.interfaces.cli.riposte_text import network_jails_text
from tests.unit.test_riposte_actions import IP, T0, _Base, _decision, _ids

# Meme expression que le filtre fail2ban d'omega-jail (catalog.yaml), <HOST> remplace.
FAIL2BAN_FILTER = r'"remote_ip": "(?P<host>[^"]+)", "jail": "{suffix}"'


class TestJailMapping(unittest.TestCase):
    def test_longest_jail_not_above_the_tier(self):
        self.assertEqual(jail_for(HOUR), (HOUR, "1h"))
        self.assertEqual(jail_for(2 * HOUR), (HOUR, "1h"))
        self.assertEqual(jail_for(6 * HOUR), (6 * HOUR, "6h"))
        self.assertEqual(jail_for(12 * HOUR), (6 * HOUR, "6h"))
        self.assertEqual(jail_for(DAY), (DAY, "24h"))
        self.assertEqual(jail_for(30 * DAY), (7 * DAY, "7d"))

    def test_shorter_than_every_jail_goes_to_the_shortest(self):
        self.assertEqual(jail_for(600), (HOUR, "1h"))

    def test_jail_name_is_per_instance(self):
        self.assertEqual(jail_name("omega-serv-blog", 7 * DAY), "omega-serv-blog-riposte-7d")

    def test_interface_says_which_jail_each_tier_uses(self):
        text = network_jails_text("omega-serv", (2 * HOUR, DAY))
        self.assertIn("2 h -> jail omega-serv-riposte-1h", text)
        self.assertIn("1 j -> jail omega-serv-riposte-24h", text)


class TestLineFormat(unittest.TestCase):
    def test_line_matches_only_its_own_jail_filter(self):
        line = network_ban_line(at=T0, ip="2001:db8::7", action_id="abc", policy_id="scan", tier_index=1,
                                duration_seconds=12 * HOUR)
        self.assertEqual(re.search(FAIL2BAN_FILTER.format(suffix="6h"), line).group("host"), "2001:db8::7")
        for other in ("1h", "24h", "7d"):
            self.assertIsNone(re.search(FAIL2BAN_FILTER.format(suffix=other), line))
        data = json.loads(line)
        self.assertEqual((data["event"], data["tier"], data["jail_seconds"], data["duration_seconds"]),
                         ("network_ban", 2, 6 * HOUR, 12 * HOUR))
        self.assertNotIn("\n", line)


class TestActuatorWritesTheNetworkLine(_Base):
    def setUp(self):
        super().setUp()
        self.lines: list[str] = []
        self.actuator = RiposteActuator(
            self.store, ActionTargets(self.blocklist, self.deception, network_log=self.lines.append), new_id=_ids)

    def test_network_ban_writes_after_the_local_ban(self):
        action = self.actuator.apply(_decision(action="local_and_network_ban", duration=6 * HOUR), (), T0)
        self.assertEqual(action.state, "applied")
        self.assertIsNotNone(self._entry())
        [line] = self.lines
        self.assertEqual(json.loads(line)["action_id"], action.id)
        self.assertEqual(json.loads(line)["jail"], "6h")

    def test_local_ban_only_never_writes(self):
        self.actuator.apply(_decision(action="local_ban"), (), T0)
        self.assertEqual(self.lines, [])

    def test_no_network_line_when_the_local_ban_is_refused(self):
        self.blocklist.add_entry(BlocklistEntry(network=IP + "/32", reason="a la main", created_at=T0.isoformat()))
        action = self.actuator.apply(_decision(action="local_and_network_ban"), (), T0)
        self.assertEqual(action.state, "failed")
        self.assertEqual(self.lines, [])

    def test_revoke_lifts_only_the_local_part(self):
        action = self.actuator.apply(_decision(action="local_and_network_ban"), (), T0)
        self.actuator.revoke(action, by="user", now=T0 + timedelta(minutes=1))
        self.assertIsNone(self._entry())
        self.assertEqual(len(self.lines), 1)  # rien ne « retire » une ligne : fail2ban garde son ban


class TestProcessTargets(unittest.TestCase):
    """Le processus RIPOSTE n'ouvre le journal que si une politique active utilise le ban reseau."""

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.root = Path(self._tmp.name)
        self.container = DependencyContainer(project_root=self.root, instance_registry_path=self.root / "i.json")

    def tearDown(self):
        self._tmp.cleanup()

    def _targets(self, action, **settings):
        policy = {"id": "p", "name": "P", "when": {"returns": 1}, "then": {"action": action}}
        config = OmegaServConfig(options={
            "waf": Option(name="waf", enabled=True, settings={}),
            "riposte": Option(name="riposte", enabled=True, settings={"policies": [policy], **settings}),
        })
        return _Targets(self.container).build(config)

    def test_network_policy_writes_to_the_configured_journal(self):
        targets = self._targets("local_and_network_ban")
        self.assertIsNotNone(targets.network_log)
        targets.network_log("{}")
        self.assertEqual((self.root / "var" / "log" / "riposte-decisions.jsonl").read_text(), "{}\n")

    def test_no_journal_without_network_policy_or_when_disabled(self):
        self.assertIsNone(self._targets("local_ban").network_log)
        self.assertIsNone(self._targets("local_and_network_ban", network_ban_log=False).network_log)


if __name__ == "__main__":
    unittest.main()
