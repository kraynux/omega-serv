"""Teste les regles pures de rotation (domain/logs/rotation.py) - aucune
I/O, uniquement le calcul de plan."""
from __future__ import annotations

import unittest
from datetime import datetime, timezone
from pathlib import Path

from omega_serv.domain.logs.rotation import (
    compute_rotations_to_delete,
    generate_archive_name,
    plan_rotation,
)


class TestGenerateArchiveName(unittest.TestCase):
    def test_formats_name_with_timestamp(self):
        name = generate_archive_name(Path("access.log"), datetime(2026, 9, 8, 16, 27, 40, tzinfo=timezone.utc))
        self.assertEqual(name, "access.log.20260908-162740.tar.gz")


class TestComputeRotationsToDelete(unittest.TestCase):
    def test_below_keep_threshold_deletes_nothing(self):
        self.assertEqual(compute_rotations_to_delete(["a", "b"], keep=3), [])

    def test_at_keep_threshold_deletes_oldest_one(self):
        self.assertEqual(compute_rotations_to_delete(["a", "b", "c"], keep=3), ["a"])

    def test_above_keep_threshold_deletes_enough_to_make_room(self):
        self.assertEqual(compute_rotations_to_delete(["a", "b", "c", "d", "e"], keep=3), ["a", "b", "c"])

    def test_empty_existing_deletes_nothing(self):
        self.assertEqual(compute_rotations_to_delete([], keep=3), [])


class TestPlanRotation(unittest.TestCase):
    def test_below_threshold_should_not_rotate(self):
        plan = plan_rotation(Path("access.log"), file_size_bytes=100, max_size_bytes=1000, keep=3, existing_rotations=[])
        self.assertFalse(plan.should_rotate)
        self.assertEqual(plan.archive_name, "")

    def test_at_or_above_threshold_should_rotate(self):
        now = datetime(2026, 9, 8, 16, 27, 40, tzinfo=timezone.utc)
        plan = plan_rotation(
            Path("access.log"), file_size_bytes=1000, max_size_bytes=1000, keep=3, existing_rotations=[], now=now
        )
        self.assertTrue(plan.should_rotate)
        self.assertEqual(plan.archive_name, "access.log.20260908-162740.tar.gz")
        self.assertEqual(plan.rotations_to_delete, ())

    def test_rotation_carries_deletions_from_existing_rotations(self):
        plan = plan_rotation(
            Path("access.log"),
            file_size_bytes=2000,
            max_size_bytes=1000,
            keep=2,
            existing_rotations=["a", "b"],
        )
        self.assertTrue(plan.should_rotate)
        self.assertEqual(plan.rotations_to_delete, ("a",))


if __name__ == "__main__":
    unittest.main()
