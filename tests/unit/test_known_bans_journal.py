# Copyright (c) 2026 kraynux - kraynux@proton.me - Licence MIT (voir fichier LICENSE)
"""Bans connus ailleurs (journal des bans, plan omega-connect phase 3, 2026-11-21)."""
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path

from omega_lib.infrastructure.synchro.ban_writer import new_ban_event, record_ban_events
from omega_lib.synchro.models import BanAction

from omega_serv.infrastructure.active_defense.known_bans_journal import JournalKnownBans

NOW = datetime(2026, 11, 21, 12, 0, tzinfo=timezone.utc)


class _Clock:
    def __init__(self) -> None:
        self.tick = 0.0
        self.now = NOW

    def monotonic(self) -> float:
        return self.tick


def _event(action, network, origin="fail2ban:sshd", **kw):
    return new_ban_event(action, network, origin, now=NOW, host="h", **kw)


class JournalKnownBansTest(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.zone = Path(self._tmp.name)
        (self.zone / "bans").mkdir()
        self.clock = _Clock()
        self.bans = JournalKnownBans(self.zone, monotonic=self.clock.monotonic, now=lambda: self.clock.now)

    def tearDown(self) -> None:
        self._tmp.cleanup()

    def _write(self, *events) -> None:
        self.assertTrue(record_ban_events(list(events), zone=self.zone, now=NOW).ok)

    def _later(self, seconds: float = 6) -> None:
        self.clock.tick += seconds

    def test_etat_initial_puis_journal_suivi_sans_redemarrage(self) -> None:
        self._write(_event(BanAction.BAN, "203.0.113.7"))
        self.assertTrue(self.bans.is_banned("203.0.113.7"))
        self.assertTrue(self.bans.is_banned("::ffff:203.0.113.7"))
        self.assertFalse(self.bans.is_banned("198.51.100.4"))
        self._write(_event(BanAction.BAN, "198.51.100.4", "omega-fire:manual"))
        self.assertFalse(self.bans.is_banned("198.51.100.4"))  # relu au plus toutes les 5 s
        self._later()
        self.assertTrue(self.bans.is_banned("198.51.100.4"))
        self._write(_event(BanAction.UNBAN, "203.0.113.7"))
        self._later()
        self.assertFalse(self.bans.is_banned("203.0.113.7"))

    def test_riposte_ignore_echeance_et_reseau(self) -> None:
        self._write(_event(BanAction.BAN, "203.0.113.7", "fail2ban:omega-serv-riposte-404"),
                    _event(BanAction.BAN, "192.0.2.0/24", "omega-fire:manual"),
                    _event(BanAction.BAN, "198.51.100.4", expires_at=NOW + timedelta(minutes=5)))
        self.assertFalse(self.bans.is_banned("203.0.113.7"))  # anti-boucle
        self.assertTrue(self.bans.is_banned("192.0.2.77"))
        self.assertTrue(self.bans.is_banned("198.51.100.4"))
        self.clock.now = NOW + timedelta(minutes=6)
        self.assertFalse(self.bans.is_banned("198.51.100.4"))

    def test_rotation_relit_l_etat_initial(self) -> None:
        self._write(_event(BanAction.BAN, "203.0.113.7"))
        self.assertTrue(self.bans.is_banned("203.0.113.7"))
        journal = self.zone / "bans" / "journal.jsonl"
        journal.rename(journal.with_name("journal.jsonl.1"))
        self._write(_event(BanAction.BAN, "198.51.100.4"))
        self._later()
        self.assertTrue(self.bans.is_banned("198.51.100.4"))
        self.assertTrue(self.bans.is_banned("203.0.113.7"))

    def test_zone_absente_ou_adresse_invalide(self) -> None:
        bans = JournalKnownBans(self.zone / "absente")
        self.assertFalse(bans.is_banned("203.0.113.7"))
        self.assertFalse(self.bans.is_banned("pas-une-ip"))


if __name__ == "__main__":
    unittest.main()
