import unittest
from pathlib import Path

from omega_serv.application.tls.schedule_certbot_renewal import (
    check_renewal_schedule_status,
    schedule_certbot_renewal,
)
from omega_serv.domain.security.tls.renewal_schedule import renewal_cron_marker
from omega_serv.ports.process_runner_port import ProcessResult


class _FakeProcessRunner:
    def __init__(self, *, crontab_available=True, crontab_content=""):
        self._crontab_available = crontab_available
        self._crontab_content = crontab_content
        self.calls = []

    def run(self, args, input_text=None, timeout=None):
        self.calls.append((args, input_text))
        if not self._crontab_available:
            return ProcessResult(returncode=127, stdout="", stderr=f"{args[0]} : commande introuvable")
        if args == ["crontab", "-l"]:
            return ProcessResult(returncode=0, stdout=self._crontab_content, stderr="")
        if args == ["crontab", "-"]:
            self._crontab_content = input_text or ""
            return ProcessResult(returncode=0, stdout="", stderr="")
        raise AssertionError(f"appel inattendu : {args}")

    def run_interactive(self, args):
        raise NotImplementedError


class _FakeSystemdManager:
    def __init__(self):
        self.written_units: dict[Path, str] = {}
        self.reload_called = False
        self.enabled: list[str] = []
        self.started: list[str] = []
        self._active_timers: set[str] = set()
        self._enabled_timers: set[str] = set()

    def manager_type(self):
        return "systemd"

    def write_unit_file(self, unit_path, content):
        self.written_units[unit_path] = content

    def reload_daemon(self):
        self.reload_called = True

    def enable(self, service_name):
        self.enabled.append(service_name)
        self._enabled_timers.add(service_name)
        return True

    def start(self, service_name):
        self.started.append(service_name)
        self._active_timers.add(service_name)
        return True

    def is_active(self, service_name):
        return service_name in self._active_timers

    def is_enabled(self, service_name):
        return service_name in self._enabled_timers


class _FakeNonSystemdManager:
    def manager_type(self):
        return "openrc"


class TestScheduleCertbotRenewalSystemd(unittest.TestCase):
    def test_writes_both_units_scoped_by_service_name(self):
        manager = _FakeSystemdManager()
        runner = _FakeProcessRunner()
        result = schedule_certbot_renewal(
            "omega-serv", Path("/srv/x/secure/certificates/letsencrypt"), manager,
            Path("/etc/systemd/system"), runner, "kraynux",
        )
        self.assertEqual(result.outcome, "systemd")
        self.assertTrue(result.success)
        self.assertIn(Path("/etc/systemd/system/omega-serv-certbot-renew.service"), manager.written_units)
        self.assertIn(Path("/etc/systemd/system/omega-serv-certbot-renew.timer"), manager.written_units)
        self.assertEqual(runner.calls, [])  # jamais de crontab touche sur le chemin systemd

    def test_enables_and_starts_the_timer(self):
        manager = _FakeSystemdManager()
        schedule_certbot_renewal(
            "omega-serv", Path("/srv/x/secure/certificates/letsencrypt"), manager,
            Path("/etc/systemd/system"), _FakeProcessRunner(), "kraynux",
        )
        self.assertIn("omega-serv-certbot-renew.timer", manager.enabled)
        self.assertIn("omega-serv-certbot-renew.timer", manager.started)

    def test_reloads_daemon_after_writing_units(self):
        manager = _FakeSystemdManager()
        schedule_certbot_renewal(
            "omega-serv", Path("/srv/x/secure/certificates/letsencrypt"), manager,
            Path("/etc/systemd/system"), _FakeProcessRunner(), "kraynux",
        )
        self.assertTrue(manager.reload_called)

    def test_distinct_instances_never_collide(self):
        manager = _FakeSystemdManager()
        schedule_certbot_renewal(
            "omega-serv", Path("/a"), manager, Path("/etc/systemd/system"), _FakeProcessRunner(), "kraynux",
        )
        schedule_certbot_renewal(
            "omega-serv-monsite", Path("/b"), manager, Path("/etc/systemd/system"), _FakeProcessRunner(), "kraynux",
        )
        self.assertIn(Path("/etc/systemd/system/omega-serv-certbot-renew.timer"), manager.written_units)
        self.assertIn(Path("/etc/systemd/system/omega-serv-monsite-certbot-renew.timer"), manager.written_units)


class TestScheduleCertbotRenewalCron(unittest.TestCase):
    def test_installs_a_cron_line_when_no_systemd(self):
        runner = _FakeProcessRunner()
        result = schedule_certbot_renewal(
            "omega-serv", Path("/srv/x/secure/certificates/letsencrypt"), _FakeNonSystemdManager(),
            Path("/etc/systemd/system"), runner, "kraynux",
        )
        self.assertEqual(result.outcome, "cron")
        self.assertTrue(result.success)
        self.assertIn(renewal_cron_marker("omega-serv"), runner._crontab_content)

    def test_no_service_manager_at_all_still_tries_cron(self):
        runner = _FakeProcessRunner()
        result = schedule_certbot_renewal(
            "omega-serv", Path("/x"), None, Path("/etc/systemd/system"), runner, "kraynux",
        )
        self.assertEqual(result.outcome, "cron")
        self.assertTrue(result.success)

    def test_falls_back_to_manual_instructions_when_crontab_missing(self):
        runner = _FakeProcessRunner(crontab_available=False)
        result = schedule_certbot_renewal(
            "omega-serv", Path("/x"), _FakeNonSystemdManager(), Path("/etc/systemd/system"), runner, "kraynux",
        )
        self.assertEqual(result.outcome, "manual")
        self.assertFalse(result.success)
        self.assertIn("certbot renew", result.message)

    def test_reconfiguring_never_duplicates_the_cron_line(self):
        runner = _FakeProcessRunner()
        for _ in range(2):
            schedule_certbot_renewal(
                "omega-serv", Path("/x"), _FakeNonSystemdManager(), Path("/etc/systemd/system"), runner, "kraynux",
            )
        self.assertEqual(runner._crontab_content.count(renewal_cron_marker("omega-serv")), 1)


class TestCheckRenewalScheduleStatus(unittest.TestCase):
    def test_systemd_not_installed_yet(self):
        status = check_renewal_schedule_status("omega-serv", _FakeSystemdManager(), _FakeProcessRunner())
        self.assertEqual(status.mechanism, "systemd")
        self.assertFalse(status.already_configured)

    def test_systemd_already_installed(self):
        manager = _FakeSystemdManager()
        schedule_certbot_renewal("omega-serv", Path("/x"), manager, Path("/etc/systemd/system"), _FakeProcessRunner(), "kraynux")
        status = check_renewal_schedule_status("omega-serv", manager, _FakeProcessRunner())
        self.assertTrue(status.already_configured)

    def test_cron_not_configured_yet(self):
        status = check_renewal_schedule_status("omega-serv", _FakeNonSystemdManager(), _FakeProcessRunner())
        self.assertEqual(status.mechanism, "cron")
        self.assertFalse(status.already_configured)

    def test_cron_already_configured(self):
        marker = renewal_cron_marker("omega-serv")
        runner = _FakeProcessRunner(crontab_content=f"0 0 * * * certbot renew  {marker}\n")
        status = check_renewal_schedule_status("omega-serv", _FakeNonSystemdManager(), runner)
        self.assertTrue(status.already_configured)

    def test_prefix_named_instance_never_matches_another(self):
        marker_other = renewal_cron_marker("omega-serv-monsite")
        runner = _FakeProcessRunner(crontab_content=f"0 0 * * * certbot renew  {marker_other}\n")
        status = check_renewal_schedule_status("omega-serv", _FakeNonSystemdManager(), runner)
        self.assertFalse(status.already_configured)

    def test_no_mechanism_available(self):
        status = check_renewal_schedule_status(
            "omega-serv", _FakeNonSystemdManager(), _FakeProcessRunner(crontab_available=False),
        )
        self.assertEqual(status.mechanism, "none")
        self.assertFalse(status.already_configured)


if __name__ == "__main__":
    unittest.main()
