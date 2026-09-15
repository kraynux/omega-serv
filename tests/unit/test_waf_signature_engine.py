# Copyright (c) 2026 kraynux - kraynux@proton.me - Licence MIT (voir fichier LICENSE)
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


if __name__ == "__main__":
    unittest.main()
