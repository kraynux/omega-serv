"""RIPOSTE lot 3 (OMEGA-SERV_PLAN-DETAILLE_RIPOSTE.md §3.3-3.10) : moteur sur une vraie base, mesure par
rejeu, commandes de consultation sur un projet temporaire (jamais le var/ du depot)."""
import contextlib
import io
import json
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path

from omega_serv.application.riposte.engine import RiposteEngine
from omega_serv.application.riposte.measure import measure
from omega_serv.bootstrap.container import DependencyContainer
from omega_serv.domain.security.riposte.config import DAY, HOUR, RiposteConfig, RipostePolicy
from omega_serv.domain.security.riposte.events import ObservedEvent
from omega_serv.infrastructure.persistence.sqlite_riposte_connection import open_riposte_connection
from omega_serv.infrastructure.persistence.sqlite_riposte_store import SqliteRiposteStore
from omega_serv.interfaces.cli.main import build_parser

T0 = datetime(2026, 11, 1, 10, tzinfo=timezone.utc)
SCAN = RipostePolicy(id="scan", name="Scan", attack_classes=("scan",), returns=3, within_seconds=7 * DAY)


def _attack(ip, at, request_id):
    return ObservedEvent(source="waf", event_id=f"waf:{request_id}", kind="attack", timestamp=at, remote_ip=ip,
                         attack_class="scan", score=8)


def _episodes(ip, count, start=T0, spacing=timedelta(hours=2), per_episode=2):
    events = []
    for i in range(count):
        for j in range(per_episode):
            events.append(_attack(ip, start + spacing * i + timedelta(minutes=j), f"{ip}-{i}-{j}"))
    return events


class TestEngine(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.connection = open_riposte_connection(Path(self._tmp.name) / "riposte.sqlite3")
        self.store = SqliteRiposteStore(self.connection)

    def tearDown(self):
        self.connection.close()
        self._tmp.cleanup()

    def test_third_episode_is_decided_once_and_never_applied(self):
        engine = RiposteEngine(self.store, RiposteConfig(policies=(SCAN,)), exempt_networks=())
        recorded = engine.handle(_episodes("203.0.113.7", 3))
        self.assertEqual([d.status for d in recorded], ["matched"])
        decisions = self.store.list_decisions(10)
        self.assertEqual(len(decisions), 1)
        decision, applied = decisions[0]
        self.assertFalse(applied)  # lot 3 : jamais d'action reelle
        self.assertEqual(decision.policy_id, "scan")
        self.assertIn("policy_matched", [r.code for r in decision.reasons])
        history = self.store.get_source("203.0.113.7")
        self.assertTrue(history.current_episode.action_taken)
        self.assertEqual(history.actions, ())  # aucun palier consomme sans action reelle

    def test_events_processed_one_batch_at_a_time_give_the_same_result(self):
        engine = RiposteEngine(self.store, RiposteConfig(policies=(SCAN,)), exempt_networks=())
        for event in _episodes("203.0.113.7", 3):
            engine.handle([event])
        self.assertEqual(len(self.store.list_decisions(10)), 1)

    def test_exempt_source_is_recorded_as_rejected_and_never_matched(self):
        engine = RiposteEngine(self.store, RiposteConfig(policies=(SCAN,)), exempt_networks=("203.0.113.0/24",))
        engine.handle(_episodes("203.0.113.7", 1, per_episode=1))
        ((decision, _applied),) = self.store.list_decisions(10)
        self.assertEqual(decision.status, "rejected_by_safety")

    def test_emergency_stop_is_respected(self):
        self.store.set_state("emergency_stop", "1")
        engine = RiposteEngine(self.store, RiposteConfig(policies=(SCAN,)), exempt_networks=())
        recorded = engine.handle(_episodes("203.0.113.7", 3))
        self.assertTrue(recorded)
        self.assertTrue(all(d.status == "stopped" for d in recorded))

    def test_reload_changes_policies_and_keeps_memory(self):
        engine = RiposteEngine(self.store, RiposteConfig(), exempt_networks=())
        engine.handle(_episodes("203.0.113.7", 2))
        self.assertEqual(self.store.list_decisions(10), [])
        engine.update_config(RiposteConfig(policies=(SCAN,)), ())
        engine.handle(_episodes("203.0.113.7", 1, start=T0 + timedelta(hours=5)))
        self.assertEqual(len(self.store.list_decisions(10)), 1)  # les 2 episodes d'avant comptent

    def test_maintenance_bounds_and_retention(self):
        engine = RiposteEngine(self.store, RiposteConfig(policies=(SCAN,)), exempt_networks=())
        engine.handle(_episodes("203.0.113.7", 3))
        engine.maintenance(T0 + timedelta(days=200))
        self.assertIsNone(self.store.get_source("203.0.113.7"))
        self.assertEqual(self.store.list_decisions(10), [])


class TestMeasure(unittest.TestCase):
    def test_tiers_progress_across_returns(self):
        events = []
        for day in range(4):  # 3 episodes par jour : action au 3e, palier suivant chaque jour
            events += _episodes("203.0.113.7", 3, start=T0 + timedelta(days=day), per_episode=1)
        result = measure(events, RiposteConfig(policies=(SCAN,)), ())
        self.assertEqual(result.actions, 4)
        self.assertEqual(result.max_cumulative_ban_seconds, HOUR + 6 * HOUR + DAY + 7 * DAY)
        self.assertEqual(result.first_event_at, T0)

    def test_global_cap_is_simulated(self):
        events = _episodes("203.0.113.7", 3, per_episode=1) + _episodes("203.0.113.8", 3, per_episode=1)
        result = measure(events, RiposteConfig(policies=(SCAN,), max_active_bans=1), ())
        self.assertEqual((result.actions, result.rejected_by_safety), (1, 1))

    def test_since_and_exemptions(self):
        events = _episodes("203.0.113.7", 3, per_episode=1)
        self.assertEqual(measure(events, RiposteConfig(policies=(SCAN,)), (), since=T0 + timedelta(days=1)).events, 0)
        self.assertEqual(measure(events, RiposteConfig(policies=(SCAN,)), ("203.0.113.0/24",)).actions, 0)


class TestQueryCommands(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.root = Path(self._tmp.name)
        (self.root / "config").mkdir()
        self.config_path = self.root / "config" / "omega-serve.json"
        self.config_path.write_text(json.dumps({
            "version": 1, "profile": "standard", "server": {"bind": "127.0.0.1", "port": 8080},
            "options": {
                "waf": {"enabled": True},
                "riposte": {"enabled": True, "policies": [{
                    "id": "scan-recidive", "name": "Scanner récidiviste",
                    "when": {"attack_classes": ["scan"], "returns": 3, "within_seconds": 604800},
                }]},
            },
        }))
        self.container = DependencyContainer(project_root=self.root)

    def tearDown(self):
        self._tmp.cleanup()

    def _run(self, *argv):
        args = build_parser().parse_args(["--config", str(self.config_path), "riposte", *argv])
        out = io.StringIO()
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(out):
            code = args.func(args, self.container)
        return code, out.getvalue()

    def test_scenarios_and_policies(self):
        code, out = self._run("scenarios", "list")
        self.assertEqual(code, 0)
        self.assertIn("injections-repetees", out)
        code, out = self._run("scenarios", "show", "scan-recidive")
        self.assertIn("1 h / 6 h / 1 j / 7 j", out)
        _code, out = self._run("policies", "list")
        self.assertIn("scan-recidive", out)
        self.assertEqual(self._run("policies", "show", "inconnue")[0], 1)

    def test_simulate_explains_the_decision(self):
        _code, out = self._run("simulate", "--ip", "203.0.113.9", "--class", "scan", "--returns", "3")
        self.assertIn("action décidée", out)
        self.assertIn("Palier 1 sur 4", out)
        _code, out = self._run("simulate", "--ip", "203.0.113.9", "--class", "scan", "--returns", "2")
        self.assertIn("il en faut 3", out)

    def test_loopback_is_exempt_only_with_a_trusted_proxy(self):
        """Meme garde-fou que le WAF : sans proxy de confiance, tout Internet derriere un proxy local
        apparait en 127.0.0.1 - exempter le loopback reviendrait a exempter Internet."""
        _code, out = self._run("simulate", "--ip", "127.0.0.1", "--returns", "3")
        self.assertIn("action décidée", out)
        data = json.loads(self.config_path.read_text())
        data["options"]["trusted_proxy"] = {"enabled": True, "trusted_networks": ["127.0.0.1/32"]}
        self.config_path.write_text(json.dumps(data))
        _code, out = self._run("simulate", "--ip", "127.0.0.1", "--returns", "3")
        self.assertIn("refusée par les garde-fous", out)
        self.assertIn("127.0.0.0/8", out)

    def test_measure_reads_the_real_journal(self):
        log = self.root / "var" / "log" / "waf-alerts.log"
        log.parent.mkdir(parents=True)
        now = datetime.now(timezone.utc)
        lines = []
        for i in range(3):
            at = now - timedelta(hours=10 - 2 * i)
            lines.append(json.dumps({
                "timestamp": at.isoformat(), "request_id": f"r{i}", "remote_ip": "203.0.113.7", "action": "block",
                "stage": "inspection", "score": 9, "rules": ["S"], "findings": [{"id": "S", "pack": "sensitive-paths"}],
            }))
        log.write_text("\n".join(lines) + "\n")
        code, out = self._run("measure", "scan-recidive", "--days", "7")
        self.assertEqual(code, 0, out)
        self.assertIn("Aurait pris 1 action(s) sur 1 source(s)", out)
        _code, out = self._run("measure", "scenario:injections-repetees")
        self.assertIn("Aurait pris 0 action(s)", out)

    def test_read_commands_without_database(self):
        _code, out = self._run("decisions", "list")
        self.assertIn("jamais été lancé", out)
        self.assertFalse((self.root / "var" / "lib" / "riposte.sqlite3").exists())  # jamais cree en lecture


if __name__ == "__main__":
    unittest.main()
