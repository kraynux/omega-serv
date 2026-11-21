"""Plan proxy natif v2, lot 3 : option options.reverse_proxy.engine (P8) et budgets (C2), choix « native ou confiee »
par zone (§5.2), regles TLS de config check et du demarrage (P7, E9, E10), controle de boucle par les interfaces
locales et le DNS (D17+), instantane `proxy` et processus de securite (P6). Rien n'est active pour le public : tant
que le relais natif n'existe pas (lot 4), toute zone est confiee a Python."""
import argparse
import contextlib
import io
import json
import tempfile
import unittest
from pathlib import Path

from omega_serv.application.config.validate_config import (
    config_problems,
    validate_config_environment,
)
from omega_serv.application.server.engine_selection import (
    AUTO_PENDING,
    NATIVE_PROXY_GAPS,
    TLS_HANDOFF,
    ZONE_BALANCING,
    ZONE_CACHE,
    ZONE_DNS,
    ZONE_ENGINE_PYTHON,
    ZONE_TLS_DIRECT,
    ZONE_UPSTREAM_TLS,
    ZONE_WEBSOCKET,
    decide_engine,
    decide_proxy_zones,
    proxy_engine_problems,
)
from omega_serv.bootstrap.container import DependencyContainer
from omega_serv.domain.config.entities import OmegaServConfig
from omega_serv.domain.config.validation import validate_config
from omega_serv.domain.routing.proxy_engine import (
    DEFAULT_MAX_CONCURRENT_INSPECTIONS,
    DEFAULT_MAX_PENDING_BODY_MB,
    DEFAULT_MAX_UPSTREAM_CONNECTIONS,
    parse_proxy_engine_settings,
)
from omega_serv.domain.routing.proxy_zone import (
    is_link_local_upstream,
    upstream_targets_this_server,
)
from omega_serv.infrastructure.filesystem.local_filesystem import LocalFilesystem
from omega_serv.infrastructure.server.native_snapshot import build_native_snapshot
from omega_serv.interfaces.cli.main import cmd_config_check

PORTED = frozenset()
"""Lacunes du relais natif toutes levees : ce que decideront les lots 4 a 10."""


def _zone(prefix="/app/", **extra):
    return {"url_prefix": prefix, "upstreams": [{"host": "10.0.0.5", "port": 8080}], **extra}


def _config(proxy=None, zones=None, server_engine="native", tls_direct=False, bind="127.0.0.1", port=8080,
            options=None):
    data = {"server": {"engine": server_engine, "bind": bind, "port": port}, "options": dict(options or {})}
    if proxy is not None or zones is not None:
        data["options"]["reverse_proxy"] = {"enabled": True, "zones": zones if zones is not None else [_zone()],
                                            **(proxy or {})}
    if tls_direct:
        data["tls"] = {"enabled": True, "mode": "direct"}
    return OmegaServConfig.from_dict(data)


class TestProxyEngineSettings(unittest.TestCase):
    def test_defaults(self):
        settings = parse_proxy_engine_settings({})
        self.assertEqual((settings.engine, settings.max_pending_body_mb, settings.max_concurrent_inspections,
                          settings.max_upstream_connections),
                         ("auto", DEFAULT_MAX_PENDING_BODY_MB, DEFAULT_MAX_CONCURRENT_INSPECTIONS,
                          DEFAULT_MAX_UPSTREAM_CONNECTIONS))
        self.assertEqual(settings.max_pending_body_bytes, DEFAULT_MAX_PENDING_BODY_MB * 1024 * 1024)

    def test_engine_values(self):
        for engine in ("auto", "native", "python"):
            self.assertFalse([e for e in validate_config(_config({"engine": engine})) if "engine" in e], engine)
        self.assertTrue([e for e in validate_config(_config({"engine": "turbo"})) if "reverse_proxy.engine" in e])

    def test_budgets_are_bounded_integers(self):
        for key in ("max_pending_body_mb", "max_concurrent_inspections", "max_upstream_connections"):
            for bad in (0, -1, "10", 1.5, True):
                errors = validate_config(_config({key: bad}))
                self.assertTrue([e for e in errors if key in e], f"{key}={bad!r}")
            self.assertFalse([e for e in validate_config(_config({key: 200})) if key in e], key)

    def test_pending_body_budget_holds_one_max_size_request(self):
        # server.max_request_size par defaut : 10 Mio -> au moins 10 Mo, sinon 503 a coup sur
        errors = validate_config(_config({"max_pending_body_mb": 9}))
        self.assertTrue([e for e in errors if "max_pending_body_mb" in e and "max_request_size" in e])
        self.assertFalse([e for e in validate_config(_config({"max_pending_body_mb": 10})) if "max_pending" in e])


class TestZoneEngineDecision(unittest.TestCase):
    def test_auto_relays_every_zone_it_can(self):
        # Lot 11 : AUTO_PENDING leve - auto rend natives toutes les zones que le natif sait relayer.
        self.assertNotIn(AUTO_PENDING, NATIVE_PROXY_GAPS)
        zones = decide_proxy_zones(_config({}, zones=[_zone("/a/"), _zone("/b/")]))
        self.assertEqual([(z.url_prefix, z.engine, z.reasons) for z in zones],
                         [("/a/", "native", ()), ("/b/", "native", ())])

    def test_auto_kept_every_zone_in_python_before_lot_11(self):
        # Lots 4 a 10 (decision de l'auteur du 2026-11-13) : relais natif en apercu, seulement avec engine = native.
        zones = decide_proxy_zones(_config({}, zones=[_zone("/a/"), _zone("/b/")]), frozenset({AUTO_PENDING}))
        self.assertEqual([(z.url_prefix, z.engine, z.reasons) for z in zones],
                         [("/a/", "python", (AUTO_PENDING,)), ("/b/", "python", (AUTO_PENDING,))])

    def test_engine_native_relays_simple_zones(self):
        zones = decide_proxy_zones(_config({"engine": "native"}, zones=[_zone("/a/")]))
        self.assertEqual([(z.engine, z.reasons) for z in zones], [("native", ())])

    def test_lot4_perimeter(self):
        # Equilibrage et noms DNS : raisons du lot 4, levees au lot 6 (zones natives depuis).
        config = _config({"engine": "native"}, zones=[
            {"url_prefix": "/two/", "upstreams": [{"host": "10.0.0.5", "port": 1}, {"host": "10.0.0.6", "port": 1}]},
            _zone("/sticky/", sticky_session_enabled=True),
            {"url_prefix": "/cap/", "upstreams": [{"host": "10.0.0.5", "port": 1, "max_concurrent_requests": 3}]},
            {"url_prefix": "/dns/", "upstreams": [{"host": "backend.example", "port": 1}]},
        ])
        lot4 = NATIVE_PROXY_GAPS | {ZONE_BALANCING, ZONE_DNS}
        reasons = {z.url_prefix: z.reasons for z in decide_proxy_zones(config, lot4)}
        self.assertEqual(reasons, {"/two/": (ZONE_BALANCING,), "/sticky/": (ZONE_BALANCING,),
                                   "/cap/": (ZONE_BALANCING,), "/dns/": (ZONE_DNS,)})
        self.assertEqual({z.url_prefix: z.engine for z in decide_proxy_zones(config)},
                         dict.fromkeys(reasons, "native"))

    def test_native_when_nothing_is_missing(self):
        zones = decide_proxy_zones(_config({}), PORTED)
        self.assertEqual([(z.engine, z.reasons) for z in zones], [("native", ())])

    def test_reasons_per_zone(self):
        config = _config({}, zones=[
            _zone("/cache/", cache_enabled=True),
            _zone("/ws/", websocket_enabled=True),
            {"url_prefix": "/tls/", "upstreams": [{"host": "10.0.0.5", "port": 443, "use_tls": True}]},
        ])
        zones = {z.url_prefix: z.reasons for z in decide_proxy_zones(config, frozenset({ZONE_WEBSOCKET,
                                                                                          ZONE_UPSTREAM_TLS}))}
        self.assertEqual(zones, {"/cache/": (ZONE_CACHE,), "/ws/": (ZONE_WEBSOCKET,), "/tls/": (ZONE_UPSTREAM_TLS,)})
        # Le cache reste en Python pour toujours (Q6), quelles que soient les lacunes levees.
        self.assertEqual(decide_proxy_zones(config, PORTED)[0].reasons, (ZONE_CACHE,))

    def test_direct_tls_until_lot_9(self):
        config = _config({}, tls_direct=True)
        self.assertEqual(decide_proxy_zones(config, frozenset({ZONE_TLS_DIRECT}))[0].reasons, (ZONE_TLS_DIRECT,))
        self.assertEqual(decide_proxy_zones(config, PORTED)[0].engine, "native")

    def test_engine_python_delegates_every_zone(self):
        zones = decide_proxy_zones(_config({"engine": "python"}), PORTED)
        self.assertEqual([(z.engine, z.reasons) for z in zones], [("python", (ZONE_ENGINE_PYTHON,))])

    def test_no_reverse_proxy_no_zone(self):
        self.assertEqual(decide_proxy_zones(_config()), ())


class TestTlsRulesP7(unittest.TestCase):
    """Tableau du §5.2 : un test par cas, et par option applicative (E9, E10)."""

    def test_auto_with_direct_tls_starts_in_python_with_a_warning(self):
        # Lot 11 : avec auto, seule une zone confiee (cache) fait demarrer en Python sous TLS direct.
        self.assertEqual(proxy_engine_problems(_config({"engine": "auto"}, tls_direct=True)).warnings, ())
        config = _config({"engine": "auto"}, zones=[_zone(cache_enabled=True)], tls_direct=True)
        problems = proxy_engine_problems(config)
        self.assertEqual(problems.errors, ())
        self.assertEqual(len(problems.warnings), 1)
        self.assertIn("behind_proxy", problems.warnings[0].text)
        self.assertIn("'/app/'", problems.warnings[0].log_text)
        decision = decide_engine(config, None)
        self.assertEqual((decision.effective, decision.reasons), ("python", (TLS_HANDOFF,)))

    def test_native_with_direct_tls_is_refused(self):
        # Lot 9 : une zone relayee par le natif se sert en TLS direct ; le refus ne vise que la zone confiee (cache).
        self.assertEqual(proxy_engine_problems(_config({"engine": "native"}, tls_direct=True)).errors, ())
        problems = proxy_engine_problems(_config({"engine": "native"}, zones=[_zone(cache_enabled=True)],
                                                 tls_direct=True))
        self.assertEqual(len(problems.errors), 1)
        self.assertIn("engine = native", problems.errors[0].text)

    def test_python_with_direct_tls_is_accepted_with_a_warning(self):
        # E10 : le retour en arriere ne doit jamais etre refuse.
        problems = proxy_engine_problems(_config({"engine": "python"}, tls_direct=True))
        self.assertEqual(problems.errors, ())
        self.assertEqual(len(problems.warnings), 1)

    def test_native_without_tls_accepted_for_a_simple_zone(self):
        self.assertEqual(proxy_engine_problems(_config({"engine": "native"})).errors, ())

    def test_native_refusal_hides_reasons_that_removing_cannot_fix(self):
        # Raisons internes des lots a venir jamais montrees : rien a retirer de la zone ne suffirait (TLS direct).
        problems = proxy_engine_problems(_config({"engine": "native"}, tls_direct=True),
                                         NATIVE_PROXY_GAPS | {ZONE_TLS_DIRECT})  # configuration d'avant le lot 9
        self.assertEqual(len(problems.errors), 1)
        self.assertNotIn("tls_direct", problems.errors[0].text)
        self.assertNotIn("fonctions à retirer", problems.errors[0].text)

    def test_native_refusal_names_dns_name(self):
        # Lot 6 : un nom DNS ne fait plus refuser engine = native ; le libelle reste juste pour la lacune.
        zones = [{"url_prefix": "/dns/", "upstreams": [{"host": "backend.example", "port": 1}]}]
        self.assertEqual(proxy_engine_problems(_config({"engine": "native"}, zones=zones)).errors, ())
        problems = proxy_engine_problems(_config({"engine": "native"}, zones=zones), NATIVE_PROXY_GAPS | {ZONE_DNS})
        self.assertEqual(len(problems.errors), 1)
        self.assertIn("adresse IP", problems.errors[0].text)

    def test_native_refusal_names_what_to_remove_when_that_is_enough(self):
        config = _config({"engine": "native"}, zones=[_zone(cache_enabled=True)])
        problems = proxy_engine_problems(config, PORTED)
        self.assertEqual(len(problems.errors), 1)
        self.assertIn("cache", problems.errors[0].text)

    def test_native_is_ignored_with_python_server_engine(self):
        # Decision de l'auteur du 2026-11-13 : server.engine = python reste le retour en arriere, toujours demarre.
        problems = proxy_engine_problems(_config({"engine": "native"}, server_engine="python", tls_direct=True))
        self.assertEqual((problems.errors, problems.warnings), ((), ()))
        self.assertEqual(len(problems.notices), 1)
        self.assertIn("sans effet", problems.notices[0].text)

    def test_auto_without_tls_says_nothing(self):
        self.assertEqual(proxy_engine_problems(_config({})), proxy_engine_problems(_config()))
        problems = proxy_engine_problems(_config({}))
        self.assertEqual((problems.errors, problems.warnings, problems.notices), ((), (), ()))

    def test_fastcgi_and_upload_with_direct_tls_warn_and_never_refuse(self):
        # E9 : FastCGI et l'envoi de fichiers gardent leur repli actuel, avec un avertissement.
        for option in ("fastcgi", "upload"):
            config = _config(tls_direct=True, options={option: {"enabled": True}})
            problems = proxy_engine_problems(config)
            self.assertEqual(problems.errors, (), option)
            self.assertEqual(len(problems.warnings), 1, option)
            self.assertIn(f"options.{option}", problems.warnings[0].log_text)
            self.assertEqual(decide_engine(config, None).reasons, (TLS_HANDOFF,), option)

    def test_warnings_only_with_the_native_engine(self):
        problems = proxy_engine_problems(_config({}, server_engine="python", tls_direct=True,
                                                 options={"fastcgi": {"enabled": True}}))
        self.assertEqual((problems.errors, problems.warnings), ((), ()))

    def test_environment_check_refuses_only_engine_native(self):
        # E9 : validate_config_environment sert a config check ET a serve - aucun refus pour auto, python, FastCGI,
        # envoi de fichiers.
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "webroot").mkdir()
            # Lot 10 : une zone WebSocket est native ; le cache reste confie pour toujours (Q6).
            dns = [{"url_prefix": "/c/", "upstreams": [{"host": "10.0.0.5", "port": 1}], "cache_enabled": True}]
            for proxy, expected in (({"engine": "auto"}, False), ({"engine": "python"}, False),
                                    ({"engine": "native"}, True)):
                errors = validate_config_environment(_config(proxy, zones=dns), LocalFilesystem(), root,
                                                     local_addresses=())
                self.assertEqual(any("reverse_proxy.engine" in e for e in errors), expected, proxy)


class TestLoopThroughLocalInterfaces(unittest.TestCase):
    """D17+ (decision de l'auteur du 2026-11-13) : interface locale = refus, nom DNS = avertissement, adresse locale
    au lien = avertissement."""

    LOCAL = ("192.168.1.20", "fe80::1%eth0", "2001:db8::7", "127.0.0.1", "::1")

    def test_unspecified_bind_loops_through_local_interfaces(self):
        self.assertTrue(upstream_targets_this_server("192.168.1.20", 8080, "0.0.0.0", 8080, self.LOCAL))
        self.assertTrue(upstream_targets_this_server("2001:db8::7", 8080, "::", 8080, self.LOCAL))
        self.assertTrue(upstream_targets_this_server("192.168.1.20", 8080, "::", 8080, self.LOCAL))  # double pile

    def test_no_loop_when_not_listening_there(self):
        self.assertFalse(upstream_targets_this_server("2001:db8::7", 8080, "0.0.0.0", 8080, self.LOCAL))  # IPv4 seul
        self.assertFalse(upstream_targets_this_server("192.168.1.20", 8080, "10.0.0.1", 8080, self.LOCAL))
        self.assertFalse(upstream_targets_this_server("192.168.1.20", 9090, "0.0.0.0", 8080, self.LOCAL))
        self.assertFalse(upstream_targets_this_server("192.168.1.21", 8080, "0.0.0.0", 8080, self.LOCAL))

    def test_interface_loop_is_refused(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "webroot").mkdir()
            zones = [{"url_prefix": "/app/", "upstreams": [{"host": "192.168.1.20", "port": 8080}]}]
            errors = validate_config_environment(_config({}, zones=zones, bind="0.0.0.0"), LocalFilesystem(), root,
                                                 local_addresses=self.LOCAL)
            self.assertTrue([e for e in errors if "192.168.1.20:8080" in e and "boucle" in e])
            # adresse d'ecoute precise : l'interface n'est pas ecoutee, aucune boucle
            errors = validate_config_environment(_config({}, zones=zones, bind="10.0.0.1"), LocalFilesystem(), root,
                                                 local_addresses=self.LOCAL)
            self.assertFalse([e for e in errors if "boucle" in e])

    def test_decoy_loop_is_refused_too(self):
        decoys = {"active_defense": {"enabled": True, "deception": {"enabled": True, "decoy_zones": {
            "piege": {"upstreams": [{"host": "192.168.1.20", "port": 8080}]}}}}}
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "webroot").mkdir()
            errors = validate_config_environment(_config(bind="0.0.0.0", options=decoys), LocalFilesystem(), root,
                                                 local_addresses=self.LOCAL)
            self.assertTrue([e for e in errors if "decoy_zones.piege" in e and "boucle" in e])

    def test_link_local_upstream_warns(self):
        for host in ("169.254.169.254", "fe80::1", "fe80::1%eth0"):
            self.assertTrue(is_link_local_upstream(host), host)
        for host in ("10.0.0.1", "backend.example", "2001:db8::1"):
            self.assertFalse(is_link_local_upstream(host), host)
        zones = [{"url_prefix": "/meta/", "upstreams": [{"host": "169.254.169.254", "port": 80}]}]
        warnings = config_problems(_config({}, zones=zones), local_addresses=()).warnings
        self.assertTrue([w for w in warnings if "169.254.169.254" in w.text])

    def test_dns_name_resolving_here_warns_only_when_asked(self):
        zones = [{"url_prefix": "/app/", "upstreams": [{"host": "moi.example", "port": 8080}]},
                 {"url_prefix": "/autre/", "upstreams": [{"host": "ailleurs.example", "port": 8080}]}]
        config = _config({}, zones=zones, bind="0.0.0.0")
        asked = []

        def resolver(names):
            asked.extend(names)
            return {"moi.example": ("192.168.1.20",), "ailleurs.example": ("203.0.113.9",)}

        warnings = config_problems(config, local_addresses=self.LOCAL, resolve_names=True, resolver=resolver).warnings
        self.assertEqual([w.log_text.split(" : ")[0] for w in warnings], ["options.reverse_proxy zone '/app/'"])
        self.assertEqual(sorted(asked), ["ailleurs.example", "moi.example"])
        # demarrage : jamais de resolution (un nom lent ne retarde jamais serve)
        asked.clear()
        self.assertEqual(config_problems(config, local_addresses=self.LOCAL, resolver=resolver).warnings, ())
        self.assertEqual(asked, [])
        # nom resolu vers la boucle locale : avertissement aussi
        loopback = config_problems(_config({}, zones=zones[:1]), local_addresses=(), resolve_names=True,
                                   resolver=lambda names: {"moi.example": ("127.0.0.1",)}).warnings
        self.assertEqual(len(loopback), 1)


class TestProxySnapshot(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.root = Path(self._tmp.name)
        (self.root / "webroot").mkdir()

    def tearDown(self):
        self._tmp.cleanup()

    def test_no_reverse_proxy_no_section(self):
        self.assertIsNone(build_native_snapshot(_config(), self.root, 1)["proxy"])

    def test_section_from_the_real_zone_parser(self):
        zones = [{
            "url_prefix": "/api/", "connect_timeout_seconds": 2.5, "read_timeout_seconds": 12,
            "preserve_host_header": True, "verify_upstream_tls": False, "load_balancing": "ip_hash",
            "sticky_session_enabled": True, "sticky_cookie_name": "s", "sticky_cookie_max_age_seconds": 60,
            "routing_rules": [{"header_name": "X-T", "pattern": "a*", "upstream_key": "::1:9000"}],
            "unhealthy_after": 4, "healthy_after": 1,
            "upstreams": [{"host": "::1", "port": 9000, "weight": 2, "max_concurrent_requests": 7,
                           "load_source": "native"},
                          {"host": "api.example", "port": 443, "use_tls": True}],
        }]
        config = _config({"max_pending_body_mb": 32, "max_concurrent_inspections": 8, "max_upstream_connections": 99,
                          "max_response_body_mb": 3}, zones=zones)
        proxy = build_native_snapshot(config, self.root, 1)["proxy"]
        self.assertEqual(proxy["engine"], "auto")
        self.assertEqual(proxy["budgets"], {"pending_body_bytes": 32 << 20, "inspections": 8,
                                            "upstream_connections": 99})
        self.assertEqual(proxy["max_response_body_bytes"], 3 << 20)
        zone = proxy["zones"][0]
        self.assertEqual((zone["prefix"], zone["engine"], zone["inspect"]), ("/api/", "native", "never"))
        self.assertEqual(zone["reasons"], [])  # lot 11 : auto rend la zone native (AUTO_PENDING leve)
        self.assertEqual((zone["connect_timeout_ms"], zone["read_timeout_ms"]), (2500, 12000))
        self.assertEqual(zone["sticky"], {"cookie_name": "s", "max_age_seconds": 60})
        self.assertEqual(zone["routing_rules"], [{"header": "X-T", "pattern": "a*", "upstream": "::1:9000"}])
        first, second = zone["upstreams"]
        self.assertEqual((first["key"], first["address"], first["host_header"]), ("::1:9000", "::1", "[::1]:9000"))
        self.assertEqual((first["weight"], first["max_concurrent"], first["load_source"]), (2, 7, "native"))
        self.assertEqual((second["address"], second["tls"], second["max_concurrent"]), (None, True, None))

    def test_only_delegated_zones_are_handed_off(self):
        # python : toutes les zones confiees ; auto (lot 11) et native : seules celles que le relais ne sait pas servir.
        inspect = build_native_snapshot(_config({"engine": "python"}, zones=[_zone("/a/"), _zone("/b/")]), self.root,
                                        1)["inspect"]
        self.assertTrue({"/a/", "/b/"} <= set(inspect["handoff_any"]))
        auto = build_native_snapshot(_config({}, zones=[_zone("/a/"), _zone("/b/", cache_enabled=True)]), self.root, 1)
        self.assertNotIn("/a/", auto["inspect"]["handoff_any"])
        self.assertIn("/b/", auto["inspect"]["handoff_any"])
        native = _config({"engine": "native"}, zones=[_zone("/a/"), _zone("/b/", cache_enabled=True)])
        with self.assertRaises(AssertionError):  # zone avec cache : engine = native refuse a la validation...
            self.assertEqual(proxy_engine_problems(native).errors, ())
        snapshot = build_native_snapshot(native, self.root, 1)  # ...mais l'instantane reste coherent
        self.assertNotIn("/a/", snapshot["inspect"]["handoff_any"])
        self.assertIn("/b/", snapshot["inspect"]["handoff_any"])
        self.assertEqual([z["engine"] for z in snapshot["proxy"]["zones"]], ["native", "python"])

    def test_security_process_whenever_a_proxy_zone_exists(self):
        # P6 : meme sans option de securite (sondes, route d'administration).
        inspect = build_native_snapshot(_config({}), self.root, 1)["inspect"]
        self.assertIsNotNone(inspect)
        self.assertFalse(inspect["security_stage"])
        self.assertEqual(inspect["security_processes"], 1)
        two = build_native_snapshot(_config({}), self.root, 1, security_processes=2)["inspect"]
        self.assertEqual(two["security_processes"], 2)

    def test_inspect_mode_per_zone(self):
        def mode(options, zones=None):
            return build_native_snapshot(_config({}, zones=zones, options=options), self.root, 1)["proxy"]["zones"]

        self.assertEqual(mode({})[0]["inspect"], "never")
        self.assertEqual(mode({"waf": {"enabled": True}})[0]["inspect"], "filter")
        self.assertEqual(mode({"waf": {"enabled": True, "magnet": {"enabled": True}}})[0]["inspect"], "always")
        self.assertEqual(mode({"auth": {"enabled": True}})[0]["inspect"], "always")  # pas de filtre sans WAF
        self.assertEqual(mode({"active_defense": {"enabled": True}})[0]["inspect"], "always")


class TestConfigCheckOutput(unittest.TestCase):
    """config check : avertissements et avis affiches, configuration toujours valide (code 0)."""

    def _check(self, options: dict, server: dict | None = None) -> tuple[int, str]:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "webroot").mkdir()
            path = root / "omega-serv.json"
            path.write_text(json.dumps({"server": {"engine": "native", "port": 8080, **(server or {})},
                                        "options": options}), encoding="utf-8")
            args = argparse.Namespace(config=path, confirm_self_signed_public_bind=False,
                                      confirm_auth_without_tls=False)
            out = io.StringIO()
            with contextlib.redirect_stdout(out), contextlib.redirect_stderr(io.StringIO()):
                code = cmd_config_check(args, DependencyContainer(project_root=root))
            return code, out.getvalue()

    def test_notice_for_native_with_python_server_engine(self):
        code, out = self._check({"reverse_proxy": {"enabled": True, "engine": "native", "zones": [_zone()]}},
                                {"engine": "python"})
        self.assertEqual(code, 0)
        self.assertIn("sans effet", out)
        self.assertIn("configuration valide", out)

    def test_link_local_warning(self):
        zones = [{"url_prefix": "/meta/", "upstreams": [{"host": "169.254.169.254", "port": 80}]}]
        code, out = self._check({"reverse_proxy": {"enabled": True, "zones": zones}})
        self.assertEqual(code, 0)
        self.assertIn("169.254.169.254", out)
        self.assertIn("configuration valide", out)

    def test_engine_native_refused(self):
        # Lot 10 : une zone WebSocket est native ; le cache reste confie pour toujours (Q6).
        zones = [{"url_prefix": "/c/", "upstreams": [{"host": "10.0.0.5", "port": 1}], "cache_enabled": True}]
        code, out = self._check({"reverse_proxy": {"enabled": True, "engine": "native", "zones": zones}})
        self.assertEqual(code, 1)
        self.assertNotIn("configuration valide", out)


if __name__ == "__main__":
    unittest.main()
