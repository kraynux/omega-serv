# Copyright (c) 2026 kraynux - kraynux@proton.me - Licence MIT (voir fichier LICENSE)
import unittest

from omega_serv.infrastructure.process.subprocess_runner import SubprocessRunner


class TestSubprocessRunner(unittest.TestCase):
    def test_runs_real_command(self):
        result = SubprocessRunner().run(["echo", "hello"])
        self.assertTrue(result.ok)
        self.assertEqual(result.stdout.strip(), "hello")

    def test_nonzero_exit_reflected(self):
        result = SubprocessRunner().run(["false"])
        self.assertFalse(result.ok)
        self.assertEqual(result.returncode, 1)

    def test_missing_binary_returns_127_instead_of_raising(self):
        result = SubprocessRunner().run(["this-binary-does-not-exist-anywhere"])
        self.assertEqual(result.returncode, 127)
        self.assertFalse(result.ok)
        self.assertIn("introuvable", result.stderr)


if __name__ == "__main__":
    unittest.main()
