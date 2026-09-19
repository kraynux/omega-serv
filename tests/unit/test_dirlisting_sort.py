import unittest

from omega_serv.domain.routing.dirlisting_sort import (
    DirEntryInfo,
    DirlistingSort,
    parse_dirlisting_sort,
    sort_entry_names,
)


class TestParseDirlistingSort(unittest.TestCase):
    def test_empty_query_defaults_to_name_ascending(self):
        sort = parse_dirlisting_sort("")
        self.assertEqual(sort.key, "name")
        self.assertFalse(sort.descending)

    def test_parses_known_key_and_order(self):
        sort = parse_dirlisting_sort("sort=size&order=desc")
        self.assertEqual(sort.key, "size")
        self.assertTrue(sort.descending)

    def test_unknown_key_falls_back_to_name(self):
        sort = parse_dirlisting_sort("sort=not-a-real-column&order=desc")
        self.assertEqual(sort.key, "name")

    def test_unknown_order_falls_back_to_ascending(self):
        sort = parse_dirlisting_sort("sort=mtime&order=sideways")
        self.assertFalse(sort.descending)


class TestDirlistingSortQueryFor(unittest.TestCase):
    def test_active_ascending_column_toggles_to_descending(self):
        sort = DirlistingSort(key="name", descending=False)
        self.assertEqual(sort.query_for("name"), "sort=name&order=desc")

    def test_active_descending_column_toggles_to_ascending(self):
        sort = DirlistingSort(key="name", descending=True)
        self.assertEqual(sort.query_for("name"), "sort=name&order=asc")

    def test_inactive_column_defaults_to_ascending(self):
        sort = DirlistingSort(key="name", descending=True)
        self.assertEqual(sort.query_for("size"), "sort=size&order=asc")


class TestSortEntryNames(unittest.TestCase):
    def test_sorts_by_name_case_insensitively(self):
        names = ["banana", "Apple", "cherry"]
        result = sort_entry_names(names, {}, DirlistingSort(key="name"))
        self.assertEqual(result, ["Apple", "banana", "cherry"])

    def test_sorts_by_size_ascending(self):
        info = {"big": DirEntryInfo(size=1000), "small": DirEntryInfo(size=10)}
        result = sort_entry_names(["big", "small"], info, DirlistingSort(key="size"))
        self.assertEqual(result, ["small", "big"])

    def test_sorts_by_mtime_descending(self):
        info = {"old": DirEntryInfo(mtime=100.0), "new": DirEntryInfo(mtime=200.0)}
        result = sort_entry_names(
            ["old", "new"], info, DirlistingSort(key="mtime", descending=True)
        )
        self.assertEqual(result, ["new", "old"])

    def test_directories_without_size_sort_before_files_when_ascending(self):
        info = {"a-dir": DirEntryInfo(is_directory=True, size=None), "a-file": DirEntryInfo(size=5)}
        result = sort_entry_names(["a-file", "a-dir"], info, DirlistingSort(key="size"))
        self.assertEqual(result, ["a-dir", "a-file"])

    def test_missing_entry_info_does_not_crash(self):
        result = sort_entry_names(["mystery"], {}, DirlistingSort(key="size"))
        self.assertEqual(result, ["mystery"])


if __name__ == "__main__":
    unittest.main()
