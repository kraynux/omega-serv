"""Catalogues de traduction livres (OMEGA-SERV_PLAN-DETAILLE_I18N.md §7, lots 5 a 8).

Lus tels que l'application les charge (.mo compile, module gettext de Python) et compares au
modele extrait du code (.pot) :
- chaque traduction garde exactement les memes {variables} que la phrase source - sinon
  `.format()` leverait KeyError a l'affichage, dans cette langue seulement ;
- le .mo reflete le .po (oubli de `tools/i18n_catalog.py compile` apres une correction) ;
- une langue marquee "validated" est complete (porte de validation de chaque lot de langue).
"""
from __future__ import annotations

import ast
import gettext
import re
import unittest
from pathlib import Path

from omega_serv.core.i18n import DOMAIN

LOCALE = Path(__file__).resolve().parents[2] / "src" / "omega_serv" / "locale"
_PLACEHOLDER = re.compile(r"(?<!\{)\{([^{}]*)\}(?!\})")


def _read_po(path: Path) -> dict[str, str]:
    """msgid -> msgstr (sans l'en-tete), lecture minimale du format ecrit par xgettext/msgmerge."""
    entries: dict[str, str] = {}
    current: dict[str, str] = {}
    field = ""

    def flush() -> None:
        if current.get("msgid"):
            entries[current["msgid"]] = current.get("msgstr", "")
        current.clear()

    for line in path.read_text(encoding="utf-8").splitlines():
        if line.startswith("#~"):
            continue
        if line.startswith("msgid "):
            flush()
            field = "msgid"
            current[field] = ast.literal_eval(line[6:])
        elif line.startswith("msgstr "):
            field = "msgstr"
            current[field] = ast.literal_eval(line[7:])
        elif line.startswith('"') and field:
            current[field] = current.get(field, "") + ast.literal_eval(line)
        elif not line.strip():
            field = ""
    flush()
    return entries


def _languages() -> list[Path]:
    return sorted(p for p in LOCALE.glob(f"*/LC_MESSAGES/{DOMAIN}.po"))


def _status(po: Path) -> str:
    match = re.search(r'"X-Omega-Status: ([a-z]+)\\n"', po.read_text(encoding="utf-8"))
    return match.group(1) if match else ""


class TestTranslationCatalogs(unittest.TestCase):
    def test_placeholders_identical_to_source(self):
        for po in _languages():
            with self.subTest(langue=po.parts[-3]):
                wrong = [(msgid, msgstr) for msgid, msgstr in _read_po(po).items()
                         if msgstr and sorted(_PLACEHOLDER.findall(msgid)) != sorted(_PLACEHOLDER.findall(msgstr))]
                self.assertEqual(wrong, [], "variables differentes entre source et traduction")

    def test_compiled_catalog_matches_po(self):
        for po in _languages():
            with self.subTest(langue=po.parts[-3]):
                mo = po.with_suffix(".mo")
                self.assertTrue(mo.exists(), f"{mo.name} absent : lancer tools/i18n_catalog.py compile")
                with mo.open("rb") as handle:
                    compiled = gettext.GNUTranslations(handle)
                stale = [msgid for msgid, msgstr in _read_po(po).items()
                         if msgstr and compiled.gettext(msgid) != msgstr]
                self.assertEqual(stale, [], ".mo en retard sur le .po : lancer tools/i18n_catalog.py compile")

    def test_validated_language_is_complete(self):
        template = set(_read_po(LOCALE / f"{DOMAIN}.pot"))
        for po in _languages():
            if _status(po) != "validated":
                continue
            with self.subTest(langue=po.parts[-3]):
                translated = {msgid for msgid, msgstr in _read_po(po).items() if msgstr}
                self.assertEqual(sorted(template - translated), [],
                                 "langue validee incomplete : lancer tools/i18n_catalog.py update puis traduire")


if __name__ == "__main__":
    unittest.main()
