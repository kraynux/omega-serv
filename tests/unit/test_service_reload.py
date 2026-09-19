"""Retour utilisateur 2026-09-14 : "il faut qu'il puisse pas taper de
commande a chaque fois qu'il change le mode de blocage ou met une
nouvelle regle" - reload_service_after_waf_change() declenche le
rechargement a chaud (SIGHUP) automatiquement. `ServiceManagerPort`
double en memoire (pas de vrai systemctl/sudo en test), meme discipline
que test_tui_service.py - jamais le vrai registre multi-instance de la
machine (`instance_registry_path` injecte vers un fichier temporaire)."""
from __future__ import annotations

import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path

from omega_serv.bootstrap.container import DependencyContainer
from omega_serv.domain.instances.entities import InstanceEntry
from omega_serv.domain.services.entities import ServiceStatus
from omega_serv.domain.services.exceptions import ServiceControlError, ServiceNotFoundError
from omega_serv.interfaces.tui.screens._service_reload import reload_service_after_waf_change
from omega_serv.ports.service_manager_port import ServiceManagerType


class _FakeServiceManager:
    def __init__(self, *, active: bool = True, known_service: str = "omega-serv", reload_succeeds: bool = True):
        self._active = active
        self._known_service = known_service
        self._reload_succeeds = reload_succeeds
        self.reload_calls: list[str] = []

    def manager_type(self) -> ServiceManagerType:
        return "systemd"

    def start(self, service_name: str) -> bool:
        return True

    def stop(self, service_name: str) -> bool:
        return True

    def restart(self, service_name: str) -> bool:
        return True

    def reload(self, service_name: str) -> bool:
        self.reload_calls.append(service_name)
        if service_name != self._known_service:
            raise ServiceNotFoundError(service_name, "systemd")
        if not self._reload_succeeds:
            raise ServiceControlError(service_name, "reload", "ExecReload absente", "systemd")
        return True

    def enable(self, service_name: str) -> bool:
        return True

    def disable(self, service_name: str) -> bool:
        return True

    def status(self, service_name: str) -> ServiceStatus:
        return ServiceStatus(
            service_name=service_name, active=self._active, enabled=True,
            state="active" if self._active else "inactive", sub_state="running", description="",
        )

    def is_active(self, service_name: str) -> bool:
        return self._active and service_name == self._known_service

    def is_enabled(self, service_name: str) -> bool:
        return True

    def is_available(self) -> bool:
        return True


class TestReloadServiceAfterWafChange(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.root = Path(self._tmp.name)
        self.registry_path = self.root.parent / f"{self.root.name}-instances.json"

    def tearDown(self):
        self._tmp.cleanup()

    def _container(self, manager: _FakeServiceManager | None) -> DependencyContainer:
        factory = (lambda: manager) if manager is not None else (lambda: None)
        return DependencyContainer(
            project_root=self.root, service_manager_factory=factory, instance_registry_path=self.registry_path,
        )

    def test_no_manager_factory_returns_none_silently(self):
        container = DependencyContainer(project_root=self.root, instance_registry_path=self.registry_path)
        self.assertIsNone(reload_service_after_waf_change(container))

    def test_factory_returning_none_returns_none_silently(self):
        container = self._container(None)
        self.assertIsNone(reload_service_after_waf_change(container))

    def test_inactive_service_is_never_reloaded(self):
        """Retour utilisateur implicite : pas de notification "service
        introuvable" genante pour qui developpe sans jamais avoir
        installe de service - situation normale, pas une erreur."""
        manager = _FakeServiceManager(active=False)
        container = self._container(manager)
        self.assertIsNone(reload_service_after_waf_change(container))
        self.assertEqual(manager.reload_calls, [])

    def test_active_service_is_reloaded_and_a_message_is_returned(self):
        manager = _FakeServiceManager(active=True)
        container = self._container(manager)
        message = reload_service_after_waf_change(container)
        self.assertIsNotNone(message)
        self.assertEqual(manager.reload_calls, ["omega-serv"])

    def test_reload_failure_returns_a_clean_message_never_raises(self):
        manager = _FakeServiceManager(active=True, reload_succeeds=False)
        container = self._container(manager)
        message = reload_service_after_waf_change(container)
        self.assertIsNotNone(message)
        assert message is not None
        self.assertIn("ExecReload", message)

    def test_uses_the_registered_instance_service_name_when_present(self):
        manager = _FakeServiceManager(active=True, known_service="my-custom-name")
        container = self._container(manager)
        real_path = container.filesystem.resolve_real_path(self.root)
        container.instance_registry.save([InstanceEntry(
            name="test", path=real_path, bind="127.0.0.1", port=8080,
            service_name="my-custom-name", created_at=datetime(2026, 9, 14, tzinfo=timezone.utc),
        )])
        message = reload_service_after_waf_change(container)
        self.assertIsNotNone(message)
        self.assertEqual(manager.reload_calls, ["my-custom-name"])

    def test_uses_the_persisted_settings_service_name_when_not_registered(self):
        manager = _FakeServiceManager(active=True, known_service="renamed-service")
        container = self._container(manager)
        container.settings_store.set("service_name", "renamed-service")
        message = reload_service_after_waf_change(container)
        self.assertIsNotNone(message)
        self.assertEqual(manager.reload_calls, ["renamed-service"])


if __name__ == "__main__":
    unittest.main()
