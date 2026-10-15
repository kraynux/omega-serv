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


class TestMagnetDependencyDetection(unittest.TestCase):
    """Remplace l'ancienne sonde binaire `lua`/`lua5.4` (sans rapport
    avec le besoin reel - `lupa` embarque son propre runtime Lua, ne
    requiert aucun interpreteur systeme) par une sonde du paquet Python
    'lupa' lui-meme."""

    def _scanner(self, tmp_path: Path) -> SystemCapabilityScanner:
        return SystemCapabilityScanner(
            project_root=tmp_path, filesystem=LocalFilesystem(),
            configured_port=8080, fastcgi_socket=None,
        )

    def test_magnet_available_when_lupa_installed(self):
        """Environnement reel de developpement de ce projet - 'lupa'
        y est effectivement installe (extra 'magnet', voir pyproject.toml)."""
        capabilities = self._scanner(Path("/tmp")).scan()
        magnet = next(c for c in capabilities if c.id == "waf-magnet")
        self.assertEqual(magnet.status, CapabilityStatus.AVAILABLE)
        self.assertIn("lupa", magnet.reason)
        self.assertEqual(magnet.category, "waf")

    def test_magnet_missing_when_lupa_absent(self):
        with patch(
            "omega_serv.infrastructure.probe.scanner.importlib.util.find_spec", return_value=None,
        ):
            capabilities = self._scanner(Path("/tmp")).scan()
        magnet = next(c for c in capabilities if c.id == "waf-magnet")
        self.assertEqual(magnet.status, CapabilityStatus.MISSING)
        self.assertIn("pip install -e \".[magnet]\"", magnet.reason)


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


class TestScpDetection(unittest.TestCase):
    """OMEGA-SERV_ETUDE-FAISABILITE_LOGS_DISTANTS.md, 2026-10-15 - meme
    sonde generique que certbot, aucune logique nouvelle a tester."""

    def _scanner(self, tmp_path: Path) -> SystemCapabilityScanner:
        return SystemCapabilityScanner(
            project_root=tmp_path, filesystem=LocalFilesystem(),
            configured_port=8080, fastcgi_socket=None,
        )

    def test_scp_available_when_binary_found(self):
        with patch(
            "omega_serv.infrastructure.probe.scanner.shutil.which",
            side_effect=lambda name: "/usr/bin/scp" if name == "scp" else None,
        ):
            capabilities = self._scanner(Path("/tmp")).scan()
        scp = next(c for c in capabilities if c.id == "scp")
        self.assertEqual(scp.status, CapabilityStatus.AVAILABLE)
        self.assertIn("/usr/bin/scp", scp.reason)
        self.assertEqual(scp.category, "outil")

    def test_scp_missing_when_binary_absent(self):
        with patch("omega_serv.infrastructure.probe.scanner.shutil.which", return_value=None):
            capabilities = self._scanner(Path("/tmp")).scan()
        scp = next(c for c in capabilities if c.id == "scp")
        self.assertEqual(scp.status, CapabilityStatus.MISSING)


if __name__ == "__main__":
    unittest.main()
