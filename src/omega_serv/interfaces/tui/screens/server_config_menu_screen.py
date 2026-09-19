"""Ecran Configuration detaillee du serveur (plan interface §7, menu 3) -
sous-menu plat (meme convention que home.py) vers un sous-ecran par
ligne du tableau §7, y compris TLS (§7.3, Phase III, ajoute le
2026-09-08).

Second cadre "OPTIONS ET VERIFICATION" (retour utilisateur 2026-09-09) :
raccourcis directs vers OptionsScreen/ConfigCheckScreen - toujours les
memes ecrans qu'au menu principal (jamais dupliques ni retires de
l'accueil), juste un second point d'entree pour le meme parcours
utilisateur (activer/ajuster des options puis verifier), sans repasser
par l'accueil entre les deux."""
from __future__ import annotations

from typing import TYPE_CHECKING

from textual.app import ComposeResult
from textual.containers import Center, Container, Grid, Horizontal, Vertical
from textual.screen import Screen
from textual.widgets import Button, Footer, Header, Static

from omega_serv.interfaces.tui.screens._base import OmegaScreen
from omega_serv.interfaces.tui.screens.access_control_screen import AccessControlScreen
from omega_serv.interfaces.tui.screens.aliases_screen import AliasesScreen
from omega_serv.interfaces.tui.screens.auth_menu_screen import AuthMenuScreen
from omega_serv.interfaces.tui.screens.base_config_screen import BaseConfigScreen
from omega_serv.interfaces.tui.screens.cache_screen import CacheScreen
from omega_serv.interfaces.tui.screens.config_check_screen import ConfigCheckScreen
from omega_serv.interfaces.tui.screens.dirlisting_screen import DirlistingScreen
from omega_serv.interfaces.tui.screens.error_pages_screen import ErrorPagesScreen
from omega_serv.interfaces.tui.screens.fastcgi_screen import FastCgiScreen
from omega_serv.interfaces.tui.screens.limits_screen import LimitsScreen
from omega_serv.interfaces.tui.screens.options_screen import OptionsScreen
from omega_serv.interfaces.tui.screens.redirects_screen import RedirectsScreen
from omega_serv.interfaces.tui.screens.reverse_proxy_screen import ReverseProxyScreen
from omega_serv.interfaces.tui.screens.rewrites_screen import RewritesScreen
from omega_serv.interfaces.tui.screens.security_screen import SecurityScreen
from omega_serv.interfaces.tui.screens.tls_menu_screen import TlsMenuScreen
from omega_serv.interfaces.tui.screens.trusted_proxy_screen import TrustedProxyScreen

if TYPE_CHECKING:
    from omega_serv.bootstrap.container import DependencyContainer

_MENU_ITEMS: tuple[tuple[str, str], ...] = (
    ("base", "Configuration de base"),
    ("limits", "Resistance et limites"),
    ("security", "Securite generique"),
    ("access-control", "Controle d'acces"),
    ("aliases", "Alias"),
    ("redirects", "Redirections"),
    ("rewrites", "Rewrites"),
    ("fastcgi", "FastCGI / PHP-FPM"),
    ("dirlisting", "Directory listing"),
    ("auth", "Authentification"),
    ("cache", "Cache"),
    ("error-pages", "Pages d'erreur"),
    ("trusted-proxy", "Proxies de confiance"),
    ("reverse-proxy", "Reverse Proxy"),
    ("tls", "TLS"),
)

_STATUS_MENU_ITEMS: tuple[tuple[str, str], ...] = (
    ("options", "Voir options actives"),
    ("config-check", "Verifier la configuration"),
)


class ServerConfigMenuScreen(OmegaScreen):
    def __init__(self, *, container: DependencyContainer) -> None:
        super().__init__()
        self._container = container

    def compose(self) -> ComposeResult:
        yield Header()
        with Vertical(classes="omega-panel"):
            with Center():
                yield Static("CONFIGURATION DETAILLEE DU SERVEUR", classes="omega-title")
            with Center(), Grid(classes="omega-home-menu omega-home-menu-2col") as menu:
                for item_id, label in _MENU_ITEMS:
                    with Container(classes="omega-btn-frame"):
                        yield Button(label, id=item_id)
                menu.border_title = "SOUS-ECRANS"
            with Center(), Grid(classes="omega-home-menu omega-home-menu-2col") as status_menu:
                for item_id, label in _STATUS_MENU_ITEMS:
                    with Container(classes="omega-btn-frame"):
                        yield Button(label, id=item_id)
                status_menu.border_title = "OPTIONS ET VERIFICATION"
            with Center(), Horizontal(classes="omega-actions"), Container(classes="omega-btn-frame"):
                yield Button("Retour", id="back")
        yield Footer()

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "back":
            self.dismiss()
            return
        screen = self._screen_for(event.button.id)
        if screen is not None:
            self.app.push_screen(screen)

    def _screen_for(self, item_id: str | None) -> Screen[None] | None:
        mapping = {
            "base": BaseConfigScreen, "limits": LimitsScreen, "security": SecurityScreen,
            "access-control": AccessControlScreen,
            "aliases": AliasesScreen, "redirects": RedirectsScreen, "rewrites": RewritesScreen,
            "fastcgi": FastCgiScreen, "dirlisting": DirlistingScreen, "cache": CacheScreen,
            "trusted-proxy": TrustedProxyScreen, "reverse-proxy": ReverseProxyScreen,
            "auth": AuthMenuScreen,
            "tls": TlsMenuScreen, "error-pages": ErrorPagesScreen,
            "options": OptionsScreen, "config-check": ConfigCheckScreen,
        }
        screen_cls = mapping.get(item_id) if item_id else None
        if screen_cls is None:
            return None
        return screen_cls(container=self._container)
