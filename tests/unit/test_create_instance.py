"""TestCreateInstanceOrchestration : double de ProcessRunnerPort (pas
de vrai venv/pip) pour verifier l'ORCHESTRATION (ordre des 6 etapes,
propagation d'erreur, appels a on_step) rapidement et de facon
deterministe.

TestCreateInstanceRealVenv (une seule classe, discipline "verifier
avec de vraies I/O reelles" deja etablie dans ce projet) : un vrai
`python -m venv` + `pip install -e .` reels, contre un package
synthetique MINIMAL (zero dependance) plutot que la vraie arborescence
omega-serv complete - le but est de prouver que le pipeline reel
fonctionne, pas de re-tester l'installation d'omega-serv lui-meme
(deja couverte par tests/integration/test_cli.py::install.sh)."""
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import patch

from omega_serv.application.instances.create_instance import create_instance
from omega_serv.infrastructure.filesystem.local_filesystem import LocalFilesystem
from omega_serv.infrastructure.instances.json_instance_registry import JsonInstanceRegistry
from omega_serv.ports.process_runner_port import ProcessResult


class _FixedClock:
    def now(self):
        return datetime(2026, 9, 11, tzinfo=timezone.utc)


class _FakeProcessRunner:
    def __init__(self, failing_args_prefix: tuple[str, ...] | None = None):
        self.calls: list[list[str]] = []
        self._failing_args_prefix = failing_args_prefix

    def run(self, args, input_text=None, timeout=None):
        self.calls.append(args)
        if self._failing_args_prefix is not None and tuple(args[:len(self._failing_args_prefix)]) == self._failing_args_prefix:
            return ProcessResult(returncode=1, stdout="", stderr="echec simule")
        return ProcessResult(returncode=0, stdout="", stderr="")


class TestCreateInstanceOrchestration(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.root = Path(self._tmp.name)
        self.source_root = self.root / "source"
        self.source_root.mkdir()
        (self.source_root / "pyproject.toml").write_text("[project]\nname='fake'\n")
        (self.source_root / "src").mkdir()
        (self.source_root / "src" / "dummy.py").write_text("x = 1\n")
        self.parent_dir = self.root / "instances"
        self.parent_dir.mkdir()
        self.filesystem = LocalFilesystem()
        self.registry = JsonInstanceRegistry(self.filesystem, self.root / "instances.json")
        self.clock = _FixedClock()

    def tearDown(self):
        self._tmp.cleanup()

    def _create(self, process_runner, name="test-instance"):
        steps = []
        return steps, create_instance(
            self.filesystem, process_runner, self.registry, self.clock,
            source_root=self.source_root, name=name, target_parent_dir=self.parent_dir,
            bind="127.0.0.1", port=8081, service_name="omega-serv-test",
            on_step=lambda index, total, label: steps.append((index, total, label)),
        )

    def test_all_steps_reported_in_order_on_success(self):
        steps, error = self._create(_FakeProcessRunner())
        self.assertIsNone(error)
        self.assertEqual([s[0] for s in steps], [1, 2, 3, 4, 5, 6])
        self.assertTrue(all(s[1] == 6 for s in steps))

    def test_copies_tree_and_creates_empty_directories(self):
        _, error = self._create(_FakeProcessRunner())
        self.assertIsNone(error)
        target = self.parent_dir / "test-instance"
        self.assertTrue((target / "pyproject.toml").exists())
        self.assertTrue((target / "src" / "dummy.py").exists())
        for empty_dir in ("webroot", "secure", "var"):
            self.assertTrue((target / empty_dir).is_dir())
        self.assertFalse((target / ".venv").exists())

    def test_registers_instance_on_full_success(self):
        _, error = self._create(_FakeProcessRunner())
        self.assertIsNone(error)
        entries = self.registry.load()
        self.assertEqual(len(entries), 1)
        self.assertEqual(entries[0].name, "test-instance")
        self.assertEqual(entries[0].port, 8081)

    def test_venv_failure_stops_before_pip_and_leaves_no_registry_entry(self):
        class _AlwaysFailRunner:
            def __init__(self):
                self.calls: list[list[str]] = []

            def run(self, args, input_text=None, timeout=None):
                self.calls.append(args)
                return ProcessResult(returncode=1, stdout="", stderr="venv creation failed")

        runner = _AlwaysFailRunner()
        steps, error = self._create(runner)
        self.assertIsNotNone(error)
        self.assertIn("venv", error)
        self.assertEqual([s[0] for s in steps], [1, 2, 3])
        self.assertEqual(len(runner.calls), 1)
        self.assertEqual(self.registry.load(), [])

    def test_failure_after_copy_removes_the_partially_created_directory(self):
        class _AlwaysFailRunner:
            def run(self, args, input_text=None, timeout=None):
                return ProcessResult(returncode=1, stdout="", stderr="venv creation failed")

        _, error = self._create(_AlwaysFailRunner(), name="stuck-name")
        self.assertIsNotNone(error)
        target = self.parent_dir / "stuck-name"
        self.assertFalse(target.exists())

    def test_can_retry_with_the_same_name_after_a_failed_attempt(self):
        class _FailOnceThenSucceedRunner:
            def __init__(self):
                self.attempts = 0

            def run(self, args, input_text=None, timeout=None):
                if args[1:3] == ["-m", "venv"]:
                    self.attempts += 1
                    if self.attempts == 1:
                        return ProcessResult(returncode=1, stdout="", stderr="venv creation failed")
                return ProcessResult(returncode=0, stdout="", stderr="")

        runner = _FailOnceThenSucceedRunner()
        _, first_error = self._create(runner, name="retry-me")
        self.assertIsNotNone(first_error)
        _, second_error = self._create(runner, name="retry-me")
        self.assertIsNone(second_error)
        entries = self.registry.load()
        self.assertEqual(len(entries), 1)
        self.assertEqual(entries[0].name, "retry-me")

    def test_duplicate_name_fails_before_any_copy_or_subprocess_call(self):
        runner = _FakeProcessRunner()
        self._create(runner, name="already-there")
        calls_after_first_success = len(runner.calls)
        steps, error = self._create(runner, name="already-there")
        self.assertIsNotNone(error)
        self.assertEqual([s[0] for s in steps], [1])
        self.assertEqual(len(runner.calls), calls_after_first_success)

    def test_existing_target_directory_rejected(self):
        (self.parent_dir / "existing").mkdir()
        steps, error = self._create(_FakeProcessRunner(), name="existing")
        self.assertIsNotNone(error)
        self.assertIn("existe deja", error)
        self.assertEqual(steps, [(1, 6, "Validation des parametres")])

    def test_copies_vendor_directory_when_present_in_source(self):
        (self.source_root / "vendor" / "omega-lib").mkdir(parents=True)
        (self.source_root / "vendor" / "omega-lib" / "pyproject.toml").write_text("[project]\nname='omega-lib'\n")
        _, error = self._create(_FakeProcessRunner())
        self.assertIsNone(error)
        target = self.parent_dir / "test-instance"
        self.assertTrue((target / "vendor" / "omega-lib" / "pyproject.toml").exists())

    def test_installs_vendored_omega_lib_when_copied_to_target(self):
        (self.source_root / "vendor" / "omega-lib").mkdir(parents=True)
        runner = _FakeProcessRunner()
        _, error = self._create(runner)
        self.assertIsNone(error)
        target = self.parent_dir / "test-instance"
        pip = str(target / ".venv" / "bin" / "pip")
        expected_lib_path = str(target / "vendor" / "omega-lib")
        self.assertIn([pip, "install", "-q", "-e", expected_lib_path], runner.calls)

    def test_installs_omega_lib_from_resolved_editable_source_when_not_vendored(self):
        fake_lib_source = self.root / "external-omega-lib"
        fake_lib_source.mkdir()
        runner = _FakeProcessRunner()
        with patch(
            "omega_serv.application.instances.create_instance._resolve_omega_lib_editable_source",
            return_value=fake_lib_source,
        ):
            _, error = self._create(runner)
        self.assertIsNone(error)
        target = self.parent_dir / "test-instance"
        pip = str(target / ".venv" / "bin" / "pip")
        self.assertIn([pip, "install", "-q", "-e", str(fake_lib_source)], runner.calls)

    def test_skips_omega_lib_install_when_neither_vendored_nor_resolvable(self):
        runner = _FakeProcessRunner()
        with patch(
            "omega_serv.application.instances.create_instance._resolve_omega_lib_editable_source",
            return_value=None,
        ):
            _, error = self._create(runner)
        self.assertIsNone(error)
        target = self.parent_dir / "test-instance"
        pip = str(target / ".venv" / "bin" / "pip")
        editable_installs = [call for call in runner.calls if call[:2] == [pip, "install"] and "-e" in call]
        self.assertEqual(len(editable_installs), 1)
        self.assertEqual(editable_installs[0][-1], str(target))


class TestCreateInstanceRealVenv(unittest.TestCase):
    """Un seul test lent et reel (pas de double) - le pipeline complet
    contre un package synthetique minimal, jamais la vraie
    arborescence omega-serv (trop lourde a re-tester ici, deja couverte
    ailleurs)."""

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.root = Path(self._tmp.name)
        self.source_root = self.root / "source"
        (self.source_root / "src" / "fakepkg").mkdir(parents=True)
        (self.source_root / "src" / "fakepkg" / "__init__.py").write_text("")
        (self.source_root / "pyproject.toml").write_text(
            "[build-system]\nrequires = ['setuptools>=61']\nbuild-backend = 'setuptools.build_meta'\n"
            "[project]\nname = 'fakepkg'\nversion = '0.0.1'\n"
            "[tool.setuptools.packages.find]\nwhere = ['src']\n"
        )
        self.parent_dir = self.root / "instances"
        self.parent_dir.mkdir()
        self.filesystem = LocalFilesystem()
        self.registry = JsonInstanceRegistry(self.filesystem, self.root / "instances.json")
        self.clock = _FixedClock()

    def tearDown(self):
        self._tmp.cleanup()

    def test_real_venv_and_pip_install_end_to_end(self):
        from omega_serv.infrastructure.process.subprocess_runner import SubprocessRunner

        steps = []
        error = create_instance(
            self.filesystem, SubprocessRunner(), self.registry, self.clock,
            source_root=self.source_root, name="real-instance", target_parent_dir=self.parent_dir,
            bind="127.0.0.1", port=8082, service_name="omega-serv-real",
            on_step=lambda index, total, label: steps.append(label),
        )
        self.assertIsNone(error, error)
        target = self.parent_dir / "real-instance"
        self.assertTrue((target / ".venv" / "bin" / "python3").exists())
        self.assertTrue((target / "config" / "omega-serve.json").exists())
        config_text = (target / "config" / "omega-serve.json").read_text()
        self.assertIn('"port": 8082', config_text)
        settings_text = (target / "var" / "settings.json").read_text()
        self.assertIn("omega-serv-real", settings_text)
        entries = self.registry.load()
        self.assertEqual(entries[0].name, "real-instance")


if __name__ == "__main__":
    unittest.main()
