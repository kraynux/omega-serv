# Copyright (c) 2026 kraynux - kraynux@proton.me - Licence MIT (voir fichier LICENSE)
"""Profil Custom (projets 3.0.0 §B et §7.1) : identification bornee, trous, application qui garde adresse, port, TLS,
chemins et journaux, reglages des options gardes, stockage dans config/profiles/custom/."""
from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from omega_serv.application.config.apply_profile import plan_profile_application
from omega_serv.application.config.create_custom_profile import (
    build_custom_profile,
    check_custom_profile,
)
from omega_serv.domain.config.custom_profile import identification_errors, minimal_selection
from omega_serv.domain.config.entities import OmegaServConfig
from omega_serv.domain.config.profile import Profile
from omega_serv.infrastructure.config.profile_repository import FileProfileRepository
from omega_serv.infrastructure.filesystem.local_filesystem import LocalFilesystem


def _config() -> OmegaServConfig:
    return OmegaServConfig.from_dict({
        "server": {"bind": "0.0.0.0", "port": 8443},
        "tls": {"enabled": False},
        "options": {"aliases": {"enabled": True, "list": [
            {"url_prefix": "/m/", "target_path": "webroot", "allow_outside_webroot": False}]},
            "waf": {"enabled": False, "mode": "block"}},
    })


class TestIdentification(unittest.TestCase):
    def test_bounds(self):
        self.assertEqual(identification_errors("mon-site", "Mon site", "", set()), {})
        self.assertIn("name", identification_errors("Mo", "Mon site", "", set()))
        self.assertIn("name", identification_errors("standard", "Mon site", "", {"standard"}))
        self.assertIn("name", identification_errors("a b c", "Mon site", "", set()))
        self.assertIn("label", identification_errors("mon-site", "  ", "", set()))
        self.assertIn("label", identification_errors("mon-site", "x" * 41, "", set()))
        self.assertIn("label", identification_errors("mon-site", "a\x1bb c", "", set()))
        self.assertIn("description", identification_errors("mon-site", "Mon site", "d" * 201, set()))


class TestCheck(unittest.TestCase):
    def test_minimal_server_lists_holes_to_accept_one_by_one(self):
        selection = minimal_selection()
        check = check_custom_profile("ouvert", "Serveur ouvert", "", selection, set(), set(), _config())
        codes = {code for code, _message in check.to_accept}
        self.assertTrue({"no-security-headers", "csp-report-only", "hidden-files-served", "write-methods-open",
                         "no-waf"} <= codes)
        self.assertFalse(check.can_save)
        check = check_custom_profile("ouvert", "Serveur ouvert", "", selection, codes, set(), _config())
        self.assertTrue(check.can_save, check)

    def test_blocking_hole_prevents_saving_even_when_everything_is_accepted(self):
        selection = {**minimal_selection(), "fastcgi": "on", "methods": "read"}
        check = check_custom_profile("php", "PHP", "", selection, {"x"}, set(), _config())
        self.assertTrue(check.blocking)
        self.assertFalse(check.can_save)


class TestApplyAndStore(unittest.TestCase):
    def test_apply_keeps_identity_and_option_settings(self):
        selection = {**minimal_selection(), "waf": "on", "security_headers": "on"}
        profile = build_custom_profile("durci", "Durci", "", selection, "2026-11-15T10:00:00+00:00")
        new = plan_profile_application(_config(), profile).new_config
        self.assertEqual((new.server.bind, new.server.port), ("0.0.0.0", 8443))
        self.assertTrue(new.options["waf"].enabled)  # choix du profil, malgre l'option presente et desactivee
        self.assertEqual(new.options["waf"].settings, {"mode": "block"})  # reglages gardes
        self.assertEqual(len(new.options["aliases"].settings["list"]), 1)
        self.assertTrue(new.security.security_headers_enabled)
        self.assertEqual(new.profile, "durci")

    def test_provided_profiles_keep_their_behaviour(self):
        provided = Profile(name="p", description="", values={"server": {"bind": "127.0.0.1"}})
        self.assertEqual(plan_profile_application(_config(), provided).new_config.server.bind, "127.0.0.1")

    def test_repository_round_trip_without_metadata_leaking_into_values(self):
        with tempfile.TemporaryDirectory() as tmp:
            directory = Path(tmp) / "profiles"
            directory.mkdir()
            (directory / "standard.json").write_text(json.dumps({"name": "standard", "description": "d"}))
            repo = FileProfileRepository(LocalFilesystem(), directory)
            profile = build_custom_profile("mien", "Le mien", "desc", minimal_selection(), "2026-11-15")
            path = repo.save_custom_profile(profile)
            self.assertEqual(path, directory / "custom" / "mien.json")
            self.assertEqual(repo.list_profile_names(), ["standard", "mien"])
            self.assertEqual(repo.provided_profile_names(), ["standard"])
            loaded = repo.load_profile("mien")
            self.assertTrue(loaded.custom)
            self.assertEqual((loaded.label, loaded.selection), ("Le mien", minimal_selection()))
            self.assertEqual(set(loaded.values), {"security", "options"})
            self.assertTrue(repo.delete_custom_profile("mien"))
            self.assertEqual(repo.list_profile_names(), ["standard"])


if __name__ == "__main__":
    unittest.main()
