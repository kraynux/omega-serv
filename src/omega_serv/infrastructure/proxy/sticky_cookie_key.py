# Copyright (c) 2026 kraynux - kraynux@proton.me - Licence MIT (voir fichier LICENSE)
"""Cle secrete du cookie sticky du reverse proxy (scan de securite n° 1, 2026-11-20, F41/F42).

`var/lib/proxy/sticky-cookie.key` (etat ecrit sous var/ seulement) : 32 octets aleatoires en hexadecimal, crees au
premier demarrage, puis relus - meme cle pour tous les processus de l'instance (mode boost, moteur natif) et apres
un redemarrage, pour que l'affinite de session survive. Creation atomique (lien) : deux processus qui demarrent
ensemble lisent la meme cle. Fichier illisible ou impossible a creer : None, le cookie reste un simple SHA-256
(comportement d'avant, jamais un arret du serveur)."""
from __future__ import annotations

import os
import secrets
from pathlib import Path

STICKY_COOKIE_KEY_RELATIVE_PATH = Path("var") / "lib" / "proxy" / "sticky-cookie.key"


def _read_key(path: Path) -> bytes | None:
    try:
        text = path.read_text(encoding="ascii").strip()
        key = bytes.fromhex(text)
    except (OSError, ValueError):
        return None
    return key if len(key) >= 16 else None


def load_or_create_sticky_cookie_key(project_root: Path) -> bytes | None:
    path = project_root / STICKY_COOKIE_KEY_RELATIVE_PATH
    if path.exists():
        return _read_key(path)
    key = secrets.token_bytes(32)
    temporary = path.with_name(f".{path.name}.{os.getpid()}.tmp")
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        fd = os.open(temporary, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o640)
        with os.fdopen(fd, "w", encoding="ascii") as handle:
            handle.write(key.hex() + "\n")
        # Lien atomique : la cle n'apparait que complete ; un autre processus arrive le premier -> sa cle.
        os.link(temporary, path)
    except FileExistsError:
        return _read_key(path)
    except OSError:
        return None
    finally:
        temporary.unlink(missing_ok=True)
    return key
