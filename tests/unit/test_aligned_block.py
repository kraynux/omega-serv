"""Blocs alignes independants de la langue (plan i18n, lot 4 - ecran Etat & Ressources)."""
from __future__ import annotations

import unittest

from rich.cells import cell_len
from rich.text import Text

from omega_serv.interfaces.tui.rendering.aligned_block import (
    SECTION_WIDTH,
    AlignedBlock,
    centered_section_title,
    section_title,
)
from omega_serv.interfaces.tui.screens.resource_status_screen import gauge_level, sparkline


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


class TestCenteredSectionTitle(unittest.TestCase):
    def test_fills_the_box_with_the_title_in_the_middle(self):
        for title, width in (("CLIENTS", 40), ("SÉCURITÉ", 33), ("系统状态", 50)):
            with self.subTest(title=title):
                line = centered_section_title(title, width).rstrip("\n")
                self.assertEqual(cell_len(line), width)
                left, right = line.split(f" {title} ")
                self.assertLessEqual(abs(len(left) - len(right)), 1)

    def test_too_narrow_box_keeps_three_dashes_each_side(self):
        line = centered_section_title("X" * 60, 20).rstrip("\n")
        self.assertTrue(line.startswith("───") and line.endswith("───"))

    def test_styled_value_keeps_its_own_colour(self):
        content = AlignedBlock().row("CPU", Text("[██] 50%", style="red")).render_into(Text())
        self.assertEqual(content.plain, "  CPU : [██] 50%\n")
        self.assertIn("red", [str(span.style) for span in content.spans])


class TestGaugeLevel(unittest.TestCase):
    def test_thresholds(self):
        cases = {0: "success", 49.9: "success", 50: "warning", 74.9: "warning",
                 75: "orange", 94.9: "orange", 95: "error", 100: "error"}
        for percent, level in cases.items():
            with self.subTest(percent=percent):
                self.assertEqual(gauge_level(percent), level)


class TestFreeLineAndSparkline(unittest.TestCase):
    def test_free_line_does_not_widen_the_label_column(self):
        lines = _lines(AlignedBlock().row("A", "1").line(Text("TCP ▁▂▃ tres long libelle")).row("BB", "2"))
        self.assertEqual(lines, ["  A  : 1", "  TCP ▁▂▃ tres long libelle", "  BB : 2"])

    def test_apply_lets_a_function_add_lines(self):
        lines = _lines(AlignedBlock().row("A", "1").apply(lambda b: b.line(Text("x"))))
        self.assertEqual(lines, ["  A : 1", "  x"])

    def test_sparkline_scales_on_the_peak_and_keeps_the_last_values(self):
        self.assertEqual(sparkline([0, 50, 100], 3), "▁▅█")
        self.assertEqual(sparkline([100, 0, 0, 0], 2), "▁▁")
        self.assertEqual(sparkline([0, 0], 5), "▁▁")
        self.assertEqual(sparkline([1, 2], 0), "")


if __name__ == "__main__":
    unittest.main()
