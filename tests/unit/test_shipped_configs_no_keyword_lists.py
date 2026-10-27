"""Aucune configuration livrée n'active les listes de chemins sensibles d'office.

OMEGA-SERV_PLAN-DETAILLE_SENSITIVE_PATHS.md, lot 9.2 (décision A5) : les références
(`sensitive-paths-hostile`, `sensitive-paths-probe`, `referer-spam`) ne sont chargées que par
l'utilisateur, depuis l'assistant Custom. Ni `config/omega-serve.json` ni un profil livré ne
doivent les référencer, sinon une mise à jour activerait des blocages sans accord.
"""
import json
import unittest
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
SHIPPED_CONFIGS = (PROJECT_ROOT / "config/omega-serve.json", *sorted((PROJECT_ROOT / "config/profiles").glob("*.json")))
REFERENCE_DIR = PROJECT_ROOT / "src/omega_serv/infrastructure/waf/keyword_references"


def _waf_options(config: dict) -> dict:
    waf = config.get("options", {}).get("waf", {})
    return waf if isinstance(waf, dict) else {}


class TestShippedConfigsNoKeywordLists(unittest.TestCase):
    def test_shipped_configs_exist(self):
        self.assertTrue((PROJECT_ROOT / "config/omega-serve.json").is_file())
        self.assertGreaterEqual(len(SHIPPED_CONFIGS), 2)

    def test_no_shipped_config_declares_keyword_lists(self):
        for path in SHIPPED_CONFIGS:
            with self.subTest(config=path.name):
                waf = _waf_options(json.loads(path.read_text(encoding="utf-8")))
                self.assertFalse(waf.get("keyword_lists"), f"{path.name} déclare des keyword_lists")

    def test_no_shipped_config_mentions_a_reference_list(self):
        names = [p.stem for p in REFERENCE_DIR.iterdir() if p.is_file()]
        self.assertTrue(names, "références introuvables : le test ne vérifierait rien")
        for path in SHIPPED_CONFIGS:
            text = path.read_text(encoding="utf-8")
            with self.subTest(config=path.name):
                self.assertNotIn("rules/keywords/", text)
                for name in names:
                    self.assertNotIn(name.split(".")[0], text)


if __name__ == "__main__":
    unittest.main()
