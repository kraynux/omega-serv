# Copyright (c) 2026 kraynux - kraynux@proton.me - Licence MIT (voir fichier LICENSE)
"""Verifie SystemdServiceManager contre le vrai `systemctl` de cette
machine (elle tourne sous systemd, confirme) - operations LECTURE SEULE
uniquement (status/is-active/is-enabled/--version) contre
systemd-journald.service, present et deja actif sur toute machine
systemd reelle. Jamais start/stop/enable/disable ici : ce test ne doit
modifier aucun etat systeme partage."""
import shutil
import unittest

from omega_serv.infrastructure.process.subprocess_runner import SubprocessRunner
from omega_serv.infrastructure.services.systemd_service_manager import SystemdServiceManager

_SYSTEMCTL_MISSING = shutil.which("systemctl") is None
_SERVICE = "systemd-journald"


@unittest.skipIf(_SYSTEMCTL_MISSING, "systemctl introuvable sur ce systeme")
class TestSystemdServiceManagerReal(unittest.TestCase):
    def setUp(self):
        self.manager = SystemdServiceManager(SubprocessRunner())

    def test_is_available(self):
        self.assertTrue(self.manager.is_available())

    def test_is_active_on_a_real_running_unit(self):
        self.assertTrue(self.manager.is_active(_SERVICE))

    def test_status_reflects_real_unit(self):
        status = self.manager.status(_SERVICE)
        self.assertTrue(status.active)
        self.assertEqual(status.sub_state, "running")
        self.assertTrue(status.is_running)

    def test_manager_type(self):
        self.assertEqual(self.manager.manager_type(), "systemd")


if __name__ == "__main__":
    unittest.main()
