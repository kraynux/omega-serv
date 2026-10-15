import tempfile
import unittest
from pathlib import Path

from omega_serv.domain.logs.remote_source import RemoteLogSource
from omega_serv.infrastructure.logging.json_remote_log_source_repository import (
    JsonRemoteLogSourceRepository,
)


class TestJsonRemoteLogSourceRepository(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.path = Path(self._tmp.name) / "sub" / "remote-log-sources.json"

    def tearDown(self):
        self._tmp.cleanup()

    def test_list_all_on_missing_file_is_empty(self):
        self.assertEqual(JsonRemoteLogSourceRepository(self.path).list_all(), [])

    def test_survives_a_fresh_instance_round_trip(self):
        source = RemoteLogSource(
            label="backend1", host="192.168.1.10", remote_path="/var/log/access.log",
            user="admin", port=2222, identity_file="/home/me/.ssh/id_ed25519",
        )
        JsonRemoteLogSourceRepository(self.path).add(source)
        reloaded = JsonRemoteLogSourceRepository(self.path).list_all()
        self.assertEqual(reloaded, [source])

    def test_optional_fields_round_trip_as_none(self):
        source = RemoteLogSource(label="backend1", host="192.168.1.10", remote_path="/var/log/access.log")
        JsonRemoteLogSourceRepository(self.path).add(source)
        reloaded = JsonRemoteLogSourceRepository(self.path).list_all()
        self.assertEqual(reloaded, [source])
        self.assertIsNone(reloaded[0].user)
        self.assertIsNone(reloaded[0].port)
        self.assertIsNone(reloaded[0].identity_file)

    def test_add_same_label_replaces_not_duplicates(self):
        repo = JsonRemoteLogSourceRepository(self.path)
        repo.add(RemoteLogSource(label="x", host="h1", remote_path="/a.log"))
        repo.add(RemoteLogSource(label="x", host="h2", remote_path="/b.log"))
        sources = repo.list_all()
        self.assertEqual(len(sources), 1)
        self.assertEqual(sources[0].host, "h2")

    def test_remove(self):
        repo = JsonRemoteLogSourceRepository(self.path)
        repo.add(RemoteLogSource(label="x", host="h1", remote_path="/a.log"))
        repo.remove("x")
        self.assertEqual(repo.list_all(), [])


if __name__ == "__main__":
    unittest.main()
