import tempfile
import unittest
from pathlib import Path

from omega_serv.application.logs.remote_fetch import fetch_remote_log
from omega_serv.domain.logs.remote_source import RemoteLogSource
from omega_serv.ports.process_runner_port import ProcessResult


class _FakeProcessRunner:
    def __init__(self, result: ProcessResult) -> None:
        self._result = result
        self.calls: list[tuple] = []

    def run(self, args, input_text=None, timeout=None):
        self.calls.append((args, timeout))
        return self._result

    def run_interactive(self, args):
        raise NotImplementedError


class TestFetchRemoteLog(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.local_dest = Path(self._tmp.name) / "cache" / "backend1.log"
        self.source = RemoteLogSource(label="backend1", host="192.168.1.10", remote_path="/var/log/access.log")

    def tearDown(self):
        self._tmp.cleanup()

    def test_success(self):
        runner = _FakeProcessRunner(ProcessResult(returncode=0, stdout="", stderr=""))
        result = fetch_remote_log(runner, self.source, self.local_dest)
        self.assertTrue(result.success)
        self.assertIn(str(self.local_dest), result.message)

    def test_failure_surfaces_stderr(self):
        runner = _FakeProcessRunner(ProcessResult(returncode=1, stdout="", stderr="Connection refused"))
        result = fetch_remote_log(runner, self.source, self.local_dest)
        self.assertFalse(result.success)
        self.assertIn("Connection refused", result.message)

    def test_failure_with_no_stderr_falls_back_to_returncode(self):
        runner = _FakeProcessRunner(ProcessResult(returncode=127, stdout="", stderr=""))
        result = fetch_remote_log(runner, self.source, self.local_dest)
        self.assertFalse(result.success)
        self.assertIn("127", result.message)

    def test_creates_parent_directory(self):
        runner = _FakeProcessRunner(ProcessResult(returncode=0, stdout="", stderr=""))
        self.assertFalse(self.local_dest.parent.exists())
        fetch_remote_log(runner, self.source, self.local_dest)
        self.assertTrue(self.local_dest.parent.exists())

    def test_passes_timeout_through_to_the_runner(self):
        runner = _FakeProcessRunner(ProcessResult(returncode=0, stdout="", stderr=""))
        fetch_remote_log(runner, self.source, self.local_dest, timeout=5.0)
        self.assertEqual(runner.calls[0][1], 5.0)


if __name__ == "__main__":
    unittest.main()
