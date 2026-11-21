# Copyright (c) 2026 kraynux - kraynux@proton.me - Licence MIT (voir fichier LICENSE)
"""Nom d'unite de service sur lequel omega-serv accepte d'agir avec des droits root (scan de securite n° 2 du
2026-11-20, F10/F12/F14/F20/F22/F42).

Le nom vient souvent de `var/settings.json`, que le compte du service (celui qui recoit le reseau) peut ecrire :
un nom `../../etc/x`, `/etc/x` ou `*` faisait ecrire root hors de /etc/systemd/system, ou arreter toutes les
unites (`systemctl stop '*'`). Meme regle que la saisie de l'ecran SERVICE (rename_service.validate_service_name) :
minuscules, chiffres, `-`, `_`, `.`, debut par une lettre ou un chiffre, 64 caracteres au plus, sans `.service`."""
from __future__ import annotations

import re

SERVICE_NAME_MAX_LENGTH = 64
SERVICE_NAME_PATTERN = re.compile(r"[a-z0-9][a-z0-9._-]*")


def is_safe_service_name(name: str) -> bool:
    return (
        bool(name)
        and len(name) <= SERVICE_NAME_MAX_LENGTH
        and not name.endswith(".service")
        and SERVICE_NAME_PATTERN.fullmatch(name) is not None
    )
