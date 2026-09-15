# Copyright (c) 2026 kraynux - kraynux@proton.me - Licence MIT (voir fichier LICENSE)
"""Exception racine du projet - toute exception specifique a une
couche (config, WAF, TLS...) en herite, pour permettre un
`except OmegaServError` de dernier recours au point d'entree."""
from __future__ import annotations


class OmegaServError(Exception):
    """Exception racine OMEGA-SERV."""
