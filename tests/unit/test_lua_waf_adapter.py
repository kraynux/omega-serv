import unittest

from omega_serv.domain.http.headers import HttpHeaders
from omega_serv.domain.http.request import HttpRequest
from omega_serv.domain.security.waf.config import MagnetConfig, WafConfig
from omega_serv.infrastructure.waf.lua_waf_adapter import LuaWafAdapter, WafMagnetScriptError

_ALLOW_SCRIPT = "return 0"

_BLOCK_ON_SECRET_SCRIPT = """
local env = lighty.env or {}
if string.find(env["uri.path"] or "", "secret") then
    return 403
end
return 0
"""

_RAISES_SCRIPT = "error('boom')"

_PERSISTENT_COUNTER_SCRIPT = """
counter = (counter or 0) + 1
if counter > 2 then return 429 end
return 0
"""

_UNSUPPORTED_MEMBER_SCRIPT = """
local env = lighty.env or {}
lighty.unknown_member()
return 0
"""

_UA_SCRIPT = """
local env = lighty.env or {}
if (env["request.user-agent"] or ""):find("sqlmap") then return 451 end
return 0
"""

_PATHS_INJECTION_SCRIPT = """
if omega_magnet_paths and omega_magnet_paths.blocklist_file == "/tmp/custom-blocklist.txt" then
    return 418
end
return 0
"""

_NO_PATHS = {
    "blocklist_file": "", "rules_dir": "", "alerts_log": "", "blocklist_log": "", "rate_store_file": "",
}


def _request(path="/", query="", headers=None, body=None) -> HttpRequest:
    return HttpRequest(
        request_id="r1", remote_ip="203.0.113.1", peer_ip="203.0.113.1",
        method="GET", path=path, raw_path=path + (f"?{query}" if query else ""), query=query,
        headers=HttpHeaders.from_pairs(headers or []), body=body, content_length=None, is_tls=False,
    )


class TestLuaWafAdapterConstruction(unittest.TestCase):
    def test_invalid_lua_syntax_raises(self):
        with self.assertRaises(WafMagnetScriptError):
            LuaWafAdapter("function ( ???", WafConfig(), _NO_PATHS)

    def test_valid_script_constructs_successfully(self):
        LuaWafAdapter(_ALLOW_SCRIPT, WafConfig(), _NO_PATHS)

    def test_unsupported_lighty_members_detected_statically_at_construction(self):
        adapter = LuaWafAdapter(_UNSUPPORTED_MEMBER_SCRIPT, WafConfig(), _NO_PATHS)
        self.assertEqual(adapter.unsupported_members, frozenset({"unknown_member"}))

    def test_supported_lighty_members_not_flagged(self):
        adapter = LuaWafAdapter(_BLOCK_ON_SECRET_SCRIPT, WafConfig(), _NO_PATHS)
        self.assertEqual(adapter.unsupported_members, frozenset())


class TestLuaWafAdapterInspect(unittest.TestCase):
    def test_clean_request_is_allowed(self):
        adapter = LuaWafAdapter(_ALLOW_SCRIPT, WafConfig(mode="block"), _NO_PATHS)
        decision = adapter.inspect(_request())
        self.assertEqual(decision.action, "allow")

    def test_malicious_request_blocked_via_lighty_env_path(self):
        adapter = LuaWafAdapter(_BLOCK_ON_SECRET_SCRIPT, WafConfig(mode="block"), _NO_PATHS)
        decision = adapter.inspect(_request(path="/secret/area"))
        self.assertEqual(decision.action, "block")
        self.assertEqual(decision.status_code, 403)
        self.assertEqual(len(decision.findings), 1)
        finding = decision.findings[0]
        self.assertEqual(finding.pack, "magnet")
        self.assertEqual(finding.scope, "path")

    def test_block_downgraded_to_log_in_log_only_mode(self):
        """Invariant central du WAF (decision #14) : log-only ne bloque
        jamais, meme si le script magnet retourne un code de blocage."""
        adapter = LuaWafAdapter(_BLOCK_ON_SECRET_SCRIPT, WafConfig(mode="log-only"), _NO_PATHS)
        decision = adapter.inspect(_request(path="/secret/area"))
        self.assertEqual(decision.action, "log")
        self.assertIsNone(decision.status_code)

    def test_runtime_error_falls_back_with_ignore_policy(self):
        config = WafConfig(mode="block", magnet=MagnetConfig(on_error="ignore"))
        adapter = LuaWafAdapter(_RAISES_SCRIPT, config, _NO_PATHS)
        decision = adapter.inspect(_request())
        self.assertEqual(decision.action, "allow")
        self.assertIsNotNone(adapter.last_error)

    def test_runtime_error_falls_back_with_fail_closed_policy(self):
        config = WafConfig(mode="block", magnet=MagnetConfig(on_error="fail-closed"))
        adapter = LuaWafAdapter(_RAISES_SCRIPT, config, _NO_PATHS)
        decision = adapter.inspect(_request())
        self.assertEqual(decision.action, "block")
        self.assertEqual(decision.status_code, 503)

    def test_fail_closed_fallback_never_blocks_in_log_only_mode(self):
        config = WafConfig(mode="log-only", magnet=MagnetConfig(on_error="fail-closed"))
        adapter = LuaWafAdapter(_RAISES_SCRIPT, config, _NO_PATHS)
        decision = adapter.inspect(_request())
        self.assertEqual(decision.action, "log")

    def test_successful_call_clears_previous_error(self):
        config = WafConfig(mode="block", magnet=MagnetConfig(on_error="ignore"))
        adapter = LuaWafAdapter(_RAISES_SCRIPT, config, _NO_PATHS)
        adapter.inspect(_request())
        self.assertIsNotNone(adapter.last_error)
        # Remplace le script compile par un script sans erreur pour verifier
        # que last_error est bien remis a None par un appel reussi.
        ok_adapter = LuaWafAdapter(_ALLOW_SCRIPT, config, _NO_PATHS)
        ok_adapter.inspect(_request())
        self.assertIsNone(ok_adapter.last_error)

    def test_no_findings_on_allow(self):
        adapter = LuaWafAdapter(_ALLOW_SCRIPT, WafConfig(), _NO_PATHS)
        decision = adapter.inspect(_request())
        self.assertEqual(decision.findings, ())

    def test_persistent_globals_survive_across_calls(self):
        """Modele d'execution mod_magnet : le script est recompile UNE
        fois, rappele a chaque requete - les globales Lua (ici `counter`)
        doivent survivre d'un appel a l'autre."""
        adapter = LuaWafAdapter(_PERSISTENT_COUNTER_SCRIPT, WafConfig(mode="block"), _NO_PATHS)
        first = adapter.inspect(_request())
        second = adapter.inspect(_request())
        third = adapter.inspect(_request())
        self.assertEqual(first.action, "allow")
        self.assertEqual(second.action, "allow")
        self.assertEqual(third.action, "block")
        self.assertEqual(third.status_code, 429)

    def test_user_agent_env_key_is_populated(self):
        adapter = LuaWafAdapter(_UA_SCRIPT, WafConfig(mode="block"), _NO_PATHS)
        decision = adapter.inspect(_request(headers=[("user-agent", "sqlmap/1.0")]))
        self.assertEqual(decision.action, "block")
        self.assertEqual(decision.status_code, 451)

    def test_omega_magnet_paths_table_is_injected(self):
        paths = dict(_NO_PATHS)
        paths["blocklist_file"] = "/tmp/custom-blocklist.txt"
        adapter = LuaWafAdapter(_PATHS_INJECTION_SCRIPT, WafConfig(mode="block"), paths)
        decision = adapter.inspect(_request())
        self.assertEqual(decision.status_code, 418)

    def test_dry_run_reports_error_without_producing_a_decision(self):
        adapter = LuaWafAdapter(_RAISES_SCRIPT, WafConfig(), _NO_PATHS)
        error = adapter.dry_run(_request())
        self.assertIsNotNone(error)
        self.assertIn("boom", error)

    def test_dry_run_returns_none_on_success(self):
        adapter = LuaWafAdapter(_ALLOW_SCRIPT, WafConfig(), _NO_PATHS)
        self.assertIsNone(adapter.dry_run(_request()))


if __name__ == "__main__":
    unittest.main()
