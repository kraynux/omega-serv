"""Teste ArchiveStore contre de vrais fichiers/tarballs temporaires (pas
de mock) - creation/extraction/liste/info/suppression."""
from __future__ import annotations

import shutil
import tarfile
import tempfile
import unittest
from pathlib import Path

from omega_serv.domain.logs.exceptions import ArchiveStoreError
from omega_serv.infrastructure.storage.files.archive_store import ArchiveStore, _safe_members


class TestArchiveStore(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.root = Path(self._tmp.name)
        self.base_dir = self.root / "archives"
        self.store = ArchiveStore(self.base_dir)
        self.source = self.root / "access.log"
        self.source.write_text("line1\nline2\n")

    def tearDown(self):
        self._tmp.cleanup()

    def test_init_creates_base_dir(self):
        self.assertTrue(self.base_dir.is_dir())

    def test_create_archive_writes_tar_gz(self):
        path = self.store.create_archive("a.tar.gz", [self.source])
        self.assertTrue(path.exists())
        self.assertEqual(path, self.base_dir / "a.tar.gz")

    def test_create_archive_skips_missing_sources(self):
        missing = self.root / "missing.log"
        path = self.store.create_archive("a.tar.gz", [self.source, missing])
        self.assertTrue(path.exists())

    def test_extract_archive_restores_content(self):
        self.store.create_archive("a.tar.gz", [self.source])
        dest = self.root / "restored"
        self.store.extract_archive(self.base_dir / "a.tar.gz", dest)
        self.assertEqual((dest / "access.log").read_text(), "line1\nline2\n")

    def test_create_archive_preserves_relative_structure_under_base_path(self):
        nested = self.root / "secure" / "certificates" / "server.pem"
        nested.parent.mkdir(parents=True)
        nested.write_text("CERT")
        self.store.create_archive("a.tar.gz", [nested], base_path=self.root)
        dest = self.root / "restored"
        self.store.extract_archive(self.base_dir / "a.tar.gz", dest)
        self.assertEqual((dest / "secure" / "certificates" / "server.pem").read_text(), "CERT")

    def test_create_archive_falls_back_to_bare_name_for_source_outside_base_path(self):
        outside_dir = Path(tempfile.mkdtemp())
        try:
            outside_file = outside_dir / "custom.json"
            outside_file.write_text("{}")
            self.store.create_archive("a.tar.gz", [outside_file], base_path=self.root)
            dest = self.root / "restored"
            self.store.extract_archive(self.base_dir / "a.tar.gz", dest)
            self.assertEqual((dest / "custom.json").read_text(), "{}")
        finally:
            shutil.rmtree(outside_dir)

    def test_extract_missing_archive_raises_archive_store_error(self):
        with self.assertRaises(ArchiveStoreError):
            self.store.extract_archive(self.base_dir / "does-not-exist.tar.gz", self.root / "restored")

    def test_list_archives_returns_sorted_matching_pattern(self):
        self.store.create_archive("access.log.2.tar.gz", [self.source])
        self.store.create_archive("access.log.1.tar.gz", [self.source])
        names = [p.name for p in self.store.list_archives("access.log.*.tar.gz")]
        self.assertEqual(names, ["access.log.1.tar.gz", "access.log.2.tar.gz"])

    def test_get_archive_info_reports_size_and_modified(self):
        path = self.store.create_archive("a.tar.gz", [self.source])
        info = self.store.get_archive_info(path)
        self.assertEqual(info["name"], "a.tar.gz")
        self.assertGreater(info["size_bytes"], 0)
        self.assertIn("modified_at", info)

    def test_get_archive_info_missing_raises_archive_store_error(self):
        with self.assertRaises(ArchiveStoreError):
            self.store.get_archive_info(self.base_dir / "missing.tar.gz")

    def test_delete_archive_removes_existing_and_returns_true(self):
        path = self.store.create_archive("a.tar.gz", [self.source])
        self.assertTrue(self.store.delete_archive(path))
        self.assertFalse(path.exists())

    def test_delete_archive_missing_returns_false(self):
        self.assertFalse(self.store.delete_archive(self.base_dir / "missing.tar.gz"))


class TestSafeMembers(unittest.TestCase):
    """`_safe_members` reimplemente manuellement le coeur du filtre
    "data" (PEP 706) pour Python < 3.12 (voir ArchiveStore.extract_archive)
    - jamais exerce par les tests ci-dessus sur un Python >= 3.12 (le
    chemin `filter="data"` natif reussit directement, `except TypeError`
    n'est jamais atteint) : teste ici directement en isolation, sur de
    vrais objets TarInfo issus d'une vraie archive (jamais construits a
    la main - un TarInfo cree via `tarfile.TarInfo()` seul n'a pas le
    meme comportement `isdev()`/`issym()`/`islnk()` qu'un membre reellement
    lu depuis une archive)."""

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.root = Path(self._tmp.name)
        self.dest_dir = self.root / "dest"
        self.dest_dir.mkdir()
        self.archive_path = self.root / "crafted.tar"

    def tearDown(self):
        self._tmp.cleanup()

    def _build_archive(self, members: list[tarfile.TarInfo]) -> tarfile.TarFile:
        with tarfile.open(self.archive_path, "w") as tar:
            for member in members:
                tar.addfile(member)
        return tarfile.open(self.archive_path, "r")

    def test_keeps_a_plain_file_member(self):
        safe = tarfile.TarInfo(name="access.log")
        safe.size = 0
        with self._build_archive([safe]) as tar:
            kept = _safe_members(tar, self.dest_dir)
        self.assertEqual([m.name for m in kept], ["access.log"])

    def test_rejects_a_relative_path_traversal_member(self):
        evil = tarfile.TarInfo(name="../../etc/passwd")
        evil.size = 0
        with self._build_archive([evil]) as tar:
            kept = _safe_members(tar, self.dest_dir)
        self.assertEqual(kept, [])

    def test_rejects_an_absolute_path_member(self):
        evil = tarfile.TarInfo(name="/etc/passwd")
        evil.size = 0
        with self._build_archive([evil]) as tar:
            kept = _safe_members(tar, self.dest_dir)
        self.assertEqual(kept, [])

    def test_rejects_a_symlink_escaping_dest_dir(self):
        evil = tarfile.TarInfo(name="escape-link")
        evil.type = tarfile.SYMTYPE
        evil.linkname = "../../outside"
        with self._build_archive([evil]) as tar:
            kept = _safe_members(tar, self.dest_dir)
        self.assertEqual(kept, [])

    def test_keeps_a_symlink_staying_within_dest_dir(self):
        target = tarfile.TarInfo(name="real-file")
        target.size = 0
        link = tarfile.TarInfo(name="link-to-real-file")
        link.type = tarfile.SYMTYPE
        link.linkname = "real-file"
        with self._build_archive([target, link]) as tar:
            kept = {m.name for m in _safe_members(tar, self.dest_dir)}
        self.assertEqual(kept, {"real-file", "link-to-real-file"})

    def test_rejects_a_device_file_member(self):
        device = tarfile.TarInfo(name="null-device")
        device.type = tarfile.CHRTYPE
        with self._build_archive([device]) as tar:
            kept = _safe_members(tar, self.dest_dir)
        self.assertEqual(kept, [])


if __name__ == "__main__":
    unittest.main()
