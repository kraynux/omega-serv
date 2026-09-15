# Copyright (c) 2026 kraynux - kraynux@proton.me - Licence MIT (voir fichier LICENSE)
import unittest

from omega_serv.domain.services.exceptions import ServiceControlError, ServiceNotFoundError
from omega_serv.infrastructure.services.openrc_service_manager import OpenRCServiceManager
from omega_serv.ports.process_runner_port import ProcessResult


class _FakeProcessRunner:
    def __init__(self, responses: dict):
        self._responses = responses

    def run(self, args, input_text=None, timeout=None):
        key = tuple(args)
        return self._responses.get(key, ProcessResult(1, "", "unmapped call"))


class TestOpenRCServiceManager(unittest.TestCase):
    def test_start_success(self):
        runner = _FakeProcessRunner({("rc-service", "svc", "start"): ProcessResult(0, "", "")})
        manager = OpenRCServiceManager(runner)
        self.assertTrue(manager.start("svc"))

    def test_start_not_found(self):
        runner = _FakeProcessRunner({("rc-service", "ghost", "start"): ProcessResult(1, "", "service not found")})
        manager = OpenRCServiceManager(runner)
        with self.assertRaises(ServiceNotFoundError):
            manager.start("ghost")

    def test_start_control_error(self):
        runner = _FakeProcessRunner({("rc-service", "svc", "start"): ProcessResult(1, "", "permission denied")})
        manager = OpenRCServiceManager(runner)
        with self.assertRaises(ServiceControlError):
            manager.start("svc")

    def test_reload_success(self):
        # Retour utilisateur 2026-09-11 : meme verbe que start/stop/
        # restart, echoue proprement si le script rc ne l'implemente pas.
        runner = _FakeProcessRunner({("rc-service", "svc", "reload"): ProcessResult(0, "", "")})
        manager = OpenRCServiceManager(runner)
        self.assertTrue(manager.reload("svc"))

    def test_reload_not_supported_by_script_raises_control_error(self):
        runner = _FakeProcessRunner({("rc-service", "svc", "reload"): ProcessResult(1, "", "reload not supported")})
        manager = OpenRCServiceManager(runner)
        with self.assertRaises(ServiceControlError):
            manager.reload("svc")

    def test_enable_uses_rc_update_add(self):
        runner = _FakeProcessRunner({("rc-update", "add", "svc"): ProcessResult(0, "", "")})
        manager = OpenRCServiceManager(runner)
        self.assertTrue(manager.enable("svc"))

    def test_disable_uses_rc_update_del(self):
        runner = _FakeProcessRunner({("rc-update", "del", "svc"): ProcessResult(0, "", "")})
        manager = OpenRCServiceManager(runner)
        self.assertTrue(manager.disable("svc"))

    def test_is_enabled_checks_rc_update_show_output(self):
        runner = _FakeProcessRunner({("rc-update", "show"): ProcessResult(0, "svc | default\nother | default\n", "")})
        manager = OpenRCServiceManager(runner)
        self.assertTrue(manager.is_enabled("svc"))
        self.assertFalse(manager.is_enabled("missing"))

    def test_status_active(self):
        runner = _FakeProcessRunner({
            ("rc-service", "svc", "status"): ProcessResult(0, "status: started", ""),
            ("rc-update", "show"): ProcessResult(0, "svc | default\n", ""),
        })
        manager = OpenRCServiceManager(runner)
        status = manager.status("svc")
        self.assertTrue(status.active)
        self.assertTrue(status.enabled)

    def test_manager_type(self):
        self.assertEqual(OpenRCServiceManager(_FakeProcessRunner({})).manager_type(), "openrc")


if __name__ == "__main__":
    unittest.main()
