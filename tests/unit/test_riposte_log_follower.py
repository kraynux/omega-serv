"""Lecteur de journaux RIPOSTE (OMEGA-SERV_PLAN-DETAILLE_RIPOSTE.md §3.2, lot 2) : rien de perdu,
rien de compte deux fois, a travers rotation, remplacement, reecriture et lignes en cours d'ecriture."""
import os
import tempfile
import unittest
from pathlib import Path

from omega_serv.infrastructure.riposte.log_follower import LogFollower


class TestLogFollower(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.path = Path(self._tmp.name) / "waf-alerts.log"

    def tearDown(self):
        self._tmp.cleanup()

    def _append(self, text):
        with open(self.path, "a", encoding="utf-8") as handle:
            handle.write(text)

    def test_first_follow_can_start_exactly_at_the_end(self):
        self._append("ancienne\n")
        follower = LogFollower(self.path, None, start_back_bytes=0)
        self.assertEqual(follower.read_new_lines(), [])
        self._append("nouvelle\n")
        self.assertEqual(follower.read_new_lines(), ["nouvelle"])

    def test_first_follow_starts_a_bounded_distance_back_on_a_line_boundary(self):
        """Defaut : un peu avant la fin (les evenements du demarrage ne sont jamais perdus ; les plus
        anciens sont ecartes par leur date dans follow_once), jamais tout un gros journal."""
        self._append("".join(f"ligne {i:03d}\n" for i in range(100)))  # 10 octets par ligne
        follower = LogFollower(self.path, None, start_back_bytes=35)
        self.assertEqual(follower.read_new_lines(), ["ligne 097", "ligne 098", "ligne 099"])  # 1re ligne coupee ignoree

    def test_small_journal_is_read_entirely_on_first_follow(self):
        self._append("a\nb\n")
        self.assertEqual(LogFollower(self.path, None).read_new_lines(), ["a", "b"])

    def test_first_follow_can_start_at_the_beginning(self):
        self._append("a\nb\n")
        self.assertEqual(LogFollower(self.path, None, start_at_end=False).read_new_lines(), ["a", "b"])

    def test_missing_file_is_not_an_error(self):
        follower = LogFollower(self.path, None)
        self.assertEqual(follower.read_new_lines(), [])
        self._append("x\n")
        self.assertEqual(follower.read_new_lines(), ["x"])

    def test_partial_line_is_kept_for_the_next_read(self):
        follower = LogFollower(self.path, None, start_at_end=False)
        self._append("complete\nen cours")
        self.assertEqual(follower.read_new_lines(), ["complete"])
        self._append(" d'ecriture\n")
        self.assertEqual(follower.read_new_lines(), ["en cours d'ecriture"])

    def test_position_survives_a_restart(self):
        follower = LogFollower(self.path, None, start_at_end=False)
        self._append("1\n2\n")
        follower.read_new_lines()
        self._append("3\n")
        restarted = LogFollower(self.path, follower.position)
        self.assertEqual(restarted.read_new_lines(), ["3"])

    def test_rotation_by_truncation_restarts_at_the_beginning(self):
        follower = LogFollower(self.path, None, start_at_end=False)
        self._append("avant 1\navant 2\n")
        follower.read_new_lines()
        self.path.write_text("")  # rotation omega-serv : meme inode
        self._append("apres\n")
        self.assertEqual(follower.read_new_lines(), ["apres"])
        self.assertEqual(follower.restarts, 1)

    def test_replacement_by_os_replace_is_followed(self):
        follower = LogFollower(self.path, None, start_at_end=False)
        self._append("ligne 1\nligne 2\nligne 3\n")
        follower.read_new_lines()
        tmp = self.path.with_name("x.tmp")
        tmp.write_text("ligne 1\nligne 3\nnouvelle\n")
        os.replace(tmp, self.path)
        self.assertEqual(follower.read_new_lines(), ["ligne 1", "ligne 3", "nouvelle"])  # dedoublonnage : appelant

    def test_in_place_rewrite_longer_than_the_position_is_detected(self):
        follower = LogFollower(self.path, None, start_at_end=False)
        self._append("abc\n")
        follower.read_new_lines()
        with open(self.path, "r+", encoding="utf-8") as handle:  # meme inode, debut different, plus long
            handle.write("xyz\nnouveau contenu\n")
        self.assertEqual(follower.read_new_lines(), ["xyz", "nouveau contenu"])

    def test_bounded_read_continues_on_the_next_call(self):
        self._append("".join(f"ligne {i:04d}\n" for i in range(100)))
        follower = LogFollower(self.path, None, start_at_end=False, max_bytes_per_read=100)
        lines = []
        for _ in range(100):
            lines.extend(follower.read_new_lines())
        self.assertEqual(lines, [f"ligne {i:04d}" for i in range(100)])

    def test_overlong_line_is_skipped_and_counted(self):
        follower = LogFollower(self.path, None, start_at_end=False, max_line_bytes=50, max_bytes_per_read=64)
        self._append("avant\n" + "x" * 500 + "\napres\n")
        lines = []
        for _ in range(20):
            lines.extend(follower.read_new_lines())
        self.assertEqual(lines, ["avant", "apres"])
        self.assertEqual(follower.skipped_long_lines, 1)

    def test_invalid_utf8_never_raises(self):
        follower = LogFollower(self.path, None, start_at_end=False)
        with open(self.path, "ab") as handle:
            handle.write(b"\xff\xfe ok\n")
        self.assertEqual(len(follower.read_new_lines()), 1)


if __name__ == "__main__":
    unittest.main()
