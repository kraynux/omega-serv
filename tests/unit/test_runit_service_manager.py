import tempfile
import unittest
from pathlib import Path

from omega_serv.domain.services.exceptions import ServiceControlError, ServiceNotFoundError
from omega_serv.infrastructure.services.runit_service_manager import RunitServiceManager
from omega_serv.ports.process_runner_port import ProcessResult


class _FakeProcessRunner:
    def __init__(self, responses: dict):
        self._responses = responses

    def run(self, args, input_text=None, timeout=None):
        key = tuple(args)
        return self._responses.get(key, ProcessResult(1, "", "unmapped call"))


class TestRunitServiceManager(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.root = Path(self._tmp.name)
        self.service_dir = self.root / "sv"
        self.run_dir = self.root / "service"
        self.service_dir.mkdir()
        self.run_dir.mkdir()

    def tearDown(self):
        self._tmp.cleanup()

    def _svc_path(self, name):
        return str(self.service_dir / name)

    def test_start_success(self):
        runner = _FakeProcessRunner({("sv", "up", self._svc_path("svc")): ProcessResult(0, "", "")})
        manager = RunitServiceManager(runner, str(self.service_dir), str(self.run_dir))
        self.assertTrue(manager.start("svc"))

    def test_start_not_found(self):
        runner = _FakeProcessRunner({("sv", "up", self._svc_path("ghost")): ProcessResult(1, "", "fail: ghost: not found")})
        manager = RunitServiceManager(runner, str(self.service_dir), str(self.run_dir))
        with self.assertRaises(ServiceNotFoundError):
            manager.start("ghost")

    def test_start_control_error(self):
        runner = _FakeProcessRunner({("sv", "up", self._svc_path("svc")): ProcessResult(1, "", "permission denied")})
        manager = RunitServiceManager(runner, str(self.service_dir), str(self.run_dir))
        with self.assertRaises(ServiceControlError):
            manager.start("svc")

    def test_reload_success(self):
        runner = _FakeProcessRunner({("sv", "reload", self._svc_path("svc")): ProcessResult(0, "", "")})
        manager = RunitServiceManager(runner, str(self.service_dir), str(self.run_dir))
        self.assertTrue(manager.reload("svc"))

    def test_reload_control_error(self):
        runner = _FakeProcessRunner({("sv", "reload", self._svc_path("svc")): ProcessResult(1, "", "permission denied")})
        manager = RunitServiceManager(runner, str(self.service_dir), str(self.run_dir))
        with self.assertRaises(ServiceControlError):
            manager.reload("svc")

    def test_enable_creates_symlink(self):
        (self.service_dir / "svc").mkdir()
        manager = RunitServiceManager(_FakeProcessRunner({}), str(self.service_dir), str(self.run_dir))
        self.assertTrue(manager.enable("svc"))
        self.assertTrue((self.run_dir / "svc").is_symlink())

    def test_enable_missing_service_raises(self):
        manager = RunitServiceManager(_FakeProcessRunner({}), str(self.service_dir), str(self.run_dir))
        with self.assertRaises(ServiceNotFoundError):
            manager.enable("ghost")

    def test_disable_removes_symlink(self):
        (self.service_dir / "svc").mkdir()
        (self.run_dir / "svc").symlink_to(self.service_dir / "svc")
        manager = RunitServiceManager(_FakeProcessRunner({}), str(self.service_dir), str(self.run_dir))
        self.assertTrue(manager.disable("svc"))
        self.assertFalse((self.run_dir / "svc").exists())

    def test_is_enabled_reflects_symlink_presence(self):
        manager = RunitServiceManager(_FakeProcessRunner({}), str(self.service_dir), str(self.run_dir))
        self.assertFalse(manager.is_enabled("svc"))
        (self.service_dir / "svc").mkdir()
        manager.enable("svc")
        self.assertTrue(manager.is_enabled("svc"))

    def test_status_running(self):
        runner = _FakeProcessRunner({("sv", "status", self._svc_path("svc")): ProcessResult(0, "run: svc: (pid 123) 10s", "")})
        manager = RunitServiceManager(runner, str(self.service_dir), str(self.run_dir))
        status = manager.status("svc")
        self.assertTrue(status.active)
        self.assertEqual(status.sub_state, "running")

    def test_manager_type(self):
        manager = RunitServiceManager(_FakeProcessRunner({}), str(self.service_dir), str(self.run_dir))
        self.assertEqual(manager.manager_type(), "runit")


if __name__ == "__main__":
    unittest.main()
