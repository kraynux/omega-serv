import unittest

from omega_serv.domain.security.waf.entities import KeywordListDefinition
from omega_serv.domain.security.waf.keyword_list import (
    build_rule_pack_from_keyword_list,
    compile_keyword_pattern,
    parse_keyword_list_definition,
    tokens_from_text,
    validate_keyword_list_definition,
    validate_keyword_list_definitions,
)


class TestTokensFromText(unittest.TestCase):
    def test_one_token_per_line(self):
        self.assertEqual(tokens_from_text("casino\nviagra\n"), ("casino", "viagra"))

    def test_blank_lines_ignored(self):
        self.assertEqual(tokens_from_text("casino\n\n\nviagra\n"), ("casino", "viagra"))

    def test_comment_lines_ignored(self):
        self.assertEqual(
            tokens_from_text("# commentaire\ncasino\n   # autre commentaire indente\nviagra\n"),
            ("casino", "viagra"),
        )

    def test_surrounding_whitespace_stripped(self):
        self.assertEqual(tokens_from_text("  casino  \n"), ("casino",))

    def test_empty_text_produces_no_tokens(self):
        self.assertEqual(tokens_from_text(""), ())


class TestCompileKeywordPattern(unittest.TestCase):
    def test_single_token(self):
        self.assertEqual(compile_keyword_pattern(("casino",)), "(casino)")

    def test_multiple_tokens_joined_by_alternation(self):
        self.assertEqual(compile_keyword_pattern(("casino", "viagra")), "(casino|viagra)")

    def test_special_characters_are_escaped(self):
        pattern = compile_keyword_pattern(("a.b", "c(d)"))
        self.assertIn(r"a\.b", pattern)
        self.assertIn(r"c\(d\)", pattern)


class TestParseKeywordListDefinition(unittest.TestCase):
    def test_parses_valid_definition(self):
        definition = parse_keyword_list_definition({
            "id": "REFERER-SPAM", "scope": ["referer"], "file": "secure/waf/rules/keywords/referer-spam.txt",
            "weight": 3, "enabled": True,
        })
        self.assertEqual(definition.id, "REFERER-SPAM")
        self.assertEqual(definition.scope, ("referer",))
        self.assertEqual(definition.weight, 3)
        self.assertTrue(definition.enabled)

    def test_defaults_applied(self):
        definition = parse_keyword_list_definition({"id": "X", "scope": ["referer"], "file": "f.txt"})
        self.assertEqual(definition.weight, 1)
        self.assertTrue(definition.enabled)


class TestValidateKeywordListDefinition(unittest.TestCase):
    def _valid(self) -> KeywordListDefinition:
        return KeywordListDefinition(id="REFERER-SPAM", scope=("referer",), file="secure/waf/rules/keywords/x.txt")

    def test_valid_definition_passes(self):
        self.assertEqual(validate_keyword_list_definition(self._valid()), [])

    def test_empty_id_rejected(self):
        definition = KeywordListDefinition(id="", scope=("referer",), file="f.txt")
        errors = validate_keyword_list_definition(definition)
        self.assertTrue(any("id" in e for e in errors))

    def test_empty_scope_rejected(self):
        definition = KeywordListDefinition(id="X", scope=(), file="f.txt")
        errors = validate_keyword_list_definition(definition)
        self.assertTrue(any("scope" in e for e in errors))

    def test_unknown_scope_rejected(self):
        definition = KeywordListDefinition(id="X", scope=("cookies",), file="f.txt")
        errors = validate_keyword_list_definition(definition)
        self.assertTrue(any("scope inconnu" in e for e in errors))

    def test_absolute_path_rejected(self):
        definition = KeywordListDefinition(id="X", scope=("referer",), file="/etc/passwd")
        errors = validate_keyword_list_definition(definition)
        self.assertTrue(any("chemin relatif" in e for e in errors))

    def test_path_traversal_rejected(self):
        definition = KeywordListDefinition(id="X", scope=("referer",), file="../../etc/passwd")
        errors = validate_keyword_list_definition(definition)
        self.assertTrue(any("chemin relatif" in e for e in errors))

    def test_negative_weight_rejected(self):
        definition = KeywordListDefinition(id="X", scope=("referer",), file="f.txt", weight=-1)
        errors = validate_keyword_list_definition(definition)
        self.assertTrue(any("weight" in e for e in errors))


class TestValidateKeywordListDefinitions(unittest.TestCase):
    def test_duplicate_id_rejected(self):
        definitions = (
            KeywordListDefinition(id="X", scope=("referer",), file="a.txt"),
            KeywordListDefinition(id="X", scope=("referer",), file="b.txt"),
        )
        errors = validate_keyword_list_definitions(definitions)
        self.assertTrue(any("duplique" in e for e in errors))


class TestBuildRulePackFromKeywordList(unittest.TestCase):
    def test_builds_single_rule_pack(self):
        definition = KeywordListDefinition(id="REFERER-SPAM", scope=("referer",), file="x.txt", weight=5)
        pack = build_rule_pack_from_keyword_list(definition, ("casino", "viagra"))
        self.assertEqual(pack.pack, "REFERER-SPAM")
        self.assertEqual(len(pack.rules), 1)
        rule = pack.rules[0]
        self.assertEqual(rule.scope, ("referer",))
        self.assertEqual(rule.weight, 5)
        self.assertIn("casino", rule.pattern)
        self.assertIn("viagra", rule.pattern)

    def test_empty_token_list_never_matches_but_compiles(self):
        import re
        definition = KeywordListDefinition(id="EMPTY", scope=("referer",), file="x.txt")
        pack = build_rule_pack_from_keyword_list(definition, ())
        compiled = re.compile(pack.rules[0].pattern)
        self.assertIsNone(compiled.search("anything"))


if __name__ == "__main__":
    unittest.main()
