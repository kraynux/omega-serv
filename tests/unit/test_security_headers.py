import unittest

from omega_serv.domain.config.entities import SecurityConfig
from omega_serv.domain.http.response import HttpResponse
from omega_serv.domain.http.status_codes import HttpStatus
from omega_serv.domain.security.csp import DEFAULT_CSP_POLICY, csp_header_name
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
