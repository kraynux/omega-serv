# Copyright (c) 2026 kraynux - kraynux@proton.me - Licence MIT (voir fichier LICENSE)
"""Teste la detection reelle sur CETTE machine (systemd, confirme via
`ls /run/systemd/system` avant d'ecrire ce test) - garde le comportement
honnete plutot que de mocker shutil.which/Path.exists en boucle pour
un module qui n'est que 3 verifications triviales de systeme reel."""
import unittest

from omega_serv.infrastructure.services.detector import detect_service_manager_type


class TestDetectServiceManagerType(unittest.TestCase):
    def test_returns_a_known_value_or_none(self):
        result = detect_service_manager_type()
        self.assertIn(result, ("systemd", "openrc", "runit", None))

    def test_detects_systemd_on_this_machine(self):
        # Cette machine de developpement tourne sous systemd (verifie
        # manuellement) - test honnete plutot qu'un mock qui masquerait
        # une vraie regression de detection.
        self.assertEqual(detect_service_manager_type(), "systemd")


if __name__ == "__main__":
    unittest.main()
