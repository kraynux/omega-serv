"""Moteur effectif (plan moteur C++ §16.5) : une seule fonction decide ; repli Python explicite, jamais partiel."""
import unittest

from omega_serv.application.server.engine_selection import (
    BINARY_MISSING,
    WORKERS_IGNORED,
    decide_engine,
    describe_reason,
    log_reason,
)
from omega_serv.domain.config.entities import OmegaServConfig
from omega_serv.domain.config.validation import validate_config


def _config(**server):
    data = {"server": server}
    return OmegaServConfig.from_dict(data)


class TestDecideEngine(unittest.TestCase):
    def test_python_by_default(self):
        decision = decide_engine(OmegaServConfig.from_dict({}), BINARY_MISSING)
        self.assertEqual((decision.requested, decision.effective, decision.reasons), ("python", "python", ()))
        self.assertFalse(decision.fallback)

    def test_native_when_everything_is_supported(self):
        decision = decide_engine(_config(engine="native"), None)
        self.assertEqual((decision.effective, decision.reasons, decision.fallback), ("native", (), False))

    def test_every_cause_is_listed(self):
        config = OmegaServConfig.from_dict({
            "server": {"engine": "native", "workers": 4},
            "tls": {"enabled": True, "mode": "direct"},
            "options": {"waf": {"enabled": True}, "upload": {"enabled": True}},
        })
        decision = decide_engine(config, BINARY_MISSING)
        self.assertEqual(decision.effective, "python")
        # TLS direct (3b), WAF / Auth / AD (4), listing (5), upload (6) : pris en charge ; mais TLS direct + route
        # applicative (upload) : la connexion chiffree ne peut pas etre confiee a Python
        self.assertEqual(decision.reasons, (BINARY_MISSING, "tls_handoff"))
        self.assertEqual(decision.notices, ())  # lot 7 : workers = processus de securite (Hyperboost)
        self.assertTrue(decision.fallback)

    def test_tls_in_both_modes_stays_native(self):
        for mode in ("behind_proxy", "direct"):
            config = OmegaServConfig.from_dict({"server": {"engine": "native"}, "tls": {"enabled": True, "mode": mode}})
            self.assertEqual(decide_engine(config, None).effective, "native", mode)

    def test_every_reason_has_a_text(self):
        for code in (BINARY_MISSING, WORKERS_IGNORED, "waf", "auth", "active_defense", "upload",
                     "fastcgi", "reverse_proxy", "dirlisting"):
            self.assertNotIn("inconnue", describe_reason(code), code)
            self.assertTrue(log_reason(code))

    def test_engine_value_validated(self):
        self.assertTrue(any("server.engine" in e for e in validate_config(_config(engine="turbo"))))
        self.assertFalse(any("server.engine" in e for e in validate_config(_config(engine="native"))))
        self.assertEqual(_config(engine="native").to_dict()["server"]["engine"], "native")


if __name__ == "__main__":
    unittest.main()
