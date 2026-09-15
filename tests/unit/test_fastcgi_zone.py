# Copyright (c) 2026 kraynux - kraynux@proton.me - Licence MIT (voir fichier LICENSE)
import unittest

from omega_serv.domain.routing.fastcgi_zone import (
    FastCgiConfig,
    parse_fastcgi_config,
    validate_fastcgi_config_structure,
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


if __name__ == "__main__":
    unittest.main()
