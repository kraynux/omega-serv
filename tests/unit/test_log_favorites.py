import tempfile
import unittest
from pathlib import Path

from omega_serv.application.logs.favorites import create_favorite, list_favorites, remove_favorite
from omega_serv.domain.logs.viewer_type import ViewerType
from omega_serv.infrastructure.logging.json_log_favorite_repository import JsonLogFavoriteRepository


class TestCreateFavorite(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.repository = JsonLogFavoriteRepository(Path(self._tmp.name) / "favorites.json")

    def tearDown(self):
        self._tmp.cleanup()

    def test_create_then_list_round_trips(self):
        result = create_favorite(self.repository, name="mes acces", paths=["/var/log/a.log"], viewer=ViewerType.SIMPLE)
        self.assertTrue(result.success)
        favorites = list_favorites(self.repository)
        self.assertEqual(len(favorites), 1)
        self.assertEqual(favorites[0].name, "mes acces")
        self.assertEqual(favorites[0].viewer, ViewerType.SIMPLE)

    def test_rejects_empty_name(self):
        result = create_favorite(self.repository, name="  ", paths=["/var/log/a.log"], viewer=ViewerType.SIMPLE)
        self.assertFalse(result.success)
        self.assertEqual(list_favorites(self.repository), [])

    def test_rejects_no_paths(self):
        result = create_favorite(self.repository, name="x", paths=[], viewer=ViewerType.SIMPLE)
        self.assertFalse(result.success)

    def test_rejects_simple_viewer_for_multiple_logs(self):
        result = create_favorite(
            self.repository, name="x", paths=["/a.log", "/b.log"], viewer=ViewerType.SIMPLE,
        )
        self.assertFalse(result.success)
        self.assertIn("lnav", result.message)

    def test_allows_lnav_for_multiple_logs(self):
        result = create_favorite(
            self.repository, name="x", paths=["/a.log", "/b.log"], viewer=ViewerType.LNAV,
        )
        self.assertTrue(result.success)

    def test_same_name_replaces_previous(self):
        create_favorite(self.repository, name="x", paths=["/a.log"], viewer=ViewerType.SIMPLE)
        create_favorite(self.repository, name="x", paths=["/b.log"], viewer=ViewerType.CLASSIC)
        favorites = list_favorites(self.repository)
        self.assertEqual(len(favorites), 1)
        self.assertEqual(favorites[0].paths, ("/b.log",))

    def test_remove_favorite(self):
        create_favorite(self.repository, name="x", paths=["/a.log"], viewer=ViewerType.SIMPLE)
        remove_favorite(self.repository, "x")
        self.assertEqual(list_favorites(self.repository), [])


if __name__ == "__main__":
    unittest.main()
