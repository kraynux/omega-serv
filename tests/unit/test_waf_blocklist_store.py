# Copyright (c) 2026 kraynux - kraynux@proton.me - Licence MIT (voir fichier LICENSE)
import tempfile
import time
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import patch

from omega_serv.domain.security.waf.entities import BlocklistEntry
from omega_serv.infrastructure.filesystem.local_filesystem import LocalFilesystem
from omega_serv.infrastructure.waf.blocklist_store import JsonBlocklistStore


class _FakeClock:
    def __init__(self, now: datetime):
        self._now = now

    def now(self) -> datetime:
        return self._now


class TestJsonBlocklistStore(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.root = Path(self._tmp.name)
        self.path = self.root / "blocklist.json"
        self.now = datetime(2026, 9, 5, tzinfo=timezone.utc)
        self.clock = _FakeClock(self.now)
        self.store = JsonBlocklistStore(LocalFilesystem(), self.path, self.clock)

    def tearDown(self):
        self._tmp.cleanup()

    def test_missing_file_means_no_entries(self):
        self.assertEqual(self.store.list_entries(), ())
        self.assertIsNone(self.store.is_blocked("203.0.113.25"))

    def test_add_then_is_blocked(self):
        entry = BlocklistEntry(network="203.0.113.25/32", reason="test", created_at=self.now.isoformat())
        self.store.add_entry(entry)
        found = self.store.is_blocked("203.0.113.25")
        self.assertIsNotNone(found)
        self.assertEqual(found.reason, "test")

    def test_add_persists_across_new_store_instance(self):
        entry = BlocklistEntry(network="203.0.113.25/32", reason="test", created_at=self.now.isoformat())
        self.store.add_entry(entry)
        other_store = JsonBlocklistStore(LocalFilesystem(), self.path, self.clock)
        self.assertEqual(len(other_store.list_entries()), 1)

    def test_add_replaces_existing_same_network(self):
        entry1 = BlocklistEntry(network="203.0.113.25/32", reason="first", created_at=self.now.isoformat())
        entry2 = BlocklistEntry(network="203.0.113.25/32", reason="second", created_at=self.now.isoformat())
        self.store.add_entry(entry1)
        self.store.add_entry(entry2)
        entries = self.store.list_entries()
        self.assertEqual(len(entries), 1)
        self.assertEqual(entries[0].reason, "second")

    def test_remove_entry(self):
        entry = BlocklistEntry(network="203.0.113.25/32", reason="test", created_at=self.now.isoformat())
        self.store.add_entry(entry)
        removed = self.store.remove_entry("203.0.113.25/32")
        self.assertTrue(removed)
        self.assertEqual(self.store.list_entries(), ())

    def test_remove_missing_entry_returns_false(self):
        self.assertFalse(self.store.remove_entry("203.0.113.25/32"))

    def test_purge_expired_removes_only_expired(self):
        expired = BlocklistEntry(
            network="203.0.113.1/32", reason="old", created_at=self.now.isoformat(),
            expires_at=(self.now - timedelta(hours=1)).isoformat(),
        )
        active = BlocklistEntry(network="203.0.113.2/32", reason="active", created_at=self.now.isoformat())
        self.store.add_entry(expired)
        self.store.add_entry(active)
        removed_count = self.store.purge_expired()
        self.assertEqual(removed_count, 1)
        self.assertEqual(len(self.store.list_entries()), 1)

    def test_count_auto_entries(self):
        manual = BlocklistEntry(network="203.0.113.1/32", reason="m", created_at=self.now.isoformat(), source="manual")
        auto = BlocklistEntry(network="203.0.113.2/32", reason="a", created_at=self.now.isoformat(), source="auto")
        self.store.add_entry(manual)
        self.store.add_entry(auto)
        self.assertEqual(self.store.count_auto_entries(), 1)


class TestJsonBlocklistStoreCache(unittest.TestCase):
    """Retour utilisateur (audit performance) : `is_blocked()` est
    appelee pour CHAQUE requete des que le WAF est actif - relire et
    re-parser tout le fichier a chaque fois etait le vrai cout. Le cache
    doit rester correct (jamais de faux negatif sur une IP bannie) tout
    en evitant les lectures redondantes."""

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.root = Path(self._tmp.name)
        self.path = self.root / "blocklist.json"
        self.now = datetime(2026, 9, 5, tzinfo=timezone.utc)
        self.clock = _FakeClock(self.now)
        self.filesystem = LocalFilesystem()
        self.store = JsonBlocklistStore(self.filesystem, self.path, self.clock)

    def tearDown(self):
        self._tmp.cleanup()

    def test_repeated_reads_hit_the_disk_only_once(self):
        entry = BlocklistEntry(network="203.0.113.25/32", reason="test", created_at=self.now.isoformat())
        self.store.add_entry(entry)  # _save() reecrit deja le cache, ne compte pas comme un "read"

        with patch.object(LocalFilesystem, "read_text", wraps=self.filesystem.read_text) as spy:
            for _ in range(10):
                self.store.is_blocked("203.0.113.25")
            self.assertEqual(spy.call_count, 0, "le cache doit eviter toute relecture du fichier")

    def test_own_write_is_visible_immediately_without_relying_on_mtime_resolution(self):
        # Le cache est mis a jour directement par _save() plutot que de
        # dependre de la granularite du mtime du systeme de fichiers
        # (parfois seulement a la seconde pres) pour detecter NOS
        # PROPRES ecritures.
        entry = BlocklistEntry(network="203.0.113.25/32", reason="test", created_at=self.now.isoformat())
        self.store.add_entry(entry)
        self.assertIsNotNone(self.store.is_blocked("203.0.113.25"))

    def test_external_modification_is_picked_up_on_next_read(self):
        # Simule le CLI modifiant le fichier pendant que le serveur
        # tourne (angle mort deja documente) - le meme store, avec un
        # cache deja chaud, doit voir le changement des le prochain
        # appel, pas rester bloque sur une version perimee.
        entry = BlocklistEntry(network="203.0.113.25/32", reason="test", created_at=self.now.isoformat())
        self.store.add_entry(entry)
        self.assertIsNotNone(self.store.is_blocked("203.0.113.25"))  # cache chauffe

        time.sleep(0.01)  # laisse un ecart de mtime mesurable
        other_store = JsonBlocklistStore(self.filesystem, self.path, self.clock)
        other_store.remove_entry("203.0.113.25/32")  # "le CLI" modifie le fichier

        self.assertIsNone(self.store.is_blocked("203.0.113.25"))

    def test_missing_file_clears_a_previously_warm_cache(self):
        entry = BlocklistEntry(network="203.0.113.25/32", reason="test", created_at=self.now.isoformat())
        self.store.add_entry(entry)
        self.assertIsNotNone(self.store.is_blocked("203.0.113.25"))

        self.path.unlink()
        self.assertIsNone(self.store.is_blocked("203.0.113.25"))


if __name__ == "__main__":
    unittest.main()
