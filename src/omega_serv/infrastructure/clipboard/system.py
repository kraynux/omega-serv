"""Presse-papiers du systeme, repris d'omega-connect (retour de l'auteur du 2026-11-11 : la copie OSC 52 de Textual
seule ne copie rien dans certains terminaux).

wl-copy sous Wayland, sinon xclip, sinon xsel sous X11. Le programme est lance dans SA PROPRE session : il reste en
arriere-plan pour servir le presse-papiers apres la copie (X11 l'exige)."""
from __future__ import annotations

import os
import shutil
import subprocess
from collections.abc import Mapping

WAIT_SECONDS = 2.0


def _candidates(environ: Mapping[str, str]) -> list[list[str]]:
    found = []
    if environ.get("WAYLAND_DISPLAY"):
        found.append(["wl-copy"])
    if environ.get("DISPLAY"):
        found.append(["xclip", "-selection", "clipboard", "-in"])
        found.append(["xsel", "--clipboard", "--input"])
    return found


class SystemClipboard:
    def __init__(self, environ: Mapping[str, str] | None = None) -> None:
        self._environ = environ

    def copy(self, text: str) -> str:
        env = os.environ if self._environ is None else self._environ
        for argv in _candidates(env):
            if shutil.which(argv[0], path=env.get("PATH")) is None:
                continue
            try:
                process = subprocess.Popen(argv, stdin=subprocess.PIPE, stdout=subprocess.DEVNULL,
                                           stderr=subprocess.DEVNULL, start_new_session=True, close_fds=True,
                                           env=dict(env))
                assert process.stdin is not None
                process.stdin.write(text.encode("utf-8"))
                process.stdin.close()
            except OSError:
                continue
            try:
                code = process.wait(timeout=WAIT_SECONDS)
            except subprocess.TimeoutExpired:
                return argv[0]  # reste au premier plan pour servir le presse-papiers : la copie est faite
            if code == 0:
                return argv[0]
        return ""
