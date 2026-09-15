# Copyright (c) 2026 kraynux - kraynux@proton.me - Licence MIT (voir fichier LICENSE)
import unittest

from omega_lib.theme.policies import TUI_THEMES

from omega_serv.application.terminal.exceptions import UnknownThemeError
from omega_serv.application.terminal.select_theme import select_theme


class _FakeSettingsStore:
    def __init__(self):
        self.data = {}

    def get(self, key, default=None):
        return self.data.get(key, default)

    def set(self, key, value):
        self.data[key] = value

    def all(self):
        return dict(self.data)


class TestSelectTheme(unittest.TestCase):
    def test_persists_known_theme(self):
        store = _FakeSettingsStore()
        theme_name = next(iter(TUI_THEMES))
        select_theme(settings_store=store, theme_name=theme_name)
        self.assertEqual(store.get("theme"), theme_name)

    def test_unknown_theme_raises_and_does_not_persist(self):
        store = _FakeSettingsStore()
        with self.assertRaises(UnknownThemeError):
            select_theme(settings_store=store, theme_name="does-not-exist")
        self.assertIsNone(store.get("theme"))


if __name__ == "__main__":
    unittest.main()
