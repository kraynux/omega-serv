"""Regles du WAF retraduites pour le moteur natif (OMEGA-SERV_PLAN-DETAILLE_WAF_NATIF.md, lot 0).

Le dernier test compare les motifs traduits au VRAI PCRE2 (bibliotheque systeme par ctypes, test ignore si elle
est absente) : meme resultat que `re` sur le texte d'origine, pour toutes les regles livrees."""
import ctypes
import ctypes.util
import json
import random
import re
import unittest
from pathlib import Path

from omega_serv.domain.security.waf.entities import RuleDefinition, RulePack
from omega_serv.domain.security.waf.native_rule_export import (
    Untranslatable,
    export_rule_packs,
    translate_pattern,
)
from omega_serv.domain.security.waf.rule_validation import parse_rule_pack
from omega_serv.domain.security.waf.signature_engine import compile_rule_pack

RULES_DIR = Path(__file__).resolve().parents[2] / "secure" / "waf" / "rules"


def _shipped_packs():
    return tuple(compile_rule_pack(parse_rule_pack(json.loads(path.read_text(encoding="utf-8"))))
                 for path in sorted(RULES_DIR.glob("*.json")))


class _Pcre2:
    """Acces minimal a libpcre2-8 : compile (sans option, comme le natif) et cherche."""

    def __init__(self):
        name = ctypes.util.find_library("pcre2-8")
        if name is None:
            raise unittest.SkipTest("libpcre2-8 absente")
        lib = ctypes.CDLL(name)
        lib.pcre2_compile_8.restype = ctypes.c_void_p
        lib.pcre2_compile_8.argtypes = [ctypes.c_char_p, ctypes.c_size_t, ctypes.c_uint32, ctypes.POINTER(ctypes.c_int),
                                        ctypes.POINTER(ctypes.c_size_t), ctypes.c_void_p]
        lib.pcre2_match_data_create_8.restype = ctypes.c_void_p
        lib.pcre2_match_data_create_8.argtypes = [ctypes.c_uint32, ctypes.c_void_p]
        lib.pcre2_match_8.restype = ctypes.c_int
        lib.pcre2_match_8.argtypes = [ctypes.c_void_p, ctypes.c_char_p, ctypes.c_size_t, ctypes.c_size_t,
                                      ctypes.c_uint32, ctypes.c_void_p, ctypes.c_void_p]
        self._lib = lib
        self._data = lib.pcre2_match_data_create_8(32, None)

    def compile(self, pattern: str):
        error, offset = ctypes.c_int(), ctypes.c_size_t()
        raw = pattern.encode("ascii")
        code = self._lib.pcre2_compile_8(raw, len(raw), 0, ctypes.byref(error), ctypes.byref(offset), None)
        if not code:
            raise AssertionError(f"PCRE2 refuse {pattern!r} (erreur {error.value} a {offset.value})")
        return code

    def search(self, code, text: str) -> bool:
        raw = text.encode("ascii")
        result = self._lib.pcre2_match_8(code, raw, len(raw), 0, 0, self._data, None)
        if result < -1:
            raise AssertionError(f"erreur PCRE2 {result}")
        return result >= 0


class TestTranslatePattern(unittest.TestCase):
    def test_classes_are_explicit_python_semantics(self):
        # \s de Python accepte \x1c-\x1f (pas celui de PCRE2) ; casse insensible -> les deux lettres
        self.assertEqual(translate_pattern(r"\s", False), r"[\x{09}-\x{0d}\x{1c}-\x{20}]")
        self.assertEqual(translate_pattern("k", True), r"[\x{4b}\x{6b}]")
        self.assertEqual(translate_pattern("K", True), r"[\x{4b}\x{6b}]")  # K Kelvin : repli de Python
        self.assertEqual(translate_pattern("é", False), "(?!)")  # aucun caractere ASCII
        self.assertEqual(translate_pattern(".", False), r"[\x{00}-\x{09}\x{0b}-\x{7f}]")
        self.assertEqual(translate_pattern("(?s).", False), r"[\x{00}-\x{7f}]")

    def test_anchors_keep_python_meaning(self):
        self.assertEqual(translate_pattern(r"\Aa\Z", False), r"\A\x{61}\z")
        self.assertEqual(translate_pattern("^a$", False), "(?-m:^)\\x{61}(?-m:$)")
        self.assertEqual(translate_pattern("(?m)^a$", False), "(?m:^)\\x{61}(?m:$)")

    def test_local_flags_and_groups(self):
        self.assertEqual(translate_pattern("(?i:a)b", False), r"(?:[\x{41}\x{61}])\x{62}")
        # (?:b) inutile : deja retire par le parseur de Python ; numerotation des groupes conservee
        self.assertEqual(translate_pattern(r"(a)(?:b)(c)\2", False), r"(\x{61})\x{62}(\x{63})\g{2}")
        self.assertEqual(translate_pattern("a{2,5}?", False), r"(?:\x{61}){2,5}?")

    def test_refused_constructions(self):
        for pattern, case_insensitive in ((r"(a)\1", True), ("a{70000}", False), ("(", False)):
            with self.assertRaises(Untranslatable, msg=pattern):
                translate_pattern(pattern, case_insensitive)

    def test_rule_with_backreference_stays_with_python(self):
        pack = compile_rule_pack(RulePack(version=1, pack="p", enabled=True, rules=(
            RuleDefinition(id="OK", description="", scope=("query",), pattern="evil", weight=1),
            RuleDefinition(id="REF", description="", scope=("query", "body"), pattern=r"(A)\1", weight=1),
        )))
        exported, unexported = export_rule_packs((pack,))
        self.assertEqual([r.rule_id for r in exported], ["OK"])
        self.assertTrue(exported[0].lowered)
        self.assertEqual((unexported[0].rule_id, unexported[0].scopes), ("REF", ("query", "body")))

    def test_disabled_pack_not_exported(self):
        pack = compile_rule_pack(RulePack(version=1, pack="p", enabled=False, rules=(
            RuleDefinition(id="R", description="", scope=("query",), pattern="x", weight=1),)))
        self.assertEqual(export_rule_packs((pack,)), ((), ()))

    def test_every_shipped_rule_is_exported(self):
        packs = _shipped_packs()
        exported, unexported = export_rule_packs(packs)
        self.assertEqual(unexported, ())
        self.assertEqual(len(exported), sum(len(p.rules) for p in packs if p.enabled))


class TestAgainstRealPcre2(unittest.TestCase):
    def test_shipped_rules_same_result_as_python(self):
        pcre2 = _Pcre2()
        packs = _shipped_packs()
        exported, _unexported = export_rule_packs(packs)
        compiled = {(r.definition.id, p.pack): r for p in packs for r in p.rules}
        rng = random.Random(20261104)
        alphabet = "".join(chr(c) for c in range(32, 127)) + "\t\n\x0b\x0c\r\x1c\x1f\x00"
        samples = ["", "/wp-login.php", "/.GIT/HEAD", "id=1 UNION SELECT x", "' oR 1=1", "<ScRiPt>", "; CAT /etc/passwd",
                   "Mozilla/5.0 (X11; Linux x86_64)", "SQLMAP/1.8", "/Dockerfile", "a\nb", "x\x1cor\x1c1=1"]
        samples += ["".join(rng.choice(alphabet) for _ in range(rng.randint(0, 50))) for _ in range(300)]
        # morceaux de TOUTES les regles, en casse melangee, colles a du bruit : beaucoup de correspondances
        all_pieces = [piece for p in packs for r in p.rules for piece in re.findall(r"[a-z0-9_\-./]{3,}", r.definition.pattern)]
        all_pieces += ["/wp-login.php", "union select", "' or 1=1", "<script>", "; cat ", "/etc/passwd", "wget http://x"]
        for _ in range(1500):
            parts = []
            for _ in range(rng.randint(1, 3)):
                parts.append("".join(c.upper() if rng.random() < 0.5 else c for c in rng.choice(all_pieces)))
                parts.append("".join(rng.choice(alphabet) for _ in range(rng.randint(0, 3))))
            samples.append("".join(parts))
        matched = 0
        for native in exported:
            rule = compiled[(native.rule_id, native.pack)]
            pattern = pcre2.compile(native.pattern)
            exclude = pcre2.compile(native.exclude) if native.exclude else None
            pieces = re.findall(r"[a-z0-9_\-./]{2,}", rule.definition.pattern)
            texts = samples + ["".join(c.upper() if rng.random() < 0.5 else c for c in " ".join(pieces[i:i + 3]))
                               for i in range(len(pieces))]
            for text in texts:
                expected = bool(rule.pattern.search(text)) and not (rule.exclude is not None and rule.exclude.search(text))
                subject = text.lower() if native.lowered else text
                got = pcre2.search(pattern, subject) and not (exclude is not None and pcre2.search(exclude, subject))
                matched += expected
                self.assertEqual(expected, got, f"{native.pack} {native.rule_id} : {text!r}")
        self.assertGreater(matched, 500)


if __name__ == "__main__":
    unittest.main()
