# Copyright (c) 2026 kraynux - kraynux@proton.me - Licence MIT (voir fichier LICENSE)
"""Sauvegarde : fiche dans l'archive, export, import controle, identite (port, version) - projets 3.0.0 §7.4,
decisions de l'auteur du 2026-11-15. Toujours dans des dossiers temporaires."""
from __future__ import annotations

import io
import json
import tarfile
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path

from omega_serv.application.persistence.backup_manifest import MANIFEST_NAME
from omega_serv.application.persistence.backup_transfer import (
    archive_identity,
    export_backup,
    import_backup,
    sha256_of,
)
from omega_serv.application.persistence.create_backup import create_backup
from omega_serv.application.persistence.restore_backup import restore_backup
from omega_serv.domain.config.entities import OmegaServConfig, PathsConfig
from omega_serv.domain.config.option import Option
from omega_serv.domain.persistence.backup import BackupRequest
from omega_serv.infrastructure.persistence.backup_metadata_store import BackupMetadataStore
from omega_serv.infrastructure.storage.files.archive_store import ArchiveStore


class _Clock:
    def __init__(self):
        self._now = datetime(2026, 11, 15, 10, 0, 0, tzinfo=timezone.utc)

    def now(self):
        self._now += timedelta(seconds=1)
        return self._now


class TestBackupTransfer(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        base = Path(self._tmp.name)
        self.root = base / "omega-serv"
        self.other = base / "nouvelle-installation"
        self.outside = base / "exports"
        for directory in (self.root, self.other, self.outside):
            directory.mkdir()
        self.config_file = self.root / "config" / "omega-serve.json"
        self.config_file.parent.mkdir(parents=True)
        self.config_file.write_text(json.dumps({"server": {"bind": "0.0.0.0", "port": 8443}}))
        (self.root / "config" / "profiles" / "custom").mkdir(parents=True)
        (self.root / "config" / "profiles" / "custom" / "mon-profil.json").write_text("{}")
        (self.root / "webroot").mkdir()
        (self.root / "webroot" / "index.html").write_text("<p>site</p>")
        self.clock = _Clock()

    def tearDown(self):
        self._tmp.cleanup()

    def _stores(self, root: Path):
        directory = root / "var" / "backups" / "config-snapshots"
        return ArchiveStore(directory), BackupMetadataStore(directory)

    def _backup(self, **flags):
        archive_store, metadata_store = self._stores(self.root)
        result = create_backup(BackupRequest(**flags), OmegaServConfig(paths=PathsConfig()), self.root,
                               self.config_file, archive_store, metadata_store, self.clock,
                               manifest={"format": 1, "app_version": "3.0.0", "service_name": "site",
                                         "bind": "0.0.0.0", "port": 8443})
        self.assertTrue(result.success, result.message)
        return result.metadata

    def test_manifest_profiles_and_optional_site_content(self):
        metadata = self._backup()
        names = ArchiveStore(self.outside).list_members(Path(metadata.file_path))
        self.assertIn(MANIFEST_NAME, names)
        self.assertIn("config/profiles/custom/mon-profil.json", names)
        self.assertNotIn("webroot/index.html", names)
        self.assertEqual(metadata.app_version, "3.0.0")
        with_site = self._backup(include_site_content=True)
        self.assertIn("webroot/index.html", ArchiveStore(self.outside).list_members(Path(with_site.file_path)))
        self.assertIn("site_content", with_site.scope)

    def test_export_then_import_on_a_fresh_installation_then_restore(self):
        metadata = self._backup()
        _store, metadata_store = self._stores(self.root)
        exported = export_backup(metadata_store, metadata.snapshot_id, self.outside, "principale")
        self.assertTrue(exported.success, exported.message)
        sidecar = exported.path.with_name(exported.path.name + ".sha256")
        self.assertEqual(sidecar.read_text().split()[0], sha256_of(exported.path))
        self.assertEqual(exported.path.stat().st_mode & 0o077, 0)
        self.assertFalse(export_backup(metadata_store, metadata.snapshot_id, self.outside, "principale").success)

        archive_store, other_metadata = self._stores(self.other)
        imported = import_backup(exported.path, archive_store, other_metadata, self.clock)
        self.assertTrue(imported.success, imported.message)
        self.assertEqual(len(other_metadata.list_all()), 1)
        identity = archive_identity(archive_store, imported.path)
        self.assertEqual((identity.bind, identity.port, identity.service_name, identity.app_version),
                         ("0.0.0.0", 8443, "site", "3.0.0"))
        restored = restore_backup(imported.snapshot_id, self.other, archive_store, other_metadata)
        self.assertTrue(restored.success, restored.message)
        self.assertTrue((self.other / "config" / "omega-serve.json").is_file())
        self.assertFalse((self.other / MANIFEST_NAME).exists())  # la fiche n'est pas un fichier du projet

    def _forged(self, members: dict[str, bytes], *, symlink: str | None = None, sidecar: bool = True) -> Path:
        path = self.outside / "forge.tar.gz"
        with tarfile.open(path, "w:gz") as tar:
            for name, data in members.items():
                info = tarfile.TarInfo(name)
                info.size = len(data)
                tar.addfile(info, io.BytesIO(data))
            if symlink:
                info = tarfile.TarInfo(symlink)
                info.type = tarfile.SYMTYPE
                info.linkname = "/etc/passwd"
                tar.addfile(info)
        if sidecar:
            path.with_name(path.name + ".sha256").write_text(f"{sha256_of(path)}  {path.name}\n")
        return path

    def _import(self, path: Path):
        archive_store, metadata_store = self._stores(self.other)
        return import_backup(path, archive_store, metadata_store, self.clock), metadata_store

    def test_import_refuses_unsafe_or_foreign_archives(self):
        config = {"config/omega-serve.json": b"{}"}
        cases = {
            "absolu": self._forged({**config, "/etc/cron.d/x": b"x"}),
        }
        result, store = self._import(cases["absolu"])
        self.assertFalse(result.success)
        for members, symlink in (
            ({**config, "config/../../x": b"x"}, None),
            ({**config, "home/user/.bashrc": b"x"}, None),
            ({**config}, "var/lien"),
            ({"var/settings.json": b"{}"}, None),  # pas une sauvegarde omega-serv
        ):
            result, store = self._import(self._forged(members, symlink=symlink))
            self.assertFalse(result.success, members)
        self.assertEqual(store.list_all(), [])

    def test_import_requires_a_matching_fingerprint(self):
        path = self._forged({"config/omega-serve.json": b"{}"}, sidecar=False)
        result, _store = self._import(path)
        self.assertFalse(result.success)
        self.assertIn(".sha256", result.message)
        path.with_name(path.name + ".sha256").write_text("0" * 64 + "  forge.tar.gz\n")
        result, store = self._import(path)
        self.assertFalse(result.success)
        self.assertEqual(store.list_all(), [])

    def _zone_config(self) -> OmegaServConfig:
        return OmegaServConfig(paths=PathsConfig(), options={
            "aliases": Option("aliases", True, {"list": [
                {"url_prefix": "/docs/", "target_path": "documents"},
                {"url_prefix": "/media/", "target_path": str(self.outside), "allow_outside_webroot": True}]}),
            "dirlisting": Option("dirlisting", True, {"zone_prefixes": ["/fichiers/"]}),
            "fastcgi": Option("fastcgi", True, {"zones": [{"url_prefix": "/a/", "script_root": "app"},
                                                          {"url_prefix": "/b/", "script_root": "app2", "enabled": False}]}),
        })

    def test_zone_data_and_exports_are_optional_and_survive_an_import(self):
        """Donnees des zones et rapports d'export (demande de l'auteur du 2026-11-15) : hors des cases par
        defaut ; un dossier hors du projet est signale ; l'import accepte les dossiers que la configuration de
        l'archive designe, jamais un emplacement de l'installation."""
        for relative, name in (("documents", "guide.pdf"), ("webroot/fichiers", "liste.txt"), ("app", "index.php"),
                               ("app2", "run.php"), ("var/exports", "rapport.html")):
            (self.root / relative).mkdir(parents=True, exist_ok=True)
            (self.root / relative / name).write_text("x")
        archived = {"options": {"aliases": {"list": [{"url_prefix": "/docs/", "target_path": "documents"}]},
                                "fastcgi": {"zones": [{"script_root": "app"}, {"script_root": "app2"}]}}}
        self.config_file.write_text(json.dumps({"server": {"bind": "0.0.0.0", "port": 8443}, **archived}))
        archive_store, metadata_store = self._stores(self.root)

        def backup(**flags):
            result = create_backup(BackupRequest(**flags), self._zone_config(), self.root, self.config_file,
                                   archive_store, metadata_store, self.clock,
                                   exports_dir=self.root / "var" / "exports")
            self.assertTrue(result.success, result.message)
            return result, ArchiveStore(self.outside).list_members(Path(result.metadata.file_path))

        _plain, names = backup()
        self.assertFalse({"documents/guide.pdf", "app/index.php", "var/exports/rapport.html"} & set(names))
        result, names = backup(include_zone_data=True, include_exports=True, include_site_content=True)
        for expected in ("documents/guide.pdf", "webroot/fichiers/liste.txt", "app/index.php", "app2/run.php",
                         "var/exports/rapport.html"):
            self.assertIn(expected, names)
        self.assertEqual(names.count("webroot/fichiers/liste.txt"), 1)  # zone deja couverte par le webroot
        self.assertTrue(any("alias /media/" in line for line in result.skipped), result.skipped)
        self.assertIn("zone_data", result.metadata.scope)
        self.assertIn("exports", result.metadata.scope)

        exported = export_backup(metadata_store, result.metadata.snapshot_id, self.outside, "principale")
        imported, _store = self._import(exported.path)
        self.assertTrue(imported.success, imported.message)
        trap = {"config/omega-serve.json": json.dumps(
            {"options": {"aliases": {"list": [{"url_prefix": "/x/", "target_path": "src/omega_serv"}]}}}).encode(),
            "src/omega_serv/__init__.py": b"import os"}
        refused, _store = self._import(self._forged(trap))
        self.assertFalse(refused.success)


if __name__ == "__main__":
    unittest.main()
