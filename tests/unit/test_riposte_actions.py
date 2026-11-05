"""RIPOSTE lot 4 : registre des actions, application reelle (blocklist, leurre), levee, reconciliation
(dont arret brutal), commandes de l'interface, arret d'urgence (OMEGA-SERV_PLAN-DETAILLE_RIPOSTE.md §3.6-3.7)."""
import itertools
import os
import stat
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path

from omega_serv.application.riposte.actuator import ActionTargets, RiposteActuator
from omega_serv.application.riposte.commands import RiposteCommandRunner
from omega_serv.application.riposte.engine import STATE_EMERGENCY_STOP, RiposteEngine
from omega_serv.domain.security.active_defense.entities import DeceptionAssignment
from omega_serv.domain.security.riposte.actions import action_id_from_reason, blocklist_reason
from omega_serv.domain.security.riposte.config import HOUR, RiposteConfig, RipostePolicy
from omega_serv.domain.security.riposte.decide import Decision
from omega_serv.domain.security.riposte.events import ObservedEvent
from omega_serv.domain.security.waf.blocklist import validate_blocklist_entry
from omega_serv.domain.security.waf.entities import BlocklistEntry
from omega_serv.infrastructure.filesystem.local_filesystem import LocalFilesystem
from omega_serv.infrastructure.persistence.sqlite_riposte_connection import open_riposte_connection
from omega_serv.infrastructure.persistence.sqlite_riposte_store import SqliteRiposteStore
from omega_serv.infrastructure.waf.blocklist_store import JsonBlocklistStore

T0 = datetime(2026, 11, 1, 10, tzinfo=timezone.utc)
IP = "203.0.113.7"
_IDS = itertools.count(1)


class _Clock:
    def __init__(self, now: datetime):
        self.now_value = now

    def now(self) -> datetime:
        return self.now_value


class _Deception:
    """Affectations de leurre en memoire (meme contrat que SqliteDeceptionAssignmentRepository)."""

    def __init__(self):
        self.rows: dict[str, DeceptionAssignment] = {}

    def get(self, subject_id):
        return self.rows.get(subject_id)

    def save(self, assignment):
        self.rows[assignment.subject_id] = assignment

    def release(self, subject_id):
        self.rows.pop(subject_id, None)

    def list_active(self):
        return list(self.rows.values())


def _ids():
    return f"{next(_IDS):012x}"


def _event(at=T0, kind="attack", ip=IP, attack_class="scan", subject_id=None):
    return ObservedEvent(source="waf", event_id=f"ev{next(_IDS)}", kind=kind, timestamp=at, remote_ip=ip,
                         attack_class=attack_class if kind == "attack" else None, score=8, subject_id=subject_id)


def _ban_policy(**overrides):
    values = {"id": "scan", "name": "Scan", "attack_classes": ("scan",), "returns": 1,
              "within_seconds": 24 * HOUR, "action": "local_ban"}
    values.update(overrides)
    return RipostePolicy(**values)


def _decision(action="local_ban", duration=HOUR, ip=IP, profile=None):
    return Decision(status="matched", ip=ip, event_id="e1", decided_at=T0, policy_id="scan", action=action,
                    tier_index=0 if action != "decoy" else None, duration_seconds=duration, decoy_profile=profile)


class _Base(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.root = Path(self._tmp.name)
        self.clock = _Clock(T0)
        self.connection = open_riposte_connection(self.root / "var" / "lib" / "riposte.sqlite3")
        self.store = SqliteRiposteStore(self.connection)
        self.blocklist = JsonBlocklistStore(LocalFilesystem(), self.root / "blocklist.json", self.clock)
        self.deception = _Deception()
        self.actuator = RiposteActuator(self.store, ActionTargets(self.blocklist, self.deception), new_id=_ids)

    def tearDown(self):
        self.connection.close()
        self._tmp.cleanup()

    def _entry(self, network=IP + "/32"):
        return next((e for e in self.blocklist.list_entries() if e.network == network), None)


class TestDatabase(_Base):
    def test_new_database_is_shared_with_the_group(self):
        mode = stat.S_IMODE(os.stat(self.root / "var" / "lib" / "riposte.sqlite3").st_mode)
        self.assertEqual(mode & 0o660, 0o660)

    def test_command_submission_never_creates_the_database(self):
        missing = self.root / "autre" / "riposte.sqlite3"
        with self.assertRaises(FileNotFoundError):
            open_riposte_connection(missing, create=False)
        self.assertFalse(missing.exists())

    def test_reason_is_read_back_by_code(self):
        action = self.actuator.apply(_decision(), (), T0)
        self.assertEqual(action_id_from_reason(blocklist_reason(action)), action.id)
        self.assertIsNone(action_id_from_reason("auto-ban WAF"))

    def test_blocklist_accepts_riposte_source(self):
        entry = BlocklistEntry(network=IP + "/32", reason="riposte:x", created_at=T0.isoformat(), source="riposte")
        self.assertIsNone(validate_blocklist_entry(entry))


class TestApplyAndRevoke(_Base):
    def test_ban_is_written_then_recorded_applied(self):
        action = self.actuator.apply(_decision(), (), T0)
        self.assertEqual(action.state, "applied")
        entry = self._entry()
        self.assertEqual(entry.source, "riposte")
        self.assertEqual(entry.expires_at, (T0 + timedelta(hours=1)).isoformat())
        self.assertEqual(self.store.get_action(action.id).state, "applied")
        self.assertEqual(self.store.count_in_progress(bans_only=True), 1)

    def test_ipv6_uses_a_128_network(self):
        action = self.actuator.apply(_decision(ip="2001:db8::7"), (), T0)
        self.assertEqual(action.state, "applied")
        self.assertIsNotNone(self._entry("2001:db8::7/128"))

    def test_manual_ban_is_never_overwritten(self):
        self.blocklist.add_entry(BlocklistEntry(network=IP + "/32", reason="a la main", created_at=T0.isoformat()))
        action = self.actuator.apply(_decision(), (), T0)
        self.assertEqual((action.state, action.detail), ("failed", "stronger_ban_present"))
        self.assertEqual(self._entry().source, "manual")
        self.assertEqual(self.store.count_in_progress(bans_only=True), 0)

    def test_without_waf_the_ban_fails_with_an_explicit_code(self):
        actuator = RiposteActuator(self.store, ActionTargets(None, None), new_id=_ids)
        action = actuator.apply(_decision(), (), T0)
        self.assertEqual((action.state, action.detail), ("failed", "waf_inactive"))
        self.assertIsNotNone(action.finished_at)

    def test_revoke_removes_only_its_own_entry(self):
        action = self.actuator.apply(_decision(), (), T0)
        # Un ban manuel a remplace celui de RIPOSTE entre-temps : la levee n'y touche pas.
        self.blocklist.add_entry(BlocklistEntry(network=IP + "/32", reason="a la main", created_at=T0.isoformat()))
        revoked = self.actuator.revoke(action, by="user", now=T0)
        self.assertEqual((revoked.state, revoked.finished_by), ("revoked", "user"))
        self.assertEqual(self._entry().source, "manual")

    def test_revoke_removes_the_riposte_entry(self):
        action = self.actuator.apply(_decision(), (), T0)
        self.actuator.revoke(action, by="user", now=T0)
        self.assertIsNone(self._entry())
        self.assertEqual(self.store.list_actions(in_progress=False, limit=10)[0].state, "revoked")

    def test_decoy_is_assigned_and_released(self):
        action = self.actuator.apply(_decision("decoy", 24 * HOUR, profile="fake_admin"), (IP + ":ua1",), T0)
        self.assertEqual(action.state, "applied")
        self.assertFalse(action.counts_for_recidive)
        self.assertEqual(self.deception.get(IP + ":ua1").profile_name, "fake_admin")
        self.actuator.revoke(action, by="user", now=T0)
        self.assertIsNone(self.deception.get(IP + ":ua1"))

    def test_decoy_never_switches_an_active_profile(self):
        self.deception.save(DeceptionAssignment(IP + ":ua1", "fake_api", T0, T0 + timedelta(hours=2)))
        action = self.actuator.apply(_decision("decoy", HOUR, profile="fake_admin"), (IP + ":ua1",), T0)
        self.assertEqual((action.state, action.detail), ("failed", "decoy_already_assigned"))
        self.assertEqual(self.deception.get(IP + ":ua1").profile_name, "fake_api")

    def test_decoy_extends_the_same_profile(self):
        self.deception.save(DeceptionAssignment(IP + ":ua1", "fake_admin", T0, T0 + timedelta(hours=2)))
        action = self.actuator.apply(_decision("decoy", 24 * HOUR, profile="fake_admin"), (IP + ":ua1",), T0)
        self.assertEqual(action.state, "applied")
        self.assertEqual(self.deception.get(IP + ":ua1").expires_at, T0 + timedelta(hours=24))

    def test_decoy_without_known_subject_fails(self):
        action = self.actuator.apply(_decision("decoy", HOUR, profile="fake_admin"), (), T0)
        self.assertEqual(action.detail, "no_subject")


class _CrashingStore:
    """Arret brutal simule : la 2e ecriture de l'action (passage a `applied`) n'arrive jamais."""

    def __init__(self, store):
        self._store = store
        self._saves = 0

    def __getattr__(self, name):
        return getattr(self._store, name)

    def save_action(self, action):
        self._saves += 1
        if self._saves == 2:
            raise KeyboardInterrupt("arret brutal")
        self._store.save_action(action)


class TestReconcile(_Base):
    def test_crash_after_the_ban_is_written_ends_applied(self):
        crashing = RiposteActuator(_CrashingStore(self.store), ActionTargets(self.blocklist, None), new_id=_ids)
        with self.assertRaises(KeyboardInterrupt):
            crashing.apply(_decision(), (), T0)
        [pending] = self.store.list_actions(in_progress=True, limit=10)
        self.assertEqual(pending.state, "pending")
        self.assertEqual(self.actuator.reconcile(T0), {"applied": 1})
        self.assertEqual(self.store.get_action(pending.id).state, "applied")

    def test_crash_before_the_ban_is_written_ends_failed(self):
        class _Unreachable:
            def add_entry_unless_stronger(self, entry):
                raise KeyboardInterrupt("arret brutal")

        crashing = RiposteActuator(self.store, ActionTargets(_Unreachable(), None), new_id=_ids)
        with self.assertRaises(KeyboardInterrupt):
            crashing.apply(_decision(), (), T0)
        self.assertEqual(self.actuator.reconcile(T0), {"failed": 1})
        [failed] = self.store.list_actions(in_progress=False, limit=10)
        self.assertEqual(failed.detail, "interrupted")

    def test_expired_and_removed_outside(self):
        first = self.actuator.apply(_decision(), (), T0)
        second = self.actuator.apply(_decision(ip="198.51.100.9", duration=6 * HOUR), (), T0)
        self.blocklist.remove_entry("198.51.100.9/32")
        counts = self.actuator.reconcile(T0 + timedelta(hours=2))
        self.assertEqual(counts, {"expired": 1, "revoked": 1})
        self.assertEqual(self.store.get_action(first.id).finished_by, "expiry")
        self.assertEqual(self.store.get_action(second.id).detail, "removed_outside")

    def test_unreadable_blocklist_gives_unknown_then_recovers(self):
        action = self.actuator.apply(_decision(), (), T0)

        class _Broken:
            def list_entries(self):
                raise OSError("illisible")

        broken = RiposteActuator(self.store, ActionTargets(_Broken(), None))
        self.assertEqual(broken.reconcile(T0), {"unknown": 1})
        self.assertEqual(self.store.count_in_progress(bans_only=True), 1)  # toujours compte comme en cours
        self.assertEqual(self.actuator.reconcile(T0), {"applied": 1})
        self.assertEqual(self.store.get_action(action.id).detail, "")


class TestEngineActs(_Base):
    def _engine(self, *policies, **config):
        return RiposteEngine(self.store, RiposteConfig(policies=policies or (_ban_policy(),), **config), (),
                             actuator=self.actuator, clock=self.clock)

    def test_matched_decision_is_applied_and_counts_for_the_next_tier(self):
        engine = self._engine()
        engine.handle([_event()])
        self.assertEqual(self._entry().source, "riposte")
        self.assertTrue(self.store.list_decisions(10)[0][1])  # appliquee
        # Episode suivant, apres l'echeance du 1er ban (1 h) : palier 2 (6 h).
        self.clock.now_value = T0 + timedelta(hours=2)
        self.actuator.reconcile(self.clock.now())
        [second] = engine.handle([_event(at=T0 + timedelta(hours=2))])
        self.assertEqual((second.status, second.tier_index, second.duration_seconds), ("matched", 1, 6 * HOUR))
        self.assertEqual(self._entry().expires_at, (T0 + timedelta(hours=8)).isoformat())

    def test_one_action_per_source_at_a_time(self):
        engine = self._engine(_ban_policy(returns=1), episode_gap_seconds=60)
        engine.handle([_event()])
        # Nouvel episode (silence > 60 s) pendant que le 1er ban court encore : refuse.
        [decision] = engine.handle([_event(at=T0 + timedelta(minutes=5))])
        self.assertEqual(decision.status, "rejected_by_safety")
        self.assertEqual(decision.reasons[-1].code, "source_already_has_action")

    def test_max_active_bans(self):
        engine = self._engine(max_active_bans=1)
        engine.handle([_event()])
        [decision] = engine.handle([_event(ip="198.51.100.9")])
        self.assertEqual(decision.reasons[-1].code, "max_active_bans_reached")
        self.assertIsNone(self._entry("198.51.100.9/32"))

    def test_emergency_stop_blocks_new_actions(self):
        self.store.set_state(STATE_EMERGENCY_STOP, "1")
        [decision] = self._engine().handle([_event()])
        self.assertEqual(decision.status, "stopped")
        self.assertEqual(self.blocklist.list_entries(), ())

    def test_failed_action_does_not_raise_the_tier(self):
        self.blocklist.add_entry(BlocklistEntry(network=IP + "/32", reason="a la main", created_at=T0.isoformat()))
        engine = self._engine()
        engine.handle([_event()])
        self.assertFalse(self.store.list_decisions(10)[0][1])
        self.assertEqual(self.store.get_source(IP).actions, ())
        self.assertEqual(engine.actions["failed:stronger_ban_present"], 1)


class TestCommands(_Base):
    def setUp(self):
        super().setUp()
        self.reloads = []
        self.runner = RiposteCommandRunner(self.store, self.actuator, self.clock,
                                           reload=lambda: self.reloads.append(1) or None)
        self.engine = RiposteEngine(self.store, RiposteConfig(policies=(_ban_policy(),)), (),
                                    actuator=self.actuator, clock=self.clock)

    def _run(self, kind, **params):
        command_id = self.store.add_command(kind, params, self.clock.now())
        self.assertEqual(self.runner.run_pending(), 1)
        return self.store.get_command(command_id)

    def test_revoke_exempt_and_not_recidive(self):
        self.engine.handle([_event()])
        [action] = self.store.list_actions(in_progress=True, limit=10)
        done = self._run("revoke", action_id=action.id, exempt="7d", not_recidive=True)
        self.assertEqual((done.state, done.result), ("done", "revoked"))
        self.assertIsNone(self._entry())
        stored = self.store.get_action(action.id)
        self.assertFalse(stored.counts_for_recidive)
        [exemption] = self.store.list_exemptions()
        self.assertEqual((exemption.network, exemption.until), (IP + "/32", T0 + timedelta(days=7)))
        history = self.store.get_source(IP)
        self.assertFalse(history.actions[0].counts_for_recidive)
        self.assertEqual(history.actions[0].ends_at, T0)
        # La source exemptee n'est plus visee.
        self.clock.now_value = T0 + timedelta(hours=2)
        [decision] = self.engine.handle([_event(at=T0 + timedelta(hours=2))])
        self.assertEqual(decision.reasons[-1].code, "exempt_network")

    def test_not_recidive_resets_the_tier(self):
        self.engine.handle([_event()])
        [action] = self.store.list_actions(in_progress=True, limit=10)
        self._run("not_recidive", action_id=action.id)
        self.clock.now_value = T0 + timedelta(hours=2)
        self.actuator.reconcile(self.clock.now())
        [second] = self.engine.handle([_event(at=T0 + timedelta(hours=2))])
        self.assertEqual(second.tier_index, 0)

    def test_revoke_policy_and_revoke_all(self):
        self.engine.handle([_event(), _event(ip="198.51.100.9")])
        done = self._run("revoke_policy", policy_id="scan")
        self.assertEqual(done.result_params, {"count": 2})
        self.assertEqual(self.blocklist.list_entries(), ())
        self.assertEqual({a.finished_by for a in self.store.list_actions(in_progress=False, limit=10)}, {"policy"})
        self.assertEqual(self._run("revoke_all").result_params, {"count": 0})

    def test_unknown_action_and_reload(self):
        self.assertEqual(self._run("revoke", action_id="nope").result, "unknown_action")
        self.assertEqual(self._run("reload").result, "reloaded")
        self.assertEqual(self.reloads, [1])

    def test_forget_source_refused_while_an_action_runs(self):
        self.engine.handle([_event()])
        self.assertEqual(self._run("forget_source", ip=IP).result, "source_has_action")
        self._run("revoke_all")
        self.assertEqual(self._run("forget_source", ip=IP).result, "source_forgotten")
        self.assertIsNone(self.store.get_source(IP))

    def test_remove_exemption(self):
        self.engine.handle([_event()])
        [action] = self.store.list_actions(in_progress=True, limit=10)
        self._run("revoke", action_id=action.id, exempt="forever")
        self.assertIsNone(self.store.list_exemptions()[0].until)
        self.assertEqual(self._run("remove_exemption", network=IP + "/32").result, "exemption_removed")
        self.assertEqual(self.store.list_exemptions(), [])

    def test_finished_commands_and_actions_are_purged(self):
        self.engine.handle([_event()])
        self._run("revoke_all")
        later = T0 + timedelta(days=100)
        self.engine.maintenance(later)
        self.runner.maintenance(later)
        self.assertEqual(self.store.list_actions(in_progress=False, limit=10), [])
        self.assertIsNone(self.store.get_command(1))


if __name__ == "__main__":
    unittest.main()
