# Copyright (c) 2026 kraynux - kraynux@proton.me - Licence MIT (voir fichier LICENSE)
"""« Relier au maître » entre deux instances de cette machine (ecran Instances, 2026-11-16) : ordre des commandes,
jeton jamais sur la ligne de commande, remplacement seulement sur demande, retour arriere si le maitre refuse
l'ajout ; lanceur (environnement virtuel de l'instance visee, `-I`) ; adresse locale de l'administration."""
from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from omega_serv.application.admin_web.local_link import LocalLinkRequest, link_local_master
from omega_serv.domain.admin_web.master import local_admin_address
from omega_serv.infrastructure.instances.instance_command_runner import InstanceCommandRunner
from omega_serv.interfaces.cli.admin_web_commands import EXIT_MASTER_EXISTS
from omega_serv.ports.instance_command_port import CommandReply
from omega_serv.ports.process_runner_port import ProcessResult

MASTER = Path("/srv/maitre")
FOLLOWER = Path("/srv/suivie")
IDENTITY = json.dumps({"maitre_id": "b" * 32, "nom": "maitre"})
ACCEPTED = json.dumps({"jeton": "jeton-secret", "empreinte": "c" * 64, "port": 8444, "nom": "suivie"})


class _Commands:
    def __init__(self, replies: dict[str, CommandReply]) -> None:
        self.replies = replies
        self.calls: list[tuple[Path, tuple[str, ...], str]] = []

    def run(self, root, arguments, stdin=""):
        arguments = tuple(arguments)
        self.calls.append((root, arguments, stdin))
        return self.replies.get(" ".join(arguments[1:3]), CommandReply(0, "", ""))


def _request(**changes) -> LocalLinkRequest:
    values = {"follower_root": FOLLOWER, "follower_name": "suivie", "follower_address": "127.0.0.1",
              "follower_port": 8444, "master_root": MASTER, "rights": "administration", "replace": False}
    values.update(changes)
    return LocalLinkRequest(**values)


class TestLinkLocalMaster(unittest.TestCase):
    def test_identity_then_accept_on_the_follower_then_add_on_the_master(self):
        commands = _Commands({"instances identity": CommandReply(0, "banniere\n" + IDENTITY + "\n", ""),
                              "master accept": CommandReply(0, ACCEPTED, "")})
        outcome = link_local_master(commands, _request())
        self.assertTrue(outcome.ok, outcome.message)
        (root1, identity, _), (root2, accept, _), (root3, add, stdin) = commands.calls
        self.assertEqual((root1, root2, root3), (MASTER, FOLLOWER, MASTER))
        self.assertEqual(identity, ("admin-web", "instances", "identity"))
        self.assertEqual(accept, ("admin-web", "master", "accept", "--master-id", "b" * 32, "--master-name",
                                  "maitre", "--rights", "administration"))
        self.assertEqual(add, ("admin-web", "instances", "add", "127.0.0.1", "8444", "--fingerprint", "c" * 64,
                               "--name", "suivie"))
        self.assertEqual(stdin, "jeton-secret\n")
        self.assertIn("maitre", outcome.message)

    def test_existing_master_is_reported_and_replaced_only_on_request(self):
        commands = _Commands({"instances identity": CommandReply(0, IDENTITY, ""),
                              "master accept": CommandReply(EXIT_MASTER_EXISTS, "", "Un autre maître (ancien)")})
        outcome = link_local_master(commands, _request())
        self.assertFalse(outcome.ok)
        self.assertTrue(outcome.exists)
        self.assertIn("ancien", outcome.message)
        self.assertEqual(len(commands.calls), 2)  # rien d'ajoute chez le maitre
        commands = _Commands({"instances identity": CommandReply(0, IDENTITY, ""),
                              "master accept": CommandReply(0, ACCEPTED, "")})
        self.assertTrue(link_local_master(commands, _request(replace=True)).ok)
        self.assertEqual(commands.calls[1][1][-1], "--replace")

    def test_master_refusing_the_addition_revokes_the_new_master_on_the_follower(self):
        commands = _Commands({"instances identity": CommandReply(0, IDENTITY, ""),
                              "master accept": CommandReply(0, ACCEPTED, ""),
                              "instances add": CommandReply(1, "", "Trop d'instances suivies.")})
        outcome = link_local_master(commands, _request())
        self.assertFalse(outcome.ok)
        self.assertIn("Trop d'instances suivies.", outcome.message)
        self.assertEqual(commands.calls[-1][:2], (FOLLOWER, ("admin-web", "master", "revoke")))

    def test_failures_stop_before_anything_is_written(self):
        commands = _Commands({"instances identity": CommandReply(127, "", "environnement virtuel introuvable")})
        outcome = link_local_master(commands, _request())
        self.assertFalse(outcome.ok)
        self.assertIn("environnement virtuel introuvable", outcome.message)
        self.assertEqual(len(commands.calls), 1)
        commands = _Commands({"instances identity": CommandReply(0, IDENTITY, ""),
                              "master accept": CommandReply(0, "pas du JSON", "")})
        self.assertFalse(link_local_master(commands, _request()).ok)
        self.assertEqual(len(commands.calls), 2)
        self.assertFalse(link_local_master(commands, _request(master_root=FOLLOWER)).ok)  # son propre maitre
        self.assertFalse(link_local_master(commands, _request(rights="tout")).ok)
        self.assertEqual(len(commands.calls), 2)


class _Process:
    def __init__(self) -> None:
        self.calls: list[tuple[list[str], str | None]] = []

    def run(self, args, input_text=None, timeout=None):
        self.calls.append((args, input_text))
        return ProcessResult(0, "sortie", "")

    def run_interactive(self, args):
        return 0


class TestInstanceCommandRunner(unittest.TestCase):
    def test_runs_the_target_instance_venv_isolated_with_its_own_configuration(self):
        with tempfile.TemporaryDirectory() as name:
            root = Path(name)
            (root / ".venv" / "bin").mkdir(parents=True)
            (root / ".venv" / "bin" / "python").touch()
            process = _Process()
            reply = InstanceCommandRunner(process).run(root, ("admin-web", "instances", "identity"), stdin="x\n")
        self.assertEqual(reply, CommandReply(0, "sortie", ""))
        (args, stdin), = process.calls
        self.assertEqual(args[:3], [str(root / ".venv" / "bin" / "python"), "-I", "-c"])
        self.assertEqual(args[4:], [str(root / "src"), "omega_serv", "--config",  # code de l'instance visee
                                    str(root / "config" / "omega-serve.json"), "admin-web", "instances", "identity"])
        self.assertEqual(stdin, "x\n")

    def test_missing_venv_is_reported_without_running_anything(self):
        process = _Process()
        reply = InstanceCommandRunner(process).run(Path("/nulle/part"), ("admin-web",))
        self.assertEqual(reply.code, 127)
        self.assertEqual(process.calls, [])


class TestLocalAdminAddress(unittest.TestCase):
    def test_loopback_when_listening_everywhere_otherwise_the_bind_address(self):
        self.assertEqual(local_admin_address("0.0.0.0"), "127.0.0.1")
        self.assertEqual(local_admin_address("::"), "::1")
        self.assertEqual(local_admin_address("localhost"), "127.0.0.1")
        self.assertEqual(local_admin_address("127.0.0.1"), "127.0.0.1")
        self.assertEqual(local_admin_address("192.168.1.20"), "192.168.1.20")


if __name__ == "__main__":
    unittest.main()
