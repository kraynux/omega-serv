import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path

from omega_serv.application.instances.register_instance import register_instance
from omega_serv.infrastructure.filesystem.local_filesystem import LocalFilesystem
from omega_serv.infrastructure.instances.json_instance_registry import JsonInstanceRegistry


class _FixedClock:
    def now(self):
        return datetime(2026, 9, 11, tzinfo=timezone.utc)


class TestRegisterInstance(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.root = Path(self._tmp.name)
        self.filesystem = LocalFilesystem()
        self.registry = JsonInstanceRegistry(self.filesystem, self.root / "instances.json")
        self.clock = _FixedClock()

    def tearDown(self):
        self._tmp.cleanup()

    def test_registers_a_valid_instance(self):
        instance_dir = self.root / "omega-serv-prod"
        instance_dir.mkdir()
        error = register_instance(
            self.registry, self.filesystem, self.clock,
            name="prod", path=instance_dir, bind="127.0.0.1", port=8080, service_name="omega-serv",
        )
        self.assertIsNone(error)
        entries = self.registry.load()
        self.assertEqual(len(entries), 1)
        self.assertEqual(entries[0].name, "prod")
        self.assertEqual(entries[0].path, instance_dir.resolve())

    def test_rejects_duplicate_name_without_writing(self):
        instance_dir = self.root / "omega-serv-prod"
        instance_dir.mkdir()
        register_instance(
            self.registry, self.filesystem, self.clock,
            name="prod", path=instance_dir, bind="127.0.0.1", port=8080, service_name="omega-serv",
        )
        other_dir = self.root / "omega-serv-other"
        other_dir.mkdir()
        error = register_instance(
            self.registry, self.filesystem, self.clock,
            name="prod", path=other_dir, bind="127.0.0.1", port=8081, service_name="omega-serv-other",
        )
        self.assertIsNotNone(error)
        self.assertEqual(len(self.registry.load()), 1)

    def test_resolves_path_before_storing(self):
        real_dir = self.root / "real-instance"
        real_dir.mkdir()
        symlink_path = self.root / "symlinked-instance"
        symlink_path.symlink_to(real_dir)
        register_instance(
            self.registry, self.filesystem, self.clock,
            name="prod", path=symlink_path, bind="127.0.0.1", port=8080, service_name="omega-serv",
        )
        entries = self.registry.load()
        self.assertEqual(entries[0].path, real_dir.resolve())


if __name__ == "__main__":
    unittest.main()
