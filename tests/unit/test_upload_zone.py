import unittest

from omega_serv.domain.routing.upload_zone import (
    UploadPolicy,
    UploadZoneRule,
    parse_upload_zone_rules,
    validate_upload_zone_rule,
)


class TestParseUploadZoneRules(unittest.TestCase):
    def test_parses_list(self):
        rules = parse_upload_zone_rules([{
            "url_prefix": "/upload/", "storage_path": "var/uploads/public",
            "policy": {"max_file_size_bytes": 2048, "allowed_extensions": [".jpg", ".png"]},
        }])
        self.assertEqual(len(rules), 1)
        self.assertEqual(rules[0].url_prefix, "/upload/")
        self.assertEqual(rules[0].policy.max_file_size_bytes, 2048)
        self.assertEqual(rules[0].policy.allowed_extensions, (".jpg", ".png"))

    def test_missing_policy_uses_defaults(self):
        rules = parse_upload_zone_rules([{"url_prefix": "/upload/", "storage_path": "var/uploads"}])
        self.assertEqual(rules[0].policy, UploadPolicy())


class TestValidateUploadZoneRule(unittest.TestCase):
    def _rule(self, **overrides) -> UploadZoneRule:
        defaults = {"url_prefix": "/upload/", "storage_path": "var/uploads/public", "policy": UploadPolicy()}
        defaults.update(overrides)
        return UploadZoneRule(**defaults)

    def test_valid_rule_passes(self):
        self.assertIsNone(validate_upload_zone_rule(self._rule()))

    def test_prefix_without_leading_slash_rejected(self):
        self.assertIsNotNone(validate_upload_zone_rule(self._rule(url_prefix="upload/")))

    def test_empty_storage_path_rejected(self):
        self.assertIsNotNone(validate_upload_zone_rule(self._rule(storage_path="")))

    def test_absolute_storage_path_rejected(self):
        self.assertIsNotNone(validate_upload_zone_rule(self._rule(storage_path="/etc/uploads")))

    def test_storage_path_traversal_rejected(self):
        self.assertIsNotNone(validate_upload_zone_rule(self._rule(storage_path="../outside")))

    def test_non_positive_max_file_size_rejected(self):
        rule = self._rule(policy=UploadPolicy(max_file_size_bytes=0))
        self.assertIsNotNone(validate_upload_zone_rule(rule))

    def test_non_positive_max_files_per_zone_rejected(self):
        rule = self._rule(policy=UploadPolicy(max_files_per_zone=0))
        self.assertIsNotNone(validate_upload_zone_rule(rule))


if __name__ == "__main__":
    unittest.main()
