import unittest

from omega_serv.domain.config.entities import SecurityConfig
from omega_serv.domain.http.response import HttpResponse
from omega_serv.domain.http.status_codes import HttpStatus
from omega_serv.domain.routing.zone_resolver import Zone
from omega_serv.domain.security.csp import (
    DEFAULT_CSP_POLICY,
    build_csp_policy,
    csp_header_name,
    csp_policy_for_path,
    find_csp_risks,
    parse_csp_directives,
)
from omega_serv.domain.security.security_headers import (
    STATIC_SECURITY_HEADERS,
    apply_security_headers,
)


class TestCsp(unittest.TestCase):
    def test_enforce_mode_uses_standard_header_name(self):
        self.assertEqual(csp_header_name("enforce"), "Content-Security-Policy")

    def test_report_only_mode_uses_report_only_header_name(self):
        self.assertEqual(csp_header_name("report-only"), "Content-Security-Policy-Report-Only")

    def test_default_policy_denies_by_default(self):
        self.assertIn("default-src 'none'", DEFAULT_CSP_POLICY)
        self.assertIn("object-src 'none'", DEFAULT_CSP_POLICY)


class TestCspPolicyForPath(unittest.TestCase):
    def test_no_zones_returns_default(self):
        self.assertEqual(csp_policy_for_path("/anything", ()), DEFAULT_CSP_POLICY)

    def test_no_path_returns_default_even_with_zones_configured(self):
        zones = (Zone("/public/", "default-src 'self' 'unsafe-inline'"),)
        self.assertEqual(csp_policy_for_path(None, zones), DEFAULT_CSP_POLICY)

    def test_matching_zone_returns_its_own_policy_verbatim(self):
        zones = (Zone("/public/", "default-src 'self' 'unsafe-inline'"),)
        self.assertEqual(csp_policy_for_path("/public/widget.html", zones), "default-src 'self' 'unsafe-inline'")

    def test_non_matching_path_returns_default(self):
        zones = (Zone("/public/", "default-src 'self' 'unsafe-inline'"),)
        self.assertEqual(csp_policy_for_path("/private/data", zones), DEFAULT_CSP_POLICY)

    def test_most_specific_zone_wins(self):
        zones = (
            Zone("/public/", "default-src 'self'"),
            Zone("/public/legacy/", "default-src 'self' 'unsafe-inline'"),
        )
        self.assertEqual(csp_policy_for_path("/public/legacy/old.html", zones), "default-src 'self' 'unsafe-inline'")


class TestCspDirectiveHelpers(unittest.TestCase):
    """Retour utilisateur 2026-10-10 : assistant par directive pour
    l'ajout d'une zone CSP (interfaces/tui/screens/
    csp_zone_wizard_screen.py) - ces fonctions pures en sont le coeur."""

    def test_parse_splits_each_directive(self):
        directives = parse_csp_directives(DEFAULT_CSP_POLICY)
        self.assertEqual(directives["default-src"], "'none'")
        self.assertEqual(directives["object-src"], "'none'")
        self.assertEqual(directives["img-src"], "'self' data:")

    def test_parse_keeps_unknown_directives_verbatim(self):
        directives = parse_csp_directives("default-src 'self'; worker-src 'self'")
        self.assertEqual(directives["worker-src"], "'self'")

    def test_build_round_trips_the_default_policy(self):
        directives = parse_csp_directives(DEFAULT_CSP_POLICY)
        self.assertEqual(build_csp_policy(directives), DEFAULT_CSP_POLICY)

    def test_build_omits_empty_directives(self):
        policy = build_csp_policy({"default-src": "'none'", "script-src": ""})
        self.assertEqual(policy, "default-src 'none'")

    def test_build_keeps_known_directive_order_then_unknown(self):
        policy = build_csp_policy({"object-src": "'none'", "default-src": "'self'", "worker-src": "'self'"})
        self.assertEqual(policy, "default-src 'self'; object-src 'none'; worker-src 'self'")

    def test_find_risks_detects_unsafe_inline(self):
        self.assertEqual(find_csp_risks("style-src 'self' 'unsafe-inline'"), ["style-src"])

    def test_find_risks_detects_unsafe_eval_and_wildcard(self):
        risks = find_csp_risks("script-src 'unsafe-eval'; img-src *")
        self.assertEqual(set(risks), {"script-src", "img-src"})

    def test_find_risks_empty_on_strict_policy(self):
        self.assertEqual(find_csp_risks(DEFAULT_CSP_POLICY), [])


class TestApplySecurityHeaders(unittest.TestCase):
    def test_headers_applied_when_enabled(self):
        response = HttpResponse.empty(HttpStatus.OK)
        apply_security_headers(response, SecurityConfig(security_headers_enabled=True, csp_mode="enforce"))
        for name in STATIC_SECURITY_HEADERS:
            self.assertIn(name, response.headers)
        self.assertIn("Content-Security-Policy", response.headers)

    def test_report_only_csp_header_used_when_configured(self):
        response = HttpResponse.empty(HttpStatus.OK)
        apply_security_headers(response, SecurityConfig(security_headers_enabled=True, csp_mode="report-only"))
        self.assertIn("Content-Security-Policy-Report-Only", response.headers)
        self.assertNotIn("Content-Security-Policy", response.headers)

    def test_nothing_applied_when_disabled(self):
        response = HttpResponse.empty(HttpStatus.OK)
        apply_security_headers(response, SecurityConfig(security_headers_enabled=False))
        self.assertEqual(response.headers, {})

    def test_coep_always_emitted_explicitly_even_at_the_permissive_default(self):
        """Retour utilisateur 2026-10-10 : un scanner externe signalait
        l'absence de Cross-Origin-Embedder-Policy - toujours emis, meme
        permissif, pour distinguer "non considere" de "permissif par
        choix explicite"."""
        response = HttpResponse.empty(HttpStatus.OK)
        apply_security_headers(response, SecurityConfig(security_headers_enabled=True))
        self.assertEqual(response.headers["Cross-Origin-Embedder-Policy"], "unsafe-none")

    def test_coep_reflects_the_configured_mode(self):
        response = HttpResponse.empty(HttpStatus.OK)
        apply_security_headers(response, SecurityConfig(security_headers_enabled=True, coep_mode="require-corp"))
        self.assertEqual(response.headers["Cross-Origin-Embedder-Policy"], "require-corp")

    def test_csp_zone_applies_when_path_matches(self):
        security = SecurityConfig(
            security_headers_enabled=True,
            csp_zones=(Zone("/public/", "default-src 'self' 'unsafe-inline'"),),
        )
        response = HttpResponse.empty(HttpStatus.OK)
        apply_security_headers(response, security, path="/public/widget.html")
        self.assertEqual(response.headers["Content-Security-Policy"], "default-src 'self' 'unsafe-inline'")

    def test_csp_zone_does_not_apply_outside_its_prefix(self):
        security = SecurityConfig(
            security_headers_enabled=True,
            csp_zones=(Zone("/public/", "default-src 'self' 'unsafe-inline'"),),
        )
        response = HttpResponse.empty(HttpStatus.OK)
        apply_security_headers(response, security, path="/private/data")
        self.assertEqual(response.headers["Content-Security-Policy"], DEFAULT_CSP_POLICY)

    def test_global_default_still_applies_when_no_path_given(self):
        security = SecurityConfig(
            security_headers_enabled=True,
            csp_zones=(Zone("/public/", "default-src 'self' 'unsafe-inline'"),),
        )
        response = HttpResponse.empty(HttpStatus.OK)
        apply_security_headers(response, security)
        self.assertEqual(response.headers["Content-Security-Policy"], DEFAULT_CSP_POLICY)

    def test_headers_cannot_be_overridden_by_upstream_handler(self):
        response = HttpResponse.empty(HttpStatus.OK)
        response.set_header("X-Frame-Options", "ALLOWALL")  # simule un handler amont
        apply_security_headers(response, SecurityConfig(security_headers_enabled=True))
        self.assertEqual(response.headers["X-Frame-Options"], "SAMEORIGIN")

    def test_hsts_absent_when_disabled(self):
        response = HttpResponse.empty(HttpStatus.OK)
        apply_security_headers(response, SecurityConfig(security_headers_enabled=True, hsts_enabled=False), tls_enabled=True)
        self.assertNotIn("Strict-Transport-Security", response.headers)

    def test_hsts_absent_when_tls_not_enabled_even_if_configured(self):
        response = HttpResponse.empty(HttpStatus.OK)
        apply_security_headers(response, SecurityConfig(security_headers_enabled=True, hsts_enabled=True), tls_enabled=False)
        self.assertNotIn("Strict-Transport-Security", response.headers)

    def test_hsts_present_when_tls_and_config_both_enabled(self):
        response = HttpResponse.empty(HttpStatus.OK)
        apply_security_headers(
            response,
            SecurityConfig(security_headers_enabled=True, hsts_enabled=True, hsts_max_age=3600, hsts_include_subdomains=False, hsts_preload=False),
            tls_enabled=True,
        )
        self.assertEqual(response.headers["Strict-Transport-Security"], "max-age=3600")

    def test_hsts_includes_subdomains_and_preload_when_configured(self):
        response = HttpResponse.empty(HttpStatus.OK)
        apply_security_headers(
            response,
            SecurityConfig(security_headers_enabled=True, hsts_enabled=True, hsts_max_age=100, hsts_include_subdomains=True, hsts_preload=True),
            tls_enabled=True,
        )
        self.assertEqual(response.headers["Strict-Transport-Security"], "max-age=100; includeSubDomains; preload")


if __name__ == "__main__":
    unittest.main()
