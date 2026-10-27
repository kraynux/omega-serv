"""Cas d'usage "Charger une liste dans le WAF" (OMEGA-SERV_PLAN-DETAILLE_
SENSITIVE_PATHS.md lot 6.3) - vrais fichiers, vraies references du paquet."""
import os
import pwd
import tempfile
import unittest
from pathlib import Path

from omega_serv.application.security.editable_list_file import KEYWORDS_DIR
from omega_serv.application.security.load_keyword_list import (
    ListLoadRequest,
    load_keyword_list_into_config,
    remove_keyword_list_entry,
    sanitize_list_file_name,
    update_keyword_list_entry,
)
from omega_serv.domain.config.entities import OmegaServConfig
from omega_serv.domain.security.waf.config import parse_waf_config
from omega_serv.infrastructure.filesystem.local_file_access import LocalFileAccess
from omega_serv.infrastructure.filesystem.local_filesystem import LocalFilesystem
from omega_serv.infrastructure.waf.keyword_reference_store import PackagedKeywordReferences


class TestSanitize(unittest.TestCase):
    def test_names(self):
        self.assertEqual(sanitize_list_file_name("Mes Chemins!"), "mes-chemins.txt")
        self.assertEqual(sanitize_list_file_name("liste.txt"), "liste.txt")
        self.assertIsNone(sanitize_list_file_name("  ?! "))


class _LoadCase(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.root = Path(self._tmp.name)
        (self.root / KEYWORDS_DIR).mkdir(parents=True)
        self.check_errors: list[str] = []
        self.me = pwd.getpwuid(os.getuid()).pw_name

    def tearDown(self):
        self._tmp.cleanup()

    def _config(self, waf_enabled=True, reputation=None, lists=()):
        waf = {"enabled": waf_enabled, "rules": {"paths": ["secure/waf/rules/a.json"], "keyword_lists": list(lists)}}
        if reputation is not None:
            waf["reputation"] = reputation
        return OmegaServConfig.from_dict({"options": {"waf": waf}})

    def _load(self, request, config=None):
        return load_keyword_list_into_config(
            config or self._config(), request, file_access=LocalFileAccess(), filesystem=LocalFilesystem(),
            references=PackagedKeywordReferences(), project_root=self.root, service_account=self.me,
            config_check=lambda *args: list(self.check_errors),
        )

    def _hostile_request(self, **overrides):
        values = {"file_name": "sensitive-paths-hostile.txt", "reference_name": "sensitive-paths-hostile.txt",
                  "weight": 6, "observe_only": True, "escalation_threshold": 2,
                  "auto_block_duration_seconds": 86400, "label": "Chemins sensibles - bloquer"}
        values.update(overrides)
        return ListLoadRequest(**values)


class TestLoadKeywordList(_LoadCase):
    def test_first_load_copies_reference_and_enables_reputation(self):
        result = self._load(self._hostile_request())
        self.assertTrue(result.loaded, result.error)
        local = self.root / KEYWORDS_DIR / "sensitive-paths-hostile.txt"
        self.assertEqual(local.read_text(), PackagedKeywordReferences().read("sensitive-paths-hostile.txt"))
        waf = parse_waf_config(result.config.options["waf"].settings)
        self.assertTrue(waf.reputation.enabled)
        self.assertTrue(waf.reputation.auto_block)
        definition = waf.keyword_lists[0]
        self.assertEqual((definition.id, definition.match, definition.observe_only, definition.weight),
                         ("sensitive-paths-hostile", "path", True, 6))
        self.assertEqual(definition.escalation_threshold, 0, "pas de recidive en Observation")
        self.assertEqual(definition.label, "Chemins sensibles - bloquer")
        self.assertEqual(waf.rule_paths, ("secure/waf/rules/a.json",), "les packs JSON sont conserves")
        self.assertTrue(any("réputation activée" in m for m in result.messages))

    def test_reputation_already_enabled_reports_nothing(self):
        config = self._config(reputation={"enabled": True, "auto_block": True})
        result = self._load(self._hostile_request(), config)
        self.assertFalse(any(m.startswith("Active") for m in result.messages))

    def test_existing_local_file_is_never_overwritten(self):
        local = self.root / KEYWORDS_DIR / "sensitive-paths-hostile.txt"
        local.write_text("/perso\n")
        self.assertTrue(self._load(self._hostile_request()).loaded)
        self.assertEqual(local.read_text(), "/perso\n")

    def test_already_loaded_refused(self):
        first = self._load(self._hostile_request())
        second = self._load(self._hostile_request(), first.config)
        self.assertFalse(second.loaded)
        self.assertIn("déjà chargée", second.error)

    def test_invalid_list_refused_and_config_untouched(self):
        (self.root / KEYWORDS_DIR / "perso.txt").write_text("/ok\n/robots.txt\n")
        result = self._load(ListLoadRequest(file_name="perso.txt"))
        self.assertFalse(result.loaded)
        self.assertIn("ligne 2", result.error)
        self.assertIsNone(result.config)

    def test_environment_error_on_this_list_refuses(self):
        self.check_errors = ["options.waf.rules.keyword_lists['perso'] : l'entree '/api' bloquerait la route '/api/'"]
        (self.root / KEYWORDS_DIR / "perso.txt").write_text("/api\n")
        result = self._load(ListLoadRequest(file_name="perso.txt", weight=6))
        self.assertFalse(result.loaded)
        self.assertIn("bloquerait la route", result.error)

    def test_new_file_and_unique_id(self):
        existing = [{"id": "perso", "scope": ["path"], "file": f"{KEYWORDS_DIR}/autre.txt", "match": "path"}]
        result = self._load(ListLoadRequest(file_name="perso.txt"), self._config(lists=existing))
        self.assertTrue(result.loaded, result.error)
        self.assertEqual(result.list_id, "perso-2")
        self.assertTrue((self.root / KEYWORDS_DIR / "perso.txt").read_text().startswith("# Liste de chemins"))

    def test_keyword_list_scope(self):
        result = self._load(ListLoadRequest(file_name="spam.txt", match="substring", scope=("referer",)))
        self.assertTrue(result.loaded, result.error)
        definition = parse_waf_config(result.config.options["waf"].settings).keyword_lists[0]
        self.assertEqual((definition.match, definition.scope), ("substring", ("referer",)))

    def test_unsafe_names_refused(self):
        for name in ("../x.txt", "x.json", "Maj.txt", "a/b.txt"):
            with self.subTest(name=name):
                self.assertFalse(self._load(ListLoadRequest(file_name=name)).loaded)

    def test_disabled_waf_is_reported(self):
        result = self._load(self._hostile_request(), self._config(waf_enabled=False))
        self.assertTrue(result.loaded)
        self.assertTrue(any("WAF désactivé" in m for m in result.messages))


class TestUpdateAndRemove(_LoadCase):
    def _loaded(self):
        result = self._load(self._hostile_request(), self._config(reputation={"enabled": False}))
        self.assertTrue(result.loaded, result.error)
        return result.config

    def _update(self, config, changes):
        return update_keyword_list_entry(
            config, "sensitive-paths-hostile", changes, filesystem=LocalFilesystem(), project_root=self.root,
            config_check=lambda *args: list(self.check_errors),
        )

    def test_leave_observation(self):
        result = self._update(self._loaded(), {"observe_only": False, "escalation_threshold": 2})
        self.assertTrue(result.loaded, result.error)
        definition = parse_waf_config(result.config.options["waf"].settings).keyword_lists[0]
        self.assertEqual((definition.observe_only, definition.escalation_threshold), (False, 2))

    def test_back_to_observation_drops_own_threshold(self):
        config = self._update(self._loaded(), {"observe_only": False, "escalation_threshold": 2}).config
        definition = parse_waf_config(self._update(config, {"observe_only": True}).config.options["waf"].settings).keyword_lists[0]
        self.assertEqual(definition.escalation_threshold, 0)

    def test_environment_error_refuses_update(self):
        config = self._loaded()
        self.check_errors = ["options.waf.rules.keyword_lists['sensitive-paths-hostile'] : conflit"]
        result = self._update(config, {"observe_only": False})
        self.assertFalse(result.loaded)
        self.assertIn("conflit", result.error)

    def test_toggle_enabled(self):
        result = self._update(self._loaded(), {"enabled": False})
        self.assertFalse(parse_waf_config(result.config.options["waf"].settings).keyword_lists[0].enabled)

    def test_unknown_list(self):
        result = update_keyword_list_entry(self._loaded(), "nope", {}, filesystem=LocalFilesystem(),
                                           project_root=self.root, config_check=None)
        self.assertFalse(result.loaded)

    def test_remove_keeps_the_file(self):
        config = remove_keyword_list_entry(self._loaded(), "sensitive-paths-hostile")
        self.assertEqual(parse_waf_config(config.options["waf"].settings).keyword_lists, ())
        self.assertTrue((self.root / KEYWORDS_DIR / "sensitive-paths-hostile.txt").exists())


if __name__ == "__main__":
    unittest.main()
