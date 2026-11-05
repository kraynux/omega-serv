"""Branchement RIPOSTE, lot 2 (OMEGA-SERV_PLAN-DETAILLE_RIPOSTE.md §3.1) : processus serveur (D18b),
option validee, superviseur avec garde-fou, processus enfant lance par posix_spawn."""
import os
import signal
import sys
import unittest

from omega_serv.bootstrap.early_language import is_server_process
from omega_serv.domain.config.entities import OmegaServConfig
from omega_serv.domain.config.validation import validate_config
from omega_serv.infrastructure.process.child_process import SpawnedChild
from omega_serv.interfaces.cli.riposte_commands import (
    MAX_RESTARTS_IN_WINDOW,
    RiposteChildSupervisor,
    build_riposte_supervisor,
)


class TestServerProcess(unittest.TestCase):
    def test_riposte_run_keeps_french_messages_like_serve(self):
        self.assertTrue(is_server_process(["riposte", "run"]))
        self.assertTrue(is_server_process(["--config", "x.json", "riposte", "run"]))
        self.assertFalse(is_server_process(["riposte", "status"]))  # commande d'interface : traduite
        self.assertFalse(is_server_process(["riposte"]))
        self.assertTrue(is_server_process(["serve"]))


class TestOptionValidation(unittest.TestCase):
    def _config(self, riposte):
        return OmegaServConfig.from_dict({"server": {"bind": "127.0.0.1", "port": 8080}, "options": {"riposte": riposte}})

    def test_disabled_option_is_never_validated(self):
        self.assertEqual(
            [e for e in validate_config(self._config({"enabled": False, "max_active_bans": 0})) if "riposte" in e], [],
        )

    def test_enabled_option_is_validated(self):
        errors = validate_config(self._config({"enabled": True, "max_active_bans": 0}))
        self.assertTrue(any("max_active_bans" in e for e in errors), errors)

    def test_decoy_profile_must_exist_in_active_defense(self):
        policy = {"id": "leurre", "name": "Leurre", "then": {"action": "decoy", "decoy_profile": "fake_admin"}}
        errors = validate_config(self._config({"enabled": True, "policies": [policy]}))
        self.assertTrue(any("fake_admin" in e for e in errors), errors)

    def test_no_supervisor_when_disabled(self):
        self.assertIsNone(build_riposte_supervisor(self._config({"enabled": False}), "c.json"))
        supervisor = build_riposte_supervisor(self._config({"enabled": True}), "c.json")
        self.assertIsNotNone(supervisor)


class _FakeChild:
    def __init__(self, pid):
        self.pid = pid
        self.running = True
        self.signals = []
        self.stopped = False

    def is_running(self):
        return self.running

    def send_signal(self, sig):
        self.signals.append(sig)

    def stop(self, _grace):
        self.stopped = True
        self.running = False


class TestSupervisor(unittest.TestCase):
    def setUp(self):
        self.children = []
        self.now = 0.0
        self.logs = []

        def spawn(_argv):
            child = _FakeChild(1000 + len(self.children))
            self.children.append(child)
            return child

        self.supervisor = RiposteChildSupervisor(["x"], spawn=spawn, monotonic=lambda: self.now, log=self.logs.append)
        self.supervisor.start()

    def test_dead_child_is_restarted(self):
        self.children[0].running = False
        self.supervisor.tick()
        self.assertEqual(len(self.children), 2)
        self.assertIn("relance", self.logs[-1])

    def test_gives_up_after_too_many_deaths_without_touching_the_server(self):
        for _ in range(MAX_RESTARTS_IN_WINDOW + 1):
            self.children[-1].running = False
            self.supervisor.tick()
            self.now += 1
        self.assertTrue(self.supervisor.gave_up)
        count = len(self.children)
        self.supervisor.tick()
        self.assertEqual(len(self.children), count)  # plus de relance
        self.assertIn("plus de relance", self.logs[-1])

    def test_deaths_spread_over_time_never_give_up(self):
        for _ in range(MAX_RESTARTS_IN_WINDOW * 3):
            self.children[-1].running = False
            self.supervisor.tick()
            self.now += 61
        self.assertFalse(self.supervisor.gave_up)

    def test_reload_and_stop(self):
        self.supervisor.reload()
        self.assertEqual(self.children[0].signals, [signal.SIGHUP])
        self.supervisor.stop()
        self.assertTrue(self.children[0].stopped)

    def test_spawn_failure_never_raises(self):
        def broken(_argv):
            raise OSError("introuvable")
        supervisor = RiposteChildSupervisor(["x"], spawn=broken, log=self.logs.append)
        supervisor.start()
        self.assertTrue(supervisor.gave_up)
        supervisor.tick()


class TestSpawnedChild(unittest.TestCase):
    def _sleeper(self):
        return SpawnedChild.spawn([sys.executable, "-c", "import time; time.sleep(30)"])

    def test_spawn_stop(self):
        child = self._sleeper()
        self.assertTrue(child.is_running())
        child.stop(5)
        self.assertFalse(child.is_running())

    def test_child_reaped_by_someone_else_counts_as_ended(self):
        """Mode boost : le superviseur recolte par waitpid(-1) et peut prendre ce pid a sa place."""
        child = self._sleeper()
        os.kill(child.pid, signal.SIGKILL)
        os.waitpid(child.pid, 0)  # « quelqu'un d'autre » recolte
        self.assertFalse(child.is_running())
        child.stop(1)  # jamais d'exception

    def test_stop_escalates_to_sigkill(self):
        child = SpawnedChild.spawn([sys.executable, "-c",
                                    "import signal, time; signal.signal(signal.SIGTERM, signal.SIG_IGN); time.sleep(30)"])
        import time
        time.sleep(0.5)  # laisse l'enfant installer son gestionnaire
        started = time.monotonic()
        child.stop(0.5)
        self.assertFalse(child.is_running())
        self.assertLess(time.monotonic() - started, 5)


if __name__ == "__main__":
    unittest.main()
