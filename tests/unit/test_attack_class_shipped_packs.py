"""Classe d'attaque des packs WAF REELLEMENT livres (decision utilisateur 2026-11-01) : chaque pack de
secure/waf/rules/ recoit la classe attendue par Active Defense ET par RIPOSTE (une seule heuristique,
domain/security/active_defense/policies.py::attack_class_for_packs). Un pack livre sans classe echoue ici
au lieu de tomber silencieusement en « unknown »."""
import json
import unittest
from pathlib import Path

from omega_serv.domain.security.active_defense.policies import attack_class_for_packs
from omega_serv.domain.security.active_defense.value_objects import KNOWN_ATTACK_CLASSES

_RULES_DIR = Path(__file__).resolve().parents[2] / "secure" / "waf" / "rules"

EXPECTED = {
    "body-cmdi": "command_injection",
    "body-sqli": "sqli",
    "body-xss": "xss",
    "scanner-ua": "scan",
    "sensitive-paths": "scan",
    "wordpress-probes": "scan",
    "custom": "unknown",  # pack personnel de l'utilisateur : aucune classe devinee
}


class TestShippedPacks(unittest.TestCase):
    def test_every_shipped_pack_has_its_expected_class(self):
        packs = {json.loads(p.read_text(encoding="utf-8"))["pack"] for p in _RULES_DIR.glob("*.json")}
        self.assertEqual(packs, set(EXPECTED), "pack livre ajoute ou retire : completer EXPECTED (et l'heuristique)")
        for pack, expected in EXPECTED.items():
            self.assertEqual(attack_class_for_packs([pack]), expected, pack)

    def test_command_injection_is_a_known_class(self):
        self.assertIn("command_injection", KNOWN_ATTACK_CLASSES)

    def test_first_classified_pack_wins_when_several_rules_match(self):
        self.assertEqual(attack_class_for_packs(["custom", "body-cmdi", "body-sqli"]), "command_injection")


if __name__ == "__main__":
    unittest.main()
