import unittest

from omega_serv.domain.security.tls.renewal_schedule import (
    build_renewal_cron_line,
    build_renewal_service_unit,
    build_renewal_timer_unit,
    render_manual_renewal_instructions,
    renewal_cron_marker,
    renewal_unit_base_name,
    replace_marked_cron_line,
)


class TestRenewalUnitBaseName(unittest.TestCase):
    def test_scoped_by_service_name(self):
        self.assertEqual(renewal_unit_base_name("omega-serv"), "omega-serv-certbot-renew")
        self.assertEqual(renewal_unit_base_name("omega-serv-monsite"), "omega-serv-monsite-certbot-renew")


class TestBuildRenewalServiceUnit(unittest.TestCase):
    def test_never_touches_system_letsencrypt_directory(self):
        content = build_renewal_service_unit(
            certbot_config_dir="/srv/x/secure/certificates/letsencrypt/config",
            certbot_work_dir="/srv/x/secure/certificates/letsencrypt/work",
            certbot_logs_dir="/srv/x/secure/certificates/letsencrypt/logs",
            user="kraynux",
        )
        self.assertNotIn("/etc/letsencrypt", content)
        self.assertIn("secure/certificates/letsencrypt", content)

    def test_runs_as_the_given_user_never_root(self):
        content = build_renewal_service_unit(
            certbot_config_dir="/x/config", certbot_work_dir="/x/work", certbot_logs_dir="/x/logs", user="kraynux",
        )
        self.assertIn("User=kraynux", content)

    def test_oneshot_certbot_renew_never_certonly(self):
        content = build_renewal_service_unit(
            certbot_config_dir="/x/config", certbot_work_dir="/x/work", certbot_logs_dir="/x/logs", user="kraynux",
        )
        self.assertIn("Type=oneshot", content)
        self.assertIn("certbot renew", content)
        self.assertNotIn("certonly", content)


class TestBuildRenewalTimerUnit(unittest.TestCase):
    def test_runs_twice_daily_with_randomized_delay(self):
        content = build_renewal_timer_unit()
        self.assertIn("OnCalendar=", content)
        self.assertIn("RandomizedDelaySec=", content)
        self.assertIn("Persistent=true", content)


class TestRenewalCronMarker(unittest.TestCase):
    def test_scoped_by_service_name(self):
        self.assertNotEqual(renewal_cron_marker("omega-serv"), renewal_cron_marker("omega-serv-monsite"))
        self.assertIn("omega-serv", renewal_cron_marker("omega-serv"))


class TestBuildRenewalCronLine(unittest.TestCase):
    def test_line_carries_the_marker_and_the_command(self):
        line = build_renewal_cron_line(
            service_name="omega-serv", certbot_config_dir="/x/config",
            certbot_work_dir="/x/work", certbot_logs_dir="/x/logs",
        )
        self.assertIn(renewal_cron_marker("omega-serv"), line)
        self.assertIn("certbot renew", line)
        self.assertNotIn("/etc/letsencrypt", line)


class TestReplaceMarkedCronLine(unittest.TestCase):
    def test_appends_to_empty_crontab(self):
        result = replace_marked_cron_line("", "omega-serv", "0 0,12 * * * certbot renew  # marker")
        self.assertEqual(result, "0 0,12 * * * certbot renew  # marker\n")

    def test_replaces_only_the_matching_instance_line(self):
        marker_a = renewal_cron_marker("omega-serv")
        marker_b = renewal_cron_marker("omega-serv-monsite")
        existing = f"0 0 * * * old-command-a  {marker_a}\n0 1 * * * command-b  {marker_b}\n"
        new_line = f"0 0,12 * * * new-command-a  {marker_a}"
        result = replace_marked_cron_line(existing, "omega-serv", new_line)
        self.assertIn(new_line, result)
        self.assertNotIn("old-command-a", result)
        self.assertIn(f"0 1 * * * command-b  {marker_b}", result)

    def test_reconfiguring_never_duplicates_the_line(self):
        marker = renewal_cron_marker("omega-serv")
        existing = f"0 0 * * * certbot renew  {marker}\n"
        result = replace_marked_cron_line(existing, "omega-serv", f"0 0,12 * * * certbot renew  {marker}")
        self.assertEqual(result.count(marker), 1)

    def test_preserves_unrelated_user_lines(self):
        existing = "0 3 * * * /usr/local/bin/backup.sh\n"
        result = replace_marked_cron_line(existing, "omega-serv", "0 0,12 * * * certbot renew  # marker")
        self.assertIn("/usr/local/bin/backup.sh", result)


class TestRenderManualRenewalInstructions(unittest.TestCase):
    def test_includes_the_cron_line_to_add(self):
        text = render_manual_renewal_instructions(cron_line="0 0,12 * * * certbot renew")
        self.assertIn("0 0,12 * * * certbot renew", text)


if __name__ == "__main__":
    unittest.main()
