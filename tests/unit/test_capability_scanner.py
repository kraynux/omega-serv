"""Tests cibles pour la detection de certbot (etude OMEGA-SERV_PLAN-
DETAILLE_TLS_AUTO.md, Phase 1) - reutilise `_probe_binary`, deja exerce
par les autres binaires optionnels (openssl, tailscale...), jamais une
logique nouvelle a tester isolement. Aucun test prealable n'existait pour
`SystemCapabilityScanner` (verifie avant d'ecrire ce fichier) - perimetre
volontairement limite au changement introduit ici, pas une reprise
complete de couverture du scanner entier."""
from __future__ import annotations

import unittest
from pathlib import Path
from unittest.mock import patch

from omega_serv.core.capability import CapabilityStatus
from omega_serv.infrastructure.filesystem.local_filesystem import LocalFilesystem
from omega_serv.infrastructure.probe.scanner import SystemCapabilityScanner


class TestCertbotDetection(unittest.TestCase):
    def _scanner(self, tmp_path: Path) -> SystemCapabilityScanner:
        return SystemCapabilityScanner(
            project_root=tmp_path, filesystem=LocalFilesystem(),
            configured_port=8080, fastcgi_socket=None,
        )

    def test_certbot_available_when_binary_found(self):
        with patch(
            "omega_serv.infrastructure.probe.scanner.shutil.which",
            side_effect=lambda name: "/usr/bin/certbot" if name == "certbot" else None,
        ):
            capabilities = self._scanner(Path("/tmp")).scan()
        certbot = next(c for c in capabilities if c.id == "certbot")
        self.assertEqual(certbot.status, CapabilityStatus.AVAILABLE)
        self.assertIn("/usr/bin/certbot", certbot.reason)
        self.assertEqual(certbot.category, "outil")

    def test_certbot_missing_when_binary_absent(self):
        with patch("omega_serv.infrastructure.probe.scanner.shutil.which", return_value=None):
            capabilities = self._scanner(Path("/tmp")).scan()
        certbot = next(c for c in capabilities if c.id == "certbot")
        self.assertEqual(certbot.status, CapabilityStatus.MISSING)


if __name__ == "__main__":
    unittest.main()
