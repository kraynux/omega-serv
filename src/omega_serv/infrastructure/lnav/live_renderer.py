"""Rendu live de l'analyse lnav (plan interface §3.4/§8, port direct
depuis omega-fire interfaces/cli/renderers/lnav_live.py). Encapsule lnav
dans un pty avec un header/footer OMEGA-SERV persistants autour, et
interception de touches avant transmission - mecanisme valide
empiriquement chez fire (spike dedie), jamais re-derive ici.

Seule adaptation reelle par rapport a fire : les couleurs viennent
directement de la `Palette` omega-lib du theme Textual actif (9 jetons
generiques deja disponibles, voir omega_lib.theme.policies.Palette),
jamais d'un registre de themes CLI independant comme
`theme_registry` chez fire (qui n'existe pas cote SERV et n'aurait
aucune autre raison d'exister ici) - meme families de teintes que fire
(rouge/orange/jaune/vert/cyan/bleu/magenta/neutre), reassociees aux 9
jetons au lieu de styles nommes `text.danger`/`text.warning`/etc. Le
cycle de theme interne au clavier ('t' minuscule chez fire, propre a
son registre CLI) n'a pas d'equivalent ici et n'est pas porte - la
touche est transmise telle quelle a lnav comme n'importe quelle autre
touche non interceptee, aucune fonctionnalite reelle perdue puisque
rien ne reservait deja cette touche cote SERV.

Aucun subprocess ici (delegue a infrastructure/lnav/pty_session.py).
Rendu en ecriture ANSI directe (pas de Rich Live) : un redraw complet de
l'ecran a chaque frame s'est revele beaucoup trop couteux sur un grand
terminal (mesure chez fire : ~900ms sur 271x55) -- on ne redessine que
les lignes reellement modifiees (pyte.Screen.dirty)."""
from __future__ import annotations

import base64
import os
import re
import select
import shutil
import signal
import sys
import termios
import time
import tty
from pathlib import Path

import pyte
from omega_lib.theme.policies import Palette
from rich.style import Style

from omega_serv.infrastructure.lnav.pty_session import (
    TerminalResponder,
    kill_lnav,
    relay_osc52,
    resize_pty,
    spawn_lnav,
)

HEADER_ROWS = 1
FOOTER_ROWS = 3  # separateur + raccourcis + statut

CSI = "\x1b["
ALT_SCREEN_ON = CSI + "?1049h"
ALT_SCREEN_OFF = CSI + "?1049l"
HIDE_CURSOR = CSI + "?25l"
SHOW_CURSOR = CSI + "?25h"
CLEAR_SCREEN = CSI + "2J"

MAX_DRAIN_SECONDS = 0.02  # plafond dur : on rend la main au clavier au

_NAMED_HUES = {
    "red": "red", "green": "green", "yellow": "yellow", "blue": "blue",
    "magenta": "magenta", "cyan": "cyan", "white": "neutral", "black": "neutral",
    "default": "neutral",
}


def move_to(row: int, col: int = 1) -> str:
    return f"{CSI}{row};{col}H"


def pad_line(text: str, width: int) -> str:
    return text[:width].ljust(width)


def classify_hue(fg: str) -> str:
    """Classe une couleur pyte (nom ou hex 6 caracteres) dans une famille
    de teinte grossiere, pour la reassocier ensuite a un jeton de
    Palette."""
    if fg in _NAMED_HUES:
        return _NAMED_HUES[fg]
    if len(fg) != 6:
        return "neutral"
    try:
        r, g, b = int(fg[0:2], 16), int(fg[2:4], 16), int(fg[4:6], 16)
    except ValueError:
        return "neutral"
    mx, mn = max(r, g, b), min(r, g, b)
    if mx - mn < 24:
        return "neutral"
    if mx == r and g >= b:
        return "orange" if g > 100 else "red"
    if mx == r:
        return "magenta"
    if mx == g:
        return "yellow" if r > 140 else "green"
    return "cyan" if g > r else "blue"


def _hue_to_style(hue: str, palette: Palette) -> Style:
    mapping = {
        "red": palette.error, "orange": palette.warning, "yellow": palette.warning,
        "green": palette.success, "cyan": palette.accent, "blue": palette.accent,
        "magenta": palette.secondary, "neutral": palette.foreground,
    }
    return Style(color=mapping.get(hue, palette.foreground))


def _chrome_bar_style(palette: Palette) -> Style:
    """Style pour les barres internes de lnav (breadcrumb, statut) -
    fond explicite (panel) + texte clair (foreground) plutot qu'une
    simple video inversee brute (signale trop agressif a l'usage chez
    fire)."""
    return Style(color=palette.foreground, bgcolor=palette.panel, bold=True)


def compute_baseline_bg(screen: pyte.Screen, cols: int) -> str:
    """Devine le fond "normal" du contenu de lnav (pas nos barres a
    nous, pas les barres internes lnav, pas la ligne courante), en
    prenant le fond le plus frequent parmi les cellules non vides de
    tout l'ecran - necessaire car certains themes lnav peignent un fond
    explicite sur le texte normal au lieu de laisser le fond "default"
    du terminal (sans ca, chaque ligne de log serait classee a tort
    comme "surlignee")."""
    counts: dict[str, int] = {}
    for y in range(len(screen.display)):
        row = screen.buffer[y]
        for col in range(cols):
            ch = row.get(col)
            if ch is None or not ch.data or ch.data == " ":
                continue
            counts[ch.bg] = counts.get(ch.bg, 0) + 1
    if not counts:
        return "default"
    return max(counts, key=lambda key: counts[key])


def render_row_colored(screen: pyte.Screen, y: int, cols: int, palette: Palette, baseline_bg: str = "default") -> str:
    """Construit une ligne ANSI coloree, en regroupant les colonnes
    consecutives qui partagent le meme style (meme famille de teinte +
    etat surligne) en un seul segment stylise."""
    buffer_row = screen.buffer[y]
    default = screen.default_char
    segments: list[tuple[str, str]] = []
    current_text: list[str] = []
    current_key: str | None = None

    for col in range(cols):
        ch = buffer_row.get(col, default)
        highlighted = ch.reverse or (ch.bg != "default" and ch.bg != baseline_bg)
        key = f"{classify_hue(ch.fg)}|{highlighted}"
        if key != current_key:
            if current_text:
                segments.append(("".join(current_text), current_key or ""))
            current_text = []
            current_key = key
        current_text.append(ch.data if ch.data else " ")
    if current_text:
        segments.append(("".join(current_text), current_key or ""))

    out = []
    for text, key in segments:
        hue, highlighted_s = key.split("|")
        style = _chrome_bar_style(palette) if highlighted_s == "True" else _hue_to_style(hue, palette)
        out.append(style.render(text))
    return "".join(out)


_BREADCRUMB_ISO_TS_RE = re.compile(r"\d{4}-\d{2}-\d{2}T(\d{2}:\d{2}:\d{2})")

_KITTY_CTRL_C_RE = re.compile(rb"\x1b\[99;5u")
_KITTY_CTRL_Q_RE = re.compile(rb"\x1b\[113;5u")


def _row_is_highlighted(screen: pyte.Screen, row: int) -> bool:
    """La ligne reellement focalisee par lnav est surlignee sur (quasi)
    toute sa largeur - jamais un simple "au moins une cellule non
    'default'", qui matcherait a tort la colonne d'ascenseur que lnav
    dessine (fond distinct, ex. blanc) sur CHAQUE ligne de contenu, pas
    seulement la focalisee (bug reel trouve en reproduisant avec un vrai
    lnav : une seule cellule en bord droit suffisait a faire matcher
    n'importe quelle ligne). Seuil a la majorite des caracteres non-
    espace pour ne compter que le VRAI surlignage pleine ligne."""
    buffer_row = screen.buffer.get(row)
    if not buffer_row:
        return False
    non_space = [char for char in buffer_row.values() if char.data.strip()]
    if not non_space:
        return False
    highlighted = sum(1 for char in non_space if char.bg != "default")
    return highlighted > len(non_space) / 2


def extract_current_line_text(screen: pyte.Screen) -> str | None:
    """Retrouve le texte brut de la ligne actuellement focalisee par
    lnav, via son breadcrumb (horodatage ISO exact de la ligne
    focalisee, qui correspond a l'horodatage affiche en clair sur une
    des lignes de contenu). Jamais via la commande native 'c' de lnav
    (invoque `xclip` sans jamais fermer le tube d'entree - bloque
    indefiniment, constate chez fire) - copie geree nous-memes via
    OSC 52.

    Retour utilisateur 2026-09-13 ("Ctrl+C ne marche pas") - vrai bug
    trouve et reproduit avec un vrai lnav : plusieurs lignes partageant
    la MEME seconde (rafale de requetes, tres courant dans un log
    d'acces reel) faisaient toutes matcher le timestamp du breadcrumb,
    et la premiere candidate (pas forcement la ligne reellement
    focalisee) etait renvoyee silencieusement. Corrige en departageant
    les candidats par la couleur de fond (lnav surligne la ligne
    focalisee) - conserve le comportement existant (premier candidat)
    quand aucun n'est surligne, pour ne jamais regresser le cas a
    seule ligne deja fonctionnel."""
    lines = screen.display
    breadcrumb_idx = None
    hms = None
    for i, line in enumerate(lines):
        m = _BREADCRUMB_ISO_TS_RE.search(line)
        if m and "：" in line:
            breadcrumb_idx = i
            hms = m.group(1)
            break
    if hms is None:
        return None
    candidates = [i for i, line in enumerate(lines) if i != breadcrumb_idx and hms in line]
    if not candidates:
        return None
    chosen = next((i for i in candidates if _row_is_highlighted(screen, i)), candidates[0])
    return str(lines[chosen]).strip().strip("│").strip()


def osc52_copy(text: str) -> bytes:
    """Sequence OSC 52 : demande au terminal de placer `text` dans le
    presse-papier systeme (standard, supporte par la plupart des
    emulateurs modernes)."""
    b64 = base64.b64encode(text.encode("utf-8")).decode("ascii")
    return f"\x1b]52;c;{b64}\x07".encode()


def render_lnav_live(log_paths: list[Path], palette: Palette, title: str, menu_label: str) -> None:
    """Encapsule lnav sur `log_paths` (fusionnes automatiquement par
    lnav si plusieurs) dans le terminal courant, avec header/footer
    OMEGA-SERV persistants. Bloquant jusqu'a Ctrl-Q ou fermeture de
    lnav. Doit etre appele depuis un vrai terminal interactif (le
    handoff `App.suspend()` cote TUI garantit deja ca)."""
    out_fd = sys.stdout.fileno()
    os.write(out_fd, b"\x1b[<u")
    term_cols, term_rows = shutil.get_terminal_size()
    inner_rows = max(term_rows - HEADER_ROWS - FOOTER_ROWS, 5)

    master_fd, pid = spawn_lnav(inner_rows, term_cols, log_paths)
    screen = pyte.Screen(term_cols, inner_rows)
    stream = pyte.Stream(screen)
    stream.use_utf8 = False
    responder = TerminalResponder(master_fd, inner_rows, term_cols)

    baseline_bg = "default"
    copy_status: str | None = None

    stdin_fd = sys.stdin.fileno()
    old_term = termios.tcgetattr(stdin_fd)
    tty.setraw(stdin_fd)

    def draw_chrome(cols: int, rows: int) -> None:
        title_style = Style(color=palette.accent, bold=True)
        muted_style = Style(color=palette.foreground, dim=True)
        heading_style = Style(color=palette.foreground, bold=True)
        link_style = Style(color=palette.secondary)
        border_style = Style(color=palette.accent)

        header_plain = f"{title}  |  {menu_label}"
        header_line = (
            title_style.render(title)
            + muted_style.render("  |  ")
            + heading_style.render(menu_label)
            + muted_style.render(" " * max(cols - len(header_plain), 0))
        )

        sep_line = border_style.render("-" * cols)

        shortcuts_plain = (
            "[up/down] Naviguer  |  [left/right] Defiler  |  [g/G] Debut/Fin  |  "
            "[Ctrl-C] Marquer+Copier  |  [Ctrl-Q] Quitter"
        )
        shortcuts_line = (
            link_style.render("[up/down] Naviguer")
            + muted_style.render("  |  ")
            + link_style.render("[left/right] Defiler")
            + muted_style.render("  |  ")
            + link_style.render("[g/G] Debut/Fin")
            + muted_style.render("  |  ")
            + link_style.render("[Ctrl-C] Marquer+Copier")
            + muted_style.render("  |  ")
            + link_style.render("[Ctrl-Q] Quitter")
            + muted_style.render(" " * max(cols - len(shortcuts_plain), 0))
        )

        if copy_status is not None:
            status_line = link_style.render(pad_line(copy_status, cols))
        else:
            names = ", ".join(p.name for p in log_paths)
            status_line = muted_style.render(pad_line(f"Fichiers ({len(log_paths)}) : {names}", cols))

        buf = (
            move_to(1) + header_line
            + move_to(rows - 2) + sep_line
            + move_to(rows - 1) + shortcuts_line
            + move_to(rows) + status_line
        )
        os.write(out_fd, buf.encode())

    def full_redraw(cols: int, rows: int) -> None:
        nonlocal baseline_bg
        baseline_bg = compute_baseline_bg(screen, cols)
        buf = [CLEAR_SCREEN]
        for y in range(len(screen.display)):
            buf.append(move_to(HEADER_ROWS + 1 + y) + render_row_colored(screen, y, cols, palette, baseline_bg))
        os.write(out_fd, "".join(buf).encode())
        draw_chrome(cols, rows)
        screen.dirty.clear()

    def diff_redraw(cols: int) -> int:
        if not screen.dirty:
            return 0
        display = screen.display
        buf = []
        for y in sorted(screen.dirty):
            if 0 <= y < len(display):
                buf.append(move_to(HEADER_ROWS + 1 + y) + render_row_colored(screen, y, cols, palette, baseline_bg))
        n = len(buf)
        os.write(out_fd, "".join(buf).encode())
        screen.dirty.clear()
        return n

    def handle_resize(signum: int, frame: object) -> None:
        nonlocal term_cols, term_rows, inner_rows
        term_cols, term_rows = shutil.get_terminal_size()
        inner_rows = max(term_rows - HEADER_ROWS - FOOTER_ROWS, 5)
        screen.resize(inner_rows, term_cols)
        resize_pty(master_fd, pid, inner_rows, term_cols)
        responder.update_size(inner_rows, term_cols)
        full_redraw(term_cols, term_rows)

    signal.signal(signal.SIGWINCH, handle_resize)

    os.write(out_fd, (ALT_SCREEN_ON + HIDE_CURSOR).encode())
    settle_redraws_remaining = 5

    try:
        while True:
            r, _, _ = select.select([master_fd, stdin_fd], [], [], 0.05)

            if stdin_fd in r:
                key = os.read(stdin_fd, 4096)
                key = _KITTY_CTRL_C_RE.sub(b"\x03", key)
                key = _KITTY_CTRL_Q_RE.sub(b"\x11", key)

                if b"\x11" in key:  # Ctrl-Q : interceptee, jamais transmise a lnav
                    break

                if b"\x03" in key:
                    os.write(master_fd, b"m")
                    current_line = extract_current_line_text(screen)
                    if current_line:
                        os.write(out_fd, osc52_copy(current_line))
                        preview = current_line if len(current_line) <= 60 else current_line[:57] + "..."
                        copy_status = f"Copie (OSC 52) : {preview}"
                    else:
                        copy_status = "Rien a copier : ligne courante introuvable (breadcrumb lnav non detecte)"
                    draw_chrome(term_cols, term_rows)
                    key = key.replace(b"\x03", b"")

                if key:
                    os.write(master_fd, key)

            if master_fd in r:
                got_data = False
                drain_deadline = time.monotonic() + MAX_DRAIN_SECONDS
                while time.monotonic() < drain_deadline:
                    try:
                        data = os.read(master_fd, 65536)
                    except OSError:
                        data = b""
                    if not data:
                        break
                    got_data = True
                    responder.feed(data)
                    relay_osc52(data, out_fd)
                    stream.feed(data.decode("utf-8", errors="replace"))
                    more, _, _ = select.select([master_fd], [], [], 0.002)
                    if master_fd not in more:
                        break

                if not got_data:
                    break  # pty ferme (lnav a quitte)

                if settle_redraws_remaining > 0:
                    full_redraw(term_cols, term_rows)
                    settle_redraws_remaining -= 1
                else:
                    diff_redraw(term_cols)
    finally:
        os.write(out_fd, (SHOW_CURSOR + ALT_SCREEN_OFF).encode())
        termios.tcsetattr(stdin_fd, termios.TCSADRAIN, old_term)
        signal.signal(signal.SIGWINCH, signal.SIG_DFL)
        kill_lnav(pid)
        try:
            os.close(master_fd)
        except OSError:
            pass
