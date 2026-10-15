import tempfile
import unittest
from pathlib import Path

from omega_serv.domain.routing.proxy_cache import ProxyCacheEntry
from omega_serv.infrastructure.proxy_cache.filesystem_proxy_cache_store import (
    FilesystemProxyCacheStore,
)


def _entry(body: bytes = b"hello") -> ProxyCacheEntry:
    return ProxyCacheEntry(
        status_code=200, headers=(("Content-Type", "text/plain"),), body=body, stored_at=100.0,
        ttl_seconds=60.0, vary_header_names=(), vary_header_values=(),
    )


class TestFilesystemProxyCacheStore(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.base_dir = Path(self._tmp.name)

    def tearDown(self):
        self._tmp.cleanup()

    def test_get_on_empty_store_is_none(self):
        store = FilesystemProxyCacheStore(self.base_dir)
        self.assertIsNone(store.get("/api/", "abc"))

    def test_set_then_get_round_trips(self):
        store = FilesystemProxyCacheStore(self.base_dir)
        entry = _entry()
        store.set("/api/", "abc", entry)
        retrieved = store.get("/api/", "abc")
        self.assertIsNotNone(retrieved)
        self.assertEqual(retrieved.status_code, 200)
        self.assertEqual(retrieved.body, b"hello")
        self.assertEqual(retrieved.headers, (("Content-Type", "text/plain"),))
        self.assertEqual(retrieved.stored_at, 100.0)

    def test_round_trips_vary_headers(self):
        store = FilesystemProxyCacheStore(self.base_dir)
        entry = ProxyCacheEntry(
            status_code=200, headers=(), body=b"x", stored_at=1.0, ttl_seconds=1.0,
            vary_header_names=("accept-encoding",), vary_header_values=("gzip",),
        )
        store.set("/api/", "k", entry)
        retrieved = store.get("/api/", "k")
        self.assertEqual(retrieved.vary_header_names, ("accept-encoding",))
        self.assertEqual(retrieved.vary_header_values, ("gzip",))

    def test_delete_removes_entry(self):
        store = FilesystemProxyCacheStore(self.base_dir)
        store.set("/api/", "abc", _entry())
        store.delete("/api/", "abc")
        self.assertIsNone(store.get("/api/", "abc"))

    def test_get_variants_returns_all_entries_sharing_the_primary_prefix(self):
        store = FilesystemProxyCacheStore(self.base_dir)
        store.set("/api/", "primary123--aaa", _entry(b"gzip-body"))
        store.set("/api/", "primary123--bbb", _entry(b"br-body"))
        store.set("/api/", "other456--ccc", _entry(b"unrelated"))
        variants = store.get_variants("/api/", "primary123")
        self.assertEqual({v.body for v in variants}, {b"gzip-body", b"br-body"})

    def test_get_variants_on_empty_store_is_empty_tuple(self):
        store = FilesystemProxyCacheStore(self.base_dir)
        self.assertEqual(store.get_variants("/api/", "primary123"), ())

    def test_get_variants_scoped_to_zone(self):
        store = FilesystemProxyCacheStore(self.base_dir)
        store.set("/a/", "primary123--aaa", _entry(b"a-body"))
        store.set("/b/", "primary123--aaa", _entry(b"b-body"))
        variants = store.get_variants("/a/", "primary123")
        self.assertEqual([v.body for v in variants], [b"a-body"])

    def test_entries_from_different_zones_are_independent(self):
        store = FilesystemProxyCacheStore(self.base_dir)
        store.set("/a/", "same-key", _entry(b"a-body"))
        store.set("/b/", "same-key", _entry(b"b-body"))
        self.assertEqual(store.get("/a/", "same-key").body, b"a-body")
        self.assertEqual(store.get("/b/", "same-key").body, b"b-body")

    def test_stats_counts_entries_and_size(self):
        store = FilesystemProxyCacheStore(self.base_dir)
        store.set("/api/", "a", _entry(b"12345"))
        store.set("/api/", "b", _entry(b"1234567890"))
        stats = store.stats()
        self.assertEqual(stats.entry_count, 2)
        self.assertGreater(stats.total_size_bytes, 0)

    def test_stats_scoped_to_zone(self):
        store = FilesystemProxyCacheStore(self.base_dir)
        store.set("/a/", "x", _entry())
        store.set("/b/", "y", _entry())
        store.set("/b/", "z", _entry())
        self.assertEqual(store.stats(zone_key="/a/").entry_count, 1)
        self.assertEqual(store.stats(zone_key="/b/").entry_count, 2)

    def test_clear_all_removes_everything(self):
        store = FilesystemProxyCacheStore(self.base_dir)
        store.set("/a/", "x", _entry())
        store.set("/b/", "y", _entry())
        removed = store.clear()
        self.assertEqual(removed, 2)
        self.assertEqual(store.stats().entry_count, 0)

    def test_clear_scoped_to_one_zone_leaves_others_intact(self):
        store = FilesystemProxyCacheStore(self.base_dir)
        store.set("/a/", "x", _entry())
        store.set("/b/", "y", _entry())
        removed = store.clear(zone_key="/a/")
        self.assertEqual(removed, 1)
        self.assertIsNone(store.get("/a/", "x"))
        self.assertIsNotNone(store.get("/b/", "y"))

    def test_clear_on_empty_store_returns_zero(self):
        store = FilesystemProxyCacheStore(self.base_dir)
        self.assertEqual(store.clear(), 0)
        self.assertEqual(store.clear(zone_key="/never-existed/"), 0)

    def test_external_deletion_self_heals_on_next_get(self):
        """Le TUI (processus separe) peut supprimer les fichiers
        directement - `get()` doit retourner None proprement, jamais
        lever."""
        store = FilesystemProxyCacheStore(self.base_dir)
        store.set("/api/", "abc", _entry())
        for path in self.base_dir.rglob("*.json"):
            path.unlink()
        self.assertIsNone(store.get("/api/", "abc"))

    def test_eviction_removes_least_recently_accessed_entry_when_over_budget(self):
        store = FilesystemProxyCacheStore(self.base_dir, max_size_mb=1)
        store.set("/api/", "old", _entry(b"1234567890"))
        one_entry_size = store.stats().total_size_bytes
        store.get("/api/", "old")  # "old" devient la plus RECEMMENT accedee
        # budget tolerant UNE SEULE entree de cette taille, jamais deux - force un test
        # deterministe sans dependre d'une estimation a priori de l'encodage JSON/base64.
        store._max_size_bytes = int(one_entry_size * 1.5)
        store.set("/api/", "new", _entry(b"1234567890"))
        # "old" (touche en dernier AVANT ce "set") est maintenant la MOINS recemment
        # accedee des deux - c'est elle que l'eviction doit retirer en premier.
        self.assertIsNone(store.get("/api/", "old"))
        self.assertIsNotNone(store.get("/api/", "new"))

    def test_rebuild_index_on_construction_sees_preexisting_disk_entries(self):
        first_store = FilesystemProxyCacheStore(self.base_dir)
        first_store.set("/api/", "abc", _entry())
        second_store = FilesystemProxyCacheStore(self.base_dir)
        self.assertEqual(second_store.stats().entry_count, 1)


if __name__ == "__main__":
    unittest.main()
