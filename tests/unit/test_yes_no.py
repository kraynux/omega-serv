"""Champs oui/non des formulaires (plan i18n, lot 4) : affichage dans la langue de l'interface,
saisie acceptee quelle que soit la langue."""
from __future__ import annotations

import unittest

from omega_lib.i18n.models import LanguageStatus
from omega_lib.i18n.policies import PSEUDO_LANGUAGE_CODE, language_for
from omega_lib.i18n.service import PseudoTranslations

from omega_serv.core.i18n import STATE
from omega_serv.interfaces.tui.yes_no import is_no, is_yes, to_text


class TestYesNoFrench(unittest.TestCase):
    def test_display(self):
        self.assertEqual((to_text(True), to_text(False)), ("oui", "non"))

    def test_input_accepted_whatever_the_language(self):
        for value in ("oui", "OUI ", "o", "yes", "Y", "true", "vrai", "1"):
            with self.subTest(value=value):
                self.assertTrue(is_yes(value))
                self.assertFalse(is_no(value))
        for value in ("non", "n", "No", "false", "faux", "0"):
            with self.subTest(value=value):
                self.assertTrue(is_no(value))
                self.assertFalse(is_yes(value))

    def test_unknown_is_neither(self):
        self.assertFalse(is_yes("peut-etre"))
        self.assertFalse(is_no("peut-etre"))


class TestYesNoTranslated(unittest.TestCase):
    def setUp(self):
        STATE.install(language_for(PSEUDO_LANGUAGE_CODE, LanguageStatus.TESTING), PseudoTranslations())

    def tearDown(self):
        STATE.reset()

    def test_display_follows_language_and_round_trips(self):
        self.assertEqual(to_text(True), "⟦oui⟧")
        self.assertTrue(is_yes(to_text(True)))
        self.assertTrue(is_no(to_text(False)))
        self.assertTrue(is_yes("oui"), "le francais reste toujours accepte")


class _SpanishYesNo:
    def gettext(self, message: str) -> str:
        return {"oui": "sí", "non": "no"}.get(message, message)

    def ngettext(self, singular: str, plural: str, count: int) -> str:
        return singular if count == 1 else plural


class TestYesNoAccents(unittest.TestCase):
    def setUp(self):
        STATE.install(language_for("es", LanguageStatus.TESTING), _SpanishYesNo())

    def tearDown(self):
        STATE.reset()

    def test_translated_yes_accepted_with_or_without_accent(self):
        self.assertEqual(to_text(True), "sí")
        for value in ("sí", "SÍ", "si", "Si "):
            with self.subTest(value=value):
                self.assertTrue(is_yes(value))
                self.assertFalse(is_no(value))


class _HindiYesNo(_SpanishYesNo):
    def gettext(self, message: str) -> str:
        return {"oui": "हाँ", "non": "नहीं"}.get(message, message)


class TestYesNoHindi(unittest.TestCase):
    def setUp(self):
        STATE.install(language_for("hi", LanguageStatus.TESTING), _HindiYesNo())

    def tearDown(self):
        STATE.reset()

    def test_both_common_spellings_accepted(self):
        # « हाँ » (chandrabindu) et « हां » (anusvara) : les deux orthographes courantes.
        for value in ("हाँ", "हां"):
            with self.subTest(value=value):
                self.assertTrue(is_yes(value))
                self.assertFalse(is_no(value))
        self.assertTrue(is_no("नहीं"))
        self.assertFalse(is_yes("नहीं"))


if __name__ == "__main__":
    unittest.main()
