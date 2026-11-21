"""Remesure memoire 3.0.0 (2026-11-18, OMEGA-SERV_ETUDE_PROXY_ET_MEMOIRE.md §6) : gardes contre le retour des couts
mesures. Le processus `serve` passait de 32 Mo (2.6.2) a 49 Mo : deux hash scrypt temoins calcules a l'import (16 Mio
restes dans le tas) et le code de l'administration web, de l'envoi HTTPS et des metadonnees du paquet charges meme
inutilises.

Passe 2 (2026-11-19, etude §7) : le code des options (WAF, Active Defense, auth, proxy, FastCGI, envoi de fichiers,
reecritures...) n'est charge que si l'option est active, au demarrage ou au rechargement ; plus de detection du
terminal, de Rich, de psutil, de ctypes ni de html.entities pour un site statique.

Lot 5 (2026-11-19, etude §8) : superviseur reduit du natif seul (`native_watch.py`), ~6 Mo - ni dataclasses, ni typing,
ni asyncio, ni le code de la configuration."""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
import unittest
from pathlib import Path
from unittest import mock

from omega_serv.infrastructure.process.memory_tuning import keep_large_blocks_out_of_heap
from omega_serv.interfaces.cli.command_tree import lazy_command

_SRC = Path(__file__).resolve().parents[2] / "src"

# Ce que `serve` importe avant de servir : la CLI et son parseur complet, puis les modules du demarrage.
_SERVE_PATH = """
import json, sys
import omega_serv.interfaces.cli.main as cli
cli.build_parser()
import omega_serv.application.server.start_server
import omega_serv.interfaces.cli.serve_native
import omega_serv.interfaces.cli.serve_workers
import omega_serv.interfaces.cli.riposte_commands
import omega_serv.interfaces.cli.declaration_commands
import omega_serv.interfaces.cli.admin_web_entry
import omega_serv.bootstrap.container
import omega_serv.bootstrap.early_language
import omega_serv.application.server.routing_tables
import omega_serv.infrastructure.server.asyncio_server
import omega_serv.infrastructure.persistence.sqlite_snapshot
import omega_serv.infrastructure.declaration.https_sender
import omega_serv.infrastructure.declaration.app_version
modules = sorted(sys.modules)
from omega_serv.domain.security.auth import authorize
from omega_serv.application.admin_web import auth
print(json.dumps({"modules": modules,
                  "witnesses": [authorize._dummy_hash.cache_info().currsize, auth._dummy_hash.cache_info().currsize]}))
"""

_NEVER_ON_SERVE_PATH = (
    "omega_serv.interfaces.cli.admin_web_commands",
    "omega_serv.application.admin_web.web_app",
    "omega_serv.application.admin_web.actions",
    "omega_serv.application.admin_web.history",
    "omega_serv.infrastructure.exporters.ioc_exporters",
    "urllib.request",
    "http.client",
    "importlib.metadata",
    # passe 2 : code des options (charge par option_code.py / routing_tables.py quand l'option est active)
    "omega_serv.application.security.evaluate_waf_request",
    "omega_serv.application.active_defense.observe_threat",
    "omega_serv.domain.security.auth.authorize",
    "omega_serv.application.server.serve_proxy",
    "omega_serv.application.server.serve_websocket_proxy",
    "omega_serv.application.server.serve_fastcgi",
    "omega_serv.application.upload.handle_upload",
    "omega_serv.domain.routing.rewrite",
    "omega_serv.infrastructure.server.native_engine",
    "omega_serv.application.riposte.engine",
    "omega_lib.infrastructure.terminal.detector",
    "html.entities",
    "rich",
    "psutil",
    "ctypes",
)

# Construction d'un serveur sans option, puis rechargement qui en active plusieurs : le code de chaque option arrive
# au rechargement (jamais pendant une requete), et pas avant.
_BUILD_THEN_RELOAD = """
import json, sys, tempfile
from pathlib import Path
from omega_serv.application.server.start_server import build_server, reload_server
from omega_serv.domain.config.entities import OmegaServConfig
from omega_serv.infrastructure.filesystem.local_filesystem import LocalFilesystem
from omega_serv.infrastructure.logging.file_line_logger import FileLineLogger
root = Path(tempfile.mkdtemp()); (root / "webroot").mkdir()
fs = LocalFilesystem()
server = build_server(OmegaServConfig.from_dict({"server": {"bind": "127.0.0.1", "port": 0}}), root, fs, FileLineLogger())
before = sorted(sys.modules)
reload_server(server, OmegaServConfig.from_dict({"server": {"bind": "127.0.0.1", "port": 0}, "options": {
    "waf": {"enabled": True, "rules": {"paths": []}},
    "reverse_proxy": {"enabled": True, "zones": [{"url_prefix": "/api/", "upstreams": [{"host": "127.0.0.1", "port": 9}]}]},
    "rewrites": {"enabled": True, "list": []},
    "fastcgi": {"enabled": True},
    "upload": {"enabled": True, "zones": []},
}}), root, fs)
print(json.dumps({"before": before, "after": sorted(sys.modules)}))
"""

_LOADED_BY_RELOAD = (
    "omega_serv.application.security.evaluate_waf_request",
    "omega_serv.application.server.serve_proxy",
    "omega_serv.application.server.serve_websocket_proxy",
    "omega_serv.application.server.serve_fastcgi",
    "omega_serv.application.upload.handle_upload",
    "omega_serv.domain.routing.rewrite",
    "ctypes",  # reglage de l'allocateur : proxy, FastCGI et envoi de fichiers manipulent de grands blocs
)


class TestServePathStaysLight(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        done = subprocess.run([sys.executable, "-I", "-c", f"import sys; sys.path.insert(0, {str(_SRC)!r})\n{_SERVE_PATH}"],
                              capture_output=True, text=True, timeout=120, check=True)
        cls.result = json.loads(done.stdout.strip().splitlines()[-1])

    def test_heavy_modules_not_imported(self):
        loaded = set(self.result["modules"])
        self.assertEqual([name for name in _NEVER_ON_SERVE_PATH if name in loaded], [])

    def test_scrypt_witnesses_not_computed_at_import(self):
        self.assertEqual(self.result["witnesses"], [0, 0])


class TestOptionCodeLoadedWhenEnabled(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        done = subprocess.run([sys.executable, "-I", "-c", f"import sys; sys.path.insert(0, {str(_SRC)!r})\n{_BUILD_THEN_RELOAD}"],
                              capture_output=True, text=True, timeout=120, check=True)
        cls.result = json.loads(done.stdout.strip().splitlines()[-1])

    def test_absent_without_the_option(self):
        before = set(self.result["before"])
        self.assertEqual([name for name in _LOADED_BY_RELOAD if name in before], [])

    def test_loaded_by_the_reload_that_enables_it(self):
        after = set(self.result["after"])
        self.assertEqual([name for name in _LOADED_BY_RELOAD if name not in after], [])


# Ce que le superviseur reduit charge pendant sa vie (imports au niveau module et a la demande de sa boucle).
_REDUCED_SUPERVISOR = """
import json, sys
import omega_serv.interfaces.cli.native_watch
import omega_serv.infrastructure.filesystem.local_filesystem
import omega_serv.infrastructure.logging.file_line_logger
import omega_serv.infrastructure.server.native_engine
import omega_serv.infrastructure.server.native_ipc
import omega_serv.infrastructure.server.traffic_meter
import omega_serv.interfaces.cli.child_supervisor
import omega_serv.interfaces.cli.declaration_scheduler
import omega_serv.application.services.pid_file
import omega_serv.domain.logging.error_log_line
print(json.dumps(sorted(sys.modules)))
"""

_NEVER_IN_REDUCED_SUPERVISOR = (
    "dataclasses",  # 2,7 Mo avec inspect
    "typing",
    "hashlib",  # empreinte de l'instantane calculee par le fils qui le construit
    "shutil",  # 1,7 Mo (bz2, lzma, zstd)
    "asyncio",
    "argparse",
    "omega_serv.domain.config.entities",
    "omega_serv.application.server.engine_selection",
    "omega_serv.infrastructure.server.native_snapshot",
    "omega_serv.interfaces.cli.serve_native",
    "omega_serv.bootstrap.container",
    "omega_serv.core.i18n",
)


class TestReducedSupervisorStaysLight(unittest.TestCase):
    def test_heavy_modules_not_imported(self):
        done = subprocess.run([sys.executable, "-I", "-c",
                               f"import sys; sys.path.insert(0, {str(_SRC)!r})\n{_REDUCED_SUPERVISOR}"],
                              capture_output=True, text=True, timeout=120, check=True)
        loaded = set(json.loads(done.stdout.strip().splitlines()[-1]))
        self.assertEqual([name for name in _NEVER_IN_REDUCED_SUPERVISOR if name in loaded], [])


class TestLazyCommand(unittest.TestCase):
    def test_name_kept_and_module_loaded_on_call(self):
        handler = lazy_command("omega_serv.interfaces.cli.admin_web_commands", "cmd_admin_account_list")
        self.assertEqual(handler.__name__, "cmd_admin_account_list")
        with mock.patch("omega_serv.interfaces.cli.admin_web_commands.cmd_admin_account_list",
                        return_value=7) as real:
            self.assertEqual(handler(argparse.Namespace(), "conteneur"), 7)
        real.assert_called_once()

    def test_parser_points_to_lazy_handlers(self):
        from omega_serv.interfaces.cli.main import build_parser

        parser = build_parser()
        for argv, name in ((["admin-web", "run"], "cmd_admin_web_run"),
                           (["admin-web", "account", "list"], "cmd_admin_account_list"),
                           (["admin-web", "master", "show"], "cmd_admin_master_show"),
                           (["admin-web", "instances", "list"], "cmd_admin_instances_list")):
            self.assertEqual(parser.parse_args(argv).func.__name__, name)


class TestWitnessesStillProtectUnknownAccounts(unittest.TestCase):
    def test_unknown_user_checked_against_witness(self):
        from omega_serv.domain.routing.zone_resolver import Zone
        from omega_serv.domain.security.auth import authorize
        from omega_serv.domain.security.auth.entities import AuthZone

        zones = (Zone("/p/", AuthZone(path_prefix="/p/", realm="r", allowed_users=("admin",))),)
        with mock.patch.object(authorize, "verify_password", return_value=False) as verify:
            decision = authorize.authorize_request("/p/x", "GET", "Basic dW5rbm93bjpwdw==", zones, {})
        self.assertEqual(decision.outcome, "unauthenticated")
        self.assertEqual(verify.call_args.args[1], authorize._dummy_hash())


class TestKeepLargeBlocksOutOfHeap(unittest.TestCase):
    def test_returns_bool_without_raising(self):
        self.assertIsInstance(keep_large_blocks_out_of_heap(), bool)

    def test_no_libc_is_not_an_error(self):
        with mock.patch("ctypes.CDLL", side_effect=OSError("pas de libc")):
            self.assertFalse(keep_large_blocks_out_of_heap())

    @unittest.skipUnless(sys.platform.startswith("linux"), "glibc")
    def test_second_scrypt_leaves_heap_small(self):
        """Le cas mesure : sans le reglage, le 2e scrypt laisse 16 Mio dans le tas."""
        script = f"""
import sys; sys.path.insert(0, {str(_SRC)!r})
from omega_serv.infrastructure.process.memory_tuning import keep_large_blocks_out_of_heap
from omega_serv.domain.security.auth.password_hashing import hash_password
def heap():
    total, inside = 0, False
    for line in open("/proc/self/smaps"):
        parts = line.split()
        if "-" in parts[0] and ":" not in parts[0]:
            inside = len(parts) > 5 and parts[5] == "[heap]"
        elif inside and line.startswith(("Private_Dirty", "Private_Clean")):
            total += int(parts[1])
    return total
applied = keep_large_blocks_out_of_heap()
for word in ("a", "b", "c"):
    hash_password(word)
print(applied, heap())
"""
        out = subprocess.run([sys.executable, "-I", "-c", script], capture_output=True, text=True, timeout=60,
                             check=True).stdout.split()
        if out[0] != "True":
            self.skipTest("allocateur sans mallopt (pas glibc)")
        self.assertLess(int(out[1]), 8 * 1024)  # Kio ; 17 Mio sans le reglage


if __name__ == "__main__":
    unittest.main()
