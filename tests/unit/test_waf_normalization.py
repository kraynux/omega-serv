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


    def test_ascii_without_percent_is_returned_unchanged_like_full_decoding(self):
        import random
        import unicodedata
        import urllib.parse

        rng = random.Random(11)
        alphabet = "".join(chr(c) for c in range(128) if chr(c) != "%")
        for _ in range(2000):
            raw = "".join(rng.choice(alphabet) for _ in range(rng.randint(0, 40)))
            full = unicodedata.normalize("NFKC", urllib.parse.unquote(unicodedata.normalize("NFKC", raw), errors="replace"))
            self.assertEqual(decode_bounded_for_inspection(raw, 3), full)
            self.assertIs(decode_bounded_for_inspection(raw, 3), raw)
        # avec « % » ou du non ASCII : toujours decode
        self.assertEqual(decode_bounded_for_inspection("%3Cscript%3E", 2), "<script>")
        self.assertEqual(decode_bounded_for_inspection("\uff1cscript\uff1e", 2), "<script>")


if __name__ == "__main__":
    unittest.main()


class TestUnquoteReplace(unittest.TestCase):
    """Plan proxy natif v2, lot 2 (B) : `unquote_replace` remplace `urllib.parse.unquote(errors="replace")` pour la
    vitesse (3 s de CPU par Mo de corps binaire, mesure du lot 2) - le resultat doit etre EXACTEMENT le meme."""

    def test_same_result_as_urllib_unquote(self):
        import random
        import urllib.parse

        from omega_serv.domain.security.waf.normalization import unquote_replace
        rng = random.Random(20261112)
        alphabet = ["%", "%", "%", "0", "9", "a", "f", "A", "F", "g", "e", "2", "c", "8", "+", " ", "é", "中", "�",
                    "\x00", "\x7f", "€"]
        fixed = ["", "%", "%%", "%%41", "%4", "%41%", "%e2%82%ac", "%E2%82", "%e2%82a", "%e2é%82%ac", "%ff%fe",
                 "%c3%a9%c3", "%f0%9f%98%80", "%ed%a0%80", "a%2", "%zz%41", "union%20select"]
        texts = fixed + ["".join(rng.choice(alphabet) for _ in range(rng.randint(0, 30))) for _ in range(50000)]
        for text in texts:
            self.assertEqual(unquote_replace(text), urllib.parse.unquote(text, errors="replace"), repr(text))

    def test_whole_decoding_same_result_as_before(self):
        # decode_bounded_for_inspection garde EXACTEMENT son resultat d'avant le lot 2 (reference recopiee ici).
        import random
        import unicodedata
        import urllib.parse

        def reference(raw: str, max_passes: int) -> str:
            if raw.isascii() and "%" not in raw:
                return raw
            current = unicodedata.normalize("NFKC", raw)
            for _ in range(max(1, max_passes)):
                decoded = unicodedata.normalize("NFKC", urllib.parse.unquote(current, errors="replace"))
                if decoded == current:
                    break
                current = decoded
            return current

        rng = random.Random(7)
        alphabet = ["%", "%", "2", "5", "e", "F", "c", "a", "ｓ", "＜", "ﬁ", "é", "́", "€", " ", "x", "�"]
        for _ in range(30000):
            text = "".join(rng.choice(alphabet) for _ in range(rng.randint(0, 25)))
            for depth in (1, 2, 3):
                self.assertEqual(decode_bounded_for_inspection(text, depth), reference(text, depth), repr(text))
