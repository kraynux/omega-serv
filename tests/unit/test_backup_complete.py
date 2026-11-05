"""Sauvegarde complete (OMEGA-SERV_ANALYSE_SAUVEGARDE_CONFIGURATION.md, decisions du 2026-11-01) : tout ce
que la configuration designe, copie COHERENTE des bases en service, restauration jamais faite sous un
serveur actif quand l'archive contient une base, anciens -wal mis de cote."""
from __future__ import annotations

import json
import sqlite3
import tarfile
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path

from omega_serv.application.persistence.create_backup import create_backup
from omega_serv.application.persistence.restore_backup import RestoreResult, restore_backup
from omega_serv.application.persistence.restore_with_service import restore_stopping_service
from omega_serv.domain.config.entities import OmegaServConfig
from omega_serv.domain.persistence.backup import BackupRequest
from omega_serv.infrastructure.persistence.backup_metadata_store import BackupMetadataStore
from omega_serv.infrastructure.persistence.sqlite_riposte_connection import open_riposte_connection
from omega_serv.infrastructure.persistence.sqlite_snapshot import snapshot_database
from omega_serv.infrastructure.storage.files.archive_store import ArchiveStore


class _Clock:
    def now(self):
        return datetime(2026, 11, 1, 18, 0, 0, tzinfo=timezone.utc)


class _Base(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.root = Path(self._tmp.name)
        backups = self.root / "var" / "backups" / "config-snapshots"
        self.archive_store = ArchiveStore(backups)
        self.metadata_store = BackupMetadataStore(backups)
        self.config_file = self.root / "config" / "omega-serve.json"
        self.config_file.parent.mkdir(parents=True)
        self.config_file.write_text("{}")

    def tearDown(self):
        self._tmp.cleanup()

    def _write(self, relative, content="x"):
        path = self.root / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content)
        return path

    def _config(self, options):
        return OmegaServConfig.from_dict({"server": {"bind": "127.0.0.1", "port": 8080}, "options": options})

    def _backup(self, request, options=None, snapshot=snapshot_database):
        return create_backup(request, self._config(options or {}), self.root, self.config_file, self.archive_store,
                             self.metadata_store, _Clock(), snapshot=snapshot)

    def _members(self, result):
        with tarfile.open(result.metadata.file_path) as tar:
            return set(tar.getnames())

    def _riposte_db_with_unchekpointed_row(self):
        """Base en WAL dont la derniere ecriture n'est QUE dans le -wal (jamais un fichier brut suffisant)."""
        connection = open_riposte_connection(self.root / "var" / "lib" / "riposte.sqlite3")
        connection.execute("PRAGMA wal_autocheckpoint = 0")
        connection.execute("INSERT INTO state (key, value) VALUES ('recent', 'present')")
        connection.commit()
        return connection  # gardee ouverte : le -wal reste en place, comme sous un serveur actif


class TestCompleteBackup(_Base):
    def test_waf_rules_include_keyword_lists_and_magnet(self):
        self._write("secure/waf/rules/pack.json", json.dumps({"pack": "p", "rules": []}))
        self._write("secure/waf/rules/keywords/sensibles.txt")
        self._write("secure/waf/scripts/waf.lua")
        self._write("secure/waf/scripts/waf-personal.lua")
        self._write("secure/waf/magnet-rules.d/regle.lua")
        options = {"waf": {"enabled": True, "rules": {
                               "paths": ["secure/waf/rules/pack.json"],
                               "keyword_lists": [{"id": "sens", "file": "secure/waf/rules/keywords/sensibles.txt",
                                                  "scope": ["path"]}]},
                           "magnet": {"enabled": True, "script": "secure/waf/scripts/waf-personal.lua"}}}
        members = self._members(self._backup(BackupRequest(include_waf_rules=True), options))
        for expected in ("secure/waf/rules/pack.json", "secure/waf/rules/keywords/sensibles.txt",
                         "secure/waf/scripts/waf.lua", "secure/waf/scripts/waf-personal.lua",
                         "secure/waf/magnet-rules.d"):
            self.assertIn(expected, members)

    def test_new_groups(self):
        self._write("webroot/.errors/404.html")
        self._write("var/settings.json", "{}")
        self._write("var/library.json", "[]")
        self._write("var/run/log_rotation_automations.json", "[]")
        members = self._members(self._backup(BackupRequest(
            include_error_pages=True, include_preferences=True, include_logs_library=True)))
        for expected in ("webroot/.errors", "var/settings.json", "var/library.json",
                         "var/run/log_rotation_automations.json"):
            self.assertIn(expected, members)

    def test_running_database_is_copied_consistently_including_its_wal(self):
        connection = self._riposte_db_with_unchekpointed_row()
        try:
            result = self._backup(BackupRequest(include_riposte=True), {"riposte": {"enabled": True}})
        finally:
            connection.close()
        self.assertIn("var/lib/riposte.sqlite3", self._members(result))
        restored = self.root / "extrait"
        with tarfile.open(result.metadata.file_path) as tar:
            tar.extractall(restored, filter="data")
        copy = sqlite3.connect(restored / "var" / "lib" / "riposte.sqlite3")
        try:
            self.assertEqual(copy.execute("SELECT value FROM state WHERE key='recent'").fetchone(), ("present",))
        finally:
            copy.close()
        self.assertFalse(list((self.archive_store.base_dir).glob(".staging-*")))  # copie temporaire nettoyee

    def test_without_injected_snapshot_the_wal_is_archived_with_the_database(self):
        connection = self._riposte_db_with_unchekpointed_row()
        try:
            result = self._backup(BackupRequest(include_riposte=True), {"riposte": {"enabled": True}}, snapshot=None)
        finally:
            connection.close()
        members = self._members(result)
        self.assertIn("var/lib/riposte.sqlite3", members)
        self.assertIn("var/lib/riposte.sqlite3-wal", members)

    def test_certificate_outside_the_project_is_reported_never_archived(self):
        config = {"tls": {"enabled": False, "certificate": {"certificate_path": "/etc/letsencrypt/live/x/cert.pem"}}}
        result = create_backup(
            BackupRequest(include_certificates=True),
            OmegaServConfig.from_dict({"server": {"bind": "127.0.0.1", "port": 8080}, **config}),
            self.root, self.config_file, self.archive_store, self.metadata_store, _Clock(), snapshot=snapshot_database,
        )
        self.assertTrue(result.success)
        self.assertTrue(any("/etc/letsencrypt" in line for line in result.skipped), result.skipped)

    def test_everything(self):
        request = BackupRequest.everything("complet")
        self.assertTrue(all((request.include_waf_rules, request.include_auth_zones, request.include_certificates,
                             request.include_active_defense, request.include_riposte, request.include_error_pages,
                             request.include_preferences, request.include_logs_library)))
        self.assertTrue(request.includes_databases)
        result = self._backup(request)
        self.assertIn("riposte", result.metadata.scope)


class TestRestoreWithDatabases(_Base):
    def _backup_with_database(self):
        connection = self._riposte_db_with_unchekpointed_row()
        connection.close()
        return self._backup(BackupRequest(include_riposte=True), {"riposte": {"enabled": True}})

    def test_refused_while_the_server_runs(self):
        result = self._backup_with_database()
        restore = restore_backup(result.metadata.snapshot_id, self.root, self.archive_store, self.metadata_store,
                                 server_running=True)
        self.assertFalse(restore.success)
        self.assertTrue(restore.needs_service_stop)
        self.assertEqual(restore.databases, ("var/lib/riposte.sqlite3",))

    def test_backup_without_database_restores_even_while_running(self):
        result = self._backup(BackupRequest())
        restore = restore_backup(result.metadata.snapshot_id, self.root, self.archive_store, self.metadata_store,
                                 server_running=True)
        self.assertTrue(restore.success)

    def test_stale_wal_is_set_aside_and_never_replayed_on_the_restored_base(self):
        result = self._backup_with_database()
        database = self.root / "var" / "lib" / "riposte.sqlite3"
        later = open_riposte_connection(database)
        later.execute("PRAGMA wal_autocheckpoint = 0")
        later.execute("INSERT INTO state (key, value) VALUES ('apres', 'ecrit apres la sauvegarde')")
        later.commit()
        later.close()
        aside = self.root / "de-cote"
        restore = restore_backup(result.metadata.snapshot_id, self.root, self.archive_store, self.metadata_store,
                                 server_running=False, aside_dir=aside)
        self.assertTrue(restore.success, restore.message)
        self.assertTrue((aside / "var" / "lib" / "riposte.sqlite3").exists())
        check = sqlite3.connect(database)
        try:
            self.assertIsNone(check.execute("SELECT value FROM state WHERE key='apres'").fetchone())
            self.assertEqual(check.execute("SELECT value FROM state WHERE key='recent'").fetchone(), ("present",))
        finally:
            check.close()


class _Manager:
    def __init__(self, stop_ok=True):
        self.calls = []
        self.stop_ok = stop_ok

    def stop(self, name):
        self.calls.append(("stop", name))
        if not self.stop_ok:
            from omega_serv.domain.services.exceptions import ServiceControlError
            raise ServiceControlError(name, "stop", "refus")
        return True

    def start(self, name):
        self.calls.append(("start", name))
        return True


class TestRestoreStoppingService(unittest.TestCase):
    def test_stop_restore_restart(self):
        manager = _Manager()
        running = iter([True, False, False])
        result = restore_stopping_service(lambda: RestoreResult(True, "restaurée"), manager, "omega-serv",
                                          lambda: next(running), sleep=lambda _s: None)
        self.assertTrue(result.success)
        self.assertEqual(manager.calls, [("stop", "omega-serv"), ("start", "omega-serv")])

    def test_nothing_restored_when_the_service_cannot_stop(self):
        manager = _Manager(stop_ok=False)
        restored = []
        result = restore_stopping_service(lambda: restored.append(1) or RestoreResult(True, "x"), manager,
                                          "omega-serv", lambda: True, sleep=lambda _s: None)
        self.assertFalse(result.success)
        self.assertEqual(restored, [])

    def test_service_restarted_even_if_restore_fails(self):
        manager = _Manager()
        result = restore_stopping_service(lambda: RestoreResult(False, "échec"), manager, "omega-serv",
                                          lambda: False, sleep=lambda _s: None)
        self.assertFalse(result.success)
        self.assertEqual(manager.calls[-1], ("start", "omega-serv"))

    def test_server_that_never_stops_is_restarted_and_nothing_restored(self):
        manager = _Manager()
        clock = iter(range(0, 1000, 30))
        restored = []
        result = restore_stopping_service(lambda: restored.append(1) or RestoreResult(True, "x"), manager,
                                          "omega-serv", lambda: True, sleep=lambda _s: None,
                                          monotonic=lambda: float(next(clock)))
        self.assertFalse(result.success)
        self.assertEqual(restored, [])
        self.assertEqual(manager.calls[-1], ("start", "omega-serv"))


if __name__ == "__main__":
    unittest.main()
