"""I/O reelle sur un dossier temporaire - jamais un double du
filesystem (meme discipline que test_json_config_repository.py)."""
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path

from omega_serv.domain.instances.entities import InstanceEntry
from omega_serv.infrastructure.filesystem.local_filesystem import LocalFilesystem
from omega_serv.infrastructure.instances.json_instance_registry import JsonInstanceRegistry


class TestJsonInstanceRegistry(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.registry_path = Path(self._tmp.name) / "config" / "instances.json"
        self.registry = JsonInstanceRegistry(LocalFilesystem(), self.registry_path)

    def tearDown(self):
        self._tmp.cleanup()

    def test_load_returns_empty_list_when_file_absent(self):
        self.assertEqual(self.registry.load(), [])

    def test_save_then_load_round_trips(self):
        entries = [
            InstanceEntry(
                name="prod", path=Path("/a/omega-serv"), bind="127.0.0.1", port=8080,
                service_name="omega-serv", created_at=datetime(2026, 9, 11, 10, 0, tzinfo=timezone.utc),
            ),
            InstanceEntry(
                name="test", path=Path("/a/omega-serv-test"), bind="127.0.0.1", port=8081,
                service_name="omega-serv-test", created_at=datetime(2026, 9, 11, 11, 0, tzinfo=timezone.utc),
            ),
        ]
        self.registry.save(entries)
        self.assertEqual(self.registry.load(), entries)

    def test_save_creates_parent_directory(self):
        self.assertFalse(self.registry_path.parent.exists())
        self.registry.save([])
        self.assertTrue(self.registry_path.parent.exists())

    def test_registry_directory_created_with_restricted_permissions(self):
        self.registry.save([])
        mode = self.registry_path.parent.stat().st_mode & 0o777
        self.assertEqual(mode, 0o700)


if __name__ == "__main__":
    unittest.main()
