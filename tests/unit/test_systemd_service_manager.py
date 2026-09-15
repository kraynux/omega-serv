# Copyright (c) 2026 kraynux - kraynux@proton.me - Licence MIT (voir fichier LICENSE)
import unittest
from pathlib import Path
from unittest.mock import patch

from omega_serv.domain.services.exceptions import ServiceControlError, ServiceNotFoundError
from omega_serv.infrastructure.services.systemd_service_manager import SystemdServiceManager
from omega_serv.ports.process_runner_port import ProcessResult

_ROOT = "omega_serv.infrastructure.services.systemd_service_manager.running_as_root"

_STATUS_OUTPUT = """● omega-serv.service - OMEGA-SERV web server
     Loaded: loaded (/etc/systemd/system/omega-serv.service; enabled; preset: disabled)
     Active: active (running) since Sat 2026-09-06 10:00:00 UTC; 1h ago
"""


class _FakeProcessRunner:
    def __init__(self, responses: dict, *, interactive_auth_returncode: int = 0):
        self._responses = responses
        self.calls = []
        self.interactive_calls = []
        self._interactive_auth_returncode = interactive_auth_returncode

    def run(self, args, input_text=None, timeout=None):
        self.calls.append(args)
        key = tuple(args)
        if key in self._responses:
            return self._responses[key]
        return ProcessResult(returncode=1, stdout="", stderr="unmapped call")

    def run_interactive(self, args):
        # Simule une authentification sudo reussie par defaut (retour
        # utilisateur, bug reel corrige : `sudo -v` interactif AVANT
        # toute commande privilegiee capturee, voir _run_privileged) -
        # jamais comptee dans `self.calls`, qui ne suit que les appels
        # a `run()` (les commandes reelles, deja verifiees par les
        # assertions existantes de ce fichier).
        self.interactive_calls.append(args)
        return self._interactive_auth_returncode


class TestSystemdServiceManager(unittest.TestCase):
    @patch(_ROOT, return_value=True)
    def test_start_success(self, _mock_root):
        runner = _FakeProcessRunner({("systemctl", "start", "omega-serv"): ProcessResult(0, "", "")})
        manager = SystemdServiceManager(runner)
        self.assertTrue(manager.start("omega-serv"))

    @patch(_ROOT, return_value=True)
    def test_start_not_found(self, _mock_root):
        runner = _FakeProcessRunner({("systemctl", "start", "ghost"): ProcessResult(5, "", "Unit ghost.service not found.")})
        manager = SystemdServiceManager(runner)
        with self.assertRaises(ServiceNotFoundError):
            manager.start("ghost")

    @patch(_ROOT, return_value=True)
    def test_start_control_error(self, _mock_root):
        runner = _FakeProcessRunner({("systemctl", "start", "svc"): ProcessResult(1, "", "permission denied")})
        manager = SystemdServiceManager(runner)
        with self.assertRaises(ServiceControlError):
            manager.start("svc")

    @patch(_ROOT, return_value=True)
    def test_stop_restart_enable_disable_all_use_correct_verb(self, _mock_root):
        runner = _FakeProcessRunner({
            ("systemctl", "stop", "svc"): ProcessResult(0, "", ""),
            ("systemctl", "restart", "svc"): ProcessResult(0, "", ""),
            ("systemctl", "enable", "svc"): ProcessResult(0, "", ""),
            ("systemctl", "disable", "svc"): ProcessResult(0, "", ""),
        })
        manager = SystemdServiceManager(runner)
        self.assertTrue(manager.stop("svc"))
        self.assertTrue(manager.restart("svc"))
        self.assertTrue(manager.enable("svc"))
        self.assertTrue(manager.disable("svc"))

    @patch(_ROOT, return_value=True)
    def test_reload_success(self, _mock_root):
        # Retour utilisateur 2026-09-11 : distinct de restart - garde
        # les connexions actives, relit seulement la config deja codee
        # cote applicatif (SIGHUP via ExecReload=, systemd_unit.py).
        runner = _FakeProcessRunner({("systemctl", "reload", "svc"): ProcessResult(0, "", "")})
        manager = SystemdServiceManager(runner)
        self.assertTrue(manager.reload("svc"))

    @patch(_ROOT, return_value=True)
    def test_reload_fails_cleanly_without_exec_reload(self, _mock_root):
        # Si l'unite installee n'a pas ExecReload= (ancienne unite
        # jamais reinstallee depuis ce correctif), systemd refuse
        # l'operation - remonte comme un ServiceControlError normal,
        # pas un cas special.
        runner = _FakeProcessRunner({
            ("systemctl", "reload", "svc"): ProcessResult(1, "", "Job type reload is not applicable.")
        })
        manager = SystemdServiceManager(runner)
        with self.assertRaises(ServiceControlError):
            manager.reload("svc")

    def test_status_parses_real_output_shape(self):
        runner = _FakeProcessRunner({
            ("systemctl", "status", "omega-serv"): ProcessResult(0, _STATUS_OUTPUT, ""),
            ("systemctl", "is-enabled", "omega-serv"): ProcessResult(0, "enabled\n", ""),
        })
        manager = SystemdServiceManager(runner)
        status = manager.status("omega-serv")
        self.assertTrue(status.active)
        self.assertTrue(status.enabled)
        self.assertEqual(status.state, "active")
        self.assertEqual(status.sub_state, "running")
        self.assertIn("OMEGA-SERV web server", status.description)
        self.assertTrue(status.is_running)

    def test_status_not_found(self):
        runner = _FakeProcessRunner({("systemctl", "status", "ghost"): ProcessResult(4, "", "")})
        manager = SystemdServiceManager(runner)
        with self.assertRaises(ServiceNotFoundError):
            manager.status("ghost")

    def test_is_active_true_false(self):
        runner = _FakeProcessRunner({
            ("systemctl", "is-active", "up"): ProcessResult(0, "active\n", ""),
            ("systemctl", "is-active", "down"): ProcessResult(3, "inactive\n", ""),
        })
        manager = SystemdServiceManager(runner)
        self.assertTrue(manager.is_active("up"))
        self.assertFalse(manager.is_active("down"))

    def test_is_available(self):
        runner = _FakeProcessRunner({("systemctl", "--version"): ProcessResult(0, "systemd 255", "")})
        manager = SystemdServiceManager(runner)
        self.assertTrue(manager.is_available())

    def test_manager_type(self):
        manager = SystemdServiceManager(_FakeProcessRunner({}))
        self.assertEqual(manager.manager_type(), "systemd")


class TestSystemdServiceManagerPrivilegeElevation(unittest.TestCase):
    """Plan interface §3.6 (2026-09-08) : elevation ponctuelle par
    action, jamais en exigeant que l'application entiere soit lancee en
    root."""

    @patch(_ROOT, return_value=False)
    def test_control_operation_prefixed_with_sudo_when_not_root(self, _mock_root):
        runner = _FakeProcessRunner({("sudo", "systemctl", "start", "svc"): ProcessResult(0, "", "")})
        manager = SystemdServiceManager(runner)
        self.assertTrue(manager.start("svc"))
        self.assertEqual(runner.calls, [["sudo", "systemctl", "start", "svc"]])

    @patch(_ROOT, return_value=True)
    def test_control_operation_not_prefixed_when_already_root(self, _mock_root):
        runner = _FakeProcessRunner({("systemctl", "start", "svc"): ProcessResult(0, "", "")})
        manager = SystemdServiceManager(runner)
        self.assertTrue(manager.start("svc"))
        self.assertEqual(runner.calls, [["systemctl", "start", "svc"]])

    @patch(_ROOT, return_value=False)
    def test_status_and_is_active_never_prefixed_with_sudo(self, _mock_root):
        runner = _FakeProcessRunner({
            ("systemctl", "status", "svc"): ProcessResult(0, _STATUS_OUTPUT, ""),
            ("systemctl", "is-enabled", "svc"): ProcessResult(0, "enabled\n", ""),
            ("systemctl", "is-active", "svc"): ProcessResult(0, "active\n", ""),
        })
        manager = SystemdServiceManager(runner)
        manager.status("svc")
        manager.is_active("svc")
        self.assertTrue(all(call[0] != "sudo" for call in runner.calls))

    @patch(_ROOT, return_value=False)
    def test_reload_daemon_prefixed_with_sudo_when_not_root(self, _mock_root):
        runner = _FakeProcessRunner({("sudo", "systemctl", "daemon-reload"): ProcessResult(0, "", "")})
        manager = SystemdServiceManager(runner)
        self.assertTrue(manager.reload_daemon())

    @patch(_ROOT, return_value=False)
    def test_write_unit_file_uses_sudo_tee_with_content_as_stdin(self, _mock_root):
        class _RecordingRunner(_FakeProcessRunner):
            def run(self, args, input_text=None, timeout=None):
                self.calls.append((args, input_text))
                return ProcessResult(0, "", "")

        runner = _RecordingRunner({})
        manager = SystemdServiceManager(runner)
        manager.write_unit_file(Path("/etc/systemd/system/omega-serv.service"), "[Unit]\n...")
        self.assertEqual(runner.calls, [(["sudo", "tee", "/etc/systemd/system/omega-serv.service"], "[Unit]\n...")])

    @patch(_ROOT, return_value=False)
    def test_write_unit_file_raises_on_failure(self, _mock_root):
        runner = _FakeProcessRunner({})  # unmapped -> returncode 1
        manager = SystemdServiceManager(runner)
        with self.assertRaises(ServiceControlError):
            manager.write_unit_file(Path("/etc/systemd/system/omega-serv.service"), "content")

    @patch(_ROOT, return_value=False)
    def test_remove_unit_file_uses_sudo_rm(self, _mock_root):
        runner = _FakeProcessRunner({("sudo", "rm", "-f", "/etc/systemd/system/omega-serv.service"): ProcessResult(0, "", "")})
        manager = SystemdServiceManager(runner)
        manager.remove_unit_file(Path("/etc/systemd/system/omega-serv.service"))
        self.assertEqual(runner.calls, [["sudo", "rm", "-f", "/etc/systemd/system/omega-serv.service"]])

    @patch(_ROOT, return_value=True)
    def test_remove_unit_file_not_prefixed_when_already_root(self, _mock_root):
        runner = _FakeProcessRunner({("rm", "-f", "/etc/systemd/system/omega-serv.service"): ProcessResult(0, "", "")})
        manager = SystemdServiceManager(runner)
        manager.remove_unit_file(Path("/etc/systemd/system/omega-serv.service"))
        self.assertEqual(runner.calls, [["rm", "-f", "/etc/systemd/system/omega-serv.service"]])


class TestSystemdServiceManagerSudoAuthentication(unittest.TestCase):
    """Retour utilisateur (bug reel) : "le mot de passe est
    systematiquement refuse, texte qui s'incruste de facon aleatoire" -
    une commande privilegiee capturee (`self._runner.run`, sortie
    redirigee vers un tube) ne peut jamais afficher/gerer correctement
    une invite de mot de passe sudo sur le vrai terminal. `_run_privileged`
    authentifie desormais separement via un appel PLEINEMENT interactif
    (`sudo -v`, jamais de capture) avant la commande reelle capturee."""

    @patch(_ROOT, return_value=False)
    def test_authenticates_interactively_before_the_captured_command(self, _mock_root):
        runner = _FakeProcessRunner({("sudo", "systemctl", "start", "svc"): ProcessResult(0, "", "")})
        manager = SystemdServiceManager(runner)
        self.assertTrue(manager.start("svc"))
        self.assertEqual(runner.interactive_calls, [["sudo", "-v"]])
        self.assertEqual(runner.calls, [["sudo", "systemctl", "start", "svc"]])

    @patch(_ROOT, return_value=False)
    def test_failed_or_cancelled_authentication_never_runs_the_real_command(self, _mock_root):
        runner = _FakeProcessRunner(
            {("sudo", "systemctl", "start", "svc"): ProcessResult(0, "", "")},
            interactive_auth_returncode=1,
        )
        manager = SystemdServiceManager(runner)
        with self.assertRaises(ServiceControlError):
            manager.start("svc")
        self.assertEqual(runner.interactive_calls, [["sudo", "-v"]])
        self.assertEqual(runner.calls, [], "la commande reelle ne doit jamais s'executer sans authentification reussie")

    @patch(_ROOT, return_value=True)
    def test_no_interactive_authentication_needed_when_already_root(self, _mock_root):
        runner = _FakeProcessRunner({("systemctl", "start", "svc"): ProcessResult(0, "", "")})
        manager = SystemdServiceManager(runner)
        self.assertTrue(manager.start("svc"))
        self.assertEqual(runner.interactive_calls, [], "aucune authentification sudo necessaire en etant deja root")

    @patch(_ROOT, return_value=False)
    def test_authentication_reused_across_multiple_privileged_calls_in_the_same_workflow(self, _mock_root):
        # Un seul flux (ex. installation du service) enchaine plusieurs
        # appels prives (groupadd, useradd, tee...) - chacun authentifie
        # separement ici (sudo lui-meme evite de re-demander le mot de
        # passe si son cache est encore recent, invisible a ce niveau).
        runner = _FakeProcessRunner({
            ("sudo", "groupadd", "--system", "omega-serv"): ProcessResult(0, "", ""),
            (
                "sudo", "useradd", "--system", "--no-create-home", "--shell", "/usr/sbin/nologin",
                "--gid", "omega-serv", "omega-serv",
            ): ProcessResult(0, "", ""),
        })
        manager = SystemdServiceManager(runner)
        manager.create_system_user("omega-serv", "omega-serv")
        self.assertEqual(runner.interactive_calls, [["sudo", "-v"], ["sudo", "-v"]])


class TestSystemdServiceManagerCreateSystemUser(unittest.TestCase):
    """Retour utilisateur 2026-09-10 : l'unite generee referencait
    toujours User=/Group= dedies sans que rien ne les cree jamais - le
    service echouait systematiquement a chaque premier demarrage."""

    @patch(_ROOT, return_value=False)
    def test_creates_group_then_user_with_sudo(self, _mock_root):
        runner = _FakeProcessRunner({
            ("sudo", "groupadd", "--system", "omega-serv"): ProcessResult(0, "", ""),
            (
                "sudo", "useradd", "--system", "--no-create-home", "--shell", "/usr/sbin/nologin",
                "--gid", "omega-serv", "omega-serv",
            ): ProcessResult(0, "", ""),
        })
        manager = SystemdServiceManager(runner)
        manager.create_system_user("omega-serv", "omega-serv")
        self.assertEqual(
            runner.calls,
            [
                ["sudo", "groupadd", "--system", "omega-serv"],
                [
                    "sudo", "useradd", "--system", "--no-create-home", "--shell", "/usr/sbin/nologin",
                    "--gid", "omega-serv", "omega-serv",
                ],
            ],
        )

    @patch(_ROOT, return_value=True)
    def test_idempotent_when_group_and_user_already_exist(self, _mock_root):
        # groupadd/useradd renvoient le code 9 si l'entite existe deja -
        # doit etre traite comme un succes, pas une erreur, sinon
        # reinstaller l'unite echouerait a chaque fois apres la premiere.
        runner = _FakeProcessRunner({
            ("groupadd", "--system", "omega-serv"): ProcessResult(9, "", "group 'omega-serv' already exists"),
            (
                "useradd", "--system", "--no-create-home", "--shell", "/usr/sbin/nologin",
                "--gid", "omega-serv", "omega-serv",
            ): ProcessResult(9, "", "user 'omega-serv' already exists"),
        })
        manager = SystemdServiceManager(runner)
        manager.create_system_user("omega-serv", "omega-serv")  # ne leve pas

    @patch(_ROOT, return_value=True)
    def test_raises_on_genuine_groupadd_failure(self, _mock_root):
        runner = _FakeProcessRunner({
            ("groupadd", "--system", "omega-serv"): ProcessResult(1, "", "permission denied"),
        })
        manager = SystemdServiceManager(runner)
        with self.assertRaises(ServiceControlError):
            manager.create_system_user("omega-serv", "omega-serv")

    @patch(_ROOT, return_value=True)
    def test_raises_on_genuine_useradd_failure(self, _mock_root):
        runner = _FakeProcessRunner({
            ("groupadd", "--system", "omega-serv"): ProcessResult(0, "", ""),
            (
                "useradd", "--system", "--no-create-home", "--shell", "/usr/sbin/nologin",
                "--gid", "omega-serv", "omega-serv",
            ): ProcessResult(1, "", "permission denied"),
        })
        manager = SystemdServiceManager(runner)
        with self.assertRaises(ServiceControlError):
            manager.create_system_user("omega-serv", "omega-serv")


class TestSystemdServiceManagerRemoveSystemUser(unittest.TestCase):
    """Symetrique de TestSystemdServiceManagerCreateSystemUser
    (OMEGA-SERV_PLAN-DETAILLE_MULTI_INSTANCE.md §9 Phase E)."""

    @patch(_ROOT, return_value=True)
    def test_removes_user_then_group(self, _mock_root):
        runner = _FakeProcessRunner({
            ("userdel", "omega-serv"): ProcessResult(0, "", ""),
            ("groupdel", "omega-serv"): ProcessResult(0, "", ""),
        })
        manager = SystemdServiceManager(runner)
        manager.remove_system_user("omega-serv", "omega-serv")
        self.assertEqual(runner.calls, [["userdel", "omega-serv"], ["groupdel", "omega-serv"]])

    @patch(_ROOT, return_value=True)
    def test_idempotent_when_user_and_group_already_absent(self, _mock_root):
        # userdel/groupdel renvoient le code 6 si l'entite n'existe pas
        # (deja absente) - traite comme un succes, jamais une erreur.
        runner = _FakeProcessRunner({
            ("userdel", "omega-serv"): ProcessResult(6, "", "user 'omega-serv' does not exist"),
            ("groupdel", "omega-serv"): ProcessResult(6, "", "group 'omega-serv' does not exist"),
        })
        manager = SystemdServiceManager(runner)
        manager.remove_system_user("omega-serv", "omega-serv")  # ne leve pas

    @patch(_ROOT, return_value=True)
    def test_raises_on_genuine_userdel_failure(self, _mock_root):
        runner = _FakeProcessRunner({
            ("userdel", "omega-serv"): ProcessResult(1, "", "permission denied"),
        })
        manager = SystemdServiceManager(runner)
        with self.assertRaises(ServiceControlError):
            manager.remove_system_user("omega-serv", "omega-serv")

    @patch(_ROOT, return_value=True)
    def test_raises_on_genuine_groupdel_failure(self, _mock_root):
        runner = _FakeProcessRunner({
            ("userdel", "omega-serv"): ProcessResult(0, "", ""),
            ("groupdel", "omega-serv"): ProcessResult(8, "", "cannot remove the user's primary group"),
        })
        manager = SystemdServiceManager(runner)
        with self.assertRaises(ServiceControlError):
            manager.remove_system_user("omega-serv", "omega-serv")


class TestSystemdServiceManagerGrantDirectoryAccess(unittest.TestCase):
    """Retour utilisateur 2026-09-10, second vrai bug trouve juste apres
    la creation du compte systeme dedie : `journalctl` a montre le
    service en boucle de redemarrage (PermissionError en ecrivant le
    fichier PID) - `ReadWritePaths=` (systemd_unit.py) leve uniquement
    la restriction sandbox de systemd, jamais les permissions Unix
    classiques du repertoire, restees `kraynux:kraynux 755` sans droit
    d'ecriture pour le compte de service dedie."""

    @patch(_ROOT, return_value=False)
    def test_runs_chgrp_chmod_setgid_usermod_in_order_with_sudo(self, _mock_root):
        path = Path("/home/kraynux/DEV/SERV/omega-serv/var")
        runner = _FakeProcessRunner({
            ("sudo", "chgrp", "-R", "omega-serv", str(path)): ProcessResult(0, "", ""),
            ("sudo", "chmod", "-R", "g+rwX", str(path)): ProcessResult(0, "", ""),
            ("sudo", "find", str(path), "-type", "d", "-exec", "chmod", "g+s", "{}", "+"): ProcessResult(0, "", ""),
            ("sudo", "usermod", "-aG", "omega-serv", "kraynux"): ProcessResult(0, "", ""),
        })
        manager = SystemdServiceManager(runner)
        manager.grant_directory_access(path, "omega-serv", "kraynux")
        self.assertEqual(
            runner.calls,
            [
                ["sudo", "chgrp", "-R", "omega-serv", str(path)],
                ["sudo", "chmod", "-R", "g+rwX", str(path)],
                ["sudo", "find", str(path), "-type", "d", "-exec", "chmod", "g+s", "{}", "+"],
                ["sudo", "usermod", "-aG", "omega-serv", "kraynux"],
            ],
        )

    @patch(_ROOT, return_value=True)
    def test_not_prefixed_when_already_root(self, _mock_root):
        path = Path("/srv/omega-serv/var")
        runner = _FakeProcessRunner({
            ("chgrp", "-R", "omega-serv", str(path)): ProcessResult(0, "", ""),
            ("chmod", "-R", "g+rwX", str(path)): ProcessResult(0, "", ""),
            ("find", str(path), "-type", "d", "-exec", "chmod", "g+s", "{}", "+"): ProcessResult(0, "", ""),
            ("usermod", "-aG", "omega-serv", "kraynux"): ProcessResult(0, "", ""),
        })
        manager = SystemdServiceManager(runner)
        manager.grant_directory_access(path, "omega-serv", "kraynux")
        self.assertTrue(all(call[0] != "sudo" for call in runner.calls))

    @patch(_ROOT, return_value=True)
    def test_raises_on_first_failing_step(self, _mock_root):
        path = Path("/srv/omega-serv/var")
        runner = _FakeProcessRunner({
            ("chgrp", "-R", "omega-serv", str(path)): ProcessResult(1, "", "operation not permitted"),
        })
        manager = SystemdServiceManager(runner)
        with self.assertRaises(ServiceControlError):
            manager.grant_directory_access(path, "omega-serv", "kraynux")
        # S'arrete au premier echec - jamais de chmod/find/usermod apres
        # un chgrp rate.
        self.assertEqual(len(runner.calls), 1)


if __name__ == "__main__":
    unittest.main()
