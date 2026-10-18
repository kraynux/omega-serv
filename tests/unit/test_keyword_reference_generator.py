"""Generateur maitre -> references livrees (OMEGA-SERV_PLAN-DETAILLE_
SENSITIVE_PATHS.md §3.11, lot 3.7)."""
import unittest
from pathlib import Path

from omega_serv.infrastructure.waf.keyword_reference_generator import generate, split_master

_ROOT = Path(__file__).resolve().parents[2]
_REFERENCES = _ROOT / "src" / "omega_serv" / "infrastructure" / "waf" / "keyword_references"
_MASTER = Path.home() / "DEV" / "JAIL" / "sensitive-path.txt"

_SYNTHETIC = """# en-tete du maitre, ignore
/jamais-une-entree

#== HOSTILE (2) == commentaire
#Secrets
/.env
#VCS
/.git/
#== SONDAGE (1) ==
#Admin
/admin
#== EXCLU (1) ==
#Decouverte
# /sitemap.xml
"""


class TestSplitMaster(unittest.TestCase):
    def test_blocks_and_sections(self):
        blocks = split_master(_SYNTHETIC)
        self.assertEqual(blocks["hostile"], [("Secrets", ["/.env"]), ("VCS", ["/.git/"])])
        self.assertEqual(blocks["sondage"], [("Admin", ["/admin"])])
        self.assertEqual(blocks["exclu"], [("Decouverte", ["/sitemap.xml"])])


class TestGenerate(unittest.TestCase):
    def test_two_references_without_excluded_entries(self):
        outputs = generate(_SYNTHETIC)
        self.assertEqual(sorted(outputs), ["sensitive-paths-hostile.txt", "sensitive-paths-probe.txt"])
        self.assertIn("\n/.env\n", outputs["sensitive-paths-hostile.txt"])
        self.assertIn("\n/admin\n", outputs["sensitive-paths-probe.txt"])
        for content in outputs.values():
            self.assertNotIn("sitemap", content)
            self.assertNotIn("jamais-une-entree", content)

    def test_invalid_master_never_produces_a_reference(self):
        broken = _SYNTHETIC.replace("/.env", "/robots.txt")
        with self.assertRaises(ValueError) as ctx:
            generate(broken)
        self.assertIn("chemin vital", str(ctx.exception))

    def test_real_master_reproduces_shipped_references(self):
        if not _MASTER.exists():
            self.skipTest(f"fichier maitre absent : {_MASTER}")
        for name, content in generate(_MASTER.read_text(encoding="utf-8")).items():
            with self.subTest(reference=name):
                self.assertEqual(content, (_REFERENCES / name).read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main()
