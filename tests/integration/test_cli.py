# Copyright (c) 2026 kraynux - kraynux@proton.me - Licence MIT (voir fichier LICENSE)
"""Tests d'integration Phase 3 : commandes CLI reelles contre un projet
temporaire complet (config/profiles/, webroot/, var/) - aucun mock,
memes fonctions que celles invoquees par argparse en production."""
import contextlib
import io
import json
import shutil
import tempfile
import unittest
from dataclasses import replace
from datetime import timedelta
from pathlib import Path

from omega_serv.application.active_defense.manage_incidents import create_or_update_incident
from omega_serv.application.config.load_config import load_config
from omega_serv.application.server.start_server import build_active_defense_collaborators
from omega_serv.bootstrap.container import DependencyContainer
from omega_serv.core.platform_info import running_as_root
from omega_serv.domain.security.active_defense.entities import ThreatObservation, ThreatState
from omega_serv.infrastructure.clock.system_clock import SystemClock
from omega_serv.interfaces.cli.main import (
    build_parser,
    cmd_active_defense_purge,
    cmd_active_defense_simulate,
    cmd_active_defense_status,
    cmd_audit_security,
    cmd_certs_generate_ca,
    cmd_certs_generate_csr,
    cmd_certs_revoke,
    cmd_certs_sign_csr,
    cmd_config_backup,
    cmd_config_check,
    cmd_config_init,
    cmd_config_list_backups,
    cmd_config_restore,
    cmd_config_show,
    cmd_incidents_close,
    cmd_incidents_export_ioc,
    cmd_incidents_generate_report,
    cmd_incidents_list,
    cmd_incidents_show,
    cmd_option_disable,
    cmd_option_enable,
    cmd_option_list,
    cmd_profile_apply,
    cmd_profile_list,
    cmd_profile_show,
    cmd_serve,
    cmd_simulate_request,
    cmd_threats_list,
    cmd_threats_show,
)

_REAL_PROJECT_ROOT = Path(__file__).resolve().parents[2]


class TestCliCommands(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.root = Path(self._tmp.name)
        (self.root / "webroot").mkdir()
        (self.root / "webroot" / "index.html").write_text("ok")
        (self.root / "config" / "profiles").mkdir(parents=True)
        # Reprend les vrais fichiers de profils du projet plutot que
        # d'en re-ecrire des copies qui pourraient diverger silencieusement.
        for profile_file in (_REAL_PROJECT_ROOT / "config" / "profiles").glob("*.json"):
            shutil.copy(profile_file, self.root / "config" / "profiles" / profile_file.name)

        self.container = DependencyContainer(project_root=self.root)
        self.config_path = self.root / "config" / "omega-serve.json"

    def tearDown(self):
        self._tmp.cleanup()

    def _ns(self, **kwargs):
        kwargs.setdefault("config", self.config_path)
        kwargs.setdefault("confirm_self_signed_public_bind", False)
        kwargs.setdefault("confirm_auth_without_tls", False)
        kwargs.setdefault("format", "text")
        kwargs.setdefault("min_severity", "info")
        kwargs.setdefault("service_name", "omega-serv")
        kwargs.setdefault("unit_path", None)
        return type("Namespace", (), kwargs)()

    def test_config_init_then_check(self):
        result = cmd_config_init(self._ns(force=False), self.container)
        self.assertEqual(result, 0)
        self.assertTrue(self.config_path.exists())

        result = cmd_config_check(self._ns(), self.container)
        self.assertEqual(result, 0)

    def test_config_init_refuses_without_force_then_succeeds_with_force(self):
        cmd_config_init(self._ns(force=False), self.container)
        result = cmd_config_init(self._ns(force=False), self.container)
        self.assertEqual(result, 1)
        result = cmd_config_init(self._ns(force=True), self.container)
        self.assertEqual(result, 0)

    @unittest.skipIf(running_as_root(), "requiert un utilisateur non-root pour reproduire le refus de liaison")
    def test_serve_privileged_port_prints_clean_message_not_traceback(self):
        # Retour utilisateur 2026-09-09 : un port < 1024 sans privilege
        # faisait remonter un traceback Python brut jusqu'au terminal -
        # verifie ici que cmd_serve capture PermissionError et affiche
        # un message propre a la place, code de retour 1.
        cmd_config_init(self._ns(force=False), self.container)
        load_result = load_config(self.container.configuration, self.config_path)
        assert load_result.config is not None
        privileged_config = replace(load_result.config, server=replace(load_result.config.server, port=80))
        self.container.configuration.save(self.config_path, privileged_config)

        stderr = io.StringIO()
        with contextlib.redirect_stderr(stderr):
            exit_code = cmd_serve(self._ns(), self.container)
        self.assertEqual(exit_code, 1)
        self.assertIn("privileges insuffisants", stderr.getvalue())
        self.assertNotIn("Traceback", stderr.getvalue())

    def test_profile_list_finds_real_profiles(self):
        # cmd_profile_list imprime plutot que de retourner - on verifie
        # via le port directement, deja teste par ailleurs, pour rester
        # simple ici : le vrai comportement est le code de retour.
        result = cmd_profile_list(self._ns(), self.container)
        self.assertEqual(result, 0)
        self.assertIn("standard", self.container.profiles.list_profile_names())
        self.assertIn("hardened", self.container.profiles.list_profile_names())

    def test_profile_show_unknown_returns_error(self):
        result = cmd_profile_show(self._ns(name="does-not-exist"), self.container)
        self.assertEqual(result, 1)

    def test_profile_apply_writes_new_config(self):
        cmd_config_init(self._ns(force=False), self.container)
        result = cmd_profile_apply(self._ns(name="hardened", dry_run=False, force=False), self.container)
        self.assertEqual(result, 0)

        data = json.loads(self.config_path.read_text())
        self.assertEqual(data["profile"], "hardened")

    def test_profile_apply_dry_run_does_not_write(self):
        cmd_config_init(self._ns(force=False), self.container)
        before = self.config_path.read_text()
        result = cmd_profile_apply(self._ns(name="hardened", dry_run=True, force=False), self.container)
        after = self.config_path.read_text()
        self.assertEqual(before, after)
        self.assertEqual(result, 0)  # profil hardened seul ne cree aucun conflit bloquant

    def test_option_enable_then_list_then_disable(self):
        cmd_config_init(self._ns(force=False), self.container)

        result = cmd_option_enable(self._ns(name="waf"), self.container)
        self.assertEqual(result, 0)
        data = json.loads(self.config_path.read_text())
        self.assertTrue(data["options"]["waf"]["enabled"])

        result = cmd_option_list(self._ns(), self.container)
        self.assertEqual(result, 0)

        result = cmd_option_disable(self._ns(name="waf"), self.container)
        self.assertEqual(result, 0)
        data = json.loads(self.config_path.read_text())
        self.assertFalse(data["options"]["waf"]["enabled"])

    def test_option_enable_unknown_name_fails(self):
        cmd_config_init(self._ns(force=False), self.container)
        result = cmd_option_enable(self._ns(name="cgi"), self.container)
        self.assertEqual(result, 1)

    def test_config_show_prints_valid_json(self):
        cmd_config_init(self._ns(force=False), self.container)
        result = cmd_config_show(self._ns(), self.container)
        self.assertEqual(result, 0)

    def test_simulate_request_against_real_webroot(self):
        cmd_config_init(self._ns(force=False), self.container)
        result = cmd_simulate_request(self._ns(method="GET", url="/index.html"), self.container)
        self.assertEqual(result, 0)

    def test_audit_security_on_fresh_config_is_secure(self):
        cmd_config_init(self._ns(force=False), self.container)
        result = cmd_audit_security(self._ns(), self.container)
        self.assertEqual(result, 0)

    def test_audit_security_flags_dangerous_methods(self):
        cmd_config_init(self._ns(force=False), self.container)
        data = json.loads(self.config_path.read_text())
        data["security"]["allowed_methods"] = ["GET", "HEAD", "DELETE"]
        self.config_path.write_text(json.dumps(data))

        result = cmd_audit_security(self._ns(format="json"), self.container)
        self.assertEqual(result, 2)  # HIGH sans CRITICAL

    def test_audit_security_missing_config_returns_three(self):
        result = cmd_audit_security(self._ns(), self.container)
        self.assertEqual(result, 3)

    def test_audit_security_min_severity_filters_json_output(self):
        cmd_config_init(self._ns(force=False), self.container)
        data = json.loads(self.config_path.read_text())
        data["server"]["bind"] = "0.0.0.0"  # TLS-003, severite MEDIUM
        self.config_path.write_text(json.dumps(data))

        result = cmd_audit_security(self._ns(format="json", min_severity="high"), self.container)
        self.assertEqual(result, 0)  # MEDIUM seul : securise, mais filtre a l'affichage


class TestCliActiveDefense(unittest.TestCase):
    """plan_active_defense_omega_serv.md, Phase 1 - commandes CLI
    (`active-defense status`, `threats list/show`), meme patron exact
    que TestCliCommands (projet temporaire complet, aucun mock)."""

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.root = Path(self._tmp.name)
        (self.root / "webroot").mkdir()
        (self.root / "config" / "profiles").mkdir(parents=True)
        for profile_file in (_REAL_PROJECT_ROOT / "config" / "profiles").glob("*.json"):
            shutil.copy(profile_file, self.root / "config" / "profiles" / profile_file.name)
        self.container = DependencyContainer(project_root=self.root)
        self.config_path = self.root / "config" / "omega-serve.json"

    def tearDown(self):
        self._tmp.cleanup()

    def _ns(self, **kwargs):
        kwargs.setdefault("config", self.config_path)
        kwargs.setdefault("level", None)
        return type("Namespace", (), kwargs)()

    def test_status_reports_disabled_by_default(self):
        cmd_config_init(self._ns(force=False), self.container)
        stdout = io.StringIO()
        with contextlib.redirect_stdout(stdout):
            result = cmd_active_defense_status(self._ns(), self.container)
        self.assertEqual(result, 0)
        self.assertIn("desactive", stdout.getvalue())

    def test_status_reports_enabled_after_option_enable(self):
        cmd_config_init(self._ns(force=False), self.container)
        cmd_option_enable(self._ns(name="active_defense"), self.container)
        stdout = io.StringIO()
        with contextlib.redirect_stdout(stdout):
            result = cmd_active_defense_status(self._ns(), self.container)
        self.assertEqual(result, 0)
        self.assertIn("Active Defense : active", stdout.getvalue())
        self.assertIn("Sources suivies : 0", stdout.getvalue())

    def test_threats_list_fails_cleanly_when_disabled(self):
        cmd_config_init(self._ns(force=False), self.container)
        stderr = io.StringIO()
        with contextlib.redirect_stderr(stderr):
            result = cmd_threats_list(self._ns(), self.container)
        self.assertEqual(result, 1)

    def test_threats_list_empty_when_enabled_but_nothing_tracked(self):
        cmd_config_init(self._ns(force=False), self.container)
        cmd_option_enable(self._ns(name="active_defense"), self.container)
        stdout = io.StringIO()
        with contextlib.redirect_stdout(stdout):
            result = cmd_threats_list(self._ns(), self.container)
        self.assertEqual(result, 0)
        self.assertIn("Aucune menace", stdout.getvalue())

    def test_threats_show_missing_subject_fails_cleanly(self):
        cmd_config_init(self._ns(force=False), self.container)
        cmd_option_enable(self._ns(name="active_defense"), self.container)
        stderr = io.StringIO()
        with contextlib.redirect_stderr(stderr):
            result = cmd_threats_show(self._ns(subject_id="203.0.113.1:abc"), self.container)
        self.assertEqual(result, 1)

    def _seed_incident(self) -> str:
        """plan_active_defense_omega_serv.md, Phase 2 - seede un vrai
        incident dans la MEME base sqlite que celle que les commandes
        CLI liront ensuite (build_active_defense_collaborators, jamais
        une base separee) - create_or_update_incident() lui-meme est
        deja teste isolement par test_manage_incidents.py."""
        cmd_config_init(self._ns(force=False), self.container)
        cmd_option_enable(self._ns(name="active_defense"), self.container)
        load_result = load_config(self.container.configuration, self.config_path)
        assert load_result.config is not None
        active_defense = build_active_defense_collaborators(load_result.config, self.container.project_root)
        assert active_defense is not None
        observation = ThreatObservation(
            subject_id="203.0.113.1:abcd", observed_at=SystemClock().now(), kind="waf_decision",
            attack_class="sqli", score_delta=80, detail="WAF block (regles=SQLI-001)",
        )
        incident, _ = create_or_update_incident(
            active_defense.incident_repository, SystemClock(), subject_id="203.0.113.1:abcd",
            observation=observation, score=80, incident_score_threshold=70,
        )
        assert incident is not None
        return incident.incident_id

    def test_incidents_list_shows_the_seeded_incident(self):
        incident_id = self._seed_incident()
        stdout = io.StringIO()
        with contextlib.redirect_stdout(stdout):
            result = cmd_incidents_list(self._ns(status=None, since_hours=None), self.container)
        self.assertEqual(result, 0)
        self.assertIn(incident_id, stdout.getvalue())

    def test_incidents_list_empty_when_nothing_open(self):
        cmd_config_init(self._ns(force=False), self.container)
        cmd_option_enable(self._ns(name="active_defense"), self.container)
        stdout = io.StringIO()
        with contextlib.redirect_stdout(stdout):
            result = cmd_incidents_list(self._ns(status=None, since_hours=None), self.container)
        self.assertEqual(result, 0)
        self.assertIn("Aucun incident", stdout.getvalue())

    def test_incidents_show_prints_the_timeline(self):
        incident_id = self._seed_incident()
        stdout = io.StringIO()
        with contextlib.redirect_stdout(stdout):
            result = cmd_incidents_show(self._ns(incident_id=incident_id), self.container)
        self.assertEqual(result, 0)
        self.assertIn("waf_decision", stdout.getvalue())

    def test_incidents_show_missing_incident_fails_cleanly(self):
        cmd_config_init(self._ns(force=False), self.container)
        cmd_option_enable(self._ns(name="active_defense"), self.container)
        stderr = io.StringIO()
        with contextlib.redirect_stderr(stderr):
            result = cmd_incidents_show(self._ns(incident_id="does-not-exist"), self.container)
        self.assertEqual(result, 1)

    def test_incidents_close_then_list_reflects_closed_status(self):
        incident_id = self._seed_incident()
        result = cmd_incidents_close(self._ns(incident_id=incident_id), self.container)
        self.assertEqual(result, 0)
        stdout = io.StringIO()
        with contextlib.redirect_stdout(stdout):
            cmd_incidents_list(self._ns(status="closed", since_hours=None), self.container)
        self.assertIn(incident_id, stdout.getvalue())

    def test_incidents_export_ioc_writes_real_json_and_csv_files(self):
        incident_id = self._seed_incident()
        stdout = io.StringIO()
        with contextlib.redirect_stdout(stdout):
            result = cmd_incidents_export_ioc(self._ns(incident_id=incident_id, format="json,csv"), self.container)
        self.assertEqual(result, 0)
        export_dir = self.root / "var" / "lib" / "active-defense" / "exports"
        self.assertTrue((export_dir / f"{incident_id}.json").exists())
        self.assertTrue((export_dir / f"{incident_id}.csv").exists())

    def test_incidents_export_ioc_unknown_format_fails_cleanly(self):
        incident_id = self._seed_incident()
        stderr = io.StringIO()
        with contextlib.redirect_stderr(stderr):
            result = cmd_incidents_export_ioc(self._ns(incident_id=incident_id, format="xml"), self.container)
        self.assertEqual(result, 1)

    def test_incidents_generate_report_writes_a_real_markdown_file(self):
        incident_id = self._seed_incident()
        stdout = io.StringIO()
        with contextlib.redirect_stdout(stdout):
            result = cmd_incidents_generate_report(self._ns(incident_id=incident_id), self.container)
        self.assertEqual(result, 0)
        report_path = self.root / "var" / "lib" / "active-defense" / "exports" / f"{incident_id}.md"
        self.assertTrue(report_path.exists())
        self.assertIn(f"# Incident {incident_id}", report_path.read_text())

    def test_incidents_close_auto_exports_ioc_when_configured(self):
        """Plan §"Mode guerre" : "produire un export IoC a la fermeture
        de l'incident" - IoCConfig.auto_export_on_close vaut True par
        defaut (aucune surcharge necessaire ici)."""
        incident_id = self._seed_incident()
        result = cmd_incidents_close(self._ns(incident_id=incident_id), self.container)
        self.assertEqual(result, 0)
        export_dir = self.root / "var" / "lib" / "active-defense" / "exports"
        self.assertTrue((export_dir / f"{incident_id}.json").exists())
        self.assertTrue((export_dir / f"{incident_id}.csv").exists())
        self.assertTrue((export_dir / f"{incident_id}.md").exists())

    def _simulate_ns(self, **kwargs):
        kwargs.setdefault("ip", "203.0.113.42")
        kwargs.setdefault("path", "/wp-login.php")
        kwargs.setdefault("user_agent", "")
        kwargs.setdefault("attack_class", "scan")
        kwargs.setdefault("score", 65)
        return self._ns(**kwargs)

    def test_simulate_reports_a_projected_escalation_without_writing_state(self):
        cmd_config_init(self._ns(force=False), self.container)
        cmd_option_enable(self._ns(name="active_defense"), self.container)
        stdout = io.StringIO()
        with contextlib.redirect_stdout(stdout):
            result = cmd_active_defense_simulate(self._simulate_ns(), self.container)
        self.assertEqual(result, 0)
        output = stdout.getvalue()
        self.assertIn("0 -> 65", output)
        self.assertIn("normal -> hostile", output)
        # Simulation = dry-run strict : aucune source reellement suivie.
        threats_stdout = io.StringIO()
        with contextlib.redirect_stdout(threats_stdout):
            cmd_threats_list(self._ns(), self.container)
        self.assertIn("Aucune menace", threats_stdout.getvalue())

    def test_simulate_rejects_unknown_attack_class(self):
        cmd_config_init(self._ns(force=False), self.container)
        cmd_option_enable(self._ns(name="active_defense"), self.container)
        stderr = io.StringIO()
        with contextlib.redirect_stderr(stderr):
            result = cmd_active_defense_simulate(self._simulate_ns(attack_class="bogus"), self.container)
        self.assertEqual(result, 1)

    def test_simulate_fails_cleanly_when_disabled(self):
        cmd_config_init(self._ns(force=False), self.container)
        stderr = io.StringIO()
        with contextlib.redirect_stderr(stderr):
            result = cmd_active_defense_simulate(self._simulate_ns(), self.container)
        self.assertEqual(result, 1)

    def test_purge_reports_zero_when_nothing_to_purge(self):
        cmd_config_init(self._ns(force=False), self.container)
        cmd_option_enable(self._ns(name="active_defense"), self.container)
        stdout = io.StringIO()
        with contextlib.redirect_stdout(stdout):
            result = cmd_active_defense_purge(self._ns(), self.container)
        self.assertEqual(result, 0)
        self.assertIn("Etats de menace purges : 0", stdout.getvalue())
        self.assertIn("Incidents fermes automatiquement : 0", stdout.getvalue())


@unittest.skipIf(shutil.which("openssl") is None, "openssl introuvable sur ce systeme")
class TestCliCertsCaLocale(unittest.TestCase):
    """Chantier CA locale (6b) : les 4 nouvelles sous-commandes `certs`
    invoquees directement (meme patron que TestCliCommands ci-dessus),
    bout en bout jusqu'a un vrai appel openssl."""

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.root = Path(self._tmp.name)
        self.container = DependencyContainer(project_root=self.root)
        self.ca_dir = self.root / "secure" / "certificates" / "ca"
        self.server_dir = self.root / "secure" / "certificates" / "server"

    def tearDown(self):
        self._tmp.cleanup()

    def _ns(self, **kwargs):
        return type("Namespace", (), kwargs)()

    def test_generate_ca_then_csr_then_sign_then_revoke(self):
        result = cmd_certs_generate_ca(self._ns(
            cn="Test CA", org="OMEGA-SERV", ou="", city="", region="", country="",
            days=3650, key_type="rsa4096", password="capass123",
        ), self.container)
        self.assertEqual(result, 0)
        self.assertTrue((self.ca_dir / "root-ca.pem").exists())

        result = cmd_certs_generate_csr(self._ns(
            cn="test.local", san_dns=["test.local"], san_ip=["127.0.0.1"],
            org="OMEGA-SERV", ou="", city="", region="", country="", key_type="rsa2048",
            key_out=str(self.server_dir / "server.key"), csr_out=str(self.server_dir / "server.csr"),
        ), self.container)
        self.assertEqual(result, 0)
        self.assertTrue((self.server_dir / "server.csr").exists())

        result = cmd_certs_sign_csr(self._ns(
            csr=str(self.server_dir / "server.csr"),
            ca_key=str(self.ca_dir / "root-ca.key"), ca_cert=str(self.ca_dir / "root-ca.pem"),
            password="capass123", days=365,
            out=str(self.server_dir / "server.pem"), fullchain_out=str(self.server_dir / "fullchain.pem"),
        ), self.container)
        self.assertEqual(result, 0)
        self.assertTrue((self.server_dir / "server.pem").exists())
        self.assertTrue((self.server_dir / "fullchain.pem").exists())

        result = cmd_certs_revoke(self._ns(
            cert=str(self.server_dir / "server.pem"),
            ca_key=str(self.ca_dir / "root-ca.key"), ca_cert=str(self.ca_dir / "root-ca.pem"),
            password="capass123",
        ), self.container)
        self.assertEqual(result, 0)
        self.assertTrue((self.ca_dir / "index.txt").read_text().startswith("R\t"))

    def test_generate_ca_rejects_missing_common_name(self):
        result = cmd_certs_generate_ca(self._ns(
            cn="", org="OMEGA-SERV", ou="", city="", region="", country="",
            days=3650, key_type="rsa4096", password="capass123",
        ), self.container)
        self.assertEqual(result, 1)
        self.assertFalse((self.ca_dir / "root-ca.pem").exists())


class TestCliConfigBackup(unittest.TestCase):
    """Phase VII (plan interface §3.5/§10) : `config backup/restore/
    list-backups`, seule commande de la gestion des logs/sauvegardes a
    exposer un equivalent CLI explicite avant la TUI (contrairement a
    la rotation/purge de logs, Phase VI, restees TUI-only)."""

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.root = Path(self._tmp.name)
        (self.root / "webroot").mkdir()
        (self.root / "config" / "profiles").mkdir(parents=True)
        for profile_file in (_REAL_PROJECT_ROOT / "config" / "profiles").glob("*.json"):
            shutil.copy(profile_file, self.root / "config" / "profiles" / profile_file.name)
        self.container = DependencyContainer(project_root=self.root)
        self.config_path = self.root / "config" / "omega-serve.json"
        cmd_config_init(self._ns(force=False), self.container)

    def tearDown(self):
        self._tmp.cleanup()

    def _ns(self, **kwargs):
        kwargs.setdefault("config", self.config_path)
        kwargs.setdefault("include_waf", False)
        kwargs.setdefault("include_auth", False)
        kwargs.setdefault("include_certificates", False)
        kwargs.setdefault("include_active_defense", False)
        kwargs.setdefault("confirm_secrets", False)
        kwargs.setdefault("description", "")
        return type("Namespace", (), kwargs)()

    def test_backup_then_list_then_restore(self):
        result = cmd_config_backup(self._ns(description="test backup"), self.container)
        self.assertEqual(result, 0)

        backups = self.container.list_backups()
        self.assertEqual(len(backups), 1)
        snapshot_id = backups[0].snapshot_id

        self.config_path.write_text("CORRUPTED")
        result = cmd_config_restore(self._ns(snapshot_id=snapshot_id), self.container)
        self.assertEqual(result, 0)
        self.assertIn('"version"', self.config_path.read_text())

    def test_backup_including_auth_without_confirm_secrets_refused(self):
        result = cmd_config_backup(self._ns(include_auth=True, description="x"), self.container)
        self.assertEqual(result, 1)
        self.assertEqual(len(self.container.list_backups()), 0)

    def test_backup_including_auth_with_confirm_secrets_succeeds(self):
        result = cmd_config_backup(
            self._ns(include_auth=True, confirm_secrets=True, description="x"), self.container
        )
        self.assertEqual(result, 0)
        self.assertEqual(len(self.container.list_backups()), 1)

    def test_restore_unknown_snapshot_fails(self):
        result = cmd_config_restore(self._ns(snapshot_id="does-not-exist"), self.container)
        self.assertEqual(result, 1)

    def test_backup_including_active_defense_restores_the_real_sqlite_database(self):
        """plan_active_defense_omega_serv.md, Phase 6 ("retention, purge,
        sauvegarde/restauration de la base Active Defense") - vraie base
        sqlite peuplee, vraie sauvegarde/restauration via ArchiveStore,
        aucun mock."""
        cmd_option_enable(self._ns(name="active_defense"), self.container)
        load_result = load_config(self.container.configuration, self.config_path)
        assert load_result.config is not None
        active_defense = build_active_defense_collaborators(load_result.config, self.container.project_root)
        assert active_defense is not None
        active_defense.threat_state_repository.save(ThreatState(
            subject_id="203.0.113.1:abcd", score=42, level="suspicious",
            updated_at=SystemClock().now(), expires_at=SystemClock().now() + timedelta(hours=2),
        ))
        database_path = self.root / active_defense.config.storage.database

        result = cmd_config_backup(self._ns(include_active_defense=True, description="ad"), self.container)
        self.assertEqual(result, 0)
        backups = self.container.list_backups()
        self.assertEqual(len(backups), 1)
        self.assertIn("active_defense", backups[0].scope)

        database_path.unlink()
        result = cmd_config_restore(self._ns(snapshot_id=backups[0].snapshot_id), self.container)
        self.assertEqual(result, 0)
        self.assertTrue(database_path.exists())
        restored = build_active_defense_collaborators(load_result.config, self.container.project_root)
        assert restored is not None
        states = restored.threat_state_repository.list_all()
        self.assertEqual(len(states), 1)
        self.assertEqual(states[0].subject_id, "203.0.113.1:abcd")

    def test_backup_without_active_defense_flag_never_includes_the_database(self):
        cmd_option_enable(self._ns(name="active_defense"), self.container)
        result = cmd_config_backup(self._ns(description="no-ad"), self.container)
        self.assertEqual(result, 0)
        backups = self.container.list_backups()
        self.assertNotIn("active_defense", backups[0].scope)

    def test_list_backups_with_none_prints_message(self):
        result = cmd_config_list_backups(self._ns(), self.container)
        self.assertEqual(result, 0)


class TestArgumentParsing(unittest.TestCase):
    def test_config_flag_before_subcommand(self):
        parser = build_parser()
        args = parser.parse_args(["--config", "/tmp/x.json", "profile", "list"])
        self.assertEqual(str(args.config), "/tmp/x.json")
        self.assertEqual(args.func.__name__, "cmd_profile_list")

    def test_serve_command_parses(self):
        parser = build_parser()
        args = parser.parse_args(["serve"])
        self.assertEqual(args.func.__name__, "cmd_serve")

    def test_profile_apply_flags(self):
        parser = build_parser()
        args = parser.parse_args(["profile", "apply", "hardened", "--dry-run", "--force"])
        self.assertEqual(args.name, "hardened")
        self.assertTrue(args.dry_run)
        self.assertTrue(args.force)

    def test_simulate_request_flags(self):
        parser = build_parser()
        args = parser.parse_args(["simulate-request", "--method", "POST", "--url", "/a/b"])
        self.assertEqual(args.method, "POST")
        self.assertEqual(args.url, "/a/b")

    def test_active_defense_simulate_flags(self):
        parser = build_parser()
        args = parser.parse_args([
            "active-defense", "simulate", "--ip", "203.0.113.42", "--path", "/wp-login.php",
            "--attack-class", "credential_stuffing", "--score", "40",
        ])
        self.assertEqual(args.func.__name__, "cmd_active_defense_simulate")
        self.assertEqual(args.ip, "203.0.113.42")
        self.assertEqual(args.attack_class, "credential_stuffing")
        self.assertEqual(args.score, 40)

    def test_active_defense_purge_parses(self):
        parser = build_parser()
        args = parser.parse_args(["active-defense", "purge"])
        self.assertEqual(args.func.__name__, "cmd_active_defense_purge")

    def test_service_reload_parses(self):
        """Retour utilisateur 2026-09-14 : parite CLI/TUI - le bouton
        "Recharger" existait deja cote TUI (service_screen.py), la
        commande CLI equivalente manquait."""
        parser = build_parser()
        args = parser.parse_args(["service", "reload"])
        self.assertEqual(args.func.__name__, "cmd_service_reload")
        self.assertEqual(args.service_name, "omega-serv")

    def test_audit_security_flags(self):
        parser = build_parser()
        args = parser.parse_args(["audit", "security", "--format", "json", "--min-severity", "high"])
        self.assertEqual(args.func.__name__, "cmd_audit_security")
        self.assertEqual(args.format, "json")
        self.assertEqual(args.min_severity, "high")

    def test_config_backup_flags(self):
        parser = build_parser()
        args = parser.parse_args(
            ["config", "backup", "--include-waf", "--include-auth", "--confirm-secrets", "--description", "d"]
        )
        self.assertEqual(args.func.__name__, "cmd_config_backup")
        self.assertTrue(args.include_waf)
        self.assertTrue(args.include_auth)
        self.assertFalse(args.include_certificates)
        self.assertTrue(args.confirm_secrets)
        self.assertEqual(args.description, "d")

    def test_config_restore_requires_snapshot_id(self):
        parser = build_parser()
        args = parser.parse_args(["config", "restore", "--snapshot-id", "snapshot_1"])
        self.assertEqual(args.func.__name__, "cmd_config_restore")
        self.assertEqual(args.snapshot_id, "snapshot_1")

    def test_config_list_backups_parses(self):
        parser = build_parser()
        args = parser.parse_args(["config", "list-backups"])
        self.assertEqual(args.func.__name__, "cmd_config_list_backups")


if __name__ == "__main__":
    unittest.main()
