"""Fuzzing par proprietes du resolveur de chemin (porte de sortie
Phase 2, decision OMEGA-SERV_PLAN_DEVELOPPEMENT.md §9.4 : hypothesis
plutot qu'un fuzzer boite noire, disproportionne pour ce perimetre).

Proprietes verifiees, quelle que soit l'entree :
1. Jamais de crash (seule une PathDecision est retournee).
2. Un resultat accepte ne contient jamais de segment '.' ou '..'.
3. Un resultat accepte ne contient jamais de NUL byte ni de caractere
   de controle residuel.
"""
import unittest

from hypothesis import given, settings
from hypothesis import strategies as st

from omega_serv.domain.security.path_policy import normalize_uri_path


class TestFuzzNormalizeUriPath(unittest.TestCase):
    @given(st.text(max_size=300))
    @settings(max_examples=3000)
    def test_never_crashes(self, raw_path):
        decision = normalize_uri_path(raw_path)
        self.assertIsInstance(decision.ok, bool)

    @given(st.text(min_size=1, max_size=300))
    @settings(max_examples=3000)
    def test_accepted_segments_never_contain_dot_or_dotdot_or_empty(self, raw_path):
        decision = normalize_uri_path(raw_path)
        if decision.ok:
            for segment in decision.segments:
                self.assertNotIn(segment, (".", ".."))
                self.assertNotEqual(segment, "")

    @given(st.text(min_size=1, max_size=300))
    @settings(max_examples=3000)
    def test_accepted_result_never_contains_nul_or_control_chars(self, raw_path):
        decision = normalize_uri_path(raw_path)
        if decision.ok:
            joined = "/".join(decision.segments)
            self.assertNotIn("\x00", joined)
            self.assertTrue(all(ord(ch) >= 0x20 for ch in joined))

    @given(st.lists(st.text(alphabet="abcdefghij.._%2f", min_size=0, max_size=8), max_size=15))
    @settings(max_examples=3000)
    def test_targeted_traversal_alphabet_never_crashes(self, segments):
        raw_path = "/" + "/".join(segments)
        decision = normalize_uri_path(raw_path)
        self.assertIsInstance(decision.ok, bool)


if __name__ == "__main__":
    unittest.main()
