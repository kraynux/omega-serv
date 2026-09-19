import unittest

from omega_serv.domain.http.headers import HttpHeaders
from omega_serv.domain.http.request import HttpRequest
from omega_serv.domain.security.waf.config import parse_waf_config
from omega_serv.domain.security.waf.entities import RuleDefinition, RulePack
from omega_serv.domain.security.waf.signature_engine import compile_rule_pack
from omega_serv.infrastructure.waf.python_waf_engine import PythonWafEngine


def _request(method="GET", path="/", query="", headers=None, body=None) -> HttpRequest:
    return HttpRequest(
        request_id="r1", remote_ip="203.0.113.1", peer_ip="203.0.113.1",
        method=method, path=path, raw_path=path, query=query,
        headers=HttpHeaders.from_pairs(headers or []), body=body, content_length=None, is_tls=False,
    )


def _sqli_pack():
    return compile_rule_pack(RulePack(
        version=1, pack="body-sqli", enabled=True,
        rules=(RuleDefinition(id="SQLI-001", description="", scope=("query", "body"), pattern=r"union\s+select", weight=5),),
    ))


class TestPythonWafEngine(unittest.TestCase):
    def test_clean_request_is_allowed(self):
        engine = PythonWafEngine((_sqli_pack(),), parse_waf_config({"mode": "block"}))
        decision = engine.inspect(_request(query="q=hello"))
        self.assertEqual(decision.action, "allow")

    def test_malicious_query_blocked_in_block_mode(self):
        engine = PythonWafEngine((_sqli_pack(),), parse_waf_config({"mode": "block", "scoring": {"block_threshold": 5}}))
        decision = engine.inspect(_request(query="id=1 union select password from users"))
        self.assertEqual(decision.action, "block")
        self.assertEqual(decision.status_code, 403)

    def test_malicious_query_only_logged_in_log_only_mode(self):
        engine = PythonWafEngine((_sqli_pack(),), parse_waf_config({"mode": "log-only", "scoring": {"block_threshold": 5}}))
        decision = engine.inspect(_request(query="id=1 union select password from users"))
        self.assertEqual(decision.action, "log")

    def test_body_inspected_only_for_configured_methods(self):
        engine = PythonWafEngine(
            (_sqli_pack(),),
            parse_waf_config({"mode": "block", "inspect": {"body_methods": ["POST"]}}),
        )
        get_decision = engine.inspect(_request(method="GET", body=b"union select 1"))
        self.assertEqual(get_decision.action, "allow")
        post_decision = engine.inspect(_request(method="POST", body=b"union select 1"))
        self.assertEqual(post_decision.action, "block")

    def test_user_agent_scope_available_when_present(self):
        pack = compile_rule_pack(RulePack(
            version=1, pack="scanner-ua", enabled=True,
            rules=(RuleDefinition(id="UA-001", description="", scope=("user_agent",), pattern="sqlmap", weight=5),),
        ))
        engine = PythonWafEngine((pack,), parse_waf_config({"mode": "block"}))
        decision = engine.inspect(_request(headers=[("User-Agent", "sqlmap/1.6")]))
        self.assertEqual(decision.action, "block")

    def test_headers_scope_only_used_when_configured(self):
        pack = compile_rule_pack(RulePack(
            version=1, pack="p", enabled=True,
            rules=(RuleDefinition(id="H-001", description="", scope=("headers",), pattern="evil-header-value", weight=5),),
        ))
        engine = PythonWafEngine((pack,), parse_waf_config({"mode": "block", "inspect": {"headers": False}}))
        decision = engine.inspect(_request(headers=[("X-Custom", "evil-header-value")]))
        self.assertEqual(decision.action, "allow")

        engine_with_headers = PythonWafEngine((pack,), parse_waf_config({"mode": "block", "inspect": {"headers": True}}))
        decision2 = engine_with_headers.inspect(_request(headers=[("X-Custom", "evil-header-value")]))
        self.assertEqual(decision2.action, "block")


if __name__ == "__main__":
    unittest.main()
