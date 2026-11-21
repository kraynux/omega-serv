"""Projets 3.0.0 §8.2, P1 (decision de l'auteur du 2026-11-16) : dossiers des zones actives absents du disque.

Alias et listing absents = avertissement (404 tant qu'il manque) ; zone FastCGI active sans dossier = bloquant ; une
option ou une zone desactivee n'est jamais signalee. Annonce apres une restauration (conteneur), dans « Verifier la
configuration » et au demarrage."""
import tempfile
import unittest
from pathlib import Path

from omega_serv.application.persistence.restore_backup import RestoreResult
from omega_serv.application.persistence.zone_data import missing_zone_folders
from omega_serv.domain.config.entities import OmegaServConfig


def _config(options: dict) -> OmegaServConfig:
    return OmegaServConfig.from_dict({"server": {"bind": "127.0.0.1", "port": 8080}, "options": options})


class TestMissingZoneFolders(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.root = Path(self._tmp.name)
        (self.root / "webroot" / "present").mkdir(parents=True)
        (self.root / "webroot" / "fichier.pdf").write_text("pdf")
        (self.root / "media-present").mkdir()

    def tearDown(self):
        self._tmp.cleanup()

    def test_nothing_missing_means_nothing_reported(self):
        config = _config({
            "aliases": {"enabled": True, "list": [
                {"url_prefix": "/m/", "target_path": "media-present", "allow_outside_webroot": True},
                {"url_prefix": "/doc.pdf", "target_path": "webroot/fichier.pdf"}]},
            "dirlisting": {"enabled": True, "zone_prefixes": ["/present/"]},
        })
        self.assertEqual(missing_zone_folders(config, self.root), [])

    def test_missing_alias_and_listing_are_warnings(self):
        config = _config({
            "aliases": {"enabled": True, "list": [
                {"url_prefix": "/media/", "target_path": "media", "allow_outside_webroot": True},
                {"url_prefix": "/gone.pdf", "target_path": "webroot/gone.pdf"},
                {"url_prefix": "/ext/", "target_path": "/nonexistent-omega-p1/abs", "allow_outside_webroot": True}]},
            "dirlisting": {"enabled": True, "zone_prefixes": ["/absent/"]},
        })
        missing = missing_zone_folders(config, self.root)
        self.assertEqual(len(missing), 4)
        self.assertTrue(all(not m.blocking for m in missing))
        paths = {m.path for m in missing}
        self.assertIn(self.root / "media", paths)
        self.assertIn(Path("/nonexistent-omega-p1/abs"), paths)
        self.assertIn(self.root / "webroot" / "absent", paths)
        self.assertIn("404", missing[0].message())
        self.assertTrue(missing[0].log_text().startswith("dossier de zone absent : "))

    def test_active_fastcgi_zone_without_scripts_is_blocking(self):
        config = _config({"fastcgi": {"enabled": True, "zones": [
            {"url_prefix": "/blog/", "script_root": "apps/blog", "socket_path": "var/run/blog.sock", "enabled": True},
            {"url_prefix": "/wiki/", "script_root": "apps/wiki", "socket_path": "var/run/wiki.sock", "enabled": False}]}})
        missing = missing_zone_folders(config, self.root)
        self.assertEqual(len(missing), 1)  # la zone desactivee /wiki/ n'est pas signalee
        self.assertTrue(missing[0].blocking)
        self.assertIn("/blog/", missing[0].label)
        self.assertIn("FastCGI", missing[0].message())

    def test_disabled_options_are_never_reported(self):
        config = _config({
            "aliases": {"enabled": False, "list": [
                {"url_prefix": "/media/", "target_path": "media", "allow_outside_webroot": True}]},
            "dirlisting": {"enabled": False, "zone_prefixes": ["/absent/"]},
            "fastcgi": {"enabled": False, "zones": [
                {"url_prefix": "/blog/", "script_root": "apps/blog", "socket_path": "x.sock", "enabled": True}]},
        })
        self.assertEqual(missing_zone_folders(config, self.root), [])

    def test_restore_result_carries_the_messages(self):
        result = RestoreResult(True, "ok", missing_zone_folders=("alias /media/ : dossier absent",))
        self.assertEqual(result.missing_zone_folders, ("alias /media/ : dossier absent",))
        self.assertEqual(RestoreResult(True, "ok").missing_zone_folders, ())


if __name__ == "__main__":
    unittest.main()
