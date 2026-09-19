"""Couvre uniquement `_build_execv_invocation` (OMEGA-SERV_PLAN-
DETAILLE_MULTI_INSTANCE.md §9 Phase D) - la fonction pure isolee pour
rester testable. L'appel reel a `os.execv()` dans `main()` ne peut
jamais etre exerce par un test automatise (il remplacerait le
processus de test lui-meme) - limitation deliberee et documentee,
meme nature que le `exec` final d'omega-serv.sh, jamais unit-teste
non plus."""
import unittest
from pathlib import Path

from omega_serv.__main__ import _build_execv_invocation


class TestBuildExecvInvocation(unittest.TestCase):
    def test_returns_path_and_matching_argv(self):
        python_executable = Path("/home/user/DEV/SERV/omega-serv-test/.venv/bin/python")
        path, argv = _build_execv_invocation(python_executable)
        self.assertEqual(path, str(python_executable))
        self.assertEqual(argv, [str(python_executable), "-m", "omega_serv"])

    def test_argv_first_element_matches_path(self):
        python_executable = Path("/tmp/instance/.venv/bin/python")
        path, argv = _build_execv_invocation(python_executable)
        self.assertEqual(argv[0], path)


if __name__ == "__main__":
    unittest.main()
