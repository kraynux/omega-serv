"""Langue des exports (OMEGA-SERV_PLAN-DETAILLE_I18N.md, lot exports) : reglage unique dans
Options, defaut « comme l'interface » ; sinon les 3 exports HTML et le rapport d'incident sont
produits par un processus enfant lance dans cette langue, et un echec ne perd jamais le
rapport (repli dans la langue de l'interface, signale)."""
from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from omega_serv.application.terminal.exceptions import UnknownLanguageError
from omega_serv.application.terminal.select_language import (
    EXPORT_LANGUAGE_KEY,
    export_language_override,
    select_export_language,
)
from omega_serv.bootstrap.container import DependencyContainer
from omega_serv.bootstrap.early_language import EXPORT_CHILD_ENV_VAR, install_language_early
from omega_serv.core.i18n import STATE
from omega_serv.domain.security.active_defense.entities import ExportResult
from omega_serv.ports.process_runner_port import ProcessResult


class _MemorySettings:
    def __init__(self, values: dict | None = None) -> None:
        self.values = dict(values or {})

    def get(self, key, default=None):
        return self.values.get(key, default)

    def set(self, key, value) -> None:
        self.values[key] = value


class _Catalog:
    def available(self):
        from omega_lib.i18n.models import LanguageStatus

        return {"en": LanguageStatus.VALIDATED, "ja": LanguageStatus.VALIDATED}


class _Incident:
    incident_id = "inc-42"


class _Filesystem:
    def is_file(self, path: Path) -> bool:
        return True

    def file_size(self, path: Path) -> int:
        return 123


class TestExportLanguageSetting(unittest.TestCase):
    def test_default_follows_the_interface(self):
        self.assertIsNone(export_language_override(_MemorySettings(), "fr"))

    def test_same_language_as_interface_needs_no_child(self):
        self.assertIsNone(export_language_override(_MemorySettings({EXPORT_LANGUAGE_KEY: "ja"}), "ja"))

    def test_other_language_is_returned(self):
        self.assertEqual(export_language_override(_MemorySettings({EXPORT_LANGUAGE_KEY: "ja"}), "fr"), "ja")

    def test_select_persists_and_empty_means_interface(self):
        settings = _MemorySettings()
        select_export_language(settings_store=settings, catalog=_Catalog(), language_code="ja")
        self.assertEqual(settings.get(EXPORT_LANGUAGE_KEY), "ja")
        select_export_language(settings_store=settings, catalog=_Catalog(), language_code="")
        self.assertEqual(settings.get(EXPORT_LANGUAGE_KEY), "")

    def test_unknown_language_is_refused(self):
        with self.assertRaises(UnknownLanguageError):
            select_export_language(settings_store=_MemorySettings(), catalog=_Catalog(), language_code="ru")


class TestContainerExports(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.root = Path(self._tmp.name)
        self.calls: list[tuple[list[str], str]] = []
        self.child_result = ProcessResult(returncode=0, stdout="<html>ja</html>", stderr="")

    def tearDown(self) -> None:
        self._tmp.cleanup()

    def _child(self, command: list[str], code: str) -> ProcessResult:
        self.calls.append((command, code))
        return self.child_result

    def _container(self, export_language: str = "") -> DependencyContainer:
        container = DependencyContainer(
            project_root=self.root,
            instance_registry_path=self.root.parent / f"{self.root.name}-instances.json",
            export_guide_html_fn=lambda guides, faq, theme: "<html>interface</html>",
            incident_report_export_runner=lambda incident, d, fs: ExportResult(
                path=d / "interface.md", export_format="markdown", bytes_written=1),
            export_in_language_runner=self._child,
        )
        container.settings_store.set(EXPORT_LANGUAGE_KEY, export_language)
        return container

    def _other_language(self) -> str:
        return "ja" if STATE.language.code != "ja" else "en"

    def test_interface_language_renders_in_process(self):
        container = self._container()
        self.assertEqual(container.export_guide_html([], [], "omega-dark"), "<html>interface</html>")
        self.assertEqual((self.calls, container.export_language_name), ([], None))

    def test_other_language_goes_through_the_child(self):
        code = self._other_language()
        container = self._container(code)
        self.assertEqual(container.export_guide_html([], [], "omega-dark"), "<html>ja</html>")
        self.assertEqual(self.calls, [(["_export-html", "guide", "omega-dark"], code)])
        self.assertIsNotNone(container.export_language_name)

    def test_child_failure_returns_none_with_a_reason(self):
        self.child_result = ProcessResult(returncode=1, stdout="", stderr="trace\nboom")
        container = self._container(self._other_language())
        self.assertIsNone(container.export_guide_html([], [], "omega-dark"))
        self.assertIn("boom", container.last_export_error or "")

    def test_report_in_other_language_uses_the_child_path(self):
        code = self._other_language()
        self.child_result = ProcessResult(returncode=0, stdout="noise\n/x/report.md\n", stderr="")
        container = self._container(code)
        result = container.incident_report_export_runner(_Incident(), self.root, _Filesystem())
        self.assertEqual((result.path, result.bytes_written), (Path("/x/report.md"), 123))
        self.assertEqual(self.calls, [(["_export-report", "inc-42"], code)])
        self.assertIsNone(container.last_export_error)

    def test_report_child_failure_falls_back_to_interface_language(self):
        self.child_result = ProcessResult(returncode=3, stdout="", stderr="")
        container = self._container(self._other_language())
        result = container.incident_report_export_runner(_Incident(), self.root, _Filesystem())
        self.assertEqual(result.path, self.root / "interface.md", "le rapport n'est jamais perdu")
        self.assertIsNotNone(container.last_export_error)


class TestExportChildSkipsConsoleFallback(unittest.TestCase):
    """L'enfant d'export ne doit pas retomber en anglais parce que l'interface tourne dans la
    console Linux : son texte part dans un fichier, pas a l'ecran."""

    def test_child_env_flag_disables_terminal_detection(self):
        from unittest import mock

        with mock.patch("omega_serv.bootstrap.early_language.SystemTerminalDetector") as detector, \
                mock.patch("omega_serv.bootstrap.early_language.install_interface_language") as install:
            install_language_early({EXPORT_CHILD_ENV_VAR: "1"})
        detector.assert_not_called()
        self.assertIsNone(install.call_args.kwargs["terminal_family"])


if __name__ == "__main__":
    unittest.main()
