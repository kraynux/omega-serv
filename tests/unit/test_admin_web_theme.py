# Copyright (c) 2026 kraynux - kraynux@proton.me - Licence MIT (voir fichier LICENSE)
"""Theme du panneau web parmi les 10 themes omega (plan tableau de bord web §9.7, decisions de l'auteur du
2026-11-17) : reglage « comme la TUI » par defaut, choix de chaque navigateur (cookie), omega-base = la charte."""
from __future__ import annotations

import asyncio
import re
import unittest
from pathlib import Path
from urllib.parse import urlencode

from omega_lib.theme.policies import TUI_THEMES

from omega_serv.application.admin_web.auth import AdminAuth
from omega_serv.application.admin_web.web_app import COOKIE_NAME, AdminRequest, AdminWebApp
from omega_serv.application.admin_web.web_theme import (
    WEB_THEMES,
    contrast,
    resolve_theme,
    theme_css,
)
from omega_serv.domain.admin_web.accounts import AdminAccount
from omega_serv.domain.admin_web.settings import AdminWebSettings, validate_admin_web
from omega_serv.domain.security.auth.password_hashing import hash_password

_CSS = Path(__file__).parents[2] / "src" / "omega_serv" / "application" / "admin_web" / "assets" / "admin.css"


def _variables(css: str) -> dict[str, str]:
    return dict(re.findall(r"(--[\w-]+): ([^;]+);", css))


class TestSheets(unittest.TestCase):
    def test_the_ten_tui_themes_and_omega_base_is_the_charter(self):
        self.assertEqual(WEB_THEMES, tuple(TUI_THEMES))
        self.assertEqual(len(WEB_THEMES), 10)
        root = _CSS.read_text().split("}", 1)[0]
        charter = {key: value.strip() for key, value in _variables(root).items() if not key.startswith("--font")}
        self.assertEqual(_variables(theme_css("omega-base")), charter)  # meme charte, memes variables
        self.assertEqual(theme_css("inconnu"), theme_css("omega-base"))

    def test_every_theme_defines_every_variable_and_stays_readable(self):
        expected = set(_variables(theme_css("omega-base")))
        for name in WEB_THEMES:
            css = theme_css(name)
            variables = _variables(css)
            self.assertEqual(set(variables) - {"--title-glow"}, expected, name)
            self.assertNotIn("ansi", css, name)  # omega-mono / omega-minimal : noms ANSI convertis
            for key in ("--cyan", "--text-1", "--text-3", "--error", "--ok", "--warn", "--line-1", "--line-2"):
                self.assertGreaterEqual(contrast(variables[key], variables["--bg-raised"]), 4.5, (name, key))
        self.assertIn("color-scheme: light", theme_css("omega-light"))
        self.assertIn("--title-glow: none", theme_css("omega-light"))  # pas de lueur sur fond clair

    def test_resolution_browser_then_setting_then_tui(self):
        self.assertEqual(resolve_theme("tui", "omega-neon"), "omega-neon")
        self.assertEqual(resolve_theme("omega-burn", "omega-neon"), "omega-burn")
        self.assertEqual(resolve_theme("omega-burn", "omega-neon", "omega-hack"), "omega-hack")
        self.assertEqual(resolve_theme("tui", None, "pas-un-theme"), "omega-base")

    def test_setting_is_validated(self):
        errors = validate_admin_web(AdminWebSettings(theme="violet"), server_bind="0.0.0.0", server_port=8080)
        self.assertTrue(any("theme" in error for error in errors))
        for value in ("tui", "omega-light"):
            self.assertEqual(validate_admin_web(AdminWebSettings(theme=value), server_bind="0.0.0.0",
                                                server_port=8080), [])
        self.assertEqual(AdminWebSettings.from_settings(AdminWebSettings(theme="omega-pink").to_settings()).theme,
                         "omega-pink")
        self.assertEqual(AdminWebSettings.from_settings({}).theme, "tui")


class TestPages(unittest.TestCase):
    def setUp(self):
        accounts = (AdminAccount("admin", hash_password("mot-de-passe-2"), "administration"),)
        auth = AdminAuth(lambda: accounts, lambda: 1_700_000_000.0, lambda line: None, local_only=True,
                         used_backup_codes=set, mark_backup_code_used=lambda code: None)
        self.tui = ["omega-neon"]
        self.app = AdminWebApp(AdminWebSettings(allowed_networks=("127.0.0.0/8",)), auth, "prod",
                               tui_theme=lambda: self.tui[0])

    def _request(self, method, target, body=b"", cookie=""):
        headers = (("Host", "127.0.0.1:9643"), ("Cookie", cookie))
        return asyncio.run(self.app.handle(AdminRequest("127.0.0.1", method, target, headers, body)))

    def test_pages_follow_the_tui_and_each_browser_may_choose(self):
        login = self._request("GET", "/connexion").body
        self.assertIn(b'href="/static/theme/omega-neon.css"', login)  # suit la TUI, page de connexion comprise
        body = urlencode({"identifiant": "admin", "mot_de_passe": "mot-de-passe-2"}).encode()
        token = dict(self._request("POST", "/connexion", body).headers)["Set-Cookie"].split(";")[0].split("=", 1)[1]
        session = f"{COOKIE_NAME}={token}"
        page = self._request("GET", "/journaux", cookie=session).body.decode()
        self.assertIn('id="theme-select"', page)
        self.assertIn('<option value="" selected>', page)  # aucun choix du navigateur
        self.tui[0] = "omega-light"  # touche t dans la TUI : la page suivante change
        self.assertIn("/static/theme/omega-light.css", self._request("GET", "/journaux", cookie=session).body.decode())
        chosen = self._request("GET", "/journaux", cookie=f"{session}; omega_admin_theme=omega-hack").body.decode()
        self.assertIn("/static/theme/omega-hack.css", chosen)
        self.assertIn('<option value="omega-hack" selected>', chosen)
        forged = self._request("GET", "/journaux", cookie=f"{session}; omega_admin_theme=../../x").body.decode()
        self.assertIn("/static/theme/omega-light.css", forged)  # valeur inconnue : ignoree
        for name in WEB_THEMES:
            sheet = self._request("GET", f"/static/theme/{name}.css")
            self.assertEqual((sheet.status, dict(sheet.headers)["Content-Type"]), (200, "text/css; charset=utf-8"))
        self.assertEqual(self._request("GET", "/static/theme.js").status, 200)
        self.assertEqual(self._request("GET", "/static/theme/inconnu.css").status, 404)


if __name__ == "__main__":
    unittest.main()
