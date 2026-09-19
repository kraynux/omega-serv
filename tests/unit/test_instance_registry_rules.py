import unittest
from datetime import datetime, timezone
from pathlib import Path

from omega_serv.domain.instances.entities import InstanceEntry
from omega_serv.domain.instances.registry import (
    find_name_conflict,
    find_nesting_conflict,
    find_port_conflict,
    is_path_nested,
    validate_new_instance,
)


def _entry(**overrides) -> InstanceEntry:
    defaults = {
        "name": "prod", "path": Path("/home/user/DEV/SERV/omega-serv"), "bind": "127.0.0.1",
        "port": 8080, "service_name": "omega-serv", "created_at": datetime(2026, 9, 11, tzinfo=timezone.utc),
    }
    defaults.update(overrides)
    return InstanceEntry(**defaults)


class TestIsPathNested(unittest.TestCase):
    def test_identical_paths_are_nested(self):
        p = Path("/a/b")
        self.assertTrue(is_path_nested(p, p))

    def test_descendant_is_nested(self):
        self.assertTrue(is_path_nested(Path("/a/b/c"), Path("/a/b")))

    def test_ancestor_is_nested(self):
        self.assertTrue(is_path_nested(Path("/a/b"), Path("/a/b/c")))

    def test_siblings_are_not_nested(self):
        self.assertFalse(is_path_nested(Path("/a/b"), Path("/a/c")))

    def test_unrelated_paths_are_not_nested(self):
        self.assertFalse(is_path_nested(Path("/x/y"), Path("/a/b")))


class TestFindNestingConflict(unittest.TestCase):
    def test_no_conflict_for_sibling_directory(self):
        entries = [_entry(path=Path("/home/user/DEV/SERV/omega-serv"))]
        self.assertIsNone(find_nesting_conflict(entries, Path("/home/user/DEV/SERV/omega-serv-test")))

    def test_conflict_when_candidate_is_descendant(self):
        entries = [_entry(path=Path("/home/user/DEV/SERV/omega-serv"))]
        conflict = find_nesting_conflict(entries, Path("/home/user/DEV/SERV/omega-serv/webroot/nested"))
        self.assertIsNotNone(conflict)
        self.assertEqual(conflict.name, "prod")

    def test_conflict_when_candidate_is_ancestor(self):
        entries = [_entry(path=Path("/home/user/DEV/SERV/omega-serv/webroot/nested"))]
        conflict = find_nesting_conflict(entries, Path("/home/user/DEV/SERV/omega-serv"))
        self.assertIsNotNone(conflict)


class TestFindPortConflict(unittest.TestCase):
    def test_same_bind_and_port_conflicts(self):
        entries = [_entry(bind="127.0.0.1", port=8080)]
        self.assertIsNotNone(find_port_conflict(entries, "127.0.0.1", 8080))

    def test_different_bind_same_port_does_not_conflict(self):
        entries = [_entry(bind="127.0.0.1", port=8080)]
        self.assertIsNone(find_port_conflict(entries, "0.0.0.0", 8080))

    def test_different_port_does_not_conflict(self):
        entries = [_entry(bind="127.0.0.1", port=8080)]
        self.assertIsNone(find_port_conflict(entries, "127.0.0.1", 8081))


class TestFindNameConflict(unittest.TestCase):
    def test_existing_name_conflicts(self):
        entries = [_entry(name="prod")]
        self.assertIsNotNone(find_name_conflict(entries, "prod"))

    def test_new_name_does_not_conflict(self):
        entries = [_entry(name="prod")]
        self.assertIsNone(find_name_conflict(entries, "test"))


class TestValidateNewInstance(unittest.TestCase):
    def test_valid_instance_returns_none(self):
        entries = [_entry(name="prod", path=Path("/a/omega-serv"), bind="127.0.0.1", port=8080)]
        error = validate_new_instance(entries, name="test", path=Path("/a/omega-serv-test"), bind="127.0.0.1", port=8081)
        self.assertIsNone(error)

    def test_empty_name_rejected(self):
        error = validate_new_instance([], name="   ", path=Path("/a/x"), bind="127.0.0.1", port=8080)
        self.assertIsNotNone(error)

    def test_duplicate_name_rejected(self):
        entries = [_entry(name="prod")]
        error = validate_new_instance(entries, name="prod", path=Path("/a/other"), bind="127.0.0.1", port=8081)
        self.assertIn("prod", error)

    def test_nested_path_rejected(self):
        entries = [_entry(name="prod", path=Path("/a/omega-serv"))]
        error = validate_new_instance(
            entries, name="test", path=Path("/a/omega-serv/webroot/x"), bind="127.0.0.1", port=8081,
        )
        self.assertIn("imbrique", error)

    def test_port_conflict_rejected(self):
        entries = [_entry(name="prod", path=Path("/a/omega-serv"), bind="127.0.0.1", port=8080)]
        error = validate_new_instance(entries, name="test", path=Path("/a/omega-serv-test"), bind="127.0.0.1", port=8080)
        self.assertIn("8080", error)

    def test_empty_registry_always_valid(self):
        error = validate_new_instance([], name="prod", path=Path("/a/omega-serv"), bind="127.0.0.1", port=8080)
        self.assertIsNone(error)


if __name__ == "__main__":
    unittest.main()
