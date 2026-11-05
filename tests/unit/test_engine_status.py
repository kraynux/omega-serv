"""Statut du moteur affiche (ecran Etat, engine status) et detection du serveur en marche (fichier PID)."""
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from omega_serv.application.server.engine_state import EngineState, write_engine_state
from omega_serv.application.server.engine_status import engine_status, engine_status_rows
from omega_serv.bootstrap.container import DependencyContainer
from omega_serv.domain.config.entities import OmegaServConfig
from omega_serv.infrastructure.filesystem.local_filesystem import LocalFilesystem


def _dead_pid() -> int:
    child = subprocess.Popen([sys.executable, "-c", "pass"])
    child.wait()
    return child.pid


class TestEngineStatus(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.root = Path(self._tmp.name)
        (self.root / "var" / "run").mkdir(parents=True)
        self.fs = LocalFilesystem()
        self.native = OmegaServConfig.from_dict({"server": {"engine": "native"}})

    def tearDown(self):
        self._tmp.cleanup()

    def _pid_file(self, pid: int) -> None:
        (self.root / "var" / "run" / "omega-serv.pid").write_text(str(pid))

    def test_stopped_server_shows_forecast(self):
        status = engine_status(self.fs, self.root, self.native, "binary_missing")
        self.assertIsNone(status.running)
        rows = engine_status_rows(status)
        self.assertIn("prévision", rows[0][1])
        self.assertTrue(any(label == "Raison" and "binaire natif absent" in value for label, value, _ in rows))

    def test_running_server_shows_real_state(self):
        self._pid_file(os.getpid())
        write_engine_state(self.fs, self.root, EngineState("native", "native", supervisor_pid=os.getpid(),
                                                           native_pid=123, binary_version="0.1.0", generation=4))
        status = engine_status(self.fs, self.root, self.native, None)
        self.assertIsNotNone(status.running)
        rows = {label: value for label, value, _ in engine_status_rows(status)}
        self.assertEqual(rows["Génération"], "4")

    def test_stale_state_of_a_dead_server_is_not_presented_as_current(self):
        dead = _dead_pid()
        self._pid_file(dead)
        write_engine_state(self.fs, self.root, EngineState("native", "native", supervisor_pid=dead))
        self.assertIsNone(engine_status(self.fs, self.root, self.native, None).running)

    def test_container_server_running_reads_the_pid_correctly(self):
        # 2026-11-02 : le second element de pid_file_status (« illisible ») etait pris pour « vivant ».
        container = DependencyContainer(project_root=self.root)
        self.assertFalse(container.server_running())
        self._pid_file(os.getpid())
        self.assertTrue(container.server_running())
        self._pid_file(_dead_pid())
        self.assertFalse(container.server_running())


if __name__ == "__main__":
    unittest.main()
