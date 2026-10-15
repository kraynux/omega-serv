import tempfile
import unittest
from pathlib import Path

from omega_serv.domain.logs.favorite import Favorite
from omega_serv.domain.logs.viewer_type import ViewerType
from omega_serv.infrastructure.logging.json_log_favorite_repository import JsonLogFavoriteRepository


class TestJsonLogFavoriteRepository(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.path = Path(self._tmp.name) / "sub" / "favorites.json"

    def tearDown(self):
        self._tmp.cleanup()

    def test_list_all_on_missing_file_is_empty(self):
        self.assertEqual(JsonLogFavoriteRepository(self.path).list_all(), [])

    def test_survives_a_fresh_instance_round_trip(self):
        favorite = Favorite(name="x", paths=("/a.log", "/b.log"), viewer=ViewerType.LNAV)
        JsonLogFavoriteRepository(self.path).add(favorite)
        reloaded = JsonLogFavoriteRepository(self.path).list_all()
        self.assertEqual(reloaded, [favorite])

    def test_add_same_name_replaces_not_duplicates(self):
        repo = JsonLogFavoriteRepository(self.path)
        repo.add(Favorite(name="x", paths=("/a.log",), viewer=ViewerType.SIMPLE))
        repo.add(Favorite(name="x", paths=("/b.log",), viewer=ViewerType.CLASSIC))
        favorites = repo.list_all()
        self.assertEqual(len(favorites), 1)
        self.assertEqual(favorites[0].paths, ("/b.log",))

    def test_remove(self):
        repo = JsonLogFavoriteRepository(self.path)
        repo.add(Favorite(name="x", paths=("/a.log",), viewer=ViewerType.SIMPLE))
        repo.remove("x")
        self.assertEqual(repo.list_all(), [])


if __name__ == "__main__":
    unittest.main()
