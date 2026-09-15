# Copyright (c) 2026 kraynux - kraynux@proton.me - Licence MIT (voir fichier LICENSE)
"""Gestion du pty et du sous-processus lnav.

Porte quasi verbatim depuis omega-fire (infrastructure/lnav/pty_session.py,
plan interface §3.4 : "port direct") - mecanisme valide empiriquement lors
d'un spike, jamais re-derive ici. Encapsule tout ce qui touche au
processus externe lnav : ouverture d'un pty, lancement, redimensionnement,
arret propre, et le petit repondeur de capacites terminal sans lequel
lnav (notcurses) reste bloque indefiniment au demarrage.

Seul point du sous-systeme lnav qui appelle subprocess/pty/fcntl/termios
(voir le contrat import-linter "subprocess seulement dans
infrastructure.process.subprocess_runner ou infrastructure.lnav" -
exception scopee, deliberee : ProcessRunnerPort modelise un "lancer une
commande, recuperer le resultat", jamais un processus interactif long
avec flux ouvert, ce cas d'usage ne rentre pas dans ce port). Ne modifie
jamais lnav lui-meme : lance tel quel, aucune couleur ni logique de
rendu ici (voir infrastructure/lnav/live_renderer.py)."""
from __future__ import annotations

import fcntl
import os
import pty
import re
import signal
import struct
import subprocess
import termios
import time
from pathlib import Path

CONFIG_DIR = Path(__file__).resolve().parent
LNAV_BINARY = "lnav"

_OSC52_RE = re.compile(rb"\x1b\]52;[^\x07\x1b]*(?:\x07|\x1b\\)")


def spawn_lnav(rows: int, cols: int, log_paths: list[Path]) -> tuple[int, int]:
    """Ouvre un pty et y lance lnav sur les fichiers donnes (fusionnes
    automatiquement par lnav si plusieurs). Retourne (master_fd, pid)."""
    if not log_paths:
        raise ValueError("au moins un fichier de log est requis")

    master_fd, slave_fd = pty.openpty()

    winsize = struct.pack("HHHH", rows, cols, 0, 0)
    fcntl.ioctl(slave_fd, termios.TIOCSWINSZ, winsize)

    cmd = [LNAV_BINARY, "-I", str(CONFIG_DIR), *[str(p) for p in log_paths]]
    proc = subprocess.Popen(
        cmd,
        stdin=slave_fd,
        stdout=slave_fd,
        stderr=slave_fd,
        # start_new_session=True fait le meme setsid() que
        # preexec_fn=os.setsid chez fire, mais implemente cote C
        # (safe vis-a-vis des threads) plutot que via un callback
        # Python execute apres fork() - comportement identique,
        # juste l'idiome moderne recommande pour cette meme intention.
        start_new_session=True,
        close_fds=True,
    )
    os.close(slave_fd)
    return master_fd, proc.pid


def resize_pty(master_fd: int, pid: int, rows: int, cols: int) -> None:
    winsize = struct.pack("HHHH", rows, cols, 0, 0)
    fcntl.ioctl(master_fd, termios.TIOCSWINSZ, winsize)
    try:
        os.killpg(os.getpgid(pid), signal.SIGWINCH)
    except ProcessLookupError:
        pass


def wait_dead(pid: int, timeout: float) -> bool:
    """Attend au plus `timeout` secondes que le process se termine (non
    bloquant, jamais indefiniment). Retourne True s'il est mort."""
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        try:
            done_pid, _ = os.waitpid(pid, os.WNOHANG)
        except ChildProcessError:
            return True
        if done_pid == pid:
            return True
        time.sleep(0.1)
    return False


def kill_lnav(pid: int) -> None:
    """Arret propre avec filet de securite : SIGTERM, on attend un peu,
    SIGKILL si toujours vivant -- jamais de blocage indefini.

    Retour utilisateur ("Ctrl+C ne copie toujours rien") - vrai bug
    trouve et reproduit : tuer tout le GROUPE de processus (killpg,
    version d'origine, verbatim depuis omega-fire) tue aussi le
    processus `xclip`/`xsel` que la commande native de copie de lnav
    ('c') fait volontairement passer en arriere-plan pour continuer a
    servir le presse-papier X11 APRES la fin de lnav (comportement
    standard de ces outils - x11 exige que le proprietaire de la
    selection CLIPBOARD reste vivant pour repondre a un colle). Comme
    ce processus herite du meme groupe que lnav (`start_new_session`
    ne s'applique qu'a lnav lui-meme, jamais reapplique par xclip),
    quitter l'ecran lnav (Ctrl-Q) detruisait alors instantanement tout
    ce qui venait d'etre copie, avant meme que l'utilisateur ait pu
    coller. Ne cible plus desormais que le PID de lnav lui-meme,
    jamais son groupe entier - laisse un eventuel porteur de
    presse-papier survivre normalement, comme n'importe quel usage de
    xclip/xsel en dehors de lnav."""
    try:
        os.kill(pid, signal.SIGTERM)
    except ProcessLookupError:
        return
    if wait_dead(pid, 3.0):
        return
    try:
        os.kill(pid, signal.SIGKILL)
    except ProcessLookupError:
        return
    wait_dead(pid, 2.0)


def relay_osc52(data: bytes, out_fd: int) -> int:
    """Relaie vers le vrai terminal toute sequence OSC 52 (presse-papier)
    presente dans `data` - lnav ecrit sa reponse dans le flux qu'il pense
    etre le terminal (notre pty), jamais renvoye tel quel au vrai
    terminal sinon. Retourne le nombre de sequences relayees."""
    matches = _OSC52_RE.findall(data)
    for seq in matches:
        os.write(out_fd, seq)
    return len(matches)


class TerminalResponder:
    """Repond au minimum vital aux sondes de capacites terminal que lnav
    envoie au demarrage (notcurses). Sans ca, lnav reste bloque
    indefiniment a attendre des reponses qu'un pty muet ne renverra
    jamais -- constate empiriquement pendant le spike : DSR (position du
    curseur) et DA1 (device attributes) suffisent a debloquer le rendu ;
    les sondes de couleurs (OSC 4) et graphiques Kitty restent sans
    reponse et lnav s'en passe sans probleme.

    Repond a CHAQUE occurrence, pas seulement la premiere : lnav peut
    re-sonder (ex. apres un redimensionnement) et une reponse a usage
    unique le laisserait bloque indefiniment en cours de session."""

    def __init__(self, master_fd: int, rows: int, cols: int) -> None:
        self._fd = master_fd
        self._rows = rows
        self._cols = cols
        self._buffer = b""

    def update_size(self, rows: int, cols: int) -> None:
        self._rows, self._cols = rows, cols

    def feed(self, data: bytes) -> None:
        self._buffer += data
        while b"\x1b[6n" in self._buffer:
            os.write(self._fd, f"\x1b[{self._rows};1R".encode())
            self._buffer = self._buffer.replace(b"\x1b[6n", b"", 1)
        while b"\x1b[c" in self._buffer:
            os.write(self._fd, b"\x1b[?1;2c")
            self._buffer = self._buffer.replace(b"\x1b[c", b"", 1)
        if len(self._buffer) > 8192:
            self._buffer = self._buffer[-256:]
