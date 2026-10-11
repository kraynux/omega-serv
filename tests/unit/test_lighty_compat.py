import unittest

from omega_serv.domain.security.waf.lighty_compat import (
    SUPPORTED_LIGHTY_MEMBERS,
    scan_lighty_member_references,
    unsupported_lighty_members,
)


class TestScanLightyMemberReferences(unittest.TestCase):
    def test_finds_distinct_members(self):
        source = "local e = lighty.env\nlighty.header['X'] = 1\nlighty.env['y'] = 2"
        self.assertEqual(scan_lighty_member_references(source), frozenset({"env", "header"}))

    def test_no_reference_returns_empty(self):
        self.assertEqual(scan_lighty_member_references("return 0"), frozenset())

    def test_does_not_match_unrelated_dotted_names(self):
        self.assertEqual(scan_lighty_member_references("lightyX.env"), frozenset())


class TestUnsupportedLightyMembers(unittest.TestCase):
    def test_all_supported_members_yield_no_warning(self):
        source = "\n".join(f"lighty.{m}" for m in SUPPORTED_LIGHTY_MEMBERS)
        self.assertEqual(unsupported_lighty_members(source), frozenset())

    def test_unknown_member_flagged(self):
        self.assertEqual(unsupported_lighty_members("lighty.some_custom_field"), frozenset({"some_custom_field"}))

    def test_mix_of_supported_and_unsupported(self):
        source = "lighty.env\nlighty.weird\nlighty.stat"
        self.assertEqual(unsupported_lighty_members(source), frozenset({"weird"}))


if __name__ == "__main__":
    unittest.main()
