# Copyright (c) 2026 kraynux - kraynux@proton.me - Licence MIT (voir fichier LICENSE)
"""Lot 8 du tableau de bord web (OMEGA-SERV_PLAN-DETAILLE_TABLEAU_DE_BORD_WEB.md §9.4) : bilan « prêt / ce qui
manque », etat ecrit par le processus d'administration, certificat genere avec les droits du groupe du service,
essai d'ecoute reel, port par defaut 9643."""
from __future__ import annotations

import grp
import json
import os
import socket
import stat
import tempfile
import unittest
from pathlib import Path

from omega_serv.application.admin_web import certificate_setup
from omega_serv.application.admin_web.readiness import (
    ACTION_ACCOUNTS,
    ACTION_CERTIFICATE,
    ACTION_ENABLE,
    ACTION_RELOAD,
    ACTION_RESTART,
    ReadinessFacts,
    admin_web_readiness,
)
from omega_serv.domain.admin_web.accounts import AdminAccount
from omega_serv.domain.admin_web.run_state import AdminRunState
from omega_serv.domain.admin_web.settings import DEFAULT_PORT, AdminWebSettings
from omega_serv.domain.config.entities import OmegaServConfig
from omega_serv.domain.config.option import Option
from omega_serv.domain.instances.entities import InstanceEntry
from omega_serv.infrastructure.admin_web.run_state_store import AdminRunStateStore
from omega_serv.infrastructure.admin_web.setup import SystemAdminWebSetup
from omega_serv.infrastructure.filesystem.local_filesystem import LocalFilesystem
from omega_serv.ports.admin_web_setup_port import (
    LISTEN_IN_USE,
    LISTEN_NO_ADDRESS,
    SHARE_NEEDS_PRIVILEGE,
    SHARE_NO_GROUP,
)
from omega_serv.ports.process_runner_port import ProcessResult

ADMIN = AdminAccount("admin", "x", "administration")
ADMIN_TOTP = AdminAccount("admin", "x", "administration", totp_secret="JBSWY3DPEHPK3PXP")


def _config(enabled=True, **settings) -> OmegaServConfig:
    config = OmegaServConfig()
    from dataclasses import replace

    return replace(config, options={**config.options, "admin_web": Option("admin_web", enabled, settings)})


def _actions(items):
    return [item.action for item in items if item.action]


def _texts(items):
    return "\n".join(item.text for item in items)


def _listening(bind="127.0.0.1", port=DEFAULT_PORT):
    return AdminRunState(os.getpid(), True, bind, port)


class TestReadiness(unittest.TestCase):
    def test_inactive_option_offers_enable_and_never_restart(self):
        items = admin_web_readiness(_config(enabled=False), ReadinessFacts(accounts=(ADMIN,)))
        self.assertEqual(items[0].ok, False)
        self.assertEqual(_actions(items), [ACTION_ENABLE])
        self.assertIn("127.0.0.1", _texts(items))  # depuis cette machine seulement

    def test_everything_ready_on_the_local_network(self):
        config = _config(bind="0.0.0.0", tls="own")
        facts = ReadinessFacts(accounts=(ADMIN_TOTP,), run_state=_listening("0.0.0.0"), service_active=True,
                               addresses=("127.0.0.1", "192.168.1.107", "100.64.0.3", "fe80::1"))
        items = admin_web_readiness(config, facts)
        self.assertEqual(_actions(items), [])
        self.assertNotIn(False, [item.ok for item in items])
        self.assertIn("https://192.168.1.107:9643/, https://100.64.0.3:9643/", _texts(items))

    def test_missing_certificate_accounts_and_totp(self):
        config = _config(bind="192.168.1.107", tls="own")
        items = admin_web_readiness(config, ReadinessFacts(certificate_present=(False, False), accounts=()))
        self.assertEqual(_actions(items)[:2], [ACTION_CERTIFICATE, ACTION_ACCOUNTS])
        items = admin_web_readiness(config, ReadinessFacts(accounts=(ADMIN,)))
        self.assertIn(ACTION_ACCOUNTS, _actions(items))
        self.assertIn("TOTP", _texts(items))
        site = admin_web_readiness(_config(bind="192.168.1.107", tls="site"),
                                   ReadinessFacts(certificate_present=(False, True), accounts=(ADMIN_TOTP,)))
        self.assertNotIn(ACTION_CERTIFICATE, _actions(site))  # certificat du site : ecran TLS
        self.assertIn("TLS", _texts(site))

    def test_listening_states(self):
        config = _config()
        stopped = admin_web_readiness(config, ReadinessFacts(accounts=(ADMIN,), service_active=False))
        self.assertEqual(_actions(stopped), [ACTION_RESTART])
        never = admin_web_readiness(config, ReadinessFacts(accounts=(ADMIN,), service_active=True))
        self.assertEqual(_actions(never), [ACTION_RESTART])
        failed = AdminRunState(os.getpid(), False, "127.0.0.1", DEFAULT_PORT, "listen", "Address already in use")
        items = admin_web_readiness(config, ReadinessFacts(accounts=(ADMIN,), run_state=failed))
        self.assertIn("127.0.0.1:9643", _texts(items))
        self.assertIn("Address already in use", _texts(items))
        old = admin_web_readiness(config, ReadinessFacts(accounts=(ADMIN,), run_state=_listening(port=8443)))
        self.assertEqual(_actions(old), [ACTION_RELOAD])
        ok = admin_web_readiness(config, ReadinessFacts(accounts=(ADMIN,), run_state=_listening()))
        self.assertEqual(_actions(ok), [])

    def test_firewall_signalled_only_off_this_machine_and_other_instances_ports(self):
        local = admin_web_readiness(_config(), ReadinessFacts(accounts=(ADMIN,), firewall="ufw"))
        self.assertNotIn("ufw", _texts(local))
        other = InstanceEntry(name="test", path=Path("/x"), bind="0.0.0.0", port=DEFAULT_PORT, service_name="t",
                              created_at="2026-11-17T00:00:00Z")
        remote = admin_web_readiness(_config(bind="0.0.0.0", tls="own"),
                                     ReadinessFacts(accounts=(ADMIN_TOTP,), firewall="ufw", others=((other, None),)))
        texts = _texts(remote)
        self.assertIn("ufw", texts)
        self.assertIn("9643/tcp", texts)
        self.assertIn("'test'", texts)


class TestRunState(unittest.TestCase):
    def test_round_trip_validation_and_dead_process(self):
        state = AdminRunState(os.getpid(), False, "0.0.0.0", 9643, "listen", "occupé")
        self.assertEqual(AdminRunState.from_dict(state.to_dict()), state)
        self.assertIsNone(AdminRunState.from_dict({"pid": "1", "listening": True}))
        self.assertIsNone(AdminRunState.from_dict({"pid": 0, "listening": True}))
        self.assertEqual(AdminRunState.from_dict({"pid": 5, "listening": False, "problem": "???"}).problem, "config")
        with tempfile.TemporaryDirectory() as name:
            store = AdminRunStateStore(LocalFilesystem(), Path(name))
            self.assertIsNone(store.load())
            store.save(state)
            self.assertEqual(store.load(), state)
            store.save(AdminRunState(2 ** 22 + 12345, True))  # processus disparu : ignore
            self.assertIsNone(store.load())


class _Tool:
    def __init__(self, fail=False):
        self.fail, self.params = fail, None

    def generate_self_signed(self, params, key_path, cert_path):
        if self.fail:
            raise OSError("openssl absent")
        self.params = params
        key_path.parent.mkdir(parents=True, exist_ok=True)
        key_path.write_text("cle")
        cert_path.write_text("certificat")


class _Setup:
    def __init__(self, share_results=("",)):
        self.results = list(share_results)
        self.calls = []

    def machine_names(self):
        return "machine", ("127.0.0.1", "192.168.1.107")

    def share_with_group(self, directories, key, certificate, group, *, privileged):
        self.calls.append((directories, key, certificate, group, privileged))
        return self.results.pop(0)


class TestCertificateSetup(unittest.TestCase):
    def setUp(self):
        self.root = Path(tempfile.mkdtemp())
        self.addCleanup(lambda: __import__("shutil").rmtree(self.root, ignore_errors=True))
        self.settings = AdminWebSettings(bind="100.64.0.3", tls="own")

    def test_names_addresses_and_directories(self):
        params = certificate_setup.certificate_params(self.settings, "machine", ("127.0.0.1", "192.168.1.107"))
        self.assertEqual(params.san_dns, ("machine", "localhost"))
        self.assertEqual(params.san_ip, ("127.0.0.1", "192.168.1.107", "100.64.0.3"))
        self.assertEqual(params.key_type, "ecdsa-p256")
        root = self.root.resolve()
        directories = certificate_setup.shared_directories(
            root, root / "secure/certificates/admin/admin.pem", root / "secure/certificates/admin/admin.key")
        self.assertEqual(directories, (root / "secure/certificates", root / "secure/certificates/admin"))
        self.assertEqual(certificate_setup.shared_directories(root, root / "certs/a.pem", root / "certs/a.key"),
                         (root / "certs",))

    def test_generate_keeps_a_copy_and_refuses_paths_outside(self):
        key = self.root / "secure/certificates/admin/admin.key"
        key.parent.mkdir(parents=True)
        key.write_text("ancienne cle")
        tool = _Tool()
        outcome = certificate_setup.generate(tool, _Setup(), LocalFilesystem(), self.root, self.settings)
        self.assertTrue(outcome.ok, outcome.message)
        self.assertEqual((key.parent / "admin.key.ancien").read_text(), "ancienne cle")
        self.assertEqual(key.read_text(), "cle")
        self.assertIn("100.64.0.3", tool.params.san_ip)
        outside = AdminWebSettings(tls="own", certificate_path="../ailleurs.pem")
        self.assertFalse(certificate_setup.generate(_Tool(), _Setup(), LocalFilesystem(), self.root, outside).ok)
        self.assertFalse(certificate_setup.generate(_Tool(fail=True), _Setup(), LocalFilesystem(), self.root,
                                                    self.settings).ok)

    def test_share_outcomes(self):
        for result, ok, privilege in (("", True, False), (SHARE_NO_GROUP, True, False),
                                      (SHARE_NEEDS_PRIVILEGE, False, True), ("refusé", False, False)):
            outcome = certificate_setup.share(_Setup((result,)), self.root, self.settings, "omega-serv",
                                              privileged=False)
            self.assertEqual((outcome.ok, outcome.needs_privilege), (ok, privilege), result)


class _Runner:
    def __init__(self, codes):
        self.codes, self.calls = dict(codes), []

    def run(self, args, input_text=None, timeout=None):
        self.calls.append(args)
        return ProcessResult(self.codes.get(args[-1], 3), "", "")

    def run_interactive(self, args):
        return 0


class TestSystemSetup(unittest.TestCase):
    def test_can_listen_sees_a_port_taken_and_a_missing_address(self):
        setup = SystemAdminWebSetup(_Runner({}))
        with socket.socket() as taken:
            taken.bind(("127.0.0.1", 0))
            taken.listen(1)
            port = taken.getsockname()[1]
            self.assertEqual(setup.can_listen("127.0.0.1", port), LISTEN_IN_USE)
            self.assertEqual(setup.can_listen("0.0.0.0", port), LISTEN_IN_USE)
        self.assertEqual(setup.can_listen("127.0.0.1", port), "")
        self.assertEqual(setup.can_listen("192.0.2.77", port), LISTEN_NO_ADDRESS)  # TEST-NET : jamais sur la machine

    def test_firewall_names_and_machine_addresses(self):
        self.assertEqual(SystemAdminWebSetup(_Runner({"firewalld.service": 0})).active_firewall(), "firewalld")
        self.assertEqual(SystemAdminWebSetup(_Runner({})).active_firewall(), "")
        hostname, addresses = SystemAdminWebSetup(_Runner({})).machine_names()
        self.assertTrue(hostname)
        self.assertIn("127.0.0.1", addresses)

    def test_share_with_my_own_group_sets_modes_and_refuses_links(self):
        setup = SystemAdminWebSetup(_Runner({}))
        group = grp.getgrgid(os.getegid()).gr_name
        with tempfile.TemporaryDirectory() as name:
            directory = Path(name) / "admin"
            directory.mkdir()
            key, cert = directory / "admin.key", directory / "admin.pem"
            key.write_text("k")
            cert.write_text("c")
            os.chmod(key, 0o600)
            self.assertEqual(setup.share_with_group((directory,), key, cert, group, privileged=False), "")
            self.assertEqual(stat.S_IMODE(key.stat().st_mode), 0o640)
            self.assertEqual(stat.S_IMODE(cert.stat().st_mode), 0o644)
            self.assertEqual(stat.S_IMODE(directory.stat().st_mode), 0o750)
            self.assertEqual(setup.share_with_group((directory,), key, cert, "groupe-qui-n-existe-pas-42",
                                                    privileged=False), SHARE_NO_GROUP)
            link = directory / "lien.key"
            link.symlink_to(key)
            self.assertIn("lien", setup.share_with_group((directory,), link, cert, group, privileged=False))


class _Scripted:
    """Reponses donnees dans l'ordre ; garde les commandes lancees."""

    def __init__(self, results):
        self.results, self.calls, self.interactive = list(results), [], []

    def run(self, args, input_text=None, timeout=None):
        self.calls.append(args)
        return self.results.pop(0)

    def run_interactive(self, args):
        self.interactive.append(args)
        return 0


class TestFirewall(unittest.TestCase):
    """Sous-lot 8b (auteur, 2026-11-17) : omega-fire et l'instance inscrits dans la zone omega-connect -> bouton
    « Ouvrir le port » ; sinon pare-feu seulement signale."""

    def _config(self, **admin):
        return OmegaServConfig(options={"admin_web": Option("admin_web", True, {"bind": "0.0.0.0", "tls": "own",
                                                                                **admin})})

    def _firewall_line(self, facts, **admin):
        lines = [item for item in admin_web_readiness(self._config(**admin), facts) if "/tcp" in item.text]
        return lines[0] if lines else None

    def test_linked_button_then_opened_until_port_or_networks_change(self):
        from omega_serv.application.admin_web.firewall_setup import (
            FirewallRecord,
            firewall_label,
            firewall_sources,
        )
        from omega_serv.application.admin_web.readiness import ACTION_FIREWALL

        settings = AdminWebSettings.from_settings({"bind": "0.0.0.0"})
        sources = firewall_sources(settings)
        self.assertNotIn("127.0.0.0/8", sources)
        self.assertEqual(firewall_label("prod é/x"), "omega-serv:prod---x")
        line = self._firewall_line(ReadinessFacts(firewall="ufw", firewall_linked=True))
        self.assertEqual((line.ok, line.action), (False, ACTION_FIREWALL))
        opened = FirewallRecord(9643, sources, "2026-11-17T12:00:00")
        self.assertTrue(self._firewall_line(ReadinessFacts(firewall_linked=True, firewall_opened=opened)).ok)
        moved = self._firewall_line(ReadinessFacts(firewall_linked=True, firewall_opened=opened), port=9700)
        self.assertEqual(moved.action, ACTION_FIREWALL)  # autre port : a rouvrir
        wider = self._firewall_line(ReadinessFacts(firewall_linked=True, firewall_opened=opened),
                                    allowed_networks=["10.0.0.0/8", "203.0.113.0/24"])
        self.assertEqual(wider.action, ACTION_FIREWALL)  # nouveau reseau permis
        signalled = self._firewall_line(ReadinessFacts(firewall="ufw"))
        self.assertEqual((signalled.ok, signalled.action), (None, ""))
        self.assertIsNone(self._firewall_line(ReadinessFacts()))
        self.assertIsNone(self._firewall_line(ReadinessFacts(firewall="ufw", firewall_linked=True),
                                              bind="127.0.0.1"))  # boucle locale : rien a ouvrir
        self.assertIsNone(FirewallRecord.from_dict({"port": "9643"}))
        self.assertEqual(FirewallRecord.from_dict(opened.to_dict()), opened)

    def test_registry_of_the_omega_connect_zone(self):
        from omega_lib.synchro.registry import (
            LinkedInstallation,
            ZoneRegistry,
            ZoneState,
            registry_to_dict,
        )

        with tempfile.TemporaryDirectory() as name:
            zone, fire, instance = Path(name) / "zone", Path(name) / "fire", Path(name) / "serv"
            zone.mkdir()
            fire.mkdir()
            instance.mkdir()
            (fire / "omega-fire.sh").write_text("#!/bin/sh\n")

            def write(state, tools):
                entries = tuple(LinkedInstallation(f"{i:032x}", tool, tool, str(root), "moi", "1", "2026-11-17T12:00:00+00:00")
                                for i, (tool, root) in enumerate(tools))
                (zone / "registre.json").write_text(json.dumps(registry_to_dict(
                    ZoneRegistry(str(zone), state, "2026-11-17T12:00:00+00:00", installations=entries))))

            setup = SystemAdminWebSetup(_Scripted([]))
            os.environ["OMEGA_SYNCHRO_DIR"] = str(zone)
            try:
                self.assertEqual(setup.linked_firewall(instance), "")  # pas de registre
                write(ZoneState.ACTIVE, [("omega-fire", fire), ("omega-serv", instance)])
                self.assertEqual(setup.linked_firewall(instance), str(fire / "omega-fire.sh"))
                write(ZoneState.ACTIVE, [("omega-fire", fire), ("omega-serv", Path(name) / "autre")])
                self.assertEqual(setup.linked_firewall(instance), "")  # cette instance n'est pas inscrite
                write(ZoneState.ACTIVE, [("omega-serv", instance)])
                self.assertEqual(setup.linked_firewall(instance), "")  # pas d'omega-fire
                write(ZoneState.FROZEN, [("omega-fire", fire), ("omega-serv", instance)])
                self.assertEqual(setup.linked_firewall(instance), "")  # zone figee
            finally:
                del os.environ["OMEGA_SYNCHRO_DIR"]

    def test_omega_fire_is_called_under_sudo_and_its_json_read(self):
        from omega_serv.ports.process_runner_port import ProcessResult

        answer = json.dumps({"ok": True, "port": 9643, "lignes": [
            {"cible": "nftables", "source": "10.0.0.0/8", "etat": "ajoutee"},
            {"cible": "ufw", "source": "10.0.0.0/8", "etat": "deja"}]})
        runner = _Scripted([ProcessResult(0, "warning: partial scan\n" + answer, "")])
        opening = SystemAdminWebSetup(runner).open_firewall_port("/f/omega-fire.sh", 9643, ("10.0.0.0/8",),
                                                                 "omega-serv:prod")
        self.assertTrue(opening.ok)
        self.assertEqual(opening.lines, (("nftables", "10.0.0.0/8", "ajoutee"), ("ufw", "10.0.0.0/8", "deja")))
        command = runner.calls[-1]
        if os.geteuid() != 0:
            self.assertEqual(command[:2], ["sudo", "-n"])
            self.assertEqual(runner.interactive, [["sudo", "-v"]])
        self.assertEqual(command[-10:], ["/f/omega-fire.sh", "port", "ouvrir", "--port", "9643", "--sources",
                                         "10.0.0.0/8", "--pour", "omega-serv:prod", "--format", "json"][-10:])
        refused = SystemAdminWebSetup(_Scripted([ProcessResult(1, "", "Sorry, try again.")])).open_firewall_port(
            "/f/omega-fire.sh", 9643, ("10.0.0.0/8",), "omega-serv:prod")
        self.assertEqual((refused.ok, refused.error), (False, "Sorry, try again."))


class TestDefaultPort(unittest.TestCase):
    def test_default_port_is_9643(self):
        self.assertEqual(DEFAULT_PORT, 9643)  # 8443 : KULA et d'autres outils (essai reel du 2026-11-17)
        self.assertEqual(AdminWebSettings.from_settings({}).port, 9643)


class TestDashboardServiceManager(unittest.TestCase):
    def test_admin_process_gets_a_service_manager(self):
        """Le conteneur de la CLI n'en fournit pas : sans repli, la page affichait « Aucun gestionnaire de service
        reconnu » (retour de l'auteur du 2026-11-17)."""
        from types import SimpleNamespace

        from omega_serv.application.services.build_service_manager import build_service_manager
        from omega_serv.interfaces.cli.admin_web_commands import _StatusSources

        mine = object()
        self.assertIs(_StatusSources(SimpleNamespace(service_manager_factory=None)).service_manager_factory,
                      build_service_manager)
        self.assertIs(_StatusSources(SimpleNamespace(service_manager_factory=mine)).service_manager_factory, mine)


if __name__ == "__main__":
    unittest.main()
