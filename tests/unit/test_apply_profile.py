import unittest

from omega_serv.application.config.apply_profile import plan_profile_application
from omega_serv.domain.config.entities import OmegaServConfig
from omega_serv.domain.config.profile import Profile


class TestPlanProfileApplication(unittest.TestCase):
    def test_reports_changes_from_profile_values(self):
        current = OmegaServConfig()
        profile = Profile(name="hardened", description="", values={"server": {"bind": "0.0.0.0"}})
        plan = plan_profile_application(current, profile)
        self.assertEqual(plan.new_config.server.bind, "0.0.0.0")
        self.assertTrue(any(c.path == "server.bind" for c in plan.changes))
        self.assertFalse(plan.has_blocking_issues)

    def test_keeps_currently_enabled_options(self):
        current = OmegaServConfig.from_dict({"options": {"waf": {"enabled": True, "mode": "block"}}})
        profile = Profile(name="minimal", description="", values={})
        plan = plan_profile_application(current, profile)
        self.assertTrue(plan.new_config.option_enabled("waf"))
        self.assertEqual(plan.new_config.options["waf"].settings["mode"], "block")

    def test_blocking_conflict_is_reported(self):
        current = OmegaServConfig.from_dict({"options": {"trusted_proxy": {"enabled": True}}})
        profile = Profile(name="standard", description="", values={})
        plan = plan_profile_application(current, profile)
        self.assertTrue(plan.has_blocking_issues)
        self.assertTrue(plan.conflicts)

    def test_invalid_profile_values_reported_as_validation_error(self):
        current = OmegaServConfig()
        profile = Profile(name="broken", description="", values={"server": {"port": 999999}})
        plan = plan_profile_application(current, profile)
        self.assertTrue(plan.has_blocking_issues)
        self.assertTrue(any("port" in e for e in plan.validation_errors))

    def test_no_changes_when_profile_matches_current(self):
        current = OmegaServConfig()
        profile = Profile(name="standard", description="", values={})
        plan = plan_profile_application(current, profile)
        self.assertEqual([c for c in plan.changes if c.path != "profile"], [])


if __name__ == "__main__":
    unittest.main()
