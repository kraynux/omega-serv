"""Blocs alignes independants de la langue (plan i18n, lot 4 - ecran Etat & Ressources)."""
from __future__ import annotations

import unittest

from rich.cells import cell_len
from rich.text import Text

from omega_serv.interfaces.tui.rendering.aligned_block import (
    SECTION_WIDTH,
    AlignedBlock,
    section_title,
)


def _lines(block: AlignedBlock) -> list[str]:
    return block.render_into(Text()).plain.splitlines()


class TestAlignedBlock(unittest.TestCase):
    def test_values_aligned_on_longest_label(self):
        lines = _lines(AlignedBlock().row("Total", "1").row("Redirections 3xx", "2"))
        self.assertEqual([line.index(" : ") for line in lines], [2 + len("Redirections 3xx")] * 2)

    def test_double_width_labels_aligned_by_screen_width(self):
        lines = _lines(AlignedBlock().row("状态", "1").row("Total", "2"))
        positions = {cell_len(line[: line.index(" : ")]) for line in lines}
        self.assertEqual(len(positions), 1, lines)

    def test_detail_line_starts_under_the_value(self):
        lines = _lines(AlignedBlock().row("RAM", "[bar]").detail("(4 Go / 8 Go)"))
        self.assertEqual(lines[1].index("("), lines[0].index("[bar]"))

    def test_detail_without_row_refused(self):
        with self.assertRaises(ValueError):
            AlignedBlock().detail("x")


class TestSectionTitle(unittest.TestCase):
    def test_fixed_width_whatever_the_word(self):
        for title in ("CLIENTS", "SANTÉ", "СОСТОЯНИЕ СИСТЕМЫ", "系统状态"):
            with self.subTest(title=title):
                self.assertEqual(cell_len(section_title(title).rstrip("\n")), SECTION_WIDTH)

    def test_very_long_title_keeps_a_frame(self):
        self.assertTrue(section_title("X" * 60).rstrip("\n").endswith("───"))


if __name__ == "__main__":
    unittest.main()
