"""Tableau de bord web, lot 1 (OMEGA-SERV_PLAN-DETAILLE_TABLEAU_DE_BORD_WEB.md §2.1, 2026-11-16) : instantane d'etat
d'une instance, sorti de l'ecran Etat & Ressources pour etre partage (TUI, CLI, web). Vraie configuration dans un
dossier temporaire ; seules les sondes systeme (psutil) et l'administration sont remplacees."""
import asyncio
import shutil
import tempfile
import unittest
from dataclasses import replace
from datetime import datetime, timedelta, timezone
from pathlib import Path

from omega_serv.application.config.generate_config import generate_default_config
from omega_serv.application.config.load_config import load_config
from omega_serv.application.status.instance_status import InstanceStatusCollector
from omega_serv.bootstrap.container import DependencyContainer
from omega_serv.domain.config.option import KNOWN_OPTION_NAMES, Option

_REAL_PROJECT_ROOT = Path(__file__).resolve().parents[2]


class _Sources:
    """Le vrai conteneur, sauf psutil et l'administration (resultats fixes, appels comptes)."""

    def __init__(self, container: DependencyContainer) -> None:
        self._container = container
        self.machine = {"net_bytes_recv": 1000, "net_bytes_sent": 500, "packets": (10, 4)}
        self.server = {"running": False}
        self.admin_calls: list[str] = []
        self.admin_answer: tuple[int, dict | None] | None = None

    def __getattr__(self, name):
        return getattr(self._container, name)

    def collect_system_stats(self):
        return dict(self.machine)

    def collect_server_stats(self, pid, port):
        return dict(self.server)

    @property
    def admin_request_runner(self):
        async def runner(port, method, path):
            self.admin_calls.append(path)
            return self.admin_answer
        return runner


class _Clock:
    def __init__(self) -> None:
        self.value = 100.0

    def __call__(self) -> float:
        return self.value


class TestInstanceStatusCollector(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.root = Path(self._tmp.name)
        (self.root / "webroot").mkdir()
        (self.root / "config" / "profiles").mkdir(parents=True)
        for profile in (_REAL_PROJECT_ROOT / "config" / "profiles").glob("*.json"):
            shutil.copy(profile, self.root / "config" / "profiles" / profile.name)
        self.container = DependencyContainer(project_root=self.root, instance_registry_path=self.root / "instances.json")
        generate_default_config(self.container.configuration, self.container.filesystem, self.container.config_file)
        self.sources = _Sources(self.container)
        self.clock = _Clock()
        self.collector = InstanceStatusCollector(self.sources, monotonic=self.clock)

    def tearDown(self):
        self._tmp.cleanup()

    def _set_options(self, **options: dict) -> None:
        config = load_config(self.container.configuration, self.container.config_file).config
        merged = dict(config.options)
        for name, settings in options.items():
            merged[name] = Option(name=name, enabled=True, settings=settings)
        self.container.configuration.save(self.container.config_file, replace(config, options=merged))

    def test_server_state_of_a_stopped_site(self):
        state = self.collector.server_state()
        self.assertEqual((state.process.pid, state.process.running), (None, False))
        self.assertFalse(state.service.manager_found)  # open() pas appele : aucun gestionnaire
        self.assertEqual(state.instances.count, 1)
        self.assertTrue(state.instances.rows[0].current)
        self.assertEqual(state.instances.current_name, self.root.resolve().name)
        self.assertEqual((state.latest_backup, state.backup_count), (None, 0))
        self.assertIsNotNone(state.config)
        self.assertEqual(state.config.kind, "site")
        self.assertEqual(state.config.profile, "standard")
        self.assertEqual(state.config.known_options, len(KNOWN_OPTION_NAMES))
        self.assertEqual(state.config.engine.workers >= 1, True)

    def test_unreadable_configuration_gives_its_errors(self):
        self.container.config_file.write_text("{ pas du json")
        state = self.collector.server_state()
        self.assertIsNone(state.config)
        self.assertTrue(state.config_errors)

    def test_traffic_reads_history_then_new_lines(self):
        log_dir = self.root / "var" / "log"
        log_dir.mkdir(parents=True)
        now = datetime.now(timezone.utc)

        def line(when: datetime, status: int) -> str:
            return f'198.51.100.7 - - [{when.strftime("%d/%b/%Y:%H:%M:%S +0000")}] "GET / HTTP/1.1" {status} 10 "-" "c" r\n'

        access = log_dir / "access.log"
        access.write_text(line(now - timedelta(hours=2), 200) + line(now - timedelta(minutes=3), 404))
        self.collector.open()
        first = self.collector.traffic()
        self.assertEqual(first.stats.total, 1)  # la ligne d'il y a 2 h n'est pas relue
        self.assertFalse(first.waf_active)
        with access.open("a") as handle:
            handle.write(line(now, 200))
        self.assertEqual(self.collector.traffic().stats.total, 2)
        self.assertIsNone(self.collector.banned_counts())  # WAF inactif

    def test_system_rates_between_two_readings(self):
        first = self.collector.system()
        self.assertIsNone(first.net_rate)
        self.assertEqual(first.packets, {"tcp": (), "udp": ()})
        self.clock.value += 2.0
        self.sources.machine = {"net_bytes_recv": 3000, "net_bytes_sent": 900, "packets": (30, 8)}
        second = self.collector.system()
        self.assertEqual(second.net_rate, (1000.0, 200.0))
        self.assertEqual(second.packets, {"tcp": (10.0,), "udp": (2.0,)})
        self.assertEqual((second.server["pid"], second.server["port"]), (None, 8080))
        self.assertIsNone(self.collector.pending_sent_since)  # serveur arrete : rien a compter

    def test_sent_bytes_restart_from_zero_on_a_new_start(self):
        calls = []

        def sent(path, since, offset):
            calls.append((since, offset))
            return 100, (offset or 0) + 100

        self.sources.access_log_sent_bytes = sent
        first = datetime(2026, 11, 16, 10, 0, tzinfo=timezone.utc)
        self.collector.update_sent_bytes(first)
        self.collector.update_sent_bytes(first)
        self.assertEqual(self.collector.sent_total, 200)
        self.collector.update_sent_bytes(first + timedelta(hours=1))
        self.assertEqual(self.collector.sent_total, 100)
        self.assertEqual(calls[-1], (first + timedelta(hours=1), None))

    def test_backends_only_for_proxy_or_mixed(self):
        site = asyncio.run(self.collector.backends())
        self.assertEqual((site.kind, site.rows, site.problem), ("site", None, None))
        self.assertEqual(self.sources.admin_calls, [])  # un site n'interroge jamais l'administration

        self._set_options(reverse_proxy={"zones": [{"url_prefix": "/", "upstreams": [{"host": "10.0.0.5", "port": 80}]}]})
        stopped = asyncio.run(self.collector.backends())
        self.assertEqual((stopped.kind, stopped.problem), ("proxy", "stopped"))
        self.sources.admin_answer = (403, None)
        self.assertEqual(asyncio.run(self.collector.backends()).problem, "refused")
        self.sources.admin_answer = (500, None)
        unexpected = asyncio.run(self.collector.backends())
        self.assertEqual((unexpected.problem, unexpected.status), ("unexpected", 500))
        self.sources.admin_answer = (200, {"backends": [
            {"zone": "/", "name": "10.0.0.5:80", "engine": "natif", "status": "up", "requests": 3},
            {"zone": "illisible"}]})
        ok = asyncio.run(self.collector.backends())
        self.assertIsNone(ok.problem)
        self.assertEqual([(r.name, r.requests) for r in ok.rows], [("10.0.0.5:80", 3)])
        self.assertEqual(self.sources.admin_calls[-1], "/.omega-serv-admin/backends")


if __name__ == "__main__":
    unittest.main()
