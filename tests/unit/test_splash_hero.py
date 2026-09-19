import unittest

from omega_serv.interfaces.tui.widgets.splash_hero import _is_border_run, _light_up


class TestIsBorderRun(unittest.TestCase):
    def test_whole_line_is_border(self):
        line = "█████"
        self.assertTrue(_is_border_run(line, 0, len(line)))

    def test_run_touching_start_is_border(self):
        line = "██▒▒▒"
        self.assertTrue(_is_border_run(line, 0, 2))

    def test_run_touching_end_is_border(self):
        line = "▒▒▒██"
        self.assertTrue(_is_border_run(line, 3, 5))

    def test_single_column_adjacent_to_frame_char_is_border(self):
        line = "│█▒░▒█│"
        self.assertTrue(_is_border_run(line, 1, 2))
        self.assertTrue(_is_border_run(line, 5, 6))

    def test_single_isolated_column_is_not_border(self):
        line = "▒░░▓█░░░░░▓█░░▒"
        self.assertFalse(_is_border_run(line, 4, 5))
        self.assertFalse(_is_border_run(line, 11, 12))

    def test_wide_run_not_touching_edges_is_border(self):
        line = "▄████▒V1.00▒████▄"
        self.assertTrue(_is_border_run(line, 1, 5))
        self.assertTrue(_is_border_run(line, 12, 16))

    def test_wide_run_in_middle_of_foot_line_is_border(self):
        line = "█▓▒▒▓███████▓▒▒▓█"
        self.assertTrue(_is_border_run(line, 5, 12))


class TestLightUp(unittest.TestCase):
    def test_head_badge_has_no_accent(self):
        line = "▄████▒V1.00▒████▄"
        self.assertNotIn("$accent", _light_up(line))

    def test_foot_line_has_no_accent(self):
        line = "█▓▒▒▓███████▓▒▒▓█"
        self.assertNotIn("$accent", _light_up(line))

    def test_isolated_indicator_columns_stay_accent(self):
        line = "│█▒░░▓█░░░░░▓█░░▒█│"
        markup = _light_up(line)
        self.assertEqual(markup.count("[$accent]"), 2)


if __name__ == "__main__":
    unittest.main()
