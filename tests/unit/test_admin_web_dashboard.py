"""Tableau de bord web, lot 4 : lecture des journaux (instantane, direct, rotation), cache du tableau de bord (aucun
travail quand personne ne regarde), journaux limites a la bibliotheque, sections de securite."""
from __future__ import annotations

import asyncio
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path

from omega_serv.application.admin_web.dashboard import (
    IDLE_SECONDS,
    DashboardData,
    LogEntry,
    log_id_of,
)
from omega_serv.application.admin_web.dashboard_view import SecurityFacts, security_sections
from omega_serv.infrastructure.admin_web import log_reader


class TestLogReader(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.path = Path(self._tmp.name) / "access.log"

    def tearDown(self):
        self._tmp.cleanup()

    def test_tail_follow_partial_line_and_rotation(self):
        self.path.write_text("".join(f"ligne {i}\n" for i in range(10)))
        lines, cursor = log_reader.tail(self.path, 3)
        self.assertEqual(lines, ["ligne 7", "ligne 8", "ligne 9"])
        with self.path.open("a") as handle:
            handle.write("ligne 10\nligne 11 inach")  # derniere ligne pas encore finie
        added, cursor2, rotated = log_reader.read_from(self.path, cursor)
        self.assertEqual((added, rotated), (["ligne 10"], False))
        with self.path.open("a") as handle:
            handle.write("evee\n")
        added, cursor3, _rotated = log_reader.read_from(self.path, cursor2)
        self.assertEqual(added, ["ligne 11 inachevee"])
        self.path.write_text("neuf\n")  # rotation : fichier plus court que la position
        added, _cursor, rotated = log_reader.read_from(self.path, cursor3)
        self.assertEqual((added, rotated), (["neuf"], True))

    def test_tail_is_bounded_and_drops_the_cut_line(self):
        self.path.write_bytes(b"x" * (log_reader.MAX_TAIL_BYTES + 100) + b"\nfin\n")
        lines, size = log_reader.tail(self.path, 10)
        self.assertEqual(lines, ["fin"])
        self.assertEqual(size, self.path.stat().st_size)


class _Collector:
    def __init__(self):
        self.calls = 0

    async def backends(self):
        return None


class TestDashboardData(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.log = Path(self._tmp.name) / "error.log"
        self.log.write_text("un\ndeux\nERREUR trois\n")
        self.clock = [100.0]
        self.collected = 0
        entry = LogEntry(log_id_of(str(self.log)), str(self.log), self.log)
        self.data = DashboardData(_Collector(), lambda: SecurityFacts(), lambda: [entry], log_reader.tail,
                                  log_reader.read_from, lambda n: ["audit"][-n:], monotonic=lambda: self.clock[0])
        self.data._collect = self._fake_collect  # type: ignore[method-assign]
        self.entry = entry

    def tearDown(self):
        self._tmp.cleanup()

    def _fake_collect(self, backends):
        self.collected += 1
        return {"etat": {"sections": [], "updated": "x"}}

    def test_no_work_when_nobody_looks(self):
        async def scenario():
            stop = asyncio.Event()
            task = asyncio.ensure_future(self.data.run(stop))
            await asyncio.sleep(0.05)
            self.assertEqual(self.collected, 0)  # personne n'a demande de page
            self.data.panel("etat")
            await asyncio.sleep(2.2)
            self.assertGreaterEqual(self.collected, 1)
            self.clock[0] += IDLE_SECONDS + 1  # plus personne depuis 30 s
            done = self.collected
            await asyncio.sleep(2.2)
            self.assertEqual(self.collected, done)
            stop.set()
            await task
        asyncio.run(scenario())
        self.assertIsNone(self.data.panel("inconnu"))

    def test_logs_only_from_the_library(self):
        self.assertEqual(self.data.log_list(), [{"id": self.entry.log_id, "label": str(self.log)}])
        self.assertIsNone(self.data.log_snapshot("/etc/passwd", 10, ""))  # jamais un chemin venu du navigateur
        snapshot = self.data.log_snapshot(self.entry.log_id, 10, "erreur")
        self.assertEqual(snapshot["lines"], ["ERREUR trois"])
        with self.log.open("a") as handle:
            handle.write("quatre\n")
        self.assertEqual(self.data.log_follow(self.entry.log_id, snapshot["cursor"])["lines"], ["quatre"])
        self.log.unlink()
        self.assertIn("problem", self.data.log_snapshot(self.entry.log_id, 10, ""))


class TestSecuritySections(unittest.TestCase):
    def test_problems_are_texts_never_errors(self):
        sections = security_sections(SecurityFacts(bans_problem="Blocklist illisible", riposte_problem="RIPOSTE ?",
                                                   incidents=[("i1", "1.2.3.4", "open",
                                                               datetime(2026, 11, 16, tzinfo=timezone.utc), None)]))
        bans, riposte, incidents = sections
        self.assertEqual(bans.note, "Blocklist illisible")
        self.assertEqual(riposte.note, "RIPOSTE ?")
        self.assertEqual(incidents.rows[0].value, "1")
        self.assertEqual(incidents.table[0][:3], ["i1", "1.2.3.4", "open"])


if __name__ == "__main__":
    unittest.main()


class TestUnreadableBackups(unittest.TestCase):
    """Retour de l'auteur (2026-11-17) : le processus d'administration tourne sous le compte du service, qui ne lit pas
    var/backups (700, reserve au proprietaire) ; « Permission denied » faisait tomber les trois colonnes."""

    def test_only_the_backup_row_says_so(self):
        import tempfile
        from pathlib import Path

        from omega_serv.application.admin_web.dashboard_view import server_state_sections
        from omega_serv.application.config.generate_config import generate_default_config
        from omega_serv.application.status.instance_status import InstanceStatusCollector
        from omega_serv.bootstrap.container import DependencyContainer

        with tempfile.TemporaryDirectory() as name:
            root = Path(name)
            container = DependencyContainer(project_root=root, instance_registry_path=root / "instances.json")
            generate_default_config(container.configuration, container.filesystem, container.config_file)

            class _Sources:
                def __getattr__(self, attribute):
                    return getattr(container, attribute)

                def list_backups(self):
                    raise PermissionError(13, "Permission denied", str(root / "var" / "backups"))

            state = InstanceStatusCollector(_Sources()).server_state()
        self.assertTrue(state.backups_unreadable)
        self.assertIsNotNone(state.config)  # le reste du releve est la
        backup = next(section for section in server_state_sections(state) if section.title == "SAUVEGARDE")
        self.assertIn("TUI", backup.note)
