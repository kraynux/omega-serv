import unittest

from omega_serv.domain.config.entities import OmegaServConfig
from omega_serv.domain.config.option import Option
from omega_serv.domain.config.profile import Profile


class TestOmegaServConfigRoundTrip(unittest.TestCase):
    def test_default_config_round_trips(self):
        config = OmegaServConfig()
        as_dict = config.to_dict()
        restored = OmegaServConfig.from_dict(as_dict)
        self.assertEqual(restored.to_dict(), as_dict)

    def test_from_dict_applies_overrides(self):
        data = {
            "version": 1,
            "profile": "hardened",
            "server": {"bind": "0.0.0.0", "port": 8443},
            "options": {"waf": {"enabled": True, "mode": "log-only"}},
        }
        config = OmegaServConfig.from_dict(data)
        self.assertEqual(config.profile, "hardened")
        self.assertEqual(config.server.bind, "0.0.0.0")
        self.assertEqual(config.server.port, 8443)
        self.assertTrue(config.option_enabled("waf"))
        self.assertEqual(config.options["waf"].settings["mode"], "log-only")

    def test_option_enabled_false_for_unknown_option(self):
        config = OmegaServConfig()
        self.assertFalse(config.option_enabled("waf"))
        self.assertFalse(config.option_enabled("does-not-exist"))

    def test_defaults_are_safe(self):
        config = OmegaServConfig()
        self.assertEqual(config.server.bind, "127.0.0.1")
        self.assertEqual(config.security.allowed_methods, ("GET", "HEAD"))
        self.assertFalse(config.tls.enabled)
        self.assertFalse(config.security.hsts_enabled)
        for name in config.options:
            self.assertFalse(config.options[name].enabled)

    def test_tls_overrides_applied(self):
        data = {
            "tls": {
                "enabled": True,
                "mode": "direct",
                "certificate": {"certificate_path": "secure/certificates/server/server.pem", "private_key_path": "secure/certificates/server/server.key"},
                "protocols": {"min_version": "TLS1.2", "max_version": "TLS1.3"},
            },
            "security": {"hsts_enabled": True, "hsts_max_age": 3600},
        }
        config = OmegaServConfig.from_dict(data)
        self.assertTrue(config.tls.enabled)
        self.assertEqual(config.tls.mode, "direct")
        self.assertEqual(config.tls.certificate_path, "secure/certificates/server/server.pem")
        self.assertTrue(config.security.hsts_enabled)
        self.assertEqual(config.security.hsts_max_age, 3600)


class TestOption(unittest.TestCase):
    def test_from_dict_separates_enabled_from_settings(self):
        option = Option.from_dict("waf", {"enabled": True, "mode": "block"})
        self.assertTrue(option.enabled)
        self.assertEqual(option.settings, {"mode": "block"})

    def test_to_dict_merges_back(self):
        option = Option(name="waf", enabled=True, settings={"mode": "block"})
        self.assertEqual(option.to_dict(), {"enabled": True, "mode": "block"})


class TestProfile(unittest.TestCase):
    def test_from_dict_requires_name(self):
        with self.assertRaises(ValueError):
            Profile.from_dict({"description": "sans nom"})

    def test_round_trip(self):
        data = {"name": "standard", "description": "desc", "server": {"bind": "127.0.0.1"}}
        profile = Profile.from_dict(data)
        self.assertEqual(profile.name, "standard")
        self.assertEqual(profile.values, {"server": {"bind": "127.0.0.1"}})
        self.assertEqual(profile.to_dict(), data)


if __name__ == "__main__":
    unittest.main()
