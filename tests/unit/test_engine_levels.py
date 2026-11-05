"""Nombre de processus par moteur, causes du choix « natif » grisé, connecteurs et garde-fou d'enregistrement (plan
moteur C++ lot 9, §5, §7, §16.5 ; §25 : plus de noms de niveaux, maximum selon le moteur et le processeur)."""
import unittest

from omega_serv.application.server.engine_levels import (
    NATIVE,
    PYTHON_CHECK,
    PYTHON_CONNECTION,
    PYTHON_ROUTE,
    UNSUPPORTED,
    describe_run,
    engine_connectors,
    max_workers,
    native_blockers,
    resolved_worker_count,
    worker_count_notice,
)
from omega_serv.application.server.engine_selection import BINARY_MISSING, TLS_HANDOFF
from omega_serv.domain.config.entities import OmegaServConfig
from omega_serv.interfaces.cli.serve_workers import effective_worker_count
from omega_serv.interfaces.tui.screens.engine_guard import native_loss_reasons

DIRECT_TLS = {"enabled": True, "mode": "direct", "certificate_path": "c.pem", "private_key_path": "k.pem"}


def _config(**sections) -> OmegaServConfig:
    return OmegaServConfig.from_dict(sections)


class TestWorkers(unittest.TestCase):
    def test_maximum_depends_on_engine_and_cores(self):
        # Mesures du comparatif (§25) : Python, un processus par coeur physique ; natif, 2 a partir de 4 coeurs.
        self.assertEqual(max_workers("python", 1), 1)
        self.assertEqual(max_workers("python", 6), 6)
        self.assertEqual(max_workers("native", 2), 1)
        self.assertEqual(max_workers("native", 3), 1)
        self.assertEqual(max_workers("native", 4), 2)
        self.assertEqual(max_workers("native", 16), 2)

    def test_run_is_described_without_level_names(self):
        self.assertEqual(describe_run("native", 2), "moteur natif, 2 processus")
        self.assertEqual(describe_run("python", 1), "moteur Python, 1 processus")

    def test_out_of_range_values_are_brought_to_the_maximum_and_said(self):
        self.assertEqual(resolved_worker_count(4, "native", 2), 1)
        self.assertEqual(resolved_worker_count(0, "python", 4), 4)  # ancien « automatique »
        self.assertEqual(resolved_worker_count(2, "native", 4), 2)
        self.assertIsNone(worker_count_notice(2, "native", 4))
        self.assertIn("4", worker_count_notice(4, "native", 2))
        self.assertIn("automatique", worker_count_notice(0, "native", 4))

    def test_worker_count_matches_serve(self):
        for engine in ("python", "native"):
            for cores in (1, 2, 4, 8):
                for configured in (0, 1, 2, 4, 9):
                    self.assertEqual(resolved_worker_count(configured, engine, cores),
                                     effective_worker_count(configured, engine, cores)[0])


class TestNativeBlockers(unittest.TestCase):
    def test_nothing_blocks_a_plain_config(self):
        self.assertEqual(native_blockers(_config(), None), ())

    def test_blockers_are_listed_even_when_python_is_requested(self):
        config = _config(tls=DIRECT_TLS, options={"upload": {"enabled": True}})
        self.assertEqual(native_blockers(config, BINARY_MISSING), (BINARY_MISSING, TLS_HANDOFF))


class TestConnectors(unittest.TestCase):
    def test_modes_per_active_function(self):
        config = _config(options={"waf": {"enabled": True}, "dirlisting": {"enabled": True},
                                  "reverse_proxy": {"enabled": True}})
        modes = dict(engine_connectors(config))
        self.assertEqual(modes["WAF"], PYTHON_CHECK)
        self.assertEqual(modes["Listing"], PYTHON_ROUTE)
        self.assertEqual(modes["Reverse proxy"], PYTHON_CONNECTION)
        self.assertEqual(modes["Statique"], NATIVE)
        self.assertNotIn("Auth", modes)  # seulement les fonctions actives

    def test_application_route_with_direct_tls_is_unsupported(self):
        modes = dict(engine_connectors(_config(tls=DIRECT_TLS, options={"fastcgi": {"enabled": True}})))
        self.assertEqual(modes["FastCGI"], UNSUPPORTED)
        self.assertEqual(modes["TLS direct"], NATIVE)


class TestGuard(unittest.TestCase):
    def test_losing_the_native_engine_is_reported(self):
        before = _config(server={"engine": "native"}, tls=DIRECT_TLS)
        after = _config(server={"engine": "native"}, tls=DIRECT_TLS, options={"upload": {"enabled": True}})
        self.assertEqual(native_loss_reasons(before, after, None), (TLS_HANDOFF,))

    def test_nothing_to_report(self):
        native = _config(server={"engine": "native"})
        upload = _config(server={"engine": "native"}, options={"upload": {"enabled": True}})
        self.assertEqual(native_loss_reasons(native, upload, None), ())  # sans TLS direct : connexion confiee
        python = _config(tls=DIRECT_TLS, options={"upload": {"enabled": True}})
        self.assertEqual(native_loss_reasons(_config(tls=DIRECT_TLS), python, None), ())  # Python demande
        self.assertEqual(native_loss_reasons(native, upload, BINARY_MISSING), ())  # deja en repli


class TestConnectorRows(unittest.TestCase):
    def test_shown_only_with_the_native_engine(self):
        import tempfile
        from pathlib import Path

        from omega_serv.application.server.engine_status import engine_connector_rows, engine_status
        from omega_serv.infrastructure.filesystem.local_filesystem import LocalFilesystem

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "var" / "run").mkdir(parents=True)
            native = _config(server={"engine": "native"}, options={"waf": {"enabled": True}})
            rows = engine_connector_rows(engine_status(LocalFilesystem(), root, native, None))
            self.assertIn(("WAF", "contrôle Python", ""), rows)
            self.assertEqual(engine_connector_rows(engine_status(LocalFilesystem(), root, native, BINARY_MISSING)), [])
            self.assertEqual(engine_connector_rows(engine_status(LocalFilesystem(), root, _config(), None)), [])
