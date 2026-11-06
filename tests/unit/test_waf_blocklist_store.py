import contextlib
import io
import multiprocessing
import os
import tempfile
import time
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import patch

from omega_serv.domain.security.waf.entities import BlocklistEntry
from omega_serv.infrastructure.filesystem.file_lock import exclusive_file_lock
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
        entry = BlocklistEntry(network="203.0.113.25/32", reason="test", created_at=self.now.isoformat())
        self.store.add_entry(entry)
        self.assertIsNotNone(self.store.is_blocked("203.0.113.25"))

    def test_external_modification_is_picked_up_on_next_read(self):
        entry = BlocklistEntry(network="203.0.113.25/32", reason="test", created_at=self.now.isoformat())
        self.store.add_entry(entry)
        self.assertIsNotNone(self.store.is_blocked("203.0.113.25"))  # cache chauffe

        time.sleep(0.01)  # laisse un ecart de mtime mesurable
        other_store = JsonBlocklistStore(self.filesystem, self.path, self.clock)
        other_store.remove_entry("203.0.113.25/32")  # "le CLI" modifie le fichier

        self.assertIsNone(self.store.is_blocked("203.0.113.25"))

    def test_index_rebuilt_only_when_the_list_changes(self):
        from omega_serv.infrastructure.waf import blocklist_store
        entry = BlocklistEntry(network="203.0.113.25/32", reason="test", created_at=self.now.isoformat())
        self.store.add_entry(entry)
        with patch.object(blocklist_store, "BlocklistIndex", wraps=blocklist_store.BlocklistIndex) as spy:
            for _ in range(10):
                self.assertIsNotNone(self.store.is_blocked("203.0.113.25"))
            self.assertEqual(spy.call_count, 1)
            self.store.add_entry(BlocklistEntry(network="198.51.100.0/24", reason="test", created_at=self.now.isoformat()))
            self.assertIsNotNone(self.store.is_blocked("198.51.100.4"))
            self.assertEqual(spy.call_count, 2)

    def test_missing_file_clears_a_previously_warm_cache(self):
        entry = BlocklistEntry(network="203.0.113.25/32", reason="test", created_at=self.now.isoformat())
        self.store.add_entry(entry)
        self.assertIsNotNone(self.store.is_blocked("203.0.113.25"))

        self.path.unlink()
        self.assertIsNone(self.store.is_blocked("203.0.113.25"))



def _ban_many(path: str, worker: int, count: int, now_iso: str) -> None:
    """Processus enfant : ajoute `count` bans distincts, chacun par un lire-modifier-ecrire."""
    clock = _FakeClock(datetime.fromisoformat(now_iso))
    store = JsonBlocklistStore(LocalFilesystem(), Path(path), clock)
    for i in range(count):
        store.add_entry(BlocklistEntry(
            network=f"10.{worker}.{i // 250}.{i % 250 + 1}/32", reason="test", created_at=now_iso, source="auto",
        ))


class TestBlocklistStoreWritesBetweenProcesses(unittest.TestCase):
    """Lot 0 (OMEGA-SERV_PLAN-DETAILLE_RIPOSTE.md) : verrou entre processus, relecture sous verrou,
    ajouts/retraits conditionnels."""

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.path = Path(self._tmp.name) / "blocklist.json"
        self.now = datetime(2026, 9, 5, tzinfo=timezone.utc)
        self.clock = _FakeClock(self.now)
        self.store = JsonBlocklistStore(LocalFilesystem(), self.path, self.clock)

    def tearDown(self):
        self._tmp.cleanup()

    def _entry(self, network="203.0.113.25/32", hours=1, source="auto"):
        expires = None if hours is None else (self.now + timedelta(hours=hours)).isoformat()
        return BlocklistEntry(network=network, reason=source, created_at=self.now.isoformat(), expires_at=expires, source=source)

    def test_no_ban_lost_when_several_processes_write_at_once(self):
        workers, per_worker = 4, 40
        context = multiprocessing.get_context("fork")
        processes = [
            context.Process(target=_ban_many, args=(str(self.path), w, per_worker, self.now.isoformat()))
            for w in range(workers)
        ]
        for process in processes:
            process.start()
        for process in processes:
            process.join(60)
            self.assertEqual(process.exitcode, 0)
        reader = JsonBlocklistStore(LocalFilesystem(), self.path, self.clock)
        self.assertEqual(len(reader.list_entries()), workers * per_worker)

    def test_write_rereads_the_file_even_when_the_cached_mtime_looks_current(self):
        self.store.list_entries()  # cache chauffe (fichier absent)
        self.store.add_entry(self._entry("203.0.113.1/32"))
        self.store.list_entries()
        other = JsonBlocklistStore(LocalFilesystem(), self.path, self.clock)
        frozen_mtime = os.stat(self.path).st_mtime
        other.add_entry(self._entry("203.0.113.2/32"))
        os.utime(self.path, (frozen_mtime, frozen_mtime))  # meme mtime que le cache de self.store
        self.store.add_entry(self._entry("203.0.113.3/32"))
        networks = {e.network for e in JsonBlocklistStore(LocalFilesystem(), self.path, self.clock).list_entries()}
        self.assertEqual(networks, {"203.0.113.1/32", "203.0.113.2/32", "203.0.113.3/32"})

    def test_automatic_add_never_replaces_an_active_manual_ban(self):
        self.store.add_entry(self._entry(hours=1, source="manual"))
        self.assertFalse(self.store.add_entry_unless_stronger(self._entry(hours=24, source="auto")))
        (kept,) = self.store.list_entries()
        self.assertEqual(kept.source, "manual")

    def test_automatic_add_never_replaces_a_permanent_ban(self):
        self.store.add_entry(self._entry(hours=None, source="auto"))
        self.assertFalse(self.store.add_entry_unless_stronger(self._entry(hours=24, source="auto")))
        (kept,) = self.store.list_entries()
        self.assertIsNone(kept.expires_at)

    def test_automatic_add_replaces_a_shorter_automatic_ban_and_keeps_a_longer_one(self):
        self.store.add_entry(self._entry(hours=1))
        self.assertTrue(self.store.add_entry_unless_stronger(self._entry(hours=6)))
        self.assertFalse(self.store.add_entry_unless_stronger(self._entry(hours=2)))
        (kept,) = self.store.list_entries()
        self.assertEqual(kept.expires_at, (self.now + timedelta(hours=6)).isoformat())

    def test_automatic_add_replaces_an_expired_manual_ban(self):
        self.store.add_entry(self._entry(hours=-1, source="manual"))
        self.assertTrue(self.store.add_entry_unless_stronger(self._entry(hours=1)))
        (kept,) = self.store.list_entries()
        self.assertEqual(kept.source, "auto")

    def test_manual_add_still_replaces_whatever_is_there(self):
        self.store.add_entry(self._entry(hours=None, source="manual"))
        self.store.add_entry(self._entry(hours=1, source="manual"))
        (kept,) = self.store.list_entries()
        self.assertIsNotNone(kept.expires_at)

    def test_conditional_remove_only_removes_matching_entries(self):
        self.store.add_entry(self._entry(source="manual"))
        self.assertFalse(self.store.remove_entry_if("203.0.113.25/32", lambda e: e.source == "auto"))
        self.assertEqual(len(self.store.list_entries()), 1)
        self.assertTrue(self.store.remove_entry_if("203.0.113.25/32", lambda e: e.source == "manual"))
        self.assertEqual(self.store.list_entries(), ())

    def test_lock_file_is_shared_with_the_group(self):
        self.store.add_entry(self._entry())
        lock = self.path.with_name("blocklist.json.lock")
        self.assertEqual(lock.stat().st_mode & 0o777, 0o664)

    def test_unopenable_lock_file_still_writes_and_warns_once(self):
        lock = self.path.with_name("blocklist.json.lock")
        lock.touch()
        lock.chmod(0)
        if os.access(lock, os.R_OK):
            lock.chmod(0o664)
            self.skipTest("execute en root : un fichier en mode 000 reste lisible")
        stderr = io.StringIO()
        try:
            with contextlib.redirect_stderr(stderr):
                self.store.add_entry(self._entry("203.0.113.1/32"))
                self.store.add_entry(self._entry("203.0.113.2/32"))
        finally:
            lock.chmod(0o664)
        self.assertEqual(len(self.store.list_entries()), 2)
        self.assertEqual(stderr.getvalue().count("sans verrou"), 1)

    def test_lock_held_too_long_by_another_holder_does_not_block_the_write(self):
        lock = self.path.with_name("blocklist.json.lock")
        stderr = io.StringIO()
        with exclusive_file_lock(lock) as held, contextlib.redirect_stderr(stderr):
            self.assertTrue(held)
            started = time.monotonic()
            self.store.add_entry(self._entry())
            elapsed = time.monotonic() - started
        self.assertLess(elapsed, 3.0)
        self.assertEqual(len(self.store.list_entries()), 1)
        self.assertIn("occupe", stderr.getvalue())


class TestBlocklistModeIgnoresUmask(unittest.TestCase):
    """Incident craftdark 2026-11-06 : `blocklist add` lance par le pont omega-jail sous umask 077 recreait le
    fichier en 600 - le service (autre compte, meme groupe) ne pouvait plus le lire : ni 451, ni auto-ban."""

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.path = Path(self._tmp.name) / "blocklist.json"
        self.now = datetime(2026, 11, 6, tzinfo=timezone.utc)
        self.store = JsonBlocklistStore(LocalFilesystem(), self.path, _FakeClock(self.now))
        self._umask = os.umask(0o077)

    def tearDown(self):
        os.umask(self._umask)
        self._tmp.cleanup()

    def _add(self, ip: str) -> None:
        self.store.add_entry(BlocklistEntry(network=f"{ip}/32", reason="test", created_at=self.now.isoformat()))

    def _mode(self) -> int:
        return os.stat(self.path).st_mode & 0o777

    def test_new_file_is_group_readable_under_umask_077(self):
        self._add("203.0.113.7")
        self.assertEqual(self._mode(), 0o660)

    def test_rewrite_repairs_a_file_left_in_600(self):
        self._add("203.0.113.7")
        os.chmod(self.path, 0o600)
        self._add("203.0.113.8")
        self.assertEqual(self._mode(), 0o660)

    def test_rewrite_keeps_wider_existing_mode(self):
        self._add("203.0.113.7")
        os.chmod(self.path, 0o664)
        self._add("203.0.113.8")
        self.assertEqual(self._mode(), 0o664)

    def test_no_temporary_file_left(self):
        self._add("203.0.113.7")
        self.assertEqual(sorted(p.name for p in self.path.parent.iterdir() if p.suffix == ".tmp"), [])


if __name__ == "__main__":
    unittest.main()
