import tempfile
import unittest
from datetime import UTC, datetime
from pathlib import Path

from omega_serv.application.services.resolve_current_service_name import (
    DEFAULT_SERVICE_NAME,
    resolve_current_service_name,
)
from omega_serv.domain.instances.entities import InstanceEntry
from omega_serv.infrastructure.config.json_settings_store import JsonSettingsStore
from omega_serv.infrastructure.filesystem.local_filesystem import LocalFilesystem
from omega_serv.infrastructure.instances.json_instance_registry import JsonInstanceRegistry


class TestResolveCurrentServiceName(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.root = Path(self._tmp.name)
        self.filesystem = LocalFilesystem()
        self.settings_store = JsonSettingsStore(self.root / "settings.json")
        self.instance_registry = JsonInstanceRegistry(self.filesystem, self.root / "instances.json")

    def tearDown(self):
        self._tmp.cleanup()

    def test_defaults_to_omega_serv_when_nothing_registered(self):
        name = resolve_current_service_name(self.instance_registry, self.filesystem, self.settings_store, self.root)
        self.assertEqual(name, DEFAULT_SERVICE_NAME)

    def test_uses_settings_store_value_when_no_instance_registered(self):
        self.settings_store.set("service_name", "mon-service")
        name = resolve_current_service_name(self.instance_registry, self.filesystem, self.settings_store, self.root)
        self.assertEqual(name, "mon-service")

    def test_registered_instance_wins_over_settings_store(self):
        self.settings_store.set("service_name", "ignore-moi")
        self.instance_registry.save([
            InstanceEntry(
                name="prod", path=self.filesystem.resolve_real_path(self.root),
                bind="127.0.0.1", port=8080, service_name="omega-serv-prod",
                created_at=datetime.now(UTC),
            ),
        ])
        name = resolve_current_service_name(self.instance_registry, self.filesystem, self.settings_store, self.root)
        self.assertEqual(name, "omega-serv-prod")


if __name__ == "__main__":
    unittest.main()
