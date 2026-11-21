"""Superviseur reduit du natif (lot 5 memoire, 2026-11-19, OMEGA-SERV_ETUDE_PROXY_ET_MEMOIRE.md §8) : briques testees
sans binaire. Le parcours complet (re-execution, rechargement, relance, arret) est dans
tests/integration/test_native_reduced_supervisor.py."""
from __future__ import annotations

import os
import tempfile
import time
import unittest
from dataclasses import fields
from pathlib import Path

from omega_serv.application.server.engine_state import ENGINE_STATE_RELATIVE_PATH, EngineState
from omega_serv.domain.config.entities import OmegaServConfig
from omega_serv.infrastructure.server import native_ipc as ipc
from omega_serv.infrastructure.server.native_engine import SnapshotFile
from omega_serv.interfaces.cli import native_watch
from omega_serv.interfaces.cli.native_watch import (
    ReducedSupervisor,
    _declaration_due_task,
    run_in_fork,
)
from omega_serv.interfaces.cli.serve_native import (
    _restart_blocker,
    reload_fingerprint,
    restart_blocker,
)


def _config(options: dict | None = None, port: int = 8080) -> OmegaServConfig:
    return OmegaServConfig.from_dict({"server": {"bind": "127.0.0.1", "port": port}, "options": options or {}})


def _boom() -> object:
    raise RuntimeError("echec dans le fils")


def _sleep_forever() -> object:
    time.sleep(60)
    return None


class TestRunInFork(unittest.TestCase):
    def test_result_comes_back_as_json(self):
        self.assertEqual(run_in_fork(lambda: {"ok": True, "pid": os.getpid()}, 10)["ok"], True)  # type: ignore[index]

    def test_task_runs_in_another_process(self):
        result = run_in_fork(lambda: os.getpid(), 10)
        self.assertNotEqual(result, os.getpid())

    def test_failure_is_none(self):
        self.assertIsNone(run_in_fork(_boom, 10))

    def test_timeout_kills_the_child(self):
        started = time.monotonic()
        self.assertIsNone(run_in_fork(_sleep_forever, 0.5))
        self.assertLess(time.monotonic() - started, 10)

    def test_declaration_not_due_without_declaration(self):
        with tempfile.TemporaryDirectory() as root:
            self.assertIs(run_in_fork(lambda: _declaration_due_task(Path(root)), 30), False)


class TestStateFile(unittest.TestCase):
    def test_same_keys_and_order_as_engine_state(self):
        supervisor = ReducedSupervisor.__new__(ReducedSupervisor)
        supervisor.engine = _FakeEngine()
        supervisor.requested = "native"
        supervisor.notices = ["note"]
        supervisor.restarts = 0
        supervisor.last_reload = ""
        supervisor.security_config = None
        supervisor.security_pid = None
        payload = supervisor.state_payload()
        self.assertEqual(list(payload), [f.name for f in fields(EngineState)])
        self.assertEqual(EngineState(**{**payload, "reasons": (), "notices": ("note",)}).effective, "native")

    def test_same_path(self):
        self.assertEqual(native_watch.ENGINE_STATE_RELATIVE_PATH, ENGINE_STATE_RELATIVE_PATH)


class _FakeEngine:
    def __init__(self) -> None:
        from omega_serv.infrastructure.server.native_engine import NativeHealth
        self.health = NativeHealth()
        self.process = None
        self.binary_version = "0.1.0"
        self.generation = 1


class TestRestartBlocker(unittest.TestCase):
    def test_fingerprint_survives_json(self):
        import json
        config = _config()
        self.assertEqual(json.loads(json.dumps(reload_fingerprint(config))), reload_fingerprint(config))

    def test_identical_configuration_is_not_blocked(self):
        config = _config()
        self.assertIsNone(restart_blocker(reload_fingerprint(config), reload_fingerprint(config)))

    def test_port_change_is_named(self):
        old = _config()
        new = _config(port=8081)
        self.assertEqual(_restart_blocker(old, new), "server.port")

    def test_security_option_named(self):
        old = _config()
        new = _config(options={"waf": {"enabled": True}})
        label = _restart_blocker(old, new)
        self.assertIsNotNone(label)
        self.assertIn("options.waf", label or "")


class TestSnapshotFile(unittest.TestCase):
    def test_filled_and_sealed_in_place(self):
        fd = ipc.new_snapshot_memfd()
        snapshot = SnapshotFile(fd, 0, b"")
        try:
            ipc.fill_and_seal(fd, b'{"generation": 1}')
            self.assertEqual(os.pread(fd, 100, 0), b'{"generation": 1}')
            with self.assertRaises(OSError):
                os.write(fd, b"x")  # scelle : le natif lit toujours exactement ce qui a ete annonce
        finally:
            snapshot.close()
        self.assertEqual(snapshot.fd, -1)

    def test_config_frame_sized_matches_config_frame(self):
        data = b'{"generation": 3}'
        self.assertEqual(ipc.config_frame_sized(3, len(data), ipc.snapshot_digest(data)), ipc.config_frame(3, data))


if __name__ == "__main__":
    unittest.main()
