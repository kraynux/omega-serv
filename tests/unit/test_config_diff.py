import unittest

from omega_serv.domain.config.diff import diff_configs


class TestDiffConfigs(unittest.TestCase):
    def test_no_changes(self):
        self.assertEqual(diff_configs({"a": 1}, {"a": 1}), [])

    def test_changed_value(self):
        changes = diff_configs({"a": 1}, {"a": 2})
        self.assertEqual(len(changes), 1)
        self.assertEqual(changes[0].kind, "changed")
        self.assertEqual(changes[0].path, "a")
        self.assertEqual(changes[0].old_value, 1)
        self.assertEqual(changes[0].new_value, 2)

    def test_added_key(self):
        changes = diff_configs({}, {"waf": {"enabled": True}})
        self.assertEqual(len(changes), 1)
        self.assertEqual(changes[0].kind, "added")

    def test_removed_key(self):
        changes = diff_configs({"waf": {"enabled": True}}, {})
        self.assertEqual(len(changes), 1)
        self.assertEqual(changes[0].kind, "removed")

    def test_nested_change_reports_dotted_path(self):
        old = {"security": {"csp_mode": "report-only"}}
        new = {"security": {"csp_mode": "enforce"}}
        changes = diff_configs(old, new)
        self.assertEqual(len(changes), 1)
        self.assertEqual(changes[0].path, "security.csp_mode")

    def test_str_formatting(self):
        old = {"a": 1}
        new = {"a": 2, "b": 3}
        changes = diff_configs(old, new)
        rendered = {str(c) for c in changes}
        self.assertIn("  ~ a : 1 -> 2", rendered)
        self.assertIn("  + b : 3", rendered)


if __name__ == "__main__":
    unittest.main()
