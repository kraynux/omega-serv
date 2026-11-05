"""Instantane de configuration du moteur natif (plan moteur C++, lot 2) : tables produites par les VRAIES
fonctions du moteur Python, jamais recopiees ; tout ce que le natif ne sait pas faire force le repli."""
import json
import tempfile
import unittest
from pathlib import Path

from omega_serv.domain.config.entities import OmegaServConfig
from omega_serv.domain.http.error_pages import render_default_error_page
from omega_serv.domain.http.response import HttpResponse
from omega_serv.domain.security.security_headers import apply_security_headers
from omega_serv.infrastructure.server.native_snapshot import (
    SNAPSHOT_FORMAT,
    build_native_snapshot,
    native_unsupported_features,
    write_native_snapshot,
)
from omega_serv.infrastructure.tls.ssl_context_builder import _MODERN_CIPHER_SUITES


class TestNativeSnapshot(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.root = Path(self._tmp.name)
        (self.root / "webroot").mkdir()

    def tearDown(self):
        self._tmp.cleanup()

    def test_default_config_is_fully_described(self):
        config = OmegaServConfig.from_dict({})
        snapshot = build_native_snapshot(config, self.root, 7)
        self.assertEqual(snapshot["format"], SNAPSHOT_FORMAT)
        self.assertEqual(snapshot["generation"], 7)
        self.assertEqual(snapshot["server"]["webroot"], str((self.root / "webroot").resolve()))
        self.assertEqual(snapshot["server"]["index_files"], ["index.html"])
        self.assertEqual(snapshot["logs"]["access"], str(self.root / "var/log/access.log"))
        for option in ("trusted_proxy", "access_rules", "redirects", "rewrites", "aliases", "cache", "dirlisting"):
            self.assertIsNone(snapshot["routes"][option], option)
        self.assertIsNone(snapshot["error_pages"]["custom_dir"])
        json.dumps(snapshot)  # entierement serialisable

    def test_security_headers_come_from_the_real_function(self):
        config = OmegaServConfig.from_dict({"security": {"csp_mode": "report-only",
                                                         "csp_zones": [{"path_prefix": "/x", "policy": "default-src *"}]}})
        probe = HttpResponse.empty(200)
        apply_security_headers(probe, config.security, config.tls.enabled, None)
        headers = build_native_snapshot(config, self.root, 1)["security"]["headers"]
        self.assertEqual(headers["ordered"], [[name, value] for name, value in probe.headers.items()])
        self.assertEqual(headers["csp_header"], "Content-Security-Policy-Report-Only")
        self.assertEqual(headers["csp_zones"], [["/x", "default-src *"]])

    def test_security_headers_disabled(self):
        config = OmegaServConfig.from_dict({"security": {"security_headers_enabled": False}})
        self.assertIsNone(build_native_snapshot(config, self.root, 1)["security"]["headers"])

    def test_routes_keep_configured_order(self):
        config = OmegaServConfig.from_dict({"options": {
            "redirects": {"enabled": True, "list": [{"url_prefix": "/b", "destination": "/1"},
                                                    {"url_prefix": "/a", "destination": "/2", "status_code": 308}]},
            "aliases": {"enabled": True, "list": [{"url_prefix": "/al", "target_path": "webroot/docs"}]},
            "trusted_proxy": {"enabled": True, "trusted_networks": ["10.0.0.0/8"]},
        }})
        routes = build_native_snapshot(config, self.root, 1)["routes"]
        self.assertEqual(routes["redirects"]["list"], [
            {"url_prefix": "/b", "destination": "/1", "status_code": 302},
            {"url_prefix": "/a", "destination": "/2", "status_code": 308}])
        # racine d'alias NON resolue : le moteur Python la resout a chaque requete
        self.assertEqual(routes["aliases"]["list"], [{"url_prefix": "/al", "root": str(self.root / "webroot/docs")}])
        self.assertEqual(routes["trusted_proxy"], {"networks": ["10.0.0.0/8"],
                                                   "header_preference": ["Forwarded", "X-Forwarded-For"]})

    def test_error_pages_rendered_for_every_error_status(self):
        snapshot = build_native_snapshot(OmegaServConfig.from_dict({}), self.root, 1)
        defaults = snapshot["error_pages"]["defaults"]
        for code in (400, 403, 404, 405, 408, 413, 414, 416, 417, 431, 500, 503):
            self.assertEqual(defaults[str(code)], render_default_error_page(code).decode("utf-8"), code)
        self.assertNotIn("200", defaults)
        self.assertEqual(snapshot["error_pages"]["reason_phrases"]["404"], "Not Found")

    def test_unsupported_features_force_fallback(self):
        self.assertEqual(native_unsupported_features(OmegaServConfig.from_dict({})), [])
        config = OmegaServConfig.from_dict({"options": {"waf": {"enabled": True}, "dirlisting": {"enabled": True},
                                                        "cache": {"enabled": True}, "upload": {"enabled": True}}})
        self.assertEqual(native_unsupported_features(config), [])  # WAF : lot 4 ; listing : lot 5 ; upload : lot 6
        tls_upload = OmegaServConfig.from_dict({"tls": {"enabled": True, "mode": "direct"},
                                                "options": {"upload": {"enabled": True}}})
        self.assertEqual(native_unsupported_features(tls_upload), ["tls_handoff"])
        proxied_upload = OmegaServConfig.from_dict({"tls": {"enabled": True, "mode": "behind_proxy"},
                                                    "options": {"upload": {"enabled": True}}})
        self.assertEqual(native_unsupported_features(proxied_upload), [])
        tls = OmegaServConfig.from_dict({"tls": {"enabled": True, "mode": "direct"}})
        self.assertEqual(native_unsupported_features(tls), [])  # lot 3b : TLS direct natif

    def test_inspect_section(self):
        # Lot 4 : null sans leurre / WAF / Active Defense / Auth (zero aller-retour) ; Auth = toujours fail-closed.
        self.assertIsNone(build_native_snapshot(OmegaServConfig.from_dict({}), self.root, 1)["inspect"])
        waf = OmegaServConfig.from_dict({"options": {"waf": {"enabled": True, "on_internal_error": "fail-open",
                                                             "inspect": {"body_methods": ["POST"], "body_max_inspect_bytes": 99}}}})
        inspect = build_native_snapshot(waf, self.root, 1)["inspect"]
        self.assertEqual((inspect["body_methods"], inspect["body_bytes"], inspect["on_error"]), (["POST"], 99, "fail-open"))
        with_auth = OmegaServConfig.from_dict({"options": {"waf": {"enabled": True, "on_internal_error": "fail-open"},
                                                           "auth": {"enabled": True}}})
        self.assertEqual(build_native_snapshot(with_auth, self.root, 1)["inspect"]["on_error"], "fail-closed")
        ad = OmegaServConfig.from_dict({"options": {"active_defense": {"enabled": True}}})
        self.assertGreater(build_native_snapshot(ad, self.root, 1)["inspect"]["timeout_ms"], 60_000)
        self.assertTrue(build_native_snapshot(waf, self.root, 1)["inspect"]["security_stage"])
        # Lot 5 : listing de repertoire seul -> processus Python pour les routes deleguees, sans etape de securite
        listing = OmegaServConfig.from_dict({"options": {"dirlisting": {"enabled": True}}})
        self.assertFalse(build_native_snapshot(listing, self.root, 1)["inspect"]["security_stage"])

    def test_waf_filter_section(self):
        # Plan WAF natif, lot 0 : null sans WAF ; regles retraduites ; pack introuvable -> indisponible (tout a Python)
        import shutil
        self.assertIsNone(build_native_snapshot(OmegaServConfig.from_dict({}), self.root, 1)["waf_filter"])
        rules_dir = self.root / "secure" / "waf" / "rules"
        rules_dir.mkdir(parents=True)
        shipped = Path(__file__).resolve().parents[2] / "secure" / "waf" / "rules"
        for name in ("body-sqli.json", "scanner-ua.json"):
            shutil.copy(shipped / name, rules_dir / name)
        paths = ["secure/waf/rules/body-sqli.json", "secure/waf/rules/scanner-ua.json"]
        config = OmegaServConfig.from_dict({"options": {"waf": {"enabled": True, "rules": {"paths": paths}}}})
        section = build_native_snapshot(config, self.root, 1)["waf_filter"]
        self.assertTrue(section["available"])
        self.assertEqual(section["unexported"], [])
        self.assertEqual({r["pack"] for r in section["rules"]}, {"body-sqli", "scanner-ua"})
        self.assertTrue(all(r["pattern"] and isinstance(r["lowered"], bool) for r in section["rules"]))
        self.assertEqual((section["decode_depth"], section["inspect_headers"]), (2, False))
        # Lot 4 : controle 1/N et textes de controle (resultat de Python) pour chaque regle
        self.assertEqual(section["check_every"], 0)
        self.assertTrue(all(len(r["controls"]) == 32 and any(m for _t, m in r["controls"]) for r in section["rules"]))
        json.dumps(section)  # voyage dans l'instantane JSON
        # Lot 2 : decision seule du natif seulement si aucune fonction ne demande Python pour chaque requete
        self.assertEqual((section["native_decides"], section["python_reason"], section["auth_prefixes"]), (True, None, []))

        def filter_for(waf_extra=None, **options):
            settings = {"enabled": True, "rules": {"paths": paths}, **(waf_extra or {})}
            built = OmegaServConfig.from_dict({"options": {"waf": settings, **options}})
            return build_native_snapshot(built, self.root, 1)["waf_filter"]

        limited = filter_for({"rate_limit": {"enabled": True}})
        self.assertEqual((limited["native_decides"], limited["python_reason"]), (False, "rate_limit"))
        decoys = filter_for(active_defense={"enabled": True, "deception": {"enabled": True}})
        self.assertEqual((decoys["native_decides"], decoys["python_reason"]), (False, "deception"))
        self.assertTrue(decoys["native_decides_with_watch"])  # lot 3 : natif recent + sources suivies
        self.assertFalse(limited["native_decides_with_watch"])
        both = filter_for({"rate_limit": {"enabled": True}}, active_defense={"enabled": True, "deception": {"enabled": True}})
        self.assertFalse(both["native_decides_with_watch"])
        # Lot 6 : limite de debit comptee par le natif -> decision seule permise (champ lu par un natif recent)
        self.assertTrue(limited["native_decides_with_rate_limit"] and both["native_decides_with_rate_limit"])
        self.assertTrue(decoys["native_decides_with_rate_limit"])
        self.assertNotIn("rate_limit", decoys)
        magnet_and_rate = filter_for({"rate_limit": {"enabled": True}, "magnet": {"enabled": True, "script": "x.lua"}})
        self.assertEqual((magnet_and_rate["native_decides_with_rate_limit"], magnet_and_rate["python_reason"]),
                         (False, "magnet"))
        rules = filter_for({"rate_limit": {"enabled": True, "global": {"requests": 7, "window_seconds": 9},
                                           "path_policies": [{"prefix": "/g", "requests": 0}],
                                           "source_policies": [{"network": "127.0.0.0/8", "requests": 1},
                                                               {"network": "10.0.0.0/8", "requests": 2}]}})["rate_limit"]
        self.assertEqual(rules["global"], {"requests": 7, "window_seconds": 9})
        self.assertEqual(rules["path_policies"], [{"prefix": "/g", "requests": 0, "window_seconds": 60}])
        # sans proxy de confiance, une regle couvrant le loopback est ignoree (effective_source_policies, comme au demarrage)
        self.assertEqual(rules["source_policies"], [{"network": "10.0.0.0/8", "requests": 2, "window_seconds": 60}])
        self.assertEqual(rules["error_css_path"], "/.omega-serv-error-css/error-pages.css")
        self.assertTrue(filter_for(active_defense={"enabled": True})["native_decides"])  # sans leurre
        zones = self.root / "secure" / "auth" / "zones.json"
        zones.parent.mkdir(parents=True)
        zones.write_text(json.dumps({"version": 1, "zones": [
            {"path_prefix": "/prive/", "realm": "r", "allowed_users": ["a"], "allow_methods": []},
            {"path_prefix": "/admin", "realm": "r", "allowed_users": ["a"], "allow_methods": []}]}))
        protected = filter_for(auth={"enabled": True})
        self.assertEqual((protected["native_decides"], protected["auth_prefixes"]), (True, ["/admin", "/prive/"]))
        zones.write_text("{abime")
        self.assertEqual(filter_for(auth={"enabled": True})["python_reason"], "auth_zones")
        missing = OmegaServConfig.from_dict({"options": {"waf": {"enabled": True, "rules": {"paths": ["absent.json"]}}}})
        self.assertFalse(build_native_snapshot(missing, self.root, 1)["waf_filter"]["available"])

    def test_tls_section_only_for_direct_tls(self):
        self.assertIsNone(build_native_snapshot(OmegaServConfig.from_dict({}), self.root, 1)["tls"])
        proxied = OmegaServConfig.from_dict({"tls": {"enabled": True, "mode": "behind_proxy"}})
        self.assertIsNone(build_native_snapshot(proxied, self.root, 1)["tls"])
        direct = OmegaServConfig.from_dict({"tls": {
            "enabled": True, "mode": "direct",
            "certificate": {"certificate_path": "c/cert.pem", "private_key_path": "c/key.pem",
                            "private_key_passphrase_env": "MA_PHRASE"},
            "protocols": {"min_version": "TLS1.3", "max_version": "TLS1.3"}}})
        tls = build_native_snapshot(direct, self.root, 1)["tls"]
        self.assertEqual(tls["certificate"], str(self.root / "c/cert.pem"))
        self.assertEqual(tls["private_key"], str(self.root / "c/key.pem"))
        self.assertEqual((tls["passphrase_env"], tls["min_version"], tls["max_version"]), ("MA_PHRASE", "TLS1.3", "TLS1.3"))
        self.assertEqual(tls["ciphers"], _MODERN_CIPHER_SUITES)  # la meme liste que le contexte ssl Python

    def test_write_produces_utf8_json(self):
        path = self.root / "snapshot.json"
        write_native_snapshot(OmegaServConfig.from_dict({}), self.root, 3, path)
        self.assertEqual(json.loads(path.read_text(encoding="utf-8"))["generation"], 3)


if __name__ == "__main__":
    unittest.main()
