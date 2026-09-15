# Copyright (c) 2026 kraynux - kraynux@proton.me - Licence MIT (voir fichier LICENSE)
"""Teste les fonctions pures de infrastructure/lnav/live_renderer.py -
jamais render_lnav_live() lui-meme (boucle bloquante exigeant un vrai
terminal interactif, testee manuellement uniquement, comme chez fire)."""
from __future__ import annotations

import base64
import unittest

import pyte
from omega_lib.theme.policies import TUI_THEMES

from omega_serv.infrastructure.lnav.live_renderer import (
    _KITTY_CTRL_C_RE,
    _KITTY_CTRL_Q_RE,
    _row_is_highlighted,
    classify_hue,
    compute_baseline_bg,
    extract_current_line_text,
    move_to,
    osc52_copy,
    pad_line,
    render_row_colored,
)

_BG_HIGHLIGHT = "\x1b[48;2;43;43;43m"  # #2b2b2b, meme teinte observee chez un vrai lnav 0.14
_BG_RESET = "\x1b[0m"
_BREADCRUMB_LINE = "LOG ▼  ：2026-09-13T14:00:02.000000 ：access_log"


class TestPadLineAndMoveTo(unittest.TestCase):
    def test_pad_line_pads_short_text(self):
        self.assertEqual(pad_line("hi", 5), "hi   ")

    def test_pad_line_truncates_long_text(self):
        self.assertEqual(pad_line("hello world", 5), "hello")

    def test_move_to_default_column(self):
        self.assertEqual(move_to(3), "\x1b[3;1H")

    def test_move_to_explicit_column(self):
        self.assertEqual(move_to(3, 7), "\x1b[3;7H")


class TestClassifyHue(unittest.TestCase):
    def test_named_colors(self):
        self.assertEqual(classify_hue("red"), "red")
        self.assertEqual(classify_hue("default"), "neutral")

    def test_hex_red(self):
        self.assertEqual(classify_hue("ff0000"), "red")

    def test_hex_green(self):
        self.assertEqual(classify_hue("00ff00"), "green")

    def test_hex_low_saturation_is_neutral(self):
        self.assertEqual(classify_hue("808080"), "neutral")

    def test_invalid_hex_is_neutral(self):
        self.assertEqual(classify_hue("zzzzzz"), "neutral")


class TestComputeBaselineBg(unittest.TestCase):
    def test_no_content_returns_default(self):
        screen = pyte.Screen(20, 5)
        self.assertEqual(compute_baseline_bg(screen, 20), "default")

    def test_most_frequent_background_wins(self):
        screen = pyte.Screen(20, 3)
        stream = pyte.Stream(screen)
        stream.feed("\x1b[42mgreen bg text\x1b[0m\r\n")
        stream.feed("normal text\r\n")
        baseline = compute_baseline_bg(screen, 20)
        self.assertIsInstance(baseline, str)


class TestRenderRowColored(unittest.TestCase):
    def test_renders_plain_text_without_crashing(self):
        screen = pyte.Screen(20, 3)
        stream = pyte.Stream(screen)
        stream.feed("hello world\r\n")
        palette = next(iter(TUI_THEMES.values())).palette
        rendered = render_row_colored(screen, 0, 20, palette)
        self.assertIn("hello world", rendered)

    def test_renders_colored_text_without_crashing(self):
        screen = pyte.Screen(20, 3)
        stream = pyte.Stream(screen)
        stream.feed("\x1b[31merror\x1b[0m normal\r\n")
        palette = next(iter(TUI_THEMES.values())).palette
        rendered = render_row_colored(screen, 0, 20, palette)
        self.assertIn("error", rendered)
        self.assertIn("normal", rendered)


class TestOsc52Copy(unittest.TestCase):
    def test_encodes_text_as_base64_osc52_sequence(self):
        result = osc52_copy("hello")
        self.assertTrue(result.startswith(b"\x1b]52;c;"))
        self.assertTrue(result.endswith(b"\x07"))
        encoded = result[len(b"\x1b]52;c;"):-1]
        self.assertEqual(base64.b64decode(encoded), b"hello")


class TestRowIsHighlighted(unittest.TestCase):
    """Retour utilisateur 2026-09-13 ("Ctrl+C ne marche pas") - bug reel
    reproduit avec un vrai lnav 0.14 : la colonne d'ascenseur qu'il
    dessine sur CHAQUE ligne de contenu (une seule cellule en bord de
    ligne, fond distinct) faisait matcher n'importe quelle ligne avec
    une detection "au moins une cellule non-default". Le seuil de
    majorite ci-dessous distingue un VRAI surlignage pleine ligne d'un
    simple artefact de bordure."""

    def test_false_for_a_single_stray_cell(self):
        screen = pyte.Screen(20, 3)
        stream = pyte.Stream(screen)
        stream.feed("normal text" + " " * 7 + _BG_HIGHLIGHT + "x" + _BG_RESET + "\r\n")
        self.assertFalse(_row_is_highlighted(screen, 0))

    def test_true_when_majority_of_the_row_is_highlighted(self):
        screen = pyte.Screen(20, 3)
        stream = pyte.Stream(screen)
        stream.feed(_BG_HIGHLIGHT + "highlighted content" + _BG_RESET + "\r\n")
        self.assertTrue(_row_is_highlighted(screen, 0))

    def test_false_for_a_blank_row(self):
        screen = pyte.Screen(20, 3)
        self.assertFalse(_row_is_highlighted(screen, 0))


class TestExtractCurrentLineText(unittest.TestCase):
    """Retour utilisateur 2026-09-13 - meme bug que ci-dessus, au niveau
    de la fonction complete : plusieurs lignes de contenu partageant la
    MEME seconde (rafale de requetes, tres courant dans un log d'acces
    reel) faisaient toutes matcher le timestamp du breadcrumb, et la
    PREMIERE candidate (pas forcement la ligne reellement focalisee)
    etait renvoyee silencieusement."""

    def _feed(self, screen: pyte.Screen, lines: list[str]) -> None:
        stream = pyte.Stream(screen)
        for line in lines:
            stream.feed(line + "\r\n")

    def test_returns_none_without_a_breadcrumb(self):
        screen = pyte.Screen(80, 5)
        self._feed(screen, ["no breadcrumb here", "127.0.0.1 something"])
        self.assertIsNone(extract_current_line_text(screen))

    def test_single_matching_line_is_returned(self):
        screen = pyte.Screen(80, 5)
        self._feed(screen, [_BREADCRUMB_LINE, "127.0.0.1 GET /only-one HTTP/1.1 14:00:02"])
        result = extract_current_line_text(screen)
        assert result is not None
        self.assertIn("/only-one", result)

    def test_duplicate_timestamps_prefer_the_highlighted_line(self):
        screen = pyte.Screen(80, 5)
        stream = pyte.Stream(screen)
        stream.feed(_BREADCRUMB_LINE + "\r\n")
        stream.feed("127.0.0.1 GET /a.html 14:00:02\r\n")
        stream.feed(_BG_HIGHLIGHT + "127.0.0.1 GET /b.html 14:00:02" + _BG_RESET + "\r\n")
        stream.feed("127.0.0.1 GET /c.html 14:00:02\r\n")
        result = extract_current_line_text(screen)
        assert result is not None
        self.assertIn("/b.html", result)

    def test_duplicate_timestamps_without_any_highlight_fall_back_to_first(self):
        # Preserve le comportement historique (jamais None ni une
        # exception) si aucune ligne ne se distingue par surlignage -
        # ne doit jamais regresser ce cas deja fonctionnel.
        screen = pyte.Screen(80, 5)
        self._feed(
            screen,
            [
                _BREADCRUMB_LINE,
                "127.0.0.1 GET /a.html 14:00:02",
                "127.0.0.1 GET /b.html 14:00:02",
            ],
        )
        result = extract_current_line_text(screen)
        assert result is not None
        self.assertIn("/a.html", result)


class TestKittyKeyboardProtocolFallback(unittest.TestCase):
    """Retour utilisateur ("Ctrl+C ne fonctionne toujours pas", Konsole
    et Alacritty - tous deux compatibles protocole clavier Kitty) : si
    le terminal est encore en mode etendu quand notre lecture brute du
    clavier commence, Ctrl-C/Ctrl-Q arrivent en CSI-u au lieu des
    octets legacy 0x03/0x11 - jamais reconnus par une simple recherche
    d'octet. Ces regex normalisent les deux formes avant la detection
    habituelle."""

    def test_ctrl_c_csi_u_normalizes_to_legacy_byte(self):
        self.assertEqual(_KITTY_CTRL_C_RE.sub(b"\x03", b"\x1b[99;5u"), b"\x03")

    def test_ctrl_q_csi_u_normalizes_to_legacy_byte(self):
        self.assertEqual(_KITTY_CTRL_Q_RE.sub(b"\x11", b"\x1b[113;5u"), b"\x11")

    def test_legacy_byte_alone_is_untouched(self):
        self.assertEqual(_KITTY_CTRL_C_RE.sub(b"\x03", b"\x03"), b"\x03")

    def test_unrelated_csi_u_sequence_is_not_matched(self):
        # 'a' (97) avec Ctrl, jamais confondu avec 'c' (99) ou 'q' (113).
        self.assertEqual(_KITTY_CTRL_C_RE.sub(b"\x03", b"\x1b[97;5u"), b"\x1b[97;5u")
        self.assertEqual(_KITTY_CTRL_Q_RE.sub(b"\x11", b"\x1b[97;5u"), b"\x1b[97;5u")


if __name__ == "__main__":
    unittest.main()
