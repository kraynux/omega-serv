import unittest

from omega_serv.domain.config.entities import OmegaServConfig
from omega_serv.domain.config.validation import validate_config


class TestValidateAliasesAndRedirects(unittest.TestCase):
    def test_valid_alias_passes(self):
        config = OmegaServConfig.from_dict({
            "options": {"aliases": {
                "enabled": True,
                "list": [{"url_prefix": "/dl/", "target_path": "webroot/public/"}],
            }},
        })
        self.assertEqual(validate_config(config), [])

    def test_alias_outside_webroot_without_flag_is_rejected(self):
        config = OmegaServConfig.from_dict({
            "options": {"aliases": {
                "enabled": True,
                "list": [{"url_prefix": "/dl/", "target_path": "somewhere/"}],
            }},
        })
        errors = validate_config(config)
        self.assertTrue(any("options.aliases" in e for e in errors))

    def test_disabled_aliases_are_not_validated(self):
        config = OmegaServConfig.from_dict({
            "options": {"aliases": {
                "enabled": False,
                "list": [{"url_prefix": "/dl/", "target_path": "somewhere/"}],
            }},
        })
        self.assertEqual(validate_config(config), [])

    def test_valid_redirect_passes(self):
        config = OmegaServConfig.from_dict({
            "options": {"redirects": {
                "enabled": True,
                "list": [{"url_prefix": "/old/", "destination": "/new/", "status_code": 301}],
            }},
        })
        self.assertEqual(validate_config(config), [])

    def test_invalid_redirect_status_code_is_rejected(self):
        config = OmegaServConfig.from_dict({
            "options": {"redirects": {
                "enabled": True,
                "list": [{"url_prefix": "/old/", "destination": "/new/", "status_code": 200}],
            }},
        })
        errors = validate_config(config)
        self.assertTrue(any("options.redirects" in e for e in errors))

    def test_valid_upload_zone_passes(self):
        config = OmegaServConfig.from_dict({
            "options": {"upload": {
                "enabled": True,
                "zones": [{
                    "url_prefix": "/upload/", "storage_path": "var/uploads/public",
                    "policy": {"max_file_size_bytes": 1024},
                }],
            }},
        })
        self.assertEqual(validate_config(config), [])

    def test_upload_prefix_without_leading_slash_rejected(self):
        config = OmegaServConfig.from_dict({
            "options": {"upload": {
                "enabled": True,
                "zones": [{"url_prefix": "upload/", "storage_path": "var/uploads/public"}],
            }},
        })
        errors = validate_config(config)
        self.assertTrue(any("options.upload" in e for e in errors))

    def test_upload_storage_path_traversal_rejected(self):
        config = OmegaServConfig.from_dict({
            "options": {"upload": {
                "enabled": True,
                "zones": [{"url_prefix": "/upload/", "storage_path": "../outside"}],
            }},
        })
        errors = validate_config(config)
        self.assertTrue(any("options.upload" in e for e in errors))

    def test_upload_policy_exceeding_server_max_request_size_rejected(self):
        config = OmegaServConfig.from_dict({
            "server": {"max_request_size": 1000},
            "options": {"upload": {
                "enabled": True,
                "zones": [{
                    "url_prefix": "/upload/", "storage_path": "var/uploads/public",
                    "policy": {"max_file_size_bytes": 2000},
                }],
            }},
        })
        errors = validate_config(config)
        self.assertTrue(any("max_request_size" in e for e in errors))

    def test_disabled_upload_is_not_validated(self):
        config = OmegaServConfig.from_dict({
            "options": {"upload": {
                "enabled": False,
                "zones": [{"url_prefix": "upload/", "storage_path": "../outside"}],
            }},
        })
        self.assertEqual(validate_config(config), [])

    def test_valid_access_control_rules_pass(self):
        config = OmegaServConfig.from_dict({
            "options": {"access_control": {
                "enabled": True,
                "list": [
                    {"path_prefix": "/private/", "verdict": "deny"},
                    {"path_prefix": "/private/.assets/", "verdict": "allow"},
                ],
            }},
        })
        self.assertEqual(validate_config(config), [])

    def test_access_control_prefix_without_leading_slash_rejected(self):
        config = OmegaServConfig.from_dict({
            "options": {"access_control": {
                "enabled": True,
                "list": [{"path_prefix": "private/", "verdict": "deny"}],
            }},
        })
        errors = validate_config(config)
        self.assertTrue(any("options.access_control" in e for e in errors))

    def test_access_control_invalid_verdict_rejected(self):
        config = OmegaServConfig.from_dict({
            "options": {"access_control": {
                "enabled": True,
                "list": [{"path_prefix": "/private/", "verdict": "block"}],
            }},
        })
        errors = validate_config(config)
        self.assertTrue(any("options.access_control" in e for e in errors))

    def test_disabled_access_control_is_not_validated(self):
        config = OmegaServConfig.from_dict({
            "options": {"access_control": {
                "enabled": False,
                "list": [{"path_prefix": "private/", "verdict": "block"}],
            }},
        })
        self.assertEqual(validate_config(config), [])


class TestValidateReverseProxy(unittest.TestCase):
    def test_valid_zone_passes(self):
        config = OmegaServConfig.from_dict({
            "options": {"reverse_proxy": {
                "enabled": True,
                "zones": [{"url_prefix": "/api/", "upstreams": [{"host": "127.0.0.1", "port": 3000}]}],
            }},
        })
        self.assertEqual(validate_config(config), [])

    def test_valid_zone_multiple_upstreams_passes(self):
        config = OmegaServConfig.from_dict({
            "options": {"reverse_proxy": {
                "enabled": True,
                "zones": [{"url_prefix": "/api/", "upstreams": [
                    {"host": "127.0.0.1", "port": 3000}, {"host": "127.0.0.1", "port": 3001},
                ]}],
            }},
        })
        self.assertEqual(validate_config(config), [])

    def test_prefix_without_leading_slash_rejected(self):
        config = OmegaServConfig.from_dict({
            "options": {"reverse_proxy": {
                "enabled": True,
                "zones": [{"url_prefix": "api/", "upstreams": [{"host": "127.0.0.1", "port": 3000}]}],
            }},
        })
        errors = validate_config(config)
        self.assertTrue(any("options.reverse_proxy" in e for e in errors))

    def test_invalid_port_rejected(self):
        config = OmegaServConfig.from_dict({
            "options": {"reverse_proxy": {
                "enabled": True,
                "zones": [{"url_prefix": "/api/", "upstreams": [{"host": "127.0.0.1", "port": 0}]}],
            }},
        })
        errors = validate_config(config)
        self.assertTrue(any("options.reverse_proxy" in e for e in errors))

    def test_proxy_loop_to_self_rejected(self):
        config = OmegaServConfig.from_dict({
            "server": {"bind": "127.0.0.1", "port": 8080},
            "options": {"reverse_proxy": {
                "enabled": True,
                "zones": [{"url_prefix": "/api/", "upstreams": [{"host": "127.0.0.1", "port": 8080}]}],
            }},
        })
        errors = validate_config(config)
        self.assertTrue(any("boucle de proxy" in e for e in errors))

    def test_proxy_loop_to_self_rejected_even_when_not_the_only_upstream(self):
        config = OmegaServConfig.from_dict({
            "server": {"bind": "127.0.0.1", "port": 8080},
            "options": {"reverse_proxy": {
                "enabled": True,
                "zones": [{"url_prefix": "/api/", "upstreams": [
                    {"host": "10.0.0.5", "port": 3000}, {"host": "127.0.0.1", "port": 8080},
                ]}],
            }},
        })
        errors = validate_config(config)
        self.assertTrue(any("boucle de proxy" in e for e in errors))

    def test_disabled_reverse_proxy_is_not_validated(self):
        config = OmegaServConfig.from_dict({
            "options": {"reverse_proxy": {
                "enabled": False,
                "zones": [{"url_prefix": "api/", "upstreams": [{"host": "", "port": 0}]}],
            }},
        })
        self.assertEqual(validate_config(config), [])


if __name__ == "__main__":
    unittest.main()
