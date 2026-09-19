import json
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path

from omega_serv.domain.config.entities import OmegaServConfig
from omega_serv.infrastructure.filesystem.local_filesystem import LocalFilesystem
from omega_serv.infrastructure.security.waf_mode_rule import check_waf_log_only_duration

_NOW = datetime(2026, 9, 6, tzinfo=timezone.utc)


class _FakeClock:
    def __init__(self, now=_NOW):
        self._now = now

    def now(self):
        return self._now


def _config(mode="log-only", enabled=True) -> OmegaServConfig:
    return OmegaServConfig.from_dict({"options": {"waf": {"enabled": enabled, "mode": mode}}})


class TestCheckWafLogOnlyDuration(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.project_root = Path(self._tmp.name)
        self.filesystem = LocalFilesystem()
        self.state_path = self.project_root / "var" / "run" / "waf-mode-state.json"

    def tearDown(self):
        self._tmp.cleanup()

    def test_waf_disabled_skips_check_entirely(self):
        findings = check_waf_log_only_duration(_config(enabled=False), self.project_root, self.filesystem, _FakeClock())
        self.assertEqual(findings, [])
        self.assertFalse(self.state_path.exists())

    def test_first_observation_records_state_without_finding(self):
        findings = check_waf_log_only_duration(_config(), self.project_root, self.filesystem, _FakeClock())
        self.assertEqual(findings, [])
        self.assertTrue(self.state_path.exists())
        data = json.loads(self.state_path.read_text())
        self.assertEqual(data["mode"], "log-only")
        self.assertEqual(data["since"], _NOW.isoformat())

    def test_mode_change_resets_the_clock_without_finding(self):
        self.state_path.parent.mkdir(parents=True)
        self.state_path.write_text(json.dumps({"mode": "block", "since": (_NOW - timedelta(days=100)).isoformat()}))
        findings = check_waf_log_only_duration(_config(mode="log-only"), self.project_root, self.filesystem, _FakeClock())
        self.assertEqual(findings, [])
        data = json.loads(self.state_path.read_text())
        self.assertEqual(data["mode"], "log-only")
        self.assertEqual(data["since"], _NOW.isoformat())

    def test_same_mode_under_threshold_not_flagged(self):
        self.state_path.parent.mkdir(parents=True)
        since = _NOW - timedelta(days=5)
        self.state_path.write_text(json.dumps({"mode": "log-only", "since": since.isoformat()}))
        findings = check_waf_log_only_duration(_config(mode="log-only"), self.project_root, self.filesystem, _FakeClock())
        self.assertEqual(findings, [])

    def test_same_mode_over_threshold_flagged_as_waf_001(self):
        self.state_path.parent.mkdir(parents=True)
        since = _NOW - timedelta(days=20)
        self.state_path.write_text(json.dumps({"mode": "log-only", "since": since.isoformat()}))
        findings = check_waf_log_only_duration(_config(mode="log-only"), self.project_root, self.filesystem, _FakeClock())
        self.assertEqual(len(findings), 1)
        self.assertEqual(findings[0].rule_id, "WAF-001")
        self.assertEqual(findings[0].details["days_in_mode"], 20)

    def test_block_mode_never_flagged_even_if_long_lived(self):
        self.state_path.parent.mkdir(parents=True)
        since = _NOW - timedelta(days=200)
        self.state_path.write_text(json.dumps({"mode": "block", "since": since.isoformat()}))
        findings = check_waf_log_only_duration(_config(mode="block"), self.project_root, self.filesystem, _FakeClock())
        self.assertEqual(findings, [])

    def test_state_does_not_flap_on_repeated_calls_with_same_mode(self):
        clock = _FakeClock(_NOW)
        check_waf_log_only_duration(_config(), self.project_root, self.filesystem, clock)
        first_since = json.loads(self.state_path.read_text())["since"]

        later_clock = _FakeClock(_NOW + timedelta(days=5))
        check_waf_log_only_duration(_config(), self.project_root, self.filesystem, later_clock)
        second_since = json.loads(self.state_path.read_text())["since"]

        self.assertEqual(first_since, second_since)

    def test_malformed_state_file_treated_as_first_observation(self):
        self.state_path.parent.mkdir(parents=True)
        self.state_path.write_text("not json")
        findings = check_waf_log_only_duration(_config(), self.project_root, self.filesystem, _FakeClock())
        self.assertEqual(findings, [])
        data = json.loads(self.state_path.read_text())
        self.assertEqual(data["mode"], "log-only")


if __name__ == "__main__":
    unittest.main()
