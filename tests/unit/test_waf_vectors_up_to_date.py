"""Les vecteurs du filtre WAF natif (native/omega-http-core/tests/vectors/waf_filter.json) doivent correspondre aux
regles livrees : apres toute modification d'un pack ou d'une liste de reference, relancer
`.venv/bin/python tools/differential/make_waf_vectors.py native/omega-http-core/tests/vectors`."""
import importlib.util
import json
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]


class TestWafVectorsUpToDate(unittest.TestCase):
    def test_exported_rules_match_vectors(self):
        spec = importlib.util.spec_from_file_location("make_waf_vectors", REPO / "tools" / "differential" / "make_waf_vectors.py")
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        from omega_serv.domain.security.waf.config import parse_waf_config
        from omega_serv.infrastructure.server.native_snapshot import waf_filter_payload

        current = waf_filter_payload(parse_waf_config({"mode": "block"}), module.packs())
        stored = json.loads((REPO / "native" / "omega-http-core" / "tests" / "vectors" / "waf_filter.json").read_text(encoding="utf-8"))
        self.assertEqual(stored, current, "vecteurs perimes : relancer tools/differential/make_waf_vectors.py")


if __name__ == "__main__":
    unittest.main()
