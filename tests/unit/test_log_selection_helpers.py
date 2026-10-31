import unittest

from omega_serv.interfaces.tui.widgets.log_library_table import (
    selection_or_cursor,
    toggle_selection_number,
)


class TestToggleSelectionNumber(unittest.TestCase):
    def test_adds_then_removes(self):
        self.assertEqual(toggle_selection_number("", 2), "2")
        self.assertEqual(toggle_selection_number("2", 5), "2,5")
        self.assertEqual(toggle_selection_number("2,5", 2), "5")

    def test_tolerates_spaces_and_empty_tokens(self):
        self.assertEqual(toggle_selection_number(" 1 , ,3 ", 4), "1,3,4")


class TestSelectionOrCursor(unittest.TestCase):
    def test_typed_field_wins(self):
        self.assertEqual(selection_or_cursor(" 1,3 ", 4, 5), "1,3")

    def test_empty_field_uses_highlighted_row(self):
        self.assertEqual(selection_or_cursor("", 2, 5), "3")

    def test_empty_table_or_no_cursor_gives_empty(self):
        self.assertEqual(selection_or_cursor("", 0, 0), "")
        self.assertEqual(selection_or_cursor("", None, 3), "")
        self.assertEqual(selection_or_cursor("", 7, 3), "")


if __name__ == "__main__":
    unittest.main()
