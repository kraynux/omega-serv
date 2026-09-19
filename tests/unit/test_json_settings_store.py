import tempfile
import unittest
from pathlib import Path

from omega_serv.infrastructure.config.json_settings_store import JsonSettingsStore


class TestJsonSettingsStore(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.path = Path(self._tmp.name) / "settings.json"
        self.store = JsonSettingsStore(self.path)

    def tearDown(self):
        self._tmp.cleanup()

    def test_get_missing_key_returns_default(self):
        self.assertIsNone(self.store.get("theme"))
        self.assertEqual(self.store.get("theme", "omega-base"), "omega-base")

    def test_set_then_get_round_trips(self):
        self.store.set("theme", "omega-neon")
        self.assertEqual(self.store.get("theme"), "omega-neon")

    def test_set_creates_parent_directory(self):
        nested_path = Path(self._tmp.name) / "nested" / "settings.json"
        store = JsonSettingsStore(nested_path)
        store.set("theme", "omega-base")
        self.assertTrue(nested_path.exists())

    def test_all_returns_empty_dict_when_file_absent(self):
        self.assertEqual(self.store.all(), {})

    def test_all_returns_full_content(self):
        self.store.set("theme", "omega-base")
        self.store.set("render_profile_override", "complete")
        self.assertEqual(self.store.all(), {"theme": "omega-base", "render_profile_override": "complete"})

    def test_persists_across_instances(self):
        self.store.set("theme", "omega-burn")
        other = JsonSettingsStore(self.path)
        self.assertEqual(other.get("theme"), "omega-burn")


if __name__ == "__main__":
    unittest.main()
