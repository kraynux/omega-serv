import os
import tempfile
import unittest
from pathlib import Path

from omega_serv.infrastructure.filesystem.local_filesystem import LocalFilesystem


class TestAtomicWriteText(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.root = Path(self._tmp.name)
        self.filesystem = LocalFilesystem()

    def tearDown(self):
        self._tmp.cleanup()

    def test_writes_and_reads_back_content(self):
        path = self.root / "file.json"
        self.filesystem.atomic_write_text(path, "hello")
        self.assertEqual(path.read_text(), "hello")

    @unittest.skipIf(os.geteuid() == 0, "root outrepasse les permissions Unix")
    def test_temp_file_name_is_unique_per_call_not_fixed(self):
        """Regression 2026-09-29 (incident reel : boucle de crash
        systemd, PermissionError persistante sur var/run/omega-serv.pid.tmp
        - le compte dedie ne pouvait plus jamais TRONQUER un fichier
        temporaire au nom FIXE deja cree une fois par un autre compte,
        alors que le DOSSIER etait pourtant deja partage en ecriture) :
        le fichier temporaire ne doit plus jamais s'appeler exactement
        `<nom>.tmp` - un tel fichier laisse par une tentative
        precedente (n'importe quel compte) ne doit plus pouvoir bloquer
        les tentatives suivantes."""
        path = self.root / "omega-serv.pid"
        stale_tmp = path.with_name(path.name + ".tmp")
        stale_tmp.write_text("stale content from another attempt")
        stale_tmp.chmod(0o000)  # inaccessible en ecriture a quiconque, meme le proprietaire

        self.filesystem.atomic_write_text(path, "12345")

        self.assertEqual(path.read_text(), "12345")
        stale_tmp.chmod(0o644)  # tearDown doit pouvoir nettoyer le dossier

    @unittest.skipIf(os.geteuid() == 0, "root outrepasse les permissions Unix")
    def test_atomic_write_survives_a_stale_tmp_file_owned_differently(self):
        """Variante directe du bug reel : simule le fichier temporaire
        fige qu'aurait laisse l'ancien code (nom fixe) sans permission
        d'ecriture - la nouvelle ecriture (nom unique par appel) ne doit
        jamais en depender."""
        path = self.root / "omega-serv.pid"
        legacy_fixed_tmp = path.with_name(path.name + ".tmp")
        legacy_fixed_tmp.write_text("leftover")
        legacy_fixed_tmp.chmod(0o400)

        self.filesystem.atomic_write_text(path, "67890")
        self.assertEqual(path.read_text(), "67890")
        # Le fichier fige laisse par un hypothetique ancien appelant
        # reste intact (jamais touche) - preuve que la nouvelle ecriture
        # ne s'appuie plus du tout dessus.
        self.assertEqual(legacy_fixed_tmp.read_text(), "leftover")
        legacy_fixed_tmp.chmod(0o644)

    def test_two_concurrent_style_writes_do_not_collide_on_tmp_name(self):
        path1 = self.root / "a.json"
        path2 = self.root / "b.json"
        self.filesystem.atomic_write_text(path1, "one")
        self.filesystem.atomic_write_text(path2, "two")
        self.assertEqual(path1.read_text(), "one")
        self.assertEqual(path2.read_text(), "two")
        # Aucun fichier .tmp ne doit persister apres coup.
        leftovers = [p for p in self.root.iterdir() if p.name.endswith(".tmp")]
        self.assertEqual(leftovers, [])



class TestPathInfo(unittest.TestCase):
    """path_info (OMEGA-SERV_ANALYSE_OPTIMISATION.md §3) doit dire exactement ce
    que disent is_file / is_dir / file_size / file_mtime, en un seul stat()."""

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.root = Path(self._tmp.name)
        self.filesystem = LocalFilesystem()
        (self.root / "page.html").write_text("abc")
        (self.root / "dossier").mkdir()
        (self.root / "lien.html").symlink_to(self.root / "page.html")
        (self.root / "lien-casse").symlink_to(self.root / "absent")

    def tearDown(self):
        self._tmp.cleanup()

    def test_same_answers_as_the_separate_calls(self):
        for name in ("page.html", "dossier", "lien.html", "lien-casse", "absent", "page.html/sous", "nul\0"):
            path = self.root / name
            info = self.filesystem.path_info(path)
            is_file, is_dir = self.filesystem.is_file(path), self.filesystem.is_dir(path)
            if info is None:
                self.assertFalse(is_file or is_dir, name)
                continue
            self.assertEqual((info.is_file, info.is_dir), (is_file, is_dir), name)
            self.assertEqual(info.size, self.filesystem.file_size(path), name)
            self.assertEqual(info.mtime, self.filesystem.file_mtime(path), name)

    def test_missing_or_invalid_paths_give_none(self):
        self.assertIsNone(self.filesystem.path_info(self.root / "absent"))
        self.assertIsNone(self.filesystem.path_info(self.root / "page.html" / "sous"))  # ENOTDIR
        self.assertIsNone(self.filesystem.path_info(self.root / "lien-casse"))
        self.assertIsNone(self.filesystem.path_info(self.root / "nul\0"))  # ValueError

    def test_symlink_is_followed_like_is_file(self):
        info = self.filesystem.path_info(self.root / "lien.html")
        self.assertTrue(info.is_file)
        self.assertEqual(info.size, 3)


if __name__ == "__main__":
    unittest.main()
