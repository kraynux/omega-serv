import unittest

from omega_serv.domain.security.waf.entities import RuleDefinition, RulePack
from omega_serv.domain.security.waf.signature_engine import compile_rule_pack, evaluate_rules


def _sqli_pack():
    return RulePack(
        version=1,
        pack="body-sqli",
        enabled=True,
        rules=(
            RuleDefinition(id="SQLI-001", description="Union select", scope=("query", "body"), pattern=r"union\s+select", weight=5),
            RuleDefinition(id="SQLI-002", description="Sleep", scope=("query", "body"), pattern=r"sleep\s*\(", weight=5),
        ),
    )


class TestEvaluateRules(unittest.TestCase):
    def test_matching_rule_produces_finding(self):
        compiled = compile_rule_pack(_sqli_pack())
        findings = evaluate_rules((compiled,), {"query": "id=1 UNION SELECT password FROM users"})
        self.assertEqual(len(findings), 1)
        self.assertEqual(findings[0].rule_id, "SQLI-001")
        self.assertEqual(findings[0].weight, 5)

    def test_no_match_produces_no_finding(self):
        compiled = compile_rule_pack(_sqli_pack())
        findings = evaluate_rules((compiled,), {"query": "q=hello world"})
        self.assertEqual(findings, ())

    def test_missing_scope_is_ignored_not_an_error(self):
        compiled = compile_rule_pack(_sqli_pack())
        findings = evaluate_rules((compiled,), {})
        self.assertEqual(findings, ())

    def test_disabled_pack_is_skipped(self):
        pack = _sqli_pack()
        disabled_pack = RulePack(version=1, pack=pack.pack, enabled=False, rules=pack.rules)
        compiled = compile_rule_pack(disabled_pack)
        findings = evaluate_rules((compiled,), {"query": "union select 1"})
        self.assertEqual(findings, ())

    def test_disabled_rule_is_never_compiled(self):
        pack = RulePack(
            version=1, pack="p", enabled=True,
            rules=(RuleDefinition(id="R1", description="", scope=("query",), pattern="x", weight=1, enabled=False),),
        )
        compiled = compile_rule_pack(pack)
        self.assertEqual(compiled.rules, ())

    def test_excluded_pack_is_skipped(self):
        compiled = compile_rule_pack(_sqli_pack())
        findings = evaluate_rules((compiled,), {"query": "union select 1"}, excluded_packs=frozenset({"body-sqli"}))
        self.assertEqual(findings, ())

    def test_multiple_scopes_count_once(self):
        pack = RulePack(
            version=1, pack="p", enabled=True,
            rules=(RuleDefinition(id="R1", description="", scope=("query", "body"), pattern="evil", weight=3),),
        )
        compiled = compile_rule_pack(pack)
        findings = evaluate_rules((compiled,), {"query": "evil", "body": "evil"})
        self.assertEqual(len(findings), 1)

    def test_case_insensitive_by_default(self):
        pack = RulePack(
            version=1, pack="p", enabled=True,
            rules=(RuleDefinition(id="R1", description="", scope=("query",), pattern="UNION", weight=1),),
        )
        compiled = compile_rule_pack(pack)
        findings = evaluate_rules((compiled,), {"query": "union select"})
        self.assertEqual(len(findings), 1)


class TestFoldedFastPath(unittest.TestCase):
    """Voie rapide (texte ASCII en minuscules, sans IGNORECASE) : jamais un resultat different de la voie
    d'origine - preuve structurelle `_folds_safely`, puis comparaison sur toutes les regles livrees."""

    def test_patterns_proven_or_refused(self):
        from omega_serv.domain.security.waf.signature_engine import _folds_safely
        for pattern in (r"sqlmap", r"[;&|]{1,2}\s*(cat|id)\b", r"\S+", r"[^a-z]", r"(\w)\1", r"a\x61", r"(?=foo)bar"):
            self.assertTrue(_folds_safely(pattern), pattern)
        # majuscule (aussi via \x41), plage couvrant A-Z, drapeau local, caractere non ASCII repli sur l'ASCII
        for pattern in (r"HEAD", r"\x41", r"[A-Z]", r"[@-\[]", r"(?-i:b)", "\u017f", "\u212a", r"[\u017f]"):
            self.assertFalse(_folds_safely(pattern), pattern)

    def test_uppercase_rule_keeps_original_search(self):
        pack = RulePack(version=1, pack="p", enabled=True, rules=(
            RuleDefinition(id="R1", description="", scope=("path",), pattern=r"/\.git/HEAD", weight=1),))
        compiled = compile_rule_pack(pack)
        self.assertIsNone(compiled.rules[0].folded_pattern)
        self.assertEqual(len(evaluate_rules((compiled,), {"path": "/.GIT/head"})), 1)

    def test_case_sensitive_rule_never_folded(self):
        pack = RulePack(version=1, pack="p", enabled=True, rules=(
            RuleDefinition(id="R1", description="", scope=("query",), pattern="evil", case_insensitive=False, weight=1),))
        compiled = compile_rule_pack(pack)
        self.assertIsNone(compiled.rules[0].folded_pattern)
        self.assertEqual(evaluate_rules((compiled,), {"query": "EVIL"}), ())

    def test_non_ascii_text_uses_original_search(self):
        pack = RulePack(version=1, pack="p", enabled=True, rules=(
            RuleDefinition(id="R1", description="", scope=("user_agent",), pattern="nikto", weight=1),))
        compiled = compile_rule_pack(pack)
        self.assertIsNotNone(compiled.rules[0].folded_pattern)
        self.assertEqual(len(evaluate_rules((compiled,), {"user_agent": "ni\u212ato é"})), 1)  # K Kelvin

    def test_shipped_rules_same_result_on_both_paths(self):
        import json
        import random
        import re
        from pathlib import Path

        from omega_serv.domain.security.waf.rule_validation import parse_rule_pack

        rules_dir = Path(__file__).resolve().parents[2] / "secure" / "waf" / "rules"
        rng = random.Random(20261104)
        alphabet = "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789 ;&|'\"=()<>/.-_%+\t\n:,?*$#@!"
        samples = [
            "/wp-login.php", "/.GIT/Config", "/.env", "id=1 UNION SELECT password FROM users", "' OR 1=1 --",
            "<ScRiPt>alert(1)</sCrIpT>", "x=1; CAT /etc/passwd", "Mozilla/5.0 (X11; Linux x86_64)", "SQLMAP/1.8",
            "Nikto", "q=bonjour+le+monde&page=3", "WGET http://e.x/a.sh", "ExtractValue(1,2)",
        ]
        samples += ["".join(rng.choice(alphabet) for _ in range(rng.randint(0, 60))) for _ in range(400)]
        folded_count = 0
        for path in sorted(rules_dir.glob("*.json")):
            compiled = compile_rule_pack(parse_rule_pack(json.loads(path.read_text(encoding="utf-8"))))
            for rule in compiled.rules:
                if rule.folded_pattern is None:
                    continue
                folded_count += 1
                # morceaux du motif lui-meme, en casse melangee : les correspondances sont exercees, pas seulement les echecs
                pieces = re.findall(r"[a-z0-9]{2,}", rule.definition.pattern)
                texts = samples + ["".join(c.upper() if rng.random() < 0.5 else c for c in " ".join(pieces[i:i + 3]))
                                   for i in range(len(pieces))]
                for text in texts:
                    expected = bool(rule.pattern.search(text)) and not (rule.exclude is not None and rule.exclude.search(text))
                    got = bool(rule.folded_pattern.search(text.lower())) and not (
                        rule.folded_exclude is not None and rule.folded_exclude.search(text.lower()))
                    self.assertEqual(expected, got, f"{path.name} {rule.definition.id} : {text!r}")
        self.assertGreater(folded_count, 40)

    def test_evaluate_rules_matches_reference_algorithm(self):
        """Meme tuple de constats (ordre, regle, scope retenu) que l'algorithme d'origine (regle par regle,
        premier scope qui matche) - packs livres, textes ASCII, non ASCII, plusieurs scopes a la fois."""
        import json
        import random
        from pathlib import Path

        from omega_serv.domain.security.waf.rule_validation import parse_rule_pack

        def reference(packs, scope_texts):
            found = []
            for compiled_pack in packs:
                if not compiled_pack.enabled:
                    continue
                for compiled_rule in compiled_pack.rules:
                    for scope in compiled_rule.definition.scope:
                        text = scope_texts.get(scope)
                        if text and compiled_rule.pattern.search(text) and not (
                                compiled_rule.exclude is not None and compiled_rule.exclude.search(text)):
                            found.append((compiled_rule.definition.id, compiled_pack.pack, scope))
                            break
            return found

        rules_dir = Path(__file__).resolve().parents[2] / "secure" / "waf" / "rules"
        packs = tuple(compile_rule_pack(parse_rule_pack(json.loads(path.read_text(encoding="utf-8"))))
                      for path in sorted(rules_dir.glob("*.json")))
        pieces = ["/wp-login.php", "/.GIT/HEAD", "/.env", "UNION SELECT", "' or 1=1", "<script>", "; cat ",
                  "sqlmap", "Nikto", "bonjour", "Kelvin \u212a", "é", "/etc/passwd", "wget http://x", "/", "a=1&b=2"]
        rng = random.Random(4)
        matched = 0
        for _ in range(600):
            texts = {scope: "".join(rng.choice(pieces) for _ in range(rng.randint(0, 4)))
                     for scope in ("path", "query", "body", "user_agent", "headers") if rng.random() < 0.8}
            expected = reference(packs, texts)
            matched += bool(expected)
            got = [(f.rule_id, f.pack, f.scope) for f in evaluate_rules(packs, texts)]
            self.assertEqual(expected, got, texts)
        self.assertGreater(matched, 100)


if __name__ == "__main__":
    unittest.main()
