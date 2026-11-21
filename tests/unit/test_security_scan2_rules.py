# Copyright (c) 2026 kraynux - kraynux@proton.me - Licence MIT (voir fichier LICENSE)
"""Scan de securite n° 2 du 2026-11-20 : regles corrigees, une classe par cause (A a F). Essais sur serveur reel dans
tests/integration/test_security_scan2_paths.py ; memes cas cote natif dans
native/omega-http-core/tests/test_security_scan2.cpp."""
import asyncio
import json
import os
import socket
import stat
import tarfile
import tempfile
import time
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest import mock

from omega_serv.application.admin_web.auth import AdminAuth
from omega_serv.application.admin_web.web_app import AdminRequest, AdminWebApp
from omega_serv.application.logs.privileged_logs import shown_command, sudo_fix_commands
from omega_serv.application.logs.rotate_log import rotate_log_if_needed
from omega_serv.application.server.serve_proxy import build_outgoing_headers
from omega_serv.application.server.start_server import isolate_magnet_paths
from omega_serv.application.services.resolve_current_service_name import (
    resolve_current_service_name,
)
from omega_serv.application.services.zone_group import add_zone_group
from omega_serv.application.terminal.clear_directory import check_clearable, clear_directory
from omega_serv.application.terminal.exceptions import UnsafeDirectoryError
from omega_serv.application.tls.schedule_certbot_renewal import schedule_certbot_renewal
from omega_serv.domain.admin_web.settings import AdminWebSettings
from omega_serv.domain.http.admin_cookies import without_admin_cookies
from omega_serv.domain.http.cgi_env import build_cgi_env
from omega_serv.domain.http.headers import HttpHeaders
from omega_serv.domain.http.request import HttpRequest
from omega_serv.domain.logging.error_log_line import sanitize_log_field
from omega_serv.domain.logs.exceptions import ArchiveStoreError
from omega_serv.domain.routing.access_rule import AccessRule, resolve_access_verdict
from omega_serv.domain.routing.proxy_zone import ProxyZone, UpstreamTarget
from omega_serv.domain.security.active_defense.policies import redact_fields, source_subject_id
from omega_serv.domain.security.path_policy import canonical_path
from omega_serv.domain.security.trusted_proxy import resolve_client_ip
from omega_serv.domain.security.waf.binary_formats import DEFAULT_BINARY_FORMATS, inspectable_body
from omega_serv.domain.services.exceptions import ServiceControlError
from omega_serv.domain.services.service_name import is_safe_service_name
from omega_serv.infrastructure.admin_web.log_reader import _decode
from omega_serv.infrastructure.exporters.csv_ioc_exporter import _neutral_cell
from omega_serv.infrastructure.filesystem.file_lock import exclusive_file_lock
from omega_serv.infrastructure.filesystem.local_filesystem import LocalFilesystem
from omega_serv.infrastructure.server.http_parser import has_dot_segment, is_supported_target_form
from omega_serv.infrastructure.services import secure_tree
from omega_serv.infrastructure.services.systemd_service_manager import SystemdServiceManager
from omega_serv.infrastructure.storage.files.archive_store import ArchiveStore
from omega_serv.infrastructure.tls.openssl_certificate_tool import OpensslCertificateTool
from omega_serv.ports.process_runner_port import ProcessResult

REPO = Path(__file__).resolve().parents[2]


def _request(path="/", headers=(), body=None, method="GET") -> HttpRequest:
    return HttpRequest(request_id="r", remote_ip="203.0.113.1", peer_ip="203.0.113.1", method=method, path=path,
                       raw_path=path, query="", headers=HttpHeaders.from_pairs(list(headers)), body=body,
                       content_length=None, is_tls=False)


class _Runner:
    def __init__(self, result=None):
        self.result = result or ProcessResult(0, "", "")
        self.calls = []

    def run(self, args, input_text=None, timeout=None):
        self.calls.append((list(args), input_text))
        return self.result

    def run_interactive(self, args):
        return 0


class TestCauseANonCanonicalPaths(unittest.TestCase):
    def test_only_origin_absolute_and_star_targets(self):
        for target in ("/x", "*", "http://h/x", "HTTPS://h"):
            self.assertTrue(is_supported_target_form(target), target)
        for target in ("private/x", "x", "\\private\\x", "%2Fprivate/x", "h:80"):
            self.assertFalse(is_supported_target_form(target), target)

    def test_relative_path_has_no_canonical_form(self):
        self.assertIsNone(canonical_path("private/x"))
        self.assertEqual(canonical_path("*"), "*")

    def test_path_parameter_dot_segment(self):
        for target in ("/api/..;x/admin", "/api/..;/admin", "/a/.;jsessionid=1/b", "/a/%2e%2e;x/b"):
            self.assertTrue(has_dot_segment(target), target)
        self.assertFalse(has_dot_segment("/a/b;x=1"))

    def test_extension_rule_ignores_trailing_slash(self):
        rules = [AccessRule(path_prefix="/", verdict="deny", extensions=(".db",))]
        self.assertEqual(resolve_access_verdict("/data/x.db/", rules), "deny")
        self.assertEqual(resolve_access_verdict("/data/x.db", rules), "deny")


class TestCauseBServiceAccountBoundary(unittest.TestCase):
    def test_safe_service_names(self):
        for name in ("omega-serv", "site_2", "a.b"):
            self.assertTrue(is_safe_service_name(name), name)
        for name in ("", "*", "-x", "../x", "/etc/x", "a/b", "x.service", "A", "x" * 65, "a b"):
            self.assertFalse(is_safe_service_name(name), name)

    def test_unsafe_name_from_settings_falls_back_to_default(self):
        registry = SimpleNamespace(load=list)
        filesystem = SimpleNamespace(resolve_real_path=lambda p: p)
        for value, expected in (("../../etc/x", "omega-serv"), ("*", "omega-serv"), ("mon-site", "mon-site")):
            settings = SimpleNamespace(get=lambda key, default, v=value: v)
            self.assertEqual(resolve_current_service_name(registry, filesystem, settings, Path("/srv/x")), expected)

    @mock.patch("omega_serv.infrastructure.services.systemd_service_manager.running_as_root", return_value=True)
    def test_systemctl_never_gets_unsafe_name_and_uses_double_dash(self, _root):
        runner = _Runner()
        manager = SystemdServiceManager(runner)
        with self.assertRaises(ServiceControlError):
            manager.stop("*")
        self.assertEqual(runner.calls, [])
        manager.stop("omega-serv")
        self.assertEqual(runner.calls[0][0], ["systemctl", "stop", "--", "omega-serv"])

    def test_zone_group_and_certbot_refuse_unsafe_name(self):
        result = add_zone_group(mock.Mock(), mock.Mock(), Path("/etc/systemd/system"), "../../tmp/x", Path("/srv"),
                                lambda name: True)
        self.assertFalse(result.success)
        scheduled = schedule_certbot_renewal("/etc/x", Path("/srv/le"), None, Path("/etc/systemd/system"),
                                             _Runner(), "u")
        self.assertFalse(scheduled.success)

    def test_secure_tree_fix_file_refuses_links(self):
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp) / "cible"
            target.write_text("x")
            target.chmod(0o666)
            link = Path(tmp) / "access.log"
            os.symlink(target, link)
            with self.assertRaises(OSError):
                secure_tree.fix_file(str(link), 0, None, 0, 0o002)  # lien qui n'appartient pas a root
            secure_tree.fix_file(str(target), os.getuid(), None, 0, 0o002)
            self.assertEqual(stat.S_IMODE(target.stat().st_mode), 0o664)

    def test_log_fix_is_shown_as_before(self):
        commands = sudo_fix_commands("world_writable", "/srv/x.log", None)
        self.assertNotIn("chmod", commands[0])
        self.assertEqual(shown_command(commands).replace("sudo ", ""), "chmod o-w /srv/x.log")

    def test_purge_refuses_linked_directory_inside_project(self):
        with tempfile.TemporaryDirectory() as tmp:
            project = Path(tmp) / "projet"
            (project / "var").mkdir(parents=True)
            victim = Path(tmp) / "victime"
            victim.mkdir()
            (victim / "precieux").write_text("x")
            os.symlink(victim, project / "var" / "exports")
            with self.assertRaises(UnsafeDirectoryError):
                check_clearable(project / "var" / "exports", project)
            self.assertTrue((victim / "precieux").exists())
            (project / "var" / "exports").unlink()
            (project / "var" / "exports").mkdir()
            (project / "var" / "exports" / "a").write_text("1")
            self.assertEqual(clear_directory(project / "var" / "exports", project).removed, 1)

    def test_rotation_refuses_linked_log(self):
        with tempfile.TemporaryDirectory() as tmp:
            victim = Path(tmp) / "victime"
            victim.write_text("x" * 100)
            log = Path(tmp) / "access.log"
            os.symlink(victim, log)
            result = rotate_log_if_needed(log, 1, 3, LocalFilesystem(), ArchiveStore(Path(tmp) / "a"))
            self.assertFalse(result.success)
            self.assertEqual(victim.read_text(), "x" * 100)

    def test_confined_restore_never_follows_links(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "projet"
            (root / "var" / "log").mkdir(parents=True)
            source = Path(tmp) / "a.log"
            source.write_text("ligne\n")
            store = ArchiveStore(Path(tmp) / "archives")
            archive = store.create_archive("a.tar.gz", [source])
            dest = store.extract_archive_confined(archive, root, "var/log/restored/a")
            self.assertEqual((dest / "a.log").read_text(), "ligne\n")
            self.assertEqual(stat.S_IMODE(dest.stat().st_mode), 0o700)
            elsewhere = Path(tmp) / "ailleurs"
            elsewhere.mkdir()
            os.symlink(elsewhere, root / "var" / "log" / "restored" / "b")
            with self.assertRaises(ArchiveStoreError):
                store.extract_archive_confined(archive, root, "var/log/restored/b")
            self.assertEqual(list(elsewhere.iterdir()), [])
            with self.assertRaises(ArchiveStoreError):
                store.extract_archive_confined(archive, root, "var/log/restored/a")  # existe deja

    def test_private_archives_are_created_owner_only(self):
        with tempfile.TemporaryDirectory() as tmp:
            source = Path(tmp) / "users.json"
            source.write_text("{}")
            store = ArchiveStore(Path(tmp) / "snapshots", private=True)
            archive = store.create_archive("s.tar.gz", [source])
            self.assertEqual(stat.S_IMODE(archive.stat().st_mode), 0o600)
            self.assertEqual(stat.S_IMODE((Path(tmp) / "snapshots").stat().st_mode), 0o700)
            with tarfile.open(archive) as tar:
                self.assertEqual(tar.getnames(), ["users.json"])

    def test_lock_never_follows_a_link(self):
        with tempfile.TemporaryDirectory() as tmp:
            victim = Path(tmp) / "victime"
            victim.write_text("x")
            victim.chmod(0o600)
            lock = Path(tmp) / "blocklist.json.lock"
            os.symlink(victim, lock)
            with exclusive_file_lock(lock, timeout_seconds=0.1) as held:
                self.assertFalse(held)
            self.assertEqual(stat.S_IMODE(victim.stat().st_mode), 0o600)

    def test_magnet_diagnostics_use_private_state(self):
        resolved = {"blocklist_file": "/p/var/lib/x.txt", "rules_dir": "/p/secure/waf/m.d/",
                    "alerts_log": "/p/var/log/a.log", "blocklist_log": "/p/var/log/b.log",
                    "rate_store_file": "/p/var/cache/r.lua"}
        isolated = isolate_magnet_paths(resolved, Path("/tmp/prive"))
        self.assertEqual(isolated["rules_dir"], "/p/secure/waf/m.d/")
        self.assertEqual(isolated["rate_store_file"], "/tmp/prive/r.lua")
        self.assertTrue(all(v.startswith("/tmp/prive/") for k, v in isolated.items() if k != "rules_dir"))


class TestCauseCWaf(unittest.TestCase):
    def test_polluted_content_type_body_is_inspected(self):
        body = b"GIF89a=1&id=1' UNION SELECT user FROM users"
        self.assertEqual(inspectable_body(body, "application/x-www-form-urlencoded,", DEFAULT_BINARY_FORMATS), body)
        self.assertEqual(inspectable_body(body, "image/gif", DEFAULT_BINARY_FORMATS), b"")

    def test_multipart_file_part_needs_exact_filename_parameter(self):
        boundary = "B"
        png = b"\x89PNG\r\n\x1a\n"
        fake = (b"--B\r\nContent-Disposition: form-data; name=\"xfilename=\"\r\n\r\n" + png + b"' OR 1=1\r\n--B--")
        self.assertIn(b"OR 1=1", inspectable_body(fake, f"multipart/form-data; boundary={boundary}",
                                                  DEFAULT_BINARY_FORMATS))
        long_line = b"--B\r\n" + b"content-disposition:" * 3200 + b"\r\n\r\nx\r\n--B--"
        started = time.perf_counter()
        inspectable_body(long_line, "multipart/form-data; boundary=B", DEFAULT_BINARY_FORMATS)
        self.assertLess(time.perf_counter() - started, 0.5)

    def test_shipped_body_rules_have_no_quadratic_backtracking(self):
        import re
        packs = {}
        for name in ("body-sqli.json", "body-cmdi.json", "body-xss.json"):
            data = json.loads((REPO / "secure" / "waf" / "rules" / name).read_text(encoding="utf-8"))
            for rule in data.get("rules", data):
                packs[rule["id"]] = re.compile(rule["pattern"], re.IGNORECASE)
        for rule_id, body in (("SQLI-005", " " * 65536), ("CMDI-001", "$(" * 32768), ("CMDI-002", "`" * 65536),
                              ("XSS-005", "<svg " * 13000), ("XSS-007", "<img " * 13000)):
            started = time.perf_counter()
            packs[rule_id].search(body)
            self.assertLess(time.perf_counter() - started, 1.0, rule_id)

    def test_active_defense_identity_ignores_user_agent(self):
        self.assertEqual(source_subject_id("203.0.113.9"), source_subject_id("203.0.113.9"))
        self.assertTrue(source_subject_id("203.0.113.9").startswith("203.0.113.9:"))
        self.assertTrue(source_subject_id("2001:db8::1").rpartition(":")[0] == "2001:db8::1")


class TestCauseDAdminWeb(unittest.TestCase):
    def test_admin_cookies_never_relayed(self):
        self.assertEqual(without_admin_cookies("a=1; omega_admin=tok; omega_admin_theme=dark; b=2"), "a=1; b=2")
        self.assertEqual(without_admin_cookies("omega_admin=tok"), "")
        zone = ProxyZone(url_prefix="/api/", upstreams=(UpstreamTarget(host="127.0.0.1", port=3000),))
        sent = build_outgoing_headers(_request("/api/x", [("Cookie", "omega_admin=tok; s=1")]), zone,
                                      zone.upstreams[0])
        self.assertEqual([v for n, v in sent if n.lower() == "cookie"], ["s=1"])
        sent = build_outgoing_headers(_request("/api/x", [("Cookie", "omega_admin=tok")]), zone, zone.upstreams[0])
        self.assertFalse(any(n.lower() == "cookie" for n, _ in sent))
        env = build_cgi_env(_request("/x.php", [("Cookie", "omega_admin=tok; PHPSESSID=1")]), "/srv/x.php", "/x.php",
                            "/srv", "x", 80)
        self.assertEqual(env["HTTP_COOKIE"], "PHPSESSID=1")

    def test_log_lines_split_on_newline_only(self):
        self.assertEqual(_decode("a\u0085b c\nd\r\n".encode()), ["a\u0085b c", "d"])
        self.assertEqual(sanitize_log_field("a\u0085b c\x7fd\x9be"), "a b c d e")

    def _app(self, tls=False):
        auth = AdminAuth(lambda: (), lambda: 0.0, lambda m: None, local_only=True, used_backup_codes=set,
                         mark_backup_code_used=lambda c: None)
        app = AdminWebApp(AdminWebSettings(allowed_networks=("127.0.0.0/8",)), auth, "prod")
        app._tls = tls
        return app

    def test_host_checked_without_tls(self):
        app = self._app()
        for host, status in (("127.0.0.1:8443", 200), ("localhost:8443", 200), ("[::1]:8443", 200),
                             ("rebind.attaquant.example:8443", 421), (f"{socket.gethostname()}:8443", 200)):
            reply = asyncio.run(app.handle(AdminRequest("127.0.0.1", "GET", "/connexion", (("Host", host),), b"")))
            self.assertEqual(reply.status, status, host)
        tls_app = self._app(tls=True)
        reply = asyncio.run(tls_app.handle(AdminRequest("127.0.0.1", "GET", "/connexion",
                                                        (("Host", "site.example:8443"),), b"")))
        self.assertEqual(reply.status, 200)

    def test_wrong_password_with_backup_shaped_code_waits_like_a_right_one(self):
        slept = []
        auth = AdminAuth(lambda: (), lambda: 0.0, lambda m: None, local_only=True, used_backup_codes=set,
                         mark_backup_code_used=lambda c: None, sleep=slept.append)
        self.assertEqual(auth.login("10.0.0.1", "inconnu", "faux", "abcd-efgh-j", "tableau").error, "invalid")
        self.assertEqual(len(slept), 1)
        self.assertGreater(slept[0], 0)
        auth.login("10.0.0.1", "inconnu", "faux", "123456", "tableau")
        self.assertEqual(len(slept), 1)  # code TOTP : aucun code de secours n'aurait ete essaye

    def test_token_only_sent_to_a_trusted_loopback_listener(self):
        from omega_serv.infrastructure.admin_web import remote_client
        with socket.socket() as listener:
            listener.bind(("127.0.0.1", 0))
            listener.listen()
            port = listener.getsockname()[1]
            self.assertTrue(remote_client._trusted_loopback_listener(port))
            with mock.patch.object(remote_client, "_loopback_listener_uids", return_value={4242}):
                self.assertFalse(remote_client._trusted_loopback_listener(port))


class TestCauseESecrets(unittest.TestCase):
    def test_openssl_passphrases_never_in_arguments(self):
        from omega_serv.domain.security.tls.entities import SelfSignedCertParams
        runner = _Runner()
        tool = OpensslCertificateTool(runner)
        with tempfile.TemporaryDirectory() as tmp:
            params = SelfSignedCertParams(common_name="x", key_password="phrase-secrete")
            tool.generate_self_signed(params, Path(tmp) / "k.pem", Path(tmp) / "c.pem")
            with mock.patch.object(OpensslCertificateTool, "_append_index_entry"):
                tool.sign_csr(Path(tmp) / "r.csr", Path(tmp) / "ca.key", Path(tmp) / "ca.pem", "phrase-ca",
                              Path(tmp) / "serial", Path(tmp) / "index", 30, Path(tmp) / "o.pem")
        for args, input_text in runner.calls:
            self.assertFalse(any("phrase" in arg for arg in args), args)
        self.assertEqual(runner.calls[0][1], "phrase-secrete\n")
        self.assertEqual(runner.calls[1][1], "phrase-ca\n")

    def test_credential_headers_always_masked(self):
        masked = redact_fields({"X-Api-Key": "k", "Proxy-Authorization": "p", "X-Auth-Token": "t",
                                "User-Agent": "ua"}, ())
        self.assertEqual(masked["User-Agent"], "ua")
        self.assertTrue(all(masked[name] == "***REDACTED***" for name in ("X-Api-Key", "Proxy-Authorization",
                                                                         "X-Auth-Token")))

    def test_launcher_imports_in_isolated_mode(self):
        self.assertIn('bin/python" -I -c "import omega_serv"', (REPO / "omega-serv.sh").read_text(encoding="utf-8"))


class TestCauseFDisplay(unittest.TestCase):
    def test_non_ip_forwarded_hop_falls_back_to_peer(self):
        headers = HttpHeaders.from_pairs([("Forwarded", 'for="=HYPERLINK(1)"'), ("X-Forwarded-For", "[x]")])
        for preference in (["forwarded"], ["x-forwarded-for"]):
            self.assertEqual(resolve_client_ip("127.0.0.1", headers, ["127.0.0.1/32"], preference), "127.0.0.1")
        good = HttpHeaders.from_pairs([("X-Forwarded-For", "203.0.113.7")])
        self.assertEqual(resolve_client_ip("127.0.0.1", good, ["127.0.0.1/32"], ["x-forwarded-for"]), "203.0.113.7")

    def test_csv_cells_never_formulas(self):
        self.assertEqual(_neutral_cell("=HYPERLINK(1)"), "'=HYPERLINK(1)")
        self.assertEqual(_neutral_cell("203.0.113.1"), "203.0.113.1")

    def test_ban_reason_printed_without_escape_sequences(self):
        from omega_serv.interfaces.cli.main import _printable
        self.assertEqual(_printable("motif\x1b[2J\x9b"), "motif?[2J?")



class TestIsolatedRelaunch(unittest.TestCase):
    """F35 : relance isolee (`-I`) qui execute quand meme le code du parent, jamais celui du dossier courant."""

    def test_child_ignores_the_current_directory_and_runs_the_given_tree(self):
        import subprocess
        import sys

        from omega_serv.domain.services.python_command import python_module_argv
        with tempfile.TemporaryDirectory() as name:
            work, tree = Path(name) / "courant", Path(name) / "arbre"
            (work / "sonde").mkdir(parents=True)
            (work / "sonde" / "__init__.py").write_text("")
            (work / "sonde" / "__main__.py").write_text("print('PIEGE')")
            (tree / "sonde").mkdir(parents=True)
            (tree / "sonde" / "__init__.py").write_text("")
            (tree / "sonde" / "__main__.py").write_text("import sys; print('ARBRE', sys.argv[1:])")
            done = subprocess.run(python_module_argv(sys.executable, "sonde", "a", "--b", source_root=str(tree)),
                                  cwd=work, capture_output=True, text=True, timeout=30, check=False,
                                  env={**os.environ, "PYTHONPATH": str(work)})
        self.assertEqual(done.stdout.strip(), "ARBRE ['a', '--b']", done.stderr)

    def test_default_tree_is_the_running_code(self):
        import omega_serv
        from omega_serv.domain.services.python_command import python_module_argv
        argv = python_module_argv("/x/python", "omega_serv", "serve")
        self.assertEqual(argv[1:3], ["-I", "-c"])
        self.assertEqual(argv[4:], [str(Path(omega_serv.__file__).resolve().parents[1]), "omega_serv", "serve"])



class TestSourceIndicators(unittest.TestCase):
    def test_fixed_source_fingerprint_is_never_exported_as_a_user_agent(self):
        from datetime import datetime, timezone

        from omega_serv.domain.security.active_defense.policies import (
            extract_indicator_candidates,
            source_subject_id,
        )
        observation = SimpleNamespace(observed_at=datetime(2026, 11, 20, tzinfo=timezone.utc), score_delta=40)
        incident = SimpleNamespace(subject_id=source_subject_id("2001:db8::1"), observations=[observation])
        self.assertEqual([(c.kind, c.value) for c in extract_indicator_candidates(incident)], [("ip", "2001:db8::1")])


if __name__ == "__main__":
    unittest.main()
