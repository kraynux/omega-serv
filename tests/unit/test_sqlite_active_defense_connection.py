# Copyright (c) 2026 kraynux - kraynux@proton.me - Licence MIT (voir fichier LICENSE)
"""Retour utilisateur 2026-09-13 : "Active Defense gele le terminal,
oblige de killer" - cas reel rencontre, `var/lib/` appartenant a un
compte systeme dedie (omega-serv, via systemd) avec une session
utilisateur n'ayant pas encore rafraichi son appartenance de groupe -
`sqlite3.connect()` echoue avec `sqlite3.OperationalError`, un type que
les appelants (CLI/TUI) ne peuvent jamais attraper directement (sqlite3
confine a ce seul module par le contrat import-linter). Verifie ici
avec un VRAI repertoire aux permissions reellement restreintes (jamais
un mock de sqlite3/os), meme discipline que le reste du projet."""
from __future__ import annotations

import os
import tempfile
import unittest
from pathlib import Path

from omega_serv.infrastructure.persistence.sqlite_active_defense_connection import (
    open_active_defense_connection,
)


@unittest.skipIf(os.geteuid() == 0, "root outrepasse les permissions - test non pertinent")
class TestOpenActiveDefenseConnectionPermissionError(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.root = Path(self._tmp.name)
        self.restricted_dir = self.root / "var" / "lib"
        self.restricted_dir.mkdir(parents=True)

    def tearDown(self):
        # Restaurer les droits AVANT le nettoyage - TemporaryDirectory
        # doit pouvoir supprimer ce repertoire, jamais laisse verrouille.
        self.restricted_dir.chmod(0o755)
        self._tmp.cleanup()

    def test_permission_error_on_connect_is_translated_to_oserror(self):
        # Le repertoire existe deja (mkdir(exist_ok=True) reussit sans
        # jamais avoir besoin d'y entrer) mais sqlite3.connect() ne peut
        # pas y creer de fichier - c'est bien LA, pas au mkdir, que
        # l'erreur reelle survient.
        self.restricted_dir.chmod(0o500)
        with self.assertRaises(OSError):
            open_active_defense_connection(self.restricted_dir / "active-defense.sqlite3")


if __name__ == "__main__":
    unittest.main()
