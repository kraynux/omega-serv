# Copyright (c) 2026 kraynux - kraynux@proton.me - Licence MIT (voir fichier LICENSE)
"""Retour utilisateur reel (2026-09-14) : un fichier de log jamais ecrit
avant, cree avec l'umask usuel d'un humain (022 -> 644), devient
inscriptible par son PROPRIETAIRE seul - le compte systeme dedie du
service (meme groupe, mais pas meme utilisateur) ne peut plus jamais y
ecrire ensuite. Vraie I/O reelle contre un fichier temporaire (aucun
mock), meme discipline que le reste du projet."""
import os
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

from omega_serv.infrastructure.logging.file_line_logger import FileLineLogger


class TestFileLineLogger(unittest.TestCase):
    def setUp(self):
        self._tmp = TemporaryDirectory()
        self.root = Path(self._tmp.name)
        self.logger = FileLineLogger()

    def tearDown(self):
        self._tmp.cleanup()

    def test_appends_a_line_to_a_new_file(self):
        path = self.root / "var" / "log" / "waf-alerts.log"
        self.logger.append_line(path, "first line")
        self.logger.append_line(path, "second line")
        self.assertEqual(path.read_text(), "first line\nsecond line\n")

    def test_creates_parent_directories(self):
        path = self.root / "var" / "log" / "deep" / "waf-alerts.log"
        self.logger.append_line(path, "line")
        self.assertTrue(path.exists())

    def test_a_newly_created_file_is_group_writable_regardless_of_umask(self):
        """Le vrai bug : un umask usuel (022) donnerait 644 (groupe en
        lecture seule) - inscriptible ici quel que soit l'umask ambiant,
        pour que le compte systeme dedie du service puisse toujours y
        ecrire ensuite (meme fichier partage CLI/TUI + service)."""
        path = self.root / "waf-alerts.log"
        old_umask = os.umask(0o022)
        try:
            self.logger.append_line(path, "line")
        finally:
            os.umask(old_umask)
        mode = path.stat().st_mode & 0o777
        self.assertEqual(mode, 0o664)
        self.assertTrue(mode & 0o020, "le fichier doit rester inscriptible par le groupe")

    def test_existing_file_permissions_are_never_touched_on_append(self):
        path = self.root / "waf-alerts.log"
        path.write_text("")
        path.chmod(0o600)
        self.logger.append_line(path, "line")
        self.assertEqual(path.stat().st_mode & 0o777, 0o600)

    def test_a_write_permission_error_never_propagates(self):
        """Meme retour utilisateur : une journalisation est un effet de
        bord, jamais une raison valable de faire planter une requete
        reelle deja en cours (meme principe que le fail-open du WAF)."""
        path = self.root / "waf-alerts.log"
        with patch("builtins.open", side_effect=PermissionError("Permission denied")):
            self.logger.append_line(path, "line")  # ne leve jamais

    def test_reuses_the_same_file_handle_across_calls(self):
        """Retour utilisateur (audit performance) : le vrai bug corrige
        ici - un open()/close() par ligne ecrite (4-5 appels systeme
        bloquants par REQUETE HTTP) etait le goulot d'etranglement n°1
        du serveur a forte charge. `open` ne doit plus etre appele
        qu'UNE SEULE FOIS par chemin, quel que soit le nombre de lignes
        ecrites ensuite."""
        path = self.root / "access.log"
        real_open = open
        calls = []

        def spy_open(*args, **kwargs):
            calls.append(args[0])
            return real_open(*args, **kwargs)

        with patch("builtins.open", side_effect=spy_open):
            for i in range(5):
                self.logger.append_line(path, f"line {i}")
        self.assertEqual(len([c for c in calls if str(c) == str(path)]), 1)
        self.assertEqual(path.read_text(), "".join(f"line {i}\n" for i in range(5)))

    def test_survives_in_place_truncation_by_rotation(self):
        """Retour utilisateur (audit performance) : la rotation
        (rotate_log.py) tronque le fichier EN PLACE (meme inode, jamais
        un unlink+recreation) - un descripteur garde ouvert en mode
        append doit continuer a ecrire correctement a partir de la
        nouvelle fin de fichier apres une telle troncature externe,
        propriete du mode append (O_APPEND), pas une simple convention."""
        path = self.root / "access.log"
        self.logger.append_line(path, "before rotation")
        self.assertEqual(path.read_text(), "before rotation\n")

        path.write_text("")  # meme operation que rotate_log_if_needed()

        self.logger.append_line(path, "after rotation")
        self.assertEqual(path.read_text(), "after rotation\n")

    def test_reopens_the_file_after_a_write_failure(self):
        """Un descripteur mis en cache qui echoue definitivement
        (fichier supprime, disque demonte...) ne doit pas rester bloque
        en erreur pour toujours - l'echec retire le handle du cache
        pour qu'un prochain appel retente une ouverture fraiche."""
        path = self.root / "access.log"
        self.logger.append_line(path, "first line")

        broken_handle = self.logger._handles[path]
        broken_handle.close()  # simule un descripteur devenu invalide

        self.logger.append_line(path, "second line")  # ne leve jamais, se retablit
        self.logger.append_line(path, "third line")
        self.assertIn("third line", path.read_text())


if __name__ == "__main__":
    unittest.main()
