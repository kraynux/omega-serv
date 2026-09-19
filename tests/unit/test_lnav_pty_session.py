"""Teste le vrai binaire lnav (pas de mock) - meme discipline que
tests/unit/test_openssl_certificate_tool.py, `skipIf` si lnav absent du
systeme. Ne teste PAS render_lnav_live() lui-meme (exige un vrai
terminal interactif, tty.setraw impossible sous pytest) - seulement le
cycle de vie du processus (spawn/kill), valide reellement ici."""
from __future__ import annotations

import os
import shutil
import signal
import subprocess
import tempfile
import time
import unittest
from pathlib import Path

from omega_serv.infrastructure.lnav.pty_session import kill_lnav, relay_osc52, spawn_lnav, wait_dead

_LNAV_MISSING = shutil.which("lnav") is None


@unittest.skipIf(_LNAV_MISSING, "lnav introuvable sur ce systeme")
class TestSpawnLnav(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.log_path = Path(self._tmp.name) / "access.log"
        self.log_path.write_text(
            '127.0.0.1 - - [08/Sep/2026:12:00:00 +0000] "GET / HTTP/1.1" 200 123 "-" "-" req-1\n'
        )

    def tearDown(self):
        self._tmp.cleanup()

    def test_spawn_produces_real_output_then_kill_terminates_it(self):
        master_fd, pid = spawn_lnav(24, 80, [self.log_path])
        try:
            time.sleep(1.0)
            os.set_blocking(master_fd, False)
            try:
                data = os.read(master_fd, 65536)
            except BlockingIOError:
                data = b""
            self.assertGreater(len(data), 0)
            self.assertFalse(wait_dead(pid, 0.01))
        finally:
            kill_lnav(pid)
            self.assertTrue(wait_dead(pid, 3.0))
            os.close(master_fd)

    def test_spawn_requires_at_least_one_path(self):
        with self.assertRaises(ValueError):
            spawn_lnav(24, 80, [])


class TestKillLnavPreservesDetachedChildren(unittest.TestCase):
    """Retour utilisateur ("Ctrl+C ne copie toujours rien") - vrai bug :
    `kill_lnav` tuait tout le GROUPE de processus (`killpg`), ce qui
    detruisait aussi le processus xclip/xsel que la commande native de
    copie de lnav laisse volontairement survivre en arriere-plan pour
    continuer a servir le presse-papier X11 apres la fin de lnav.
    Simule ici le meme scenario (un "lnav" factice qui demarre une
    nouvelle session/groupe puis backgrounde un enfant dans CE groupe,
    exactement comme xclip le ferait) sans dependre d'un vrai xclip/X11."""

    def test_backgrounded_child_in_the_same_group_survives(self):
        proc = subprocess.Popen(
            ["sh", "-c", "echo READY; (sh -c 'sleep 30' &) ; sleep 30"],
            stdin=subprocess.DEVNULL, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
            start_new_session=True, text=True,
        )
        try:
            self.assertEqual(proc.stdout.readline().strip(), "READY")
            time.sleep(0.3)
            group_pids = [
                int(p) for p in subprocess.run(
                    ["pgrep", "-g", str(os.getpgid(proc.pid))], capture_output=True, text=True, check=False,
                ).stdout.split()
            ]
            backgrounded_pids = [p for p in group_pids if p != proc.pid]
            self.assertTrue(backgrounded_pids, "le processus arriere-plan de test n'a pas demarre")

            kill_lnav(proc.pid)

            self.assertTrue(wait_dead(proc.pid, 2.0), "le processus principal (lnav factice) aurait du mourir")
            for child_pid in backgrounded_pids:
                self.assertTrue(
                    os.path.exists(f"/proc/{child_pid}"),
                    f"le processus arriere-plan {child_pid} (simulant xclip) n'a pas du etre tue",
                )
                os.kill(child_pid, signal.SIGKILL)
        finally:
            proc.stdout.close()
            if proc.poll() is None:
                proc.kill()
            proc.wait()


class TestRelayOsc52(unittest.TestCase):
    def test_relays_only_osc52_sequences(self):
        payload = b"before\x1b]52;c;aGVsbG8=\x07after"
        read_fd, write_fd = os.pipe()
        try:
            relayed = relay_osc52(payload, write_fd)
            self.assertEqual(relayed, 1)
            os.set_blocking(read_fd, False)
            data = os.read(read_fd, 65536)
            self.assertEqual(data, b"\x1b]52;c;aGVsbG8=\x07")
        finally:
            os.close(read_fd)
            os.close(write_fd)

    def test_no_osc52_sequence_relays_nothing(self):
        read_fd, write_fd = os.pipe()
        try:
            relayed = relay_osc52(b"plain text", write_fd)
            self.assertEqual(relayed, 0)
        finally:
            os.close(read_fd)
            os.close(write_fd)


if __name__ == "__main__":
    unittest.main()
