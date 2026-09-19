import re
import unittest

from omega_serv.domain.security.waf.rule_validation import (
    build_keyword_pattern,
    build_path_segment_pattern,
    parse_rule_pack,
    validate_rule_pack,
)


def _valid_pack_data():
    return {
        "version": 1,
        "pack": "body-sqli",
        "enabled": True,
        "rules": [
            {"id": "SQLI-001", "description": "Union select", "scope": ["query", "body"], "pattern": r"union\s+select", "weight": 5},
        ],
    }


class TestParseRulePack(unittest.TestCase):
    def test_parses_valid_pack(self):
        pack = parse_rule_pack(_valid_pack_data())
        self.assertEqual(pack.pack, "body-sqli")
        self.assertEqual(len(pack.rules), 1)
        self.assertEqual(pack.rules[0].weight, 5)


class TestValidateRulePack(unittest.TestCase):
    def test_valid_pack_passes(self):
        pack = parse_rule_pack(_valid_pack_data())
        self.assertEqual(validate_rule_pack(pack), [])

    def test_unsupported_version_rejected(self):
        data = _valid_pack_data()
        data["version"] = 2
        pack = parse_rule_pack(data)
        errors = validate_rule_pack(pack)
        self.assertTrue(any("version" in e for e in errors))

    def test_duplicate_id_rejected(self):
        data = _valid_pack_data()
        data["rules"].append(dict(data["rules"][0]))
        pack = parse_rule_pack(data)
        errors = validate_rule_pack(pack)
        self.assertTrue(any("duplique" in e for e in errors))

    def test_unknown_scope_rejected(self):
        data = _valid_pack_data()
        data["rules"][0]["scope"] = ["cookies"]
        pack = parse_rule_pack(data)
        errors = validate_rule_pack(pack)
        self.assertTrue(any("scope inconnu" in e for e in errors))

    def test_invalid_regex_rejected(self):
        data = _valid_pack_data()
        data["rules"][0]["pattern"] = "("
        pack = parse_rule_pack(data)
        errors = validate_rule_pack(pack)
        self.assertTrue(any("regex invalide" in e for e in errors))

    def test_negative_weight_rejected(self):
        data = _valid_pack_data()
        data["rules"][0]["weight"] = -1
        pack = parse_rule_pack(data)
        errors = validate_rule_pack(pack)
        self.assertTrue(any("weight" in e for e in errors))

    def test_unsupported_action_rejected(self):
        data = _valid_pack_data()
        data["rules"][0]["action"] = "block"
        pack = parse_rule_pack(data)
        errors = validate_rule_pack(pack)
        self.assertTrue(any("action non supportee" in e for e in errors))


class TestBuildPathSegmentPattern(unittest.TestCase):
    """Retour utilisateur 2026-09-14 : assistant de creation de regle
    WAF Custom pour un utilisateur qui ne sait pas ecrire de regex."""

    def test_matches_the_exact_path_and_subpaths(self):
        pattern = build_path_segment_pattern("admin")
        self.assertRegex("/admin", pattern)
        self.assertRegex("/admin/dashboard", pattern)

    def test_does_not_match_a_longer_word(self):
        pattern = build_path_segment_pattern("admin")
        self.assertNotRegex("/administrator", pattern)
        self.assertNotRegex("/adminer", pattern)

    def test_strips_leading_and_trailing_slashes_from_input(self):
        self.assertEqual(build_path_segment_pattern("/admin/"), build_path_segment_pattern("admin"))

    def test_special_characters_in_input_are_escaped_not_interpreted(self):
        pattern = build_path_segment_pattern("prix.php")
        self.assertRegex("/prix.php", pattern)
        self.assertNotRegex("/prixXphp", pattern)

    def test_empty_segment_produces_an_empty_pattern(self):
        self.assertEqual(build_path_segment_pattern(""), "")
        self.assertEqual(build_path_segment_pattern("   "), "")


class TestBuildKeywordPattern(unittest.TestCase):
    def test_matches_the_word_anywhere(self):
        pattern = build_keyword_pattern("union select")
        self.assertRegex("1 UNION SELECT password".lower(), pattern.lower())
        self.assertTrue(re.search(pattern, "?q=1 union select password", re.IGNORECASE))

    def test_special_characters_are_escaped(self):
        pattern = build_keyword_pattern("a.b")
        self.assertTrue(re.search(pattern, "a.b"))
        self.assertFalse(re.search(pattern, "aXb"))


if __name__ == "__main__":
    unittest.main()
