# Copyright (c) 2026 kraynux - kraynux@proton.me - Licence MIT (voir fichier LICENSE)
import unittest

from omega_serv.domain.security.waf.normalization import decode_bounded_for_inspection


class TestDecodeBoundedForInspection(unittest.TestCase):
    def test_decodes_single_pass(self):
        self.assertEqual(decode_bounded_for_inspection("union%20select", 2), "union select")

    def test_decodes_double_encoding_within_budget(self):
        self.assertEqual(decode_bounded_for_inspection("union%2520select", 2), "union select")

    def test_stops_at_max_passes(self):
        # %25 -> % a chaque passe : 1 passe ne revele qu'un seul niveau
        self.assertEqual(decode_bounded_for_inspection("union%2520select", 1), "union%20select")

    def test_plain_text_unchanged(self):
        self.assertEqual(decode_bounded_for_inspection("hello world", 2), "hello world")

    def test_invalid_percent_sequence_never_raises(self):
        result = decode_bounded_for_inspection("100%off", 2)
        self.assertIsInstance(result, str)

    def test_fullwidth_unicode_characters_are_normalized_to_ascii(self):
        # Retour utilisateur (audit securite) : le vrai bug corrige ici -
        # une signature WAF cherchant "<script>" litteral (ASCII) ne
        # detectait jamais l'equivalent Unicode pleine-largeur, une
        # technique de contournement reelle et connue.
        result = decode_bounded_for_inspection("＜script＞", 2)
        self.assertEqual(result, "<script>")

    def test_fullwidth_sql_keywords_normalized(self):
        result = decode_bounded_for_inspection("ｕｎｉｏｎ select", 2)
        self.assertEqual(result, "union select")

    def test_url_encoded_fullwidth_character_normalized_after_decoding(self):
        # Le decodage URL peut lui-meme reveler des caracteres non
        # normalises - la normalisation doit s'appliquer APRES le
        # decodage, pas seulement avant.
        result = decode_bounded_for_inspection("%EF%BC%9Cscript%EF%BC%9E", 2)
        self.assertEqual(result, "<script>")

    def test_ascii_text_is_never_altered_by_normalization(self):
        self.assertEqual(decode_bounded_for_inspection("union select 1", 2), "union select 1")


if __name__ == "__main__":
    unittest.main()
