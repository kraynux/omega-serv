import shlex
import unittest

from omega_serv.domain.security.tls.acme import (
    CertbotRequestParams,
    build_certbot_argv,
    build_deploy_hook_script,
    build_omega_serv_import_argv,
    build_omega_serv_restart_argv,
    validate_certbot_request_params,
)


def _params(**overrides):
    defaults = {
        "domain": "example.dynu.com", "webroot_path": "/srv/omega-serv/webroot",
        "config_dir": "/srv/omega-serv/secure/certificates/letsencrypt/config",
        "work_dir": "/srv/omega-serv/secure/certificates/letsencrypt/work",
        "logs_dir": "/srv/omega-serv/secure/certificates/letsencrypt/logs",
        "deploy_hook_path": "/srv/omega-serv/secure/certificates/letsencrypt/hooks/deploy-example.dynu.com.sh",
    }
    defaults.update(overrides)
    return CertbotRequestParams(**defaults)


class TestValidateCertbotRequestParams(unittest.TestCase):
    def test_valid_params_pass(self):
        self.assertEqual(validate_certbot_request_params(_params()), [])

    def test_empty_domain_rejected(self):
        errors = validate_certbot_request_params(_params(domain=""))
        self.assertTrue(any("domaine" in e for e in errors))

    def test_empty_webroot_rejected(self):
        errors = validate_certbot_request_params(_params(webroot_path=""))
        self.assertTrue(any("webroot" in e for e in errors))

    def test_empty_hook_path_rejected(self):
        errors = validate_certbot_request_params(_params(deploy_hook_path=""))
        self.assertTrue(any("hook" in e for e in errors))


class TestBuildCertbotArgv(unittest.TestCase):
    def test_never_touches_system_letsencrypt_directory(self):
        argv = build_certbot_argv(_params())
        joined = " ".join(argv)
        self.assertNotIn("/etc/letsencrypt", joined)
        self.assertIn("secure/certificates/letsencrypt", joined)

    def test_uses_webroot_challenge_never_standalone(self):
        argv = build_certbot_argv(_params())
        self.assertIn("--webroot", argv)
        self.assertNotIn("--standalone", argv)

    def test_includes_domain_and_webroot_path(self):
        argv = build_certbot_argv(_params(domain="mon-domaine.dynu.com", webroot_path="/x/webroot"))
        self.assertIn("mon-domaine.dynu.com", argv)
        self.assertIn("/x/webroot", argv)

    def test_staging_flag_present_by_default(self):
        argv = build_certbot_argv(_params())
        self.assertIn("--staging", argv)

    def test_staging_flag_absent_when_explicitly_disabled(self):
        argv = build_certbot_argv(_params(staging=False))
        self.assertNotIn("--staging", argv)

    def test_email_used_when_provided(self):
        argv = build_certbot_argv(_params(email="admin@example.com"))
        self.assertIn("-m", argv)
        self.assertIn("admin@example.com", argv)
        self.assertNotIn("--register-unsafely-without-email", argv)

    def test_register_without_email_when_absent(self):
        argv = build_certbot_argv(_params(email=None))
        self.assertIn("--register-unsafely-without-email", argv)
        self.assertNotIn("-m", argv)

    def test_deploy_hook_wired(self):
        argv = build_certbot_argv(_params(deploy_hook_path="/x/hook.sh"))
        self.assertIn("--deploy-hook", argv)
        self.assertIn("/x/hook.sh", argv)


class TestBuildDeployHookScript(unittest.TestCase):
    def test_script_calls_import_then_restart(self):
        script = build_deploy_hook_script(
            python_executable="/srv/omega-serv/.venv/bin/python3",
            config_dir="/srv/omega-serv/secure/certificates/letsencrypt/config",
            domain="example.dynu.com", service_name="omega-serv",
        )
        lines = [line for line in script.splitlines() if line and not line.startswith("#") and line != "set -e"]
        self.assertEqual(len(lines), 2)
        self.assertIn("certs import", lines[0])
        self.assertIn("service restart", lines[1])

    def test_script_uses_absolute_python_executable_never_bare_omega_serv(self):
        script = build_deploy_hook_script(
            python_executable="/srv/omega-serv/.venv/bin/python3",
            config_dir="/x/config", domain="example.dynu.com", service_name="omega-serv",
        )
        self.assertNotIn("\nomega-serv ", script)
        self.assertIn("/srv/omega-serv/.venv/bin/python3", script)

    def test_script_points_to_the_correct_domain_live_directory(self):
        script = build_deploy_hook_script(
            python_executable="/x/python3", config_dir="/x/config",
            domain="example.dynu.com", service_name="omega-serv",
        )
        self.assertIn("/x/config/live/example.dynu.com/privkey.pem", script)
        self.assertIn("/x/config/live/example.dynu.com/fullchain.pem", script)

    def test_script_targets_the_correct_service_name(self):
        script = build_deploy_hook_script(
            python_executable="/x/python3", config_dir="/x/config",
            domain="example.dynu.com", service_name="my-instance",
        )
        self.assertIn("my-instance", script)

    def test_script_is_shell_safe_for_domains_with_special_characters(self):
        malicious_domain = "example.com; rm -rf /"
        script = build_deploy_hook_script(
            python_executable="/x/py", config_dir="/x/config",
            domain=malicious_domain, service_name="omega-serv",
        )
        import_line = next(line for line in script.splitlines() if "certs import" in line)
        tokens = shlex.split(import_line)
        key_path = tokens[tokens.index("--key") + 1]
        self.assertEqual(key_path, f"/x/config/live/{malicious_domain}/privkey.pem")


class TestBuildOmegaServArgvHelpers(unittest.TestCase):
    def test_import_argv_uses_correct_live_paths(self):
        argv = build_omega_serv_import_argv("/x/python3", "/x/config", "example.dynu.com")
        self.assertIn("/x/config/live/example.dynu.com/privkey.pem", argv)
        self.assertIn("/x/config/live/example.dynu.com/fullchain.pem", argv)

    def test_restart_argv_uses_the_given_service_name(self):
        argv = build_omega_serv_restart_argv("/x/python3", "my-instance")
        self.assertIn("my-instance", argv)
        self.assertIn("restart", argv)


if __name__ == "__main__":
    unittest.main()
