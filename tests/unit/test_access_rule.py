# Copyright (c) 2026 kraynux - kraynux@proton.me - Licence MIT (voir fichier LICENSE)
import unittest

from omega_serv.domain.routing.access_rule import (
    AccessRule,
    has_explicit_allow_match,
    parse_access_rules,
    resolve_access_verdict,
    validate_access_rule,
)


class TestParseAccessRules(unittest.TestCase):
    def test_parses_list_of_dicts(self):
        rules = parse_access_rules([
            {"path_prefix": "/private/", "verdict": "deny"},
            {"path_prefix": "/private/.assets/", "verdict": "allow"},
        ])
        self.assertEqual(rules, [
            AccessRule(path_prefix="/private/", verdict="deny"),
            AccessRule(path_prefix="/private/.assets/", verdict="allow"),
        ])

    def test_empty_list(self):
        self.assertEqual(parse_access_rules([]), [])

    def test_parses_extensions(self):
        rules = parse_access_rules([
            {"path_prefix": "/", "verdict": "deny", "extensions": [".key", ".pem"]},
        ])
        self.assertEqual(rules, [AccessRule(path_prefix="/", verdict="deny", extensions=(".key", ".pem"))])

    def test_missing_extensions_defaults_to_empty_tuple(self):
        rules = parse_access_rules([{"path_prefix": "/", "verdict": "deny"}])
        self.assertEqual(rules[0].extensions, ())


class TestValidateAccessRule(unittest.TestCase):
    def test_valid_rule_passes(self):
        self.assertIsNone(validate_access_rule(AccessRule(path_prefix="/private/", verdict="deny")))

    def test_prefix_without_leading_slash_rejected(self):
        error = validate_access_rule(AccessRule(path_prefix="private/", verdict="deny"))
        self.assertIsNotNone(error)
        assert error is not None
        self.assertIn("path_prefix", error)

    def test_invalid_verdict_rejected(self):
        error = validate_access_rule(AccessRule(path_prefix="/private/", verdict="block"))
        self.assertIsNotNone(error)
        assert error is not None
        self.assertIn("verdict", error)


class TestResolveAccessVerdict(unittest.TestCase):
    def test_no_rules_allows_everything(self):
        self.assertEqual(resolve_access_verdict("/private/secret.txt", []), "allow")

    def test_matching_deny_rule_blocks(self):
        rules = [AccessRule(path_prefix="/private/", verdict="deny")]
        self.assertEqual(resolve_access_verdict("/private/secret.txt", rules), "deny")

    def test_non_matching_path_allowed(self):
        rules = [AccessRule(path_prefix="/private/", verdict="deny")]
        self.assertEqual(resolve_access_verdict("/public/index.html", rules), "allow")

    def test_more_specific_allow_overrides_broader_deny(self):
        rules = [
            AccessRule(path_prefix="/private/", verdict="deny"),
            AccessRule(path_prefix="/private/.assets/", verdict="allow"),
        ]
        self.assertEqual(resolve_access_verdict("/private/.assets/logo.png", rules), "allow")
        self.assertEqual(resolve_access_verdict("/private/secret.txt", rules), "deny")

    def test_more_specific_deny_overrides_broader_allow(self):
        rules = [
            AccessRule(path_prefix="/", verdict="allow"),
            AccessRule(path_prefix="/admin/", verdict="deny"),
        ]
        self.assertEqual(resolve_access_verdict("/admin/panel.html", rules), "deny")
        self.assertEqual(resolve_access_verdict("/index.html", rules), "allow")

    def test_extension_scoped_deny_ignores_non_matching_extensions(self):
        # Retour utilisateur (guide d'aide, point 2) : deny global sur
        # une extension sensible, jamais sur les fichiers ordinaires du
        # meme prefixe.
        rules = [AccessRule(path_prefix="/", verdict="deny", extensions=(".key",))]
        self.assertEqual(resolve_access_verdict("/anywhere/secret.key", rules), "deny")
        self.assertEqual(resolve_access_verdict("/anywhere/normal.txt", rules), "allow")

    def test_extension_scoped_deny_lifted_by_more_specific_allow_zone(self):
        # Exemple lighttpd de l'utilisateur : bloquer .key/.pem/etc.
        # PARTOUT SAUF sous /dossiers/ - l'allow plus specifique gagne
        # meme si lui n'a pas de restriction d'extension.
        rules = [
            AccessRule(path_prefix="/", verdict="deny", extensions=(".key", ".pem")),
            AccessRule(path_prefix="/dossiers/", verdict="allow"),
        ]
        self.assertEqual(resolve_access_verdict("/dossiers/secret.key", rules), "allow")
        self.assertEqual(resolve_access_verdict("/public/secret.key", rules), "deny")
        self.assertEqual(resolve_access_verdict("/dossiers/normal.txt", rules), "allow")

    def test_extension_match_is_case_insensitive(self):
        rules = [AccessRule(path_prefix="/", verdict="deny", extensions=(".KEY",))]
        self.assertEqual(resolve_access_verdict("/secret.key", rules), "deny")


class TestHasExplicitAllowMatch(unittest.TestCase):
    def test_no_rules_is_not_explicit(self):
        self.assertFalse(has_explicit_allow_match("/private/.assets/logo.png", []))

    def test_no_matching_rule_is_not_explicit(self):
        rules = [AccessRule(path_prefix="/other/", verdict="allow")]
        self.assertFalse(has_explicit_allow_match("/private/.assets/logo.png", rules))

    def test_matching_deny_is_not_explicit_allow(self):
        rules = [AccessRule(path_prefix="/private/", verdict="deny")]
        self.assertFalse(has_explicit_allow_match("/private/secret.txt", rules))

    def test_matching_allow_is_explicit(self):
        rules = [
            AccessRule(path_prefix="/private/", verdict="deny"),
            AccessRule(path_prefix="/private/.assets/", verdict="allow"),
        ]
        self.assertTrue(has_explicit_allow_match("/private/.assets/logo.png", rules))


if __name__ == "__main__":
    unittest.main()
