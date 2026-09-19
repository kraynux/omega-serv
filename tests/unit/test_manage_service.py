import unittest

from omega_serv.application.services.manage_service import (
    ManageServiceResult,
    disable_service,
    enable_service,
    get_service_status,
    reload_service,
    restart_service,
    start_service,
    stop_service,
)
from omega_serv.domain.services.entities import ServiceStatus
from omega_serv.domain.services.exceptions import (
    ServiceControlError,
    ServiceNotFoundError,
    ServiceStatusError,
)


class _FakeManager:
    def __init__(self, raises=None, status_value=None):
        self._raises = raises
        self._status_value = status_value
        self.calls = []

    def _maybe_raise(self, name, service_name):
        self.calls.append((name, service_name))
        if self._raises is not None:
            raise self._raises

    def start(self, service_name):
        self._maybe_raise("start", service_name)

    def stop(self, service_name):
        self._maybe_raise("stop", service_name)

    def restart(self, service_name):
        self._maybe_raise("restart", service_name)

    def reload(self, service_name):
        self._maybe_raise("reload", service_name)

    def enable(self, service_name):
        self._maybe_raise("enable", service_name)

    def disable(self, service_name):
        self._maybe_raise("disable", service_name)

    def status(self, service_name):
        self._maybe_raise("status", service_name)
        return self._status_value


class TestManageServiceControlOperations(unittest.TestCase):
    def test_start_success(self):
        manager = _FakeManager()
        result = start_service(manager, "omega-serv")
        self.assertTrue(result.success)
        self.assertEqual(manager.calls, [("start", "omega-serv")])

    def test_stop_success(self):
        result = stop_service(_FakeManager(), "omega-serv")
        self.assertTrue(result.success)

    def test_restart_success(self):
        result = restart_service(_FakeManager(), "omega-serv")
        self.assertTrue(result.success)

    def test_reload_success(self):
        manager = _FakeManager()
        result = reload_service(manager, "omega-serv")
        self.assertTrue(result.success)
        self.assertEqual(manager.calls, [("reload", "omega-serv")])

    def test_reload_not_found_reported_as_failure_not_exception(self):
        manager = _FakeManager(raises=ServiceNotFoundError("ghost", "systemd"))
        result = reload_service(manager, "ghost")
        self.assertFalse(result.success)

    def test_enable_success(self):
        result = enable_service(_FakeManager(), "omega-serv")
        self.assertTrue(result.success)

    def test_disable_success(self):
        result = disable_service(_FakeManager(), "omega-serv")
        self.assertTrue(result.success)

    def test_not_found_reported_as_failure_not_exception(self):
        manager = _FakeManager(raises=ServiceNotFoundError("ghost", "systemd"))
        result = start_service(manager, "ghost")
        self.assertFalse(result.success)
        self.assertIn("ghost", result.message)

    def test_control_error_reported_as_failure_not_exception(self):
        manager = _FakeManager(raises=ServiceControlError("svc", "start", "denied", "systemd"))
        result = start_service(manager, "svc")
        self.assertFalse(result.success)


class TestGetServiceStatus(unittest.TestCase):
    def test_returns_status_on_success(self):
        expected = ServiceStatus(service_name="omega-serv", active=True, enabled=True, sub_state="running")
        manager = _FakeManager(status_value=expected)
        result = get_service_status(manager, "omega-serv")
        self.assertIsInstance(result, ServiceStatus)
        self.assertTrue(result.is_running)

    def test_returns_failure_result_when_not_found(self):
        manager = _FakeManager(raises=ServiceNotFoundError("ghost", "systemd"))
        result = get_service_status(manager, "ghost")
        self.assertIsInstance(result, ManageServiceResult)
        self.assertFalse(result.success)

    def test_returns_failure_result_on_status_error(self):
        manager = _FakeManager(raises=ServiceStatusError("svc", "timeout", "systemd"))
        result = get_service_status(manager, "svc")
        self.assertIsInstance(result, ManageServiceResult)
        self.assertFalse(result.success)


if __name__ == "__main__":
    unittest.main()
