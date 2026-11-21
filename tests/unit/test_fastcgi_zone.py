import unittest

from omega_serv.domain.routing.fastcgi_zone import (
    FastCgiConfig,
    active_socket_paths,
    fastcgi_settings_with_zones,
    fastcgi_zone_settings,
    parse_fastcgi_config,
    parse_fastcgi_zones,
    validate_fastcgi_config_structure,
    validate_fastcgi_zones_structure,
)


class TestParseFastCgiConfig(unittest.TestCase):
    def test_defaults(self):
        config = parse_fastcgi_config({})
        self.assertEqual(config.url_prefix, "/app/")
        self.assertEqual(config.allowed_extensions, (".php",))

    def test_overrides_applied(self):
        config = parse_fastcgi_config({
            "url_prefix": "/php/", "script_root": "backend", "socket_path": "var/run/x.sock",
            "connect_timeout_seconds": 2, "read_timeout_seconds": 10,
            "allowed_extensions": [".php", ".phtml"], "index_files": ["index.php", "app.php"],
        })
        self.assertEqual(config.url_prefix, "/php/")
        self.assertEqual(config.script_root, "backend")
        self.assertEqual(config.allowed_extensions, (".php", ".phtml"))

    def test_allowed_scripts_defaults_empty(self):
        config = parse_fastcgi_config({})
        self.assertEqual(config.allowed_scripts, ())

    def test_allowed_scripts_override_applied(self):
        config = parse_fastcgi_config({"allowed_scripts": ["index.php", "api/router.php"]})
        self.assertEqual(config.allowed_scripts, ("index.php", "api/router.php"))


class TestValidateFastCgiConfigStructure(unittest.TestCase):
    def test_valid_config_passes(self):
        config = FastCgiConfig(url_prefix="/app/", script_root="backend")
        self.assertEqual(validate_fastcgi_config_structure(config), [])

    def test_prefix_without_leading_slash_rejected(self):
        config = FastCgiConfig(url_prefix="app/", script_root="backend")
        self.assertTrue(any("url_prefix" in e for e in validate_fastcgi_config_structure(config)))

    def test_empty_script_root_rejected(self):
        config = FastCgiConfig(url_prefix="/app/", script_root="")
        self.assertTrue(any("script_root" in e for e in validate_fastcgi_config_structure(config)))

    def test_empty_socket_path_rejected(self):
        config = FastCgiConfig(url_prefix="/app/", script_root="backend", socket_path="")
        self.assertTrue(any("socket_path" in e for e in validate_fastcgi_config_structure(config)))

    def test_empty_allowed_extensions_rejected(self):
        config = FastCgiConfig(url_prefix="/app/", script_root="backend", allowed_extensions=())
        self.assertTrue(any("allowed_extensions" in e for e in validate_fastcgi_config_structure(config)))

    def test_non_positive_timeouts_rejected(self):
        config = FastCgiConfig(url_prefix="/app/", script_root="backend", connect_timeout_seconds=0, read_timeout_seconds=-1)
        errors = validate_fastcgi_config_structure(config)
        self.assertTrue(any("connect_timeout_seconds" in e for e in errors))
        self.assertTrue(any("read_timeout_seconds" in e for e in errors))

    def test_allowed_scripts_with_leading_slash_rejected(self):
        config = FastCgiConfig(url_prefix="/app/", script_root="backend", allowed_scripts=("/index.php",))
        self.assertTrue(any("allowed_scripts" in e for e in validate_fastcgi_config_structure(config)))

    def test_allowed_scripts_with_empty_entry_rejected(self):
        config = FastCgiConfig(url_prefix="/app/", script_root="backend", allowed_scripts=("index.php", ""))
        self.assertTrue(any("allowed_scripts" in e for e in validate_fastcgi_config_structure(config)))

    def test_valid_allowed_scripts_passes(self):
        config = FastCgiConfig(url_prefix="/app/", script_root="backend", allowed_scripts=("index.php",))
        self.assertEqual(validate_fastcgi_config_structure(config), [])


class TestFastCgiZones(unittest.TestCase):
    """Projets 3.0.0 §8.1 : liste de zones, ancien enregistrement a plat lu comme une zone."""

    def test_legacy_flat_record_is_one_enabled_zone(self):
        zones = parse_fastcgi_zones({"url_prefix": "/php/", "script_root": "backend", "rule_paths": []})
        self.assertEqual([(z.url_prefix, z.script_root, z.enabled) for z in zones], [("/php/", "backend", True)])

    def test_no_zone_when_settings_empty_or_list_empty(self):
        self.assertEqual(parse_fastcgi_zones({}), ())
        self.assertEqual(parse_fastcgi_zones({"zones": [], "url_prefix": "/old/"}), ())

    def test_zone_list_with_its_own_switch(self):
        zones = parse_fastcgi_zones({"zones": [
            {"url_prefix": "/blog/", "script_root": "blog"},
            {"url_prefix": "/wiki/", "script_root": "wiki", "enabled": False, "socket_path": "run/wiki.sock"},
        ]})
        self.assertEqual([z.enabled for z in zones], [True, False])
        self.assertEqual(zones[1].socket_path, "run/wiki.sock")

    def test_saving_drops_the_legacy_keys_and_keeps_the_rest(self):
        settings = fastcgi_settings_with_zones({"url_prefix": "/php/", "script_root": "x", "note": "kept"},
                                               [FastCgiConfig(url_prefix="/a/", script_root="a", enabled=False)])
        self.assertEqual(set(settings), {"note", "zones"})
        self.assertEqual(parse_fastcgi_zones(settings)[0], FastCgiConfig(url_prefix="/a/", script_root="a",
                                                                         enabled=False))

    def test_duplicate_prefix_and_zone_errors_are_named(self):
        errors = validate_fastcgi_zones_structure((
            FastCgiConfig(url_prefix="/a/", script_root="a"), FastCgiConfig(url_prefix="/a", script_root="b"),
            FastCgiConfig(url_prefix="b/", script_root="c")))
        self.assertTrue(any("'/a'" in e and "double" in e for e in errors))
        self.assertTrue(any("'b/'" in e and "url_prefix" in e for e in errors))

    def test_active_sockets_skip_disabled_zones_and_duplicates(self):
        settings = {"zones": [
            {"url_prefix": "/a/", "socket_path": "run/a.sock"}, {"url_prefix": "/b/", "socket_path": "run/a.sock"},
            {"url_prefix": "/c/", "socket_path": "run/c.sock", "enabled": False}]}
        self.assertEqual(active_socket_paths(settings), ("run/a.sock",))


if __name__ == "__main__":
    unittest.main()


class TestFastCgiZoneRequestSize(unittest.TestCase):
    """Projets 3.0.0 §9 : taille maximale de requete par zone (vide = taille globale de l'ecran Limites)."""

    def test_absent_means_global_and_is_not_written(self):
        zone = parse_fastcgi_config({"url_prefix": "/a/", "script_root": "apps/a"})
        self.assertIsNone(zone.max_request_size)
        self.assertNotIn("max_request_size", fastcgi_zone_settings(zone))

    def test_round_trip(self):
        zone = parse_fastcgi_config({"url_prefix": "/a/", "script_root": "apps/a", "max_request_size": 52428800})
        self.assertEqual(zone.max_request_size, 52428800)
        self.assertEqual(parse_fastcgi_config(fastcgi_zone_settings(zone)), zone)

    def test_invalid_sizes_are_refused(self):
        for value in (0, -1, True, "10", 1.5, (1 << 50) + 1):
            zone = parse_fastcgi_config({"url_prefix": "/a/", "script_root": "apps/a", "max_request_size": value})
            self.assertTrue(any("max_request_size" in e for e in validate_fastcgi_config_structure(zone)), value)

    def test_request_size_limit_picks_the_zone_then_the_global_size(self):
        from omega_serv.application.server.routing_tables import request_size_limit
        from omega_serv.domain.config.entities import OmegaServConfig
        config = OmegaServConfig.from_dict({
            "server": {"bind": "127.0.0.1", "port": 8080, "max_request_size": 1000},
            "options": {"fastcgi": {"enabled": True, "zones": [
                {"url_prefix": "/admin/", "script_root": "a", "socket_path": "a.sock", "max_request_size": 5000},
                {"url_prefix": "/off/", "script_root": "b", "socket_path": "b.sock", "max_request_size": 9000,
                 "enabled": False},
                {"url_prefix": "/plain/", "script_root": "c", "socket_path": "c.sock"}]}},
        })
        self.assertEqual(request_size_limit(config, "/admin/upload.php"), 5000)
        self.assertEqual(request_size_limit(config, "/plain/index.php"), 1000)
        self.assertEqual(request_size_limit(config, "/off/index.php"), 1000)  # zone arretee : 503 de toute facon
        self.assertEqual(request_size_limit(config, "/static/file.txt"), 1000)
        off = OmegaServConfig.from_dict({**config.to_dict(), "options": {"fastcgi": {
            **config.to_dict()["options"]["fastcgi"], "enabled": False}}})
        self.assertEqual(request_size_limit(off, "/admin/upload.php"), 1000)
