"""Agrege toutes les fiches de content/*.py en un seul registre, cle par
le nom exact de la classe d'ecran reelle (plan guide d'aide §3.3) -
jamais un identifiant invente separement, pour qu'un ecran reel et sa
fiche ne puissent jamais diverger silencieusement (verifie par
test_guide_registry.py)."""
from __future__ import annotations

from omega_serv.interfaces.tui.guide.content.accueil import HOME_SCREEN
from omega_serv.interfaces.tui.guide.content.configuration_base import (
    ACCESS_CONTROL_SCREEN,
    BASE_CONFIG_SCREEN,
    LIMITS_SCREEN,
    SECURITY_SCREEN,
    SERVER_CONFIG_MENU_SCREEN,
)
from omega_serv.interfaces.tui.guide.content.divers import ALL_DIVERS_GUIDES
from omega_serv.interfaces.tui.guide.content.faq import FAQ_ENTRIES
from omega_serv.interfaces.tui.guide.content.logs import ALL_LOGS_GUIDES
from omega_serv.interfaces.tui.guide.content.routage import (
    ALIASES_SCREEN,
    CACHE_SCREEN,
    DIRLISTING_SCREEN,
    ERROR_PAGES_SCREEN,
    REDIRECTS_SCREEN,
    REVERSE_PROXY_SCREEN,
    REWRITES_SCREEN,
    TRUSTED_PROXY_SCREEN,
)
from omega_serv.interfaces.tui.guide.content.securite_active import ALL_ACTIVE_SECURITY_GUIDES
from omega_serv.interfaces.tui.guide.content.service_et_instances import (
    CONFIG_CHECK_SCREEN,
    INSTANCES_SCREEN,
    OPTIONS_SCREEN,
    RESOURCE_STATUS_SCREEN,
    SERVICE_SCREEN,
    SIMULATE_REQUEST_SCREEN,
)
from omega_serv.interfaces.tui.guide.content.services_avances import (
    AUTH_MENU_SCREEN,
    FASTCGI_SCREEN,
)
from omega_serv.interfaces.tui.guide.content.tls import ALL_TLS_GUIDES
from omega_serv.interfaces.tui.guide.content.wizard import ALL_WIZARD_GUIDES
from omega_serv.interfaces.tui.guide.model import FaqEntry, ScreenGuide

_ALL_GUIDES: tuple[ScreenGuide, ...] = (
    HOME_SCREEN,
    *ALL_WIZARD_GUIDES,
    SERVER_CONFIG_MENU_SCREEN,
    BASE_CONFIG_SCREEN,
    LIMITS_SCREEN,
    SECURITY_SCREEN,
    ACCESS_CONTROL_SCREEN,
    ALIASES_SCREEN,
    REDIRECTS_SCREEN,
    REWRITES_SCREEN,
    DIRLISTING_SCREEN,
    CACHE_SCREEN,
    ERROR_PAGES_SCREEN,
    TRUSTED_PROXY_SCREEN,
    REVERSE_PROXY_SCREEN,
    FASTCGI_SCREEN,
    AUTH_MENU_SCREEN,
    *ALL_TLS_GUIDES,
    *ALL_LOGS_GUIDES,
    OPTIONS_SCREEN,
    SERVICE_SCREEN,
    INSTANCES_SCREEN,
    RESOURCE_STATUS_SCREEN,
    SIMULATE_REQUEST_SCREEN,
    CONFIG_CHECK_SCREEN,
    *ALL_ACTIVE_SECURITY_GUIDES,
    *ALL_DIVERS_GUIDES,
)

SCREEN_GUIDES: dict[str, ScreenGuide] = {guide.screen_class_name: guide for guide in _ALL_GUIDES}

ALL_FAQ_ENTRIES: tuple[FaqEntry, ...] = FAQ_ENTRIES
