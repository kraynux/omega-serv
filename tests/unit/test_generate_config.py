import tempfile
import unittest
from pathlib import Path

from omega_serv.application.config.generate_config import generate_default_config
from omega_serv.infrastructure.config.json_config_repository import JsonConfigRepository
from omega_serv.infrastructure.filesystem.local_filesystem import LocalFilesystem


class TestGenerateDefaultConfig(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.root = Path(self._tmp.name)
        self.config_path = self.root / "omega-serve.json"
        self.filesystem = LocalFilesystem()
        self.repo = JsonConfigRepository(self.filesystem, backups_dir=self.root / "backups")

    def tearDown(self):
        self._tmp.cleanup()

    def test_creates_file_when_absent(self):
        result = generate_default_config(self.repo, self.filesystem, self.config_path)
        self.assertTrue(result.success)
        self.assertTrue(self.config_path.exists())

    def test_refuses_to_overwrite_without_force(self):
        generate_default_config(self.repo, self.filesystem, self.config_path)
        result = generate_default_config(self.repo, self.filesystem, self.config_path)
        self.assertFalse(result.success)

    def test_overwrites_with_force(self):
        generate_default_config(self.repo, self.filesystem, self.config_path)
        result = generate_default_config(self.repo, self.filesystem, self.config_path, force=True)
        self.assertTrue(result.success)


if __name__ == "__main__":
    unittest.main()
