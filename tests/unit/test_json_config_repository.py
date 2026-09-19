import json
import tempfile
import unittest
from pathlib import Path

from omega_serv.domain.config.entities import OmegaServConfig
from omega_serv.domain.config.exceptions import ConfigLoadError
from omega_serv.infrastructure.config.json_config_repository import JsonConfigRepository
from omega_serv.infrastructure.filesystem.local_filesystem import LocalFilesystem


class TestJsonConfigRepository(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.root = Path(self._tmp.name)
        self.config_path = self.root / "omega-serve.json"
        self.backups_dir = self.root / "backups"
        self.repo = JsonConfigRepository(LocalFilesystem(), self.backups_dir)

    def tearDown(self):
        self._tmp.cleanup()

    def test_load_missing_file_raises(self):
        with self.assertRaises(ConfigLoadError):
            self.repo.load(self.config_path)

    def test_load_invalid_json_raises(self):
        self.config_path.write_text("{ not valid json")
        with self.assertRaises(ConfigLoadError):
            self.repo.load(self.config_path)

    def test_load_non_object_json_raises(self):
        self.config_path.write_text("[1, 2, 3]")
        with self.assertRaises(ConfigLoadError):
            self.repo.load(self.config_path)

    def test_save_then_load_round_trips(self):
        config = OmegaServConfig.from_dict({"server": {"port": 9090}})
        self.repo.save(self.config_path, config)

        reloaded = self.repo.load(self.config_path)
        self.assertEqual(reloaded.server.port, 9090)

    def test_save_writes_valid_json_with_trailing_newline(self):
        config = OmegaServConfig()
        self.repo.save(self.config_path, config)
        content = self.config_path.read_text()
        self.assertTrue(content.endswith("\n"))
        json.loads(content)  # ne doit pas lever

    def test_save_leaves_no_tmp_file_behind(self):
        config = OmegaServConfig()
        self.repo.save(self.config_path, config)
        tmp_path = self.config_path.with_name(self.config_path.name + ".tmp")
        self.assertFalse(tmp_path.exists())

    def test_save_backs_up_existing_file_before_overwrite(self):
        first = OmegaServConfig.from_dict({"server": {"port": 8080}})
        self.repo.save(self.config_path, first)

        second = OmegaServConfig.from_dict({"server": {"port": 9999}})
        self.repo.save(self.config_path, second)

        backups = list(self.backups_dir.glob("*.bak"))
        self.assertEqual(len(backups), 1)
        backed_up_content = json.loads(backups[0].read_text())
        self.assertEqual(backed_up_content["server"]["port"], 8080)

    def test_first_save_creates_no_backup(self):
        config = OmegaServConfig()
        self.repo.save(self.config_path, config)
        self.assertFalse(self.backups_dir.exists() and any(self.backups_dir.iterdir()))


if __name__ == "__main__":
    unittest.main()
