# Copyright (c) 2026 kraynux - kraynux@proton.me - Licence MIT (voir fichier LICENSE)
"""Processus d'administration web : ce que le conteneur de la CLI ne fournit pas lui-meme (correctifs du 2026-11-18,
trouves en preparant les captures du tableau de bord).

- Vue Securite : la base Active Defense etait ouverte une fois puis lue depuis un autre fil (asyncio.to_thread),
  SQLite refusait (« SQLite objects created in a thread can only be used in that same thread »).
- Vue Certificats et alertes d'echeance : sans outil openssl, toujours « echeance inconnue (openssl absent) »."""
from __future__ import annotations

import shutil
import subprocess
import tempfile
import threading
import unittest
from pathlib import Path
from unittest import mock

import omega_serv.interfaces.cli.admin_web_commands as admin_web_commands
from omega_serv.application.config.generate_config import generate_default_config
from omega_serv.bootstrap.container import DependencyContainer

_REAL_PROJECT_ROOT = Path(__file__).resolve().parents[2]


class TestAdminWebProcessSources(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.root = Path(self._tmp.name)
        (self.root / "webroot").mkdir()
        (self.root / "config" / "profiles").mkdir(parents=True)
        for profile_file in (_REAL_PROJECT_ROOT / "config" / "profiles").glob("*.json"):
            shutil.copy(profile_file, self.root / "config" / "profiles" / profile_file.name)
        self.container = DependencyContainer(project_root=self.root)
        generate_default_config(self.container.configuration, self.container.filesystem, self.container.config_file)

    def tearDown(self):
        self._tmp.cleanup()

    def test_active_defense_is_opened_once_per_thread(self):
        status = admin_web_commands._StatusSources(self.container)
        with mock.patch.object(admin_web_commands, "build_active_defense_collaborators",
                               side_effect=lambda config, root: object()):
            first = status.active_defense(None)
            again = status.active_defense(None)
            other: list[object] = []
            worker = threading.Thread(target=lambda: other.append(status.active_defense(None)))
            worker.start()
            worker.join()
        self.assertIs(first, again)  # meme fil : jamais une connexion par releve
        self.assertIsNot(first, other[0])  # autre fil : sa propre connexion

    @unittest.skipUnless(shutil.which("openssl"), "openssl absent")
    def test_certificates_are_read_without_a_tool_in_the_container(self):
        directory = self.root / "secure" / "certificates" / "docs"
        directory.mkdir(parents=True)
        subprocess.run(["openssl", "req", "-x509", "-newkey", "rsa:2048", "-nodes", "-days", "40",
                        "-subj", "/CN=docs.exemple.org", "-keyout", str(directory / "docs.key"),
                        "-out", str(directory / "docs.pem")], check=True, capture_output=True)
        self.assertIsNone(self.container.certificate_tool_factory)
        process = admin_web_commands._AdminWebProcess(self.container, self.container.config_file)
        lines = [line for line in process._check_certificates() if line.path.endswith("docs.pem")]
        self.assertEqual(len(lines), 1)
        self.assertNotEqual(lines[0].state, "no_tool")
        self.assertIn(lines[0].days, (39, 40))


if __name__ == "__main__":
    unittest.main()
