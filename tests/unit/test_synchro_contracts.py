"""Contrats d'interconnexion, etape 2 du 2026-11-10 (omega-lib D-017) : jeton d'installation et fiche
d'instance d'omega-serv. Tout se passe dans un dossier temporaire (jamais le vrai var/)."""
import argparse
import json
import os
import stat
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import patch

from omega_lib.synchro.codec import sheet_from_dict, sheet_to_dict, token_from_dict
from omega_lib.synchro.models import CapabilityState, ServiceInfo

from omega_serv.application.synchro.serv_contracts import (
    SERV_CONTRACTS,
    SheetContext,
    build_serv_sheet,
    installation_id,
    refresh_serv_token,
)
from omega_serv.domain.config.entities import OmegaServConfig
from omega_serv.infrastructure.filesystem.local_filesystem import LocalFilesystem
from omega_serv.interfaces.cli import main as cli

NOW = datetime(2026, 11, 10, 14, 5, tzinfo=timezone.utc)


def _context(**overrides):
    values = {"version": "2.6.1", "instance": "omega-serv-blog", "installation_id": "", "service": None,
              "native_binary_problem": None, "effective_engine": "python", "now": NOW}
    values.update(overrides)
    return SheetContext(**values)


def _config(**options):
    return OmegaServConfig.from_dict({"options": options})


class TestServToken(unittest.TestCase):
    def test_token_created_with_serv_contracts_and_kept(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            first = refresh_serv_token(root, "2.6.1")
            self.assertEqual(first.outcome, "created")
            data = json.loads((root / "var" / "omega-jeton.json").read_text(encoding="utf-8"))
            token = token_from_dict(data).value
            self.assertIsNotNone(token)
            self.assertEqual(token.tool, "omega-serv")
            self.assertEqual(dict(token.contracts), SERV_CONTRACTS)
            self.assertEqual(stat.S_IMODE((root / "var" / "omega-jeton.json").stat().st_mode), 0o644)
            self.assertEqual(refresh_serv_token(root, "2.6.1").outcome, "unchanged")
            self.assertEqual(installation_id(root), token.installation_id)

    def test_no_token_means_empty_id(self):
        with tempfile.TemporaryDirectory() as tmp:
            self.assertEqual(installation_id(Path(tmp)), "")

    @patch.object(cli, "running_as_root", return_value=True)
    def test_token_command_refused_as_root_but_sheet_allowed(self, _root):
        with tempfile.TemporaryDirectory() as tmp:
            refused = cli._refuse_root_for_writing_command(
                argparse.Namespace(command="synchro", func=cli.cmd_synchro_jeton), Path(tmp))
            self.assertEqual(refused, 1)
            self.assertIsNone(cli._refuse_root_for_writing_command(
                argparse.Namespace(command="synchro", func=cli.cmd_synchro_fiche), Path(tmp)))


class TestServSheet(unittest.TestCase):
    def test_default_config_sheet_is_valid_and_untranslated(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            sheet = build_serv_sheet(_config(), root, LocalFilesystem(), _context())
            payload = json.loads(json.dumps(sheet_to_dict(sheet)))
            parsed = sheet_from_dict(payload)
            self.assertTrue(parsed.ok, parsed.detail)
            self.assertEqual(sheet.capabilities["waf"], CapabilityState.ABSENT)
            self.assertEqual(sheet.capabilities["omega-waf"], CapabilityState.ABSENT)
            self.assertEqual(sheet.capabilities["native-engine"], CapabilityState.DISABLED)
            self.assertEqual(sheet.files["access-log"].path, str(root / "var" / "log" / "access.log"))
            self.assertEqual(payload["exposure"], "direct")
            # Sans proxy de confiance, le loopback n'est jamais exempte (garde-fou de `waf never-auto-block`).
            self.assertNotIn("127.0.0.0/8", payload["never_auto_block"])
            self.assertIn("100.64.0.0/10", payload["never_auto_block"])

    def test_waf_riposte_and_omega_waf_detected(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            script = root / "secure" / "waf" / "scripts" / "waf.lua"
            script.parent.mkdir(parents=True)
            script.write_text('local waf_log_only = (omega_waf_mode ~= nil and omega_waf_mode ~= "block")\n',
                              encoding="utf-8")
            config = _config(
                waf={"enabled": True, "mode": "block", "magnet": {"enabled": True}},
                riposte={"enabled": True},
                active_defense={"enabled": False},
                trusted_proxy={"enabled": True},
            )
            service = ServiceInfo("systemd", "omega-serv-blog.service", "omega-serv", "omega-serv", "active")
            sheet = build_serv_sheet(config, root, LocalFilesystem(),
                                     _context(service=service, effective_engine="native"))
            self.assertEqual(sheet.capabilities["waf"], CapabilityState.ACTIVE)
            self.assertEqual(sheet.capabilities["magnet"], CapabilityState.ACTIVE)
            self.assertEqual(sheet.capabilities["omega-waf"], CapabilityState.ACTIVE)
            self.assertEqual(sheet.capabilities["riposte"], CapabilityState.ACTIVE)
            self.assertEqual(sheet.capabilities["active-defense"], CapabilityState.DISABLED)
            self.assertEqual(sheet.capabilities["native-engine"], CapabilityState.ACTIVE)
            self.assertEqual(sheet.files["waf-log"].contract, ("waf-log", 1))
            self.assertEqual(sheet.files["riposte-decisions"].contract, ("riposte-decisions", 1))
            self.assertIn("magnet-alerts-log", sheet.files)
            self.assertEqual(sheet.extra["exposure"], "proxy")
            self.assertIn("127.0.0.0/8", sheet.extra["never_auto_block"])
            self.assertEqual(sheet.extra["omega_waf"]["mode"], "block")
            self.assertTrue(sheet_from_dict(json.loads(json.dumps(sheet_to_dict(sheet)))).ok)

    def test_other_magnet_script_is_not_omega_waf(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            script = root / "secure" / "waf" / "scripts" / "waf.lua"
            script.parent.mkdir(parents=True)
            script.write_text("-- autre script\n", encoding="utf-8")
            config = _config(waf={"enabled": True, "magnet": {"enabled": True}})
            sheet = build_serv_sheet(config, root, LocalFilesystem(), _context())
            self.assertEqual(sheet.capabilities["magnet"], CapabilityState.ACTIVE)
            self.assertEqual(sheet.capabilities["omega-waf"], CapabilityState.ABSENT)
            self.assertNotIn("omega_waf", sheet.extra)

    def test_native_binary_missing_is_absent(self):
        with tempfile.TemporaryDirectory() as tmp:
            sheet = build_serv_sheet(_config(), Path(tmp), LocalFilesystem(),
                                     _context(native_binary_problem="binaire absent"))
            self.assertEqual(sheet.capabilities["native-engine"], CapabilityState.ABSENT)

    def test_paths_are_normalized(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            config = OmegaServConfig.from_dict({"logs": {"access": "var/log/../log/access.log"}})
            sheet = build_serv_sheet(config, root, LocalFilesystem(), _context())
            self.assertEqual(sheet.files["access-log"].path, os.path.join(tmp, "var", "log", "access.log"))


if __name__ == "__main__":
    unittest.main()
