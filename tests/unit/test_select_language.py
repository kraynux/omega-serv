"""Langue de l'interface (OMEGA-SERV_PLAN-DETAILLE_I18N.md lot 2) : priorite au demarrage,
replis vers le francais, enregistrement, regle D18b du processus serveur, environnement du
redemarrage de l'interface."""
from __future__ import annotations

import struct
import tempfile
import unittest
from pathlib import Path

from omega_lib.i18n.models import LanguageStatus
from omega_lib.i18n.policies import PSEUDO_LANGUAGE_CODE

from omega_serv.__main__ import _prepare_language_restart_environment
from omega_serv.application.terminal.exceptions import UnknownLanguageError
from omega_serv.application.terminal.select_language import (
    LANGUAGE_CHANGED_ENV_VAR,
    LANGUAGE_ENV_VAR,
    LANGUAGE_KEY,
    PAGE_LANGUAGE_KEY,
    available_languages,
    console_fallback_from,
    devanagari_misaligned_in,
    install_interface_language,
    install_page_language,
    page_language_code,
    select_language,
    select_page_language,
)
from omega_serv.core.i18n import DOMAIN, STATE, _, ngettext
from omega_serv.infrastructure.i18n.gettext_language_catalog import GettextLanguageCatalog
from omega_serv.interfaces.cli.main import is_server_process


def write_mo(path: Path, messages: dict[str, str], status: str | None = None) -> None:
    """Catalogue GNU .mo minimal (format documente de gettext), sans msgfmt."""
    header = "Content-Type: text/plain; charset=UTF-8\nPlural-Forms: nplurals=2; plural=(n != 1);\n"
    if status:
        header += f"X-Omega-Status: {status}\n"
    entries = sorted({"": header, **messages}.items())
    ids = b"".join(k.encode() + b"\0" for k, _v in entries)
    strs = b"".join(v.encode() + b"\0" for _k, v in entries)
    key_start = 28 + 16 * len(entries)
    offsets: list[int] = []
    pos = 0
    for key, _v in entries:
        offsets += [len(key.encode()), key_start + pos]
        pos += len(key.encode()) + 1
    pos = 0
    for _k, value in entries:
        offsets += [len(value.encode()), key_start + len(ids) + pos]
        pos += len(value.encode()) + 1
    table = struct.pack("Iiiiiii", 0x950412DE, 0, len(entries), 28, 28 + 8 * len(entries), 0, 0)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(table + struct.pack(f"{len(offsets)}i", *offsets) + ids + strs)


class _MemorySettings:
    def __init__(self, values: dict[str, str] | None = None) -> None:
        self.values = dict(values or {})

    def get(self, key: str, default: str | None = None) -> str | None:
        return self.values.get(key, default)

    def set(self, key: str, value: str) -> None:
        self.values[key] = value

    def all(self) -> dict[str, str]:
        return dict(self.values)


class _LanguageCase(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.locale = Path(self._tmp.name)
        write_mo(self.locale / "en" / "LC_MESSAGES" / f"{DOMAIN}.mo",
                 {"Retour": "Back", "{n} entree\0{n} entrees": "{n} entry\0{n} entries"}, status="validated")
        self.catalog = GettextLanguageCatalog(self.locale)

    def tearDown(self) -> None:
        STATE.reset()
        self._tmp.cleanup()

    def install(self, settings: dict[str, str] | None = None, environ: dict[str, str] | None = None):
        return install_interface_language(settings_store=_MemorySettings(settings), catalog=self.catalog,
                                          environ=environ or {})


class TestStartupLanguage(_LanguageCase):
    def test_default_is_french_identity(self):
        choice = self.install()
        self.assertEqual((choice.language.code, choice.fell_back_from), ("fr", None))
        self.assertEqual(_("Retour"), "Retour")

    def test_setting_selects_catalog(self):
        choice = self.install({LANGUAGE_KEY: "en"})
        self.assertEqual(choice.language.status, LanguageStatus.VALIDATED)
        self.assertEqual(_("Retour"), "Back")
        self.assertEqual(_("Phrase pas encore traduite"), "Phrase pas encore traduite")
        self.assertEqual(ngettext("{n} entree", "{n} entrees", 3), "{n} entries")

    def test_env_override_wins_over_setting(self):
        self.install({LANGUAGE_KEY: "en"}, {LANGUAGE_ENV_VAR: "fr"})
        self.assertEqual((STATE.language.code, _("Retour")), ("fr", "Retour"))

    def test_unknown_language_falls_back_to_french_and_is_reported(self):
        choice = self.install({LANGUAGE_KEY: "ru"})
        self.assertEqual((choice.language.code, choice.fell_back_from), ("fr", "ru"))
        self.assertEqual(STATE.fell_back_from, "ru")

    def test_corrupt_catalog_falls_back_to_french(self):
        broken = self.locale / "es" / "LC_MESSAGES" / f"{DOMAIN}.mo"
        broken.parent.mkdir(parents=True)
        broken.write_bytes(b"pas un catalogue")
        choice = self.install({LANGUAGE_KEY: "es"})
        self.assertEqual((choice.language.code, choice.fell_back_from), ("fr", "es"))
        self.assertEqual(_("Retour"), "Retour")

    def test_pseudo_language_wraps_phrases(self):
        # Absente du selecteur depuis la 2.0.0, encore accessible par OMEGA_SERV_LANG / reglage.
        self.install({LANGUAGE_KEY: PSEUDO_LANGUAGE_CODE})
        self.assertEqual(_("Retour"), "⟦Retour⟧")


    def test_missing_locale_dir_still_offers_french(self):
        catalog = GettextLanguageCatalog(self.locale / "absent")
        self.assertEqual(available_languages(catalog)[0].code, "fr")
        choice = install_interface_language(settings_store=_MemorySettings({LANGUAGE_KEY: "en"}),
                                            catalog=catalog, environ={})
        self.assertEqual((choice.language.code, choice.fell_back_from), ("fr", "en"))


class TestConsoleFallback(_LanguageCase):
    """TTY Linux : chinois/hindi/arabe/vietnamien illisibles -> anglais pour la session, reglage intact."""

    def setUp(self) -> None:
        super().setUp()
        write_mo(self.locale / "hi" / "LC_MESSAGES" / f"{DOMAIN}.mo", {"Retour": "वापस"}, status="validated")
        write_mo(self.locale / "vi" / "LC_MESSAGES" / f"{DOMAIN}.mo", {"Retour": "Quay lại"}, status="validated")
        self.catalog = GettextLanguageCatalog(self.locale)

    def install_on(self, family: str, settings: _MemorySettings):
        return install_interface_language(settings_store=settings, catalog=self.catalog, environ={},
                                          terminal_family=family)

    def test_hindi_on_linux_console_switches_to_english_for_the_session(self):
        settings = _MemorySettings({LANGUAGE_KEY: "hi"})
        choice = self.install_on("linux-tty", settings)
        self.assertEqual((choice.language.code, _("Retour")), ("en", "Back"))
        self.assertEqual(console_fallback_from(), "hi")
        self.assertEqual(settings.get(LANGUAGE_KEY), "hi")

    def test_hindi_in_graphical_terminal_is_kept(self):
        choice = self.install_on("terminator", _MemorySettings({LANGUAGE_KEY: "hi"}))
        self.assertEqual((choice.language.code, _("Retour")), ("hi", "वापस"))
        self.assertIsNone(console_fallback_from())

    def test_vietnamese_on_linux_console_switches_to_english_for_the_session(self):
        # Police viscii10-8x16 : lettres vietnamiennes mais aucun cadre (decision 2026-10-23).
        settings = _MemorySettings({LANGUAGE_KEY: "vi"})
        choice = self.install_on("linux-tty", settings)
        self.assertEqual((choice.language.code, console_fallback_from()), ("en", "vi"))
        self.assertEqual(settings.get(LANGUAGE_KEY), "vi")

    def test_vietnamese_in_graphical_terminal_is_kept(self):
        choice = self.install_on("konsole", _MemorySettings({LANGUAGE_KEY: "vi"}))
        self.assertEqual((choice.language.code, _("Retour")), ("vi", "Quay lại"))
        self.assertIsNone(console_fallback_from())

    def test_page_language_install_never_switches(self):
        # Pages visiteurs (D19) : affichees par un navigateur, jamais de repli console.
        state = type(STATE)()
        choice = install_page_language(settings_store=_MemorySettings({PAGE_LANGUAGE_KEY: "hi"}),
                                       catalog=self.catalog, state=state)
        self.assertEqual(choice.language.code, "hi")


class TestVisitorPagesLanguageSetting(_LanguageCase):
    """D19 revue (decision utilisateur 2026-10-23) : pages visiteurs et interface separees."""

    def setUp(self) -> None:
        super().setUp()
        write_mo(self.locale / "en" / "LC_MESSAGES" / f"{DOMAIN}.mo", {"Retour": "Back"}, status="validated")
        self.catalog = GettextLanguageCatalog(self.locale)
        self.state = type(STATE)()

    def test_pages_stay_french_whatever_the_interface_language(self):
        settings = _MemorySettings({LANGUAGE_KEY: "en"})
        choice = install_page_language(settings_store=settings, catalog=self.catalog, state=self.state)
        self.assertEqual((choice.language.code, self.state.gettext("Retour")), ("fr", "Retour"))

    def test_pages_follow_their_own_setting_only(self):
        settings = _MemorySettings({PAGE_LANGUAGE_KEY: "en"})
        choice = install_page_language(settings_store=settings, catalog=self.catalog, state=self.state)
        self.assertEqual((choice.language.code, self.state.gettext("Retour")), ("en", "Back"))
        self.assertEqual(STATE.language.code, "fr", "l'interface n'est pas touchee")

    def test_select_page_language_persists_and_french_clears_the_key(self):
        settings = _MemorySettings({LANGUAGE_KEY: "en"})
        select_page_language(settings_store=settings, catalog=self.catalog, language_code="en")
        self.assertEqual((settings.get(PAGE_LANGUAGE_KEY), page_language_code(settings)), ("en", "en"))
        select_page_language(settings_store=settings, catalog=self.catalog, language_code="fr")
        self.assertEqual((settings.get(PAGE_LANGUAGE_KEY), page_language_code(settings)), ("", "fr"))
        self.assertEqual(settings.get(LANGUAGE_KEY), "en", "la langue de l'interface n'est pas touchee")

    def test_unknown_page_language_is_refused(self):
        with self.assertRaises(UnknownLanguageError):
            select_page_language(settings_store=_MemorySettings(), catalog=self.catalog, language_code="ru")


class TestSelectLanguage(_LanguageCase):
    def test_french_first_then_available_pseudo_hidden(self):
        self.assertEqual([lang.code for lang in available_languages(self.catalog)], ["fr", "en"])

    def test_select_persists_and_french_clears_the_key(self):
        settings = _MemorySettings()
        select_language(settings_store=settings, catalog=self.catalog, language_code="en")
        self.assertEqual(settings.values[LANGUAGE_KEY], "en")
        select_language(settings_store=settings, catalog=self.catalog, language_code="fr")
        self.assertEqual(settings.values[LANGUAGE_KEY], "")

    def test_select_unknown_language_refused_and_not_saved(self):
        settings = _MemorySettings({LANGUAGE_KEY: "en"})
        with self.assertRaises(UnknownLanguageError):
            select_language(settings_store=settings, catalog=self.catalog, language_code="ru")
        self.assertEqual(settings.values[LANGUAGE_KEY], "en")


class TestServerProcessNeverTranslated(unittest.TestCase):
    """D18b : `serve` n'installe jamais la langue, toute autre commande la suit."""

    def test_detection(self):
        for argv, expected in ((["serve"], True), (["--config", "x.json", "serve"], True),
                               (["--config=x.json", "serve"], True), (["config", "check"], False),
                               (["--config", "serve"], False), ([], False), (["-h"], False),
                               (["service", "install"], False)):
            with self.subTest(argv=argv):
                self.assertEqual(is_server_process(argv), expected)


class TestEarlyInstallStaysLight(unittest.TestCase):
    """La langue est installee avant tout autre import (lot 4) : ce point d'entree ne doit
    JAMAIS charger un ecran, la CLI ou le conteneur, sinon leurs phrases definies au
    chargement resteraient en francais."""

    def test_no_interface_module_imported(self):
        import subprocess
        import sys

        code = ("import sys, omega_serv.bootstrap.early_language; "
                "print(sorted(m for m in sys.modules if m.startswith(('omega_serv.interfaces', "
                "'omega_serv.bootstrap.container', 'omega_serv.domain'))))")
        out = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True, check=True).stdout
        self.assertEqual(out.strip(), "[]")


class TestRestartEnvironment(unittest.TestCase):
    def test_restart_requests_splash_and_drops_one_shot_override(self):
        environ = {LANGUAGE_ENV_VAR: "fr", "PATH": "/usr/bin"}
        _prepare_language_restart_environment(environ, "en")
        self.assertEqual(environ, {LANGUAGE_CHANGED_ENV_VAR: "en", "PATH": "/usr/bin"})



class TestDevanagariShapingTerminals(unittest.TestCase):
    """Mesure reelle 2026-10-26 : Kitty et Konsole (et Ghostty) composent les lettres liees
    devanagari sur une largeur variable - avertissement, interface conservee en hindi."""

    def test_hindi_in_shaping_terminals_is_flagged(self):
        for family in ("kitty", "ghostty", "konsole"):
            self.assertTrue(devanagari_misaligned_in("hi", family), family)

    def test_vte_terminals_and_other_languages_are_never_flagged(self):
        for family in ("terminator", "gnome-terminal", "xfce4-terminal", "alacritty"):
            self.assertFalse(devanagari_misaligned_in("hi", family), family)
        for code in ("fr", "en", "ar", "th", "zh_CN"):
            self.assertFalse(devanagari_misaligned_in(code, "kitty"), code)


if __name__ == "__main__":
    unittest.main()
