"""Listes de chemins (keyword_lists, match="path") - OMEGA-SERV_PLAN-
DETAILLE_SENSITIVE_PATHS.md §3.1/§3.10. Teste de bout en bout via le VRAI
moteur (PythonWafEngine : decodage URL + NFKC compris), jamais une
reimplementation du matching dans le test."""
import unittest
from pathlib import Path

from omega_serv.domain.http.headers import HttpHeaders
from omega_serv.domain.http.request import HttpRequest
from omega_serv.domain.security.waf.config import parse_waf_config
from omega_serv.domain.security.waf.entities import KeywordListDefinition
from omega_serv.domain.security.waf.exceptions import WafRuleLoadError
from omega_serv.domain.security.waf.keyword_list import (
    RECOMMENDED_MAX_ENTRIES,
    VITAL_PATHS,
    analyze_path_list_text,
    build_rule_pack_from_keyword_list,
    compile_path_token,
    tokens_from_text,
)
from omega_serv.domain.security.waf.signature_engine import compile_rule_pack
from omega_serv.infrastructure.waf.keyword_list_loader import load_keyword_list
from omega_serv.infrastructure.waf.python_waf_engine import PythonWafEngine

_REFERENCES = Path(__file__).resolve().parents[2] / "src" / "omega_serv" / "infrastructure" / "waf" / "keyword_references"


def _request(path: str) -> HttpRequest:
    return HttpRequest(
        request_id="r1", remote_ip="203.0.113.1", peer_ip="203.0.113.1",
        method="GET", path=path, raw_path=path, query="",
        headers=HttpHeaders.from_pairs([]), body=None, content_length=None, is_tls=False,
    )


def _definition(**overrides) -> KeywordListDefinition:
    values = {"id": "sensitive-paths-test", "scope": ("path",), "file": "x.txt", "weight": 6, "match": "path"}
    values.update(overrides)
    return KeywordListDefinition(**values)


def _engine(text: str, **overrides) -> PythonWafEngine:
    pack = compile_rule_pack(build_rule_pack_from_keyword_list(_definition(**overrides), tokens_from_text(text)))
    return PythonWafEngine((pack,), parse_waf_config({"mode": "block"}))


def _matches(engine: PythonWafEngine, path: str) -> bool:
    return bool(engine.inspect(_request(path)).findings)


class _FakeFilesystem:
    def __init__(self, content: str):
        self._content = content

    def exists(self, path):
        return True

    def read_text(self, path):
        return self._content


class TestCompilePathToken(unittest.TestCase):
    def test_segment_any_reuses_custom_rule_pattern(self):
        self.assertEqual(compile_path_token("/admin", "any_segment"), "/admin(/|$)")

    def test_segment_root_is_anchored(self):
        self.assertEqual(compile_path_token("/admin", "root"), "^/admin(/|$)")

    def test_trailing_slash_directory_form(self):
        self.assertEqual(compile_path_token("/.git/", "any_segment"), r"/\.git(/|$)")

    def test_suffix_ignores_anchor(self):
        self.assertEqual(compile_path_token("/*.bak", "root"), r"\.bak$")
        self.assertEqual(compile_path_token("/*.bak", "any_segment"), r"\.bak$")


class TestPathMatching(unittest.TestCase):
    def test_segment_boundaries_prevent_false_positives(self):
        engine = _engine("/auth\n/admin\n/test\n/dev\n/cas\n")
        for legit in ("/author/kray", "/administration-guide", "/testimonials", "/devices", "/casino"):
            with self.subTest(path=legit):
                self.assertFalse(_matches(engine, legit))

    def test_exact_and_subpaths_match(self):
        engine = _engine("/admin\n")
        for hit in ("/admin", "/admin/", "/admin/login"):
            with self.subTest(path=hit):
                self.assertTrue(_matches(engine, hit))

    def test_any_segment_catches_subfolder_probes(self):
        engine = _engine("/.env\n/.git/\n", anchor="any_segment")
        self.assertTrue(_matches(engine, "/blog/.env"))
        self.assertTrue(_matches(engine, "/wp/.git/config"))

    def test_root_anchor_ignores_subfolders(self):
        engine = _engine("/api\n", anchor="root")
        self.assertTrue(_matches(engine, "/api/v1/users"))
        self.assertFalse(_matches(engine, "/shop/api"))

    def test_suffix_joker(self):
        engine = _engine("/*.bak\n")
        self.assertTrue(_matches(engine, "/index.php.bak"))
        self.assertFalse(_matches(engine, "/backup-policy.html"))

    def test_case_insensitive(self):
        self.assertTrue(_matches(_engine("/phpmyadmin\n"), "/phpMyAdmin/"))

    def test_url_encoding_is_decoded_before_matching(self):
        engine = _engine("/.env\n")
        for encoded in ("/%2e%65nv", "/%252eenv"):
            with self.subTest(path=encoded):
                self.assertTrue(_matches(engine, encoded))

    def test_fullwidth_unicode_is_normalized(self):
        self.assertTrue(_matches(_engine("/.env\n"), "/．ｅｎｖ"))

    def test_regex_metacharacters_are_literal(self):
        engine = _engine("/a.b\n")
        self.assertTrue(_matches(engine, "/a.b"))
        self.assertFalse(_matches(engine, "/axb"))


class TestExceptions(unittest.TestCase):
    def test_exception_wins_over_entry(self):
        engine = _engine("/api\n!/api/v1\n", anchor="root")
        self.assertFalse(_matches(engine, "/api/v1/users"))
        self.assertTrue(_matches(engine, "/api/v2"))

    def test_exception_wins_whatever_the_line_order(self):
        engine = _engine("!/api/v1\n/api\n", anchor="root")
        self.assertFalse(_matches(engine, "/api/v1"))

    def test_exception_lines_are_not_entries(self):
        pack = build_rule_pack_from_keyword_list(_definition(), ("!/x", "/y"))
        rule = pack.rules[0]
        self.assertIsNotNone(rule.exclude_pattern)
        self.assertIn("1 entrée(s), 1 exception(s)", rule.description)

    def test_no_exception_means_no_exclude_pattern(self):
        rule = build_rule_pack_from_keyword_list(_definition(), ("/y",)).rules[0]
        self.assertIsNone(rule.exclude_pattern)


class TestObserveOnly(unittest.TestCase):
    def test_observe_only_logs_but_never_scores(self):
        engine = _engine("/.env\n", observe_only=True)
        decision = engine.inspect(_request("/.env"))
        self.assertEqual(len(decision.findings), 1)
        self.assertEqual(decision.score, 0)
        self.assertEqual(decision.action, "log")

    def test_normal_list_blocks_at_weight_6(self):
        decision = _engine("/.env\n").inspect(_request("/.env"))
        self.assertEqual(decision.action, "block")


class TestSubstringModeUnchanged(unittest.TestCase):
    def test_default_definition_builds_exactly_the_legacy_rule(self):
        definition = KeywordListDefinition(id="REFERER-SPAM", scope=("referer",), file="f.txt", weight=3)
        rule = build_rule_pack_from_keyword_list(definition, ("casino", "viagra")).rules[0]
        self.assertEqual(rule.pattern, "(casino|viagra)")
        self.assertEqual(rule.description, "Liste de mots-clefs (2 entrée(s))")
        self.assertEqual(rule.weight, 3)
        self.assertIsNone(rule.exclude_pattern)

    def test_exclamation_is_a_plain_keyword_in_substring_mode(self):
        definition = KeywordListDefinition(id="K", scope=("referer",), file="f.txt")
        rule = build_rule_pack_from_keyword_list(definition, ("!promo",)).rules[0]
        self.assertEqual(rule.pattern, "(!promo)")


class TestAnalyzePathListText(unittest.TestCase):
    def _errors(self, text: str, anchor: str = "any_segment"):
        return analyze_path_list_text(text, anchor).errors

    def test_valid_text_has_no_diagnostic(self):
        analysis = analyze_path_list_text("# titre\n/.env\n\n/.git/\n/*.bak\n!/x\n", "any_segment")
        self.assertEqual(analysis.diagnostics, ())
        self.assertEqual(analysis.entries, ("/.env", "/.git/", "/*.bak"))
        self.assertEqual(analysis.exceptions, ("/x",))

    def test_line_numbers_are_real_file_lines(self):
        errors = self._errors("# commentaire\n\n/ok\nadmin\n")
        self.assertEqual(len(errors), 1)
        self.assertEqual(errors[0].line, 4)

    def test_syntax_errors(self):
        for bad in ("admin", "/a b", "/*", "/*.", "/", "/x*y"):
            with self.subTest(line=bad):
                self.assertEqual(len(self._errors(bad + "\n")), 1)

    def test_every_vital_path_is_protected(self):
        for vital in VITAL_PATHS:
            with self.subTest(vital=vital):
                errors = self._errors(vital + "\n")
                self.assertEqual(len(errors), 1)
                # "/" est deja refuse par la syntaxe (entree vide), avant le controle des chemins vitaux
                self.assertIn("entrée vide" if vital == "/" else "chemin vital", errors[0].message)

    def test_well_known_prefix_refused_because_of_acme(self):
        errors = self._errors("/.well-known/\n")
        self.assertIn("acme-challenge", errors[0].message)

    def test_duplicate_is_a_warning_case_insensitive(self):
        analysis = analyze_path_list_text("/x\n/X\n", "any_segment")
        self.assertEqual(analysis.errors, ())
        self.assertEqual(len(analysis.warnings), 1)
        self.assertIn("ligne 1", analysis.warnings[0].message)

    def test_too_many_entries_is_a_warning(self):
        text = "".join(f"/p{i}\n" for i in range(RECOMMENDED_MAX_ENTRIES + 1))
        analysis = analyze_path_list_text(text, "any_segment")
        self.assertEqual(analysis.errors, ())
        self.assertEqual(len(analysis.warnings), 1)


class TestLoaderRefusesInvalidPathList(unittest.TestCase):
    def test_invalid_list_raises_with_line_number(self):
        with self.assertRaises(WafRuleLoadError) as ctx:
            load_keyword_list(_FakeFilesystem("/ok\n/robots.txt\n"), _definition(), Path("x.txt"))
        self.assertIn("ligne 2", str(ctx.exception))

    def test_substring_list_is_never_path_validated(self):
        definition = KeywordListDefinition(id="K", scope=("referer",), file="f.txt")
        pack = load_keyword_list(_FakeFilesystem("casino\nrobots\n"), definition, Path("f.txt"))
        self.assertEqual(len(pack.rules), 1)


class TestShippedReferences(unittest.TestCase):
    """Les references livrees doivent toujours se charger sans aucune
    erreur ni avertissement : une edition future qui casse la syntaxe est
    detectee ici, jamais en production (plan lot 4.4)."""

    def test_references_are_clean(self):
        for name, anchor, expected in (
            ("sensitive-paths-hostile.txt", "any_segment", 298),
            ("sensitive-paths-probe.txt", "root", 132),
        ):
            with self.subTest(reference=name):
                analysis = analyze_path_list_text((_REFERENCES / name).read_text(encoding="utf-8"), anchor)
                self.assertEqual(analysis.diagnostics, ())
                self.assertEqual(len(analysis.entries), expected)

    def test_hostile_reference_blocks_classic_probes_and_spares_vital_paths(self):
        engine = _engine((_REFERENCES / "sensitive-paths-hostile.txt").read_text(encoding="utf-8"))
        for probe in ("/.env", "/blog/.git/config", "/wp-config.php", "/backup.sql", "/etc/passwd"):
            with self.subTest(probe=probe):
                self.assertTrue(_matches(engine, probe))
        for vital in VITAL_PATHS:
            with self.subTest(vital=vital):
                self.assertFalse(_matches(engine, vital))


if __name__ == "__main__":
    unittest.main()
