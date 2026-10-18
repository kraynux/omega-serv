"""`omega-serv waf never-auto-block` (OMEGA-SERV_PLAN-DETAILLE_SENSITIVE_PATHS.md
lot 10) : sortie REELLE lue par omega-jail a l'installation - un reseau par
ligne, rien d'autre sur la sortie standard."""
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


class TestNeverAutoBlockCli(unittest.TestCase):
    def _run(self, options: dict) -> subprocess.CompletedProcess:
        with tempfile.TemporaryDirectory() as tmp:
            config = Path(tmp) / "omega-serve.json"
            config.write_text(json.dumps({"options": options}))
            return subprocess.run(
                [sys.executable, "-m", "omega_serv", "--config", str(config), "waf", "never-auto-block"],
                capture_output=True, text=True, timeout=60, check=False,
            )

    def test_defaults_with_trusted_proxy(self):
        result = self._run({"trusted_proxy": {"enabled": True, "trusted_networks": ["127.0.0.1"]}})
        self.assertEqual(result.returncode, 0, result.stderr)
        lines = result.stdout.split()
        self.assertEqual(lines[:3], ["127.0.0.0/8", "::1/128", "100.64.0.0/10"])
        self.assertIn("192.168.0.0/16", lines)

    def test_loopback_dropped_without_trusted_proxy(self):
        lines = self._run({}).stdout.split()
        self.assertNotIn("127.0.0.0/8", lines)
        self.assertIn("100.64.0.0/10", lines)

    def test_configured_value_wins(self):
        lines = self._run({"waf": {"enabled": True, "reputation": {"never_auto_block": ["10.0.0.0/8"]}}}).stdout.split()
        self.assertEqual(lines, ["10.0.0.0/8"])

    def test_missing_config_fails(self):
        result = subprocess.run(
            [sys.executable, "-m", "omega_serv", "--config", "/nexiste/pas.json", "waf", "never-auto-block"],
            capture_output=True, text=True, timeout=60, check=False,
        )
        self.assertEqual(result.returncode, 1)
        self.assertEqual(result.stdout.strip(), "")


if __name__ == "__main__":
    unittest.main()
