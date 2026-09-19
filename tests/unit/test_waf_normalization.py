import unittest

from omega_serv.domain.security.waf.normalization import decode_bounded_for_inspection


class TestDecodeBoundedForInspection(unittest.TestCase):
    def test_decodes_single_pass(self):
        self.assertEqual(decode_bounded_for_inspection("union%20select", 2), "union select")

    def test_decodes_double_encoding_within_budget(self):
        self.assertEqual(decode_bounded_for_inspection("union%2520select", 2), "union select")

    def test_stops_at_max_passes(self):
        self.assertEqual(decode_bounded_for_inspection("union%2520select", 1), "union%20select")

    def test_plain_text_unchanged(self):
        self.assertEqual(decode_bounded_for_inspection("hello world", 2), "hello world")

    def test_invalid_percent_sequence_never_raises(self):
        result = decode_bounded_for_inspection("100%off", 2)
        self.assertIsInstance(result, str)

    def test_fullwidth_unicode_characters_are_normalized_to_ascii(self):
        result = decode_bounded_for_inspection("＜script＞", 2)
        self.assertEqual(result, "<script>")

    def test_fullwidth_sql_keywords_normalized(self):
        result = decode_bounded_for_inspection("ｕｎｉｏｎ select", 2)
        self.assertEqual(result, "union select")

    def test_url_encoded_fullwidth_character_normalized_after_decoding(self):
        result = decode_bounded_for_inspection("%EF%BC%9Cscript%EF%BC%9E", 2)
        self.assertEqual(result, "<script>")

    def test_ascii_text_is_never_altered_by_normalization(self):
        self.assertEqual(decode_bounded_for_inspection("union select 1", 2), "union select 1")


if __name__ == "__main__":
    unittest.main()
