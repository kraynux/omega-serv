"""Declaration anonyme d'utilisateur (OMEGA-SERV_ETUDE_TELEMETRIE.md §3b) : domaine, cas d'usage,
stockage sous var/lib/declaration/, envoi HTTP reel contre un serveur local, planificateur de
l'envoi quotidien de `serve`, commandes CLI."""
from __future__ import annotations

import argparse
import contextlib
import io
import json
import os
import signal
import stat
import tempfile
import threading
import unittest
from datetime import datetime, timedelta, timezone
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
from typing import ClassVar

from omega_serv.application.declaration.use_cases import (
    declaration_status,
    declare,
    preview_payload,
    send_scheduled,
    withdraw,
)
from omega_serv.bootstrap.container import DependencyContainer
from omega_serv.bootstrap.early_language import is_server_process
from omega_serv.domain.declaration.countries import COUNTRY_CODES
from omega_serv.domain.declaration.model import (
    MODE_DAILY,
    MODE_ONCE,
    Declaration,
    build_payload,
    daily_send_due,
    declaration_errors,
    do_not_track,
)
from omega_serv.infrastructure.declaration.app_version import application_version
from omega_serv.infrastructure.declaration.https_sender import HttpsDeclarationSender
from omega_serv.infrastructure.declaration.json_declaration_store import (
    DECLARATION_DIR,
    JsonDeclarationStore,
)
from omega_serv.interfaces.cli.declaration_commands import (
    CHECK_EVERY_SECONDS,
    FIRST_CHECK_SECONDS,
    DeclarationScheduler,
    ServeCompanions,
    cmd_declaration_declare,
)
from omega_serv.ports.declaration_port import SendOutcome, ServiceSendLog, StoredDeclaration

_NOW = datetime(2026, 11, 5, 12, 0, tzinfo=timezone.utc)
_KEY = "0123456789abcdef0123456789abcdef"


class _Clock:
    def __init__(self, now: datetime = _NOW) -> None:
        self.current = now

    def now(self) -> datetime:
        return self.current


class _Sender:
    def __init__(self, ok: bool = True) -> None:
        self.ok = ok
        self.sent: list[dict] = []

    def send(self, payload: dict) -> SendOutcome:
        self.sent.append(dict(payload))
        return SendOutcome(True) if self.ok else SendOutcome(False, "unreachable")


class TestDomain(unittest.TestCase):
    def test_payload_has_only_the_chosen_fields(self):
        self.assertEqual(build_payload(Declaration(_KEY, MODE_ONCE), "2.5.0"),
                         {"cle": _KEY, "version": "2.5.0", "envoi": "unique"})
        self.assertEqual(build_payload(Declaration(_KEY, MODE_DAILY, "EU", "FR"), "2.5.0"),
                         {"cle": _KEY, "version": "2.5.0", "envoi": "quotidien", "continent": "EU", "pays": "FR"})

    def test_closed_lists_and_other(self):
        self.assertEqual(declaration_errors(Declaration(_KEY, MODE_ONCE, "autre", "autre")), [])
        self.assertTrue(declaration_errors(Declaration(_KEY, MODE_ONCE, "XX")))
        self.assertTrue(declaration_errors(Declaration(_KEY, MODE_ONCE, "", "ZZ")))
        self.assertTrue(declaration_errors(Declaration("cle", MODE_ONCE)))
        self.assertTrue(declaration_errors(Declaration(_KEY, "hebdo")))

    def test_do_not_track(self):
        self.assertTrue(do_not_track({"DO_NOT_TRACK": "1"}))
        self.assertFalse(do_not_track({"DO_NOT_TRACK": "0"}))
        self.assertFalse(do_not_track({}))

    def test_daily_due_only_in_daily_mode_and_once_per_24h(self):
        daily = Declaration(_KEY, MODE_DAILY)
        self.assertTrue(daily_send_due(daily, None, _NOW, do_not_track_set=False))
        self.assertFalse(daily_send_due(daily, _NOW - timedelta(hours=23), _NOW, do_not_track_set=False))
        self.assertTrue(daily_send_due(daily, _NOW - timedelta(hours=24), _NOW, do_not_track_set=False))
        self.assertFalse(daily_send_due(daily, None, _NOW, do_not_track_set=True))
        self.assertFalse(daily_send_due(Declaration(_KEY, MODE_ONCE), None, _NOW, do_not_track_set=False))
        self.assertFalse(daily_send_due(None, None, _NOW, do_not_track_set=False))

    def test_country_names_cover_every_code_in_every_language(self):
        data = json.loads((Path(__file__).resolve().parents[2] / "src" / "omega_serv" / "domain" / "declaration"
                           / "country_names.json").read_text(encoding="utf-8"))["names"]
        self.assertEqual(len(COUNTRY_CODES), 249)
        self.assertEqual(len(data), 17)
        for language, table in data.items():
            self.assertEqual(sorted(table), sorted(COUNTRY_CODES), language)


class _StoreCase(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.root = Path(self._tmp.name)
        self.store = JsonDeclarationStore(self.root)

    def tearDown(self):
        self._tmp.cleanup()


class TestUseCases(_StoreCase):
    def test_once_success_records_and_key_is_reused(self):
        sender = _Sender()
        result = declare(self.store, sender, _Clock(), "2.5.0", MODE_ONCE, key_factory=lambda: _KEY)
        self.assertTrue(result.ok)
        self.assertEqual(sender.sent, [{"cle": _KEY, "version": "2.5.0", "envoi": "unique"}])
        declare(self.store, sender, _Clock(), "2.5.0", MODE_DAILY, "EU", "FR", key_factory=lambda: "f" * 32)
        self.assertEqual(sender.sent[1]["cle"], _KEY)
        stored = self.store.load()
        assert stored is not None
        self.assertEqual(stored.declaration, Declaration(_KEY, MODE_DAILY, "EU", "FR"))
        self.assertEqual(stored.declared_at, _NOW)

    def test_once_failure_records_nothing(self):
        result = declare(self.store, _Sender(ok=False), _Clock(), "2.5.0", MODE_ONCE)
        self.assertFalse(result.ok)
        self.assertFalse(result.recorded)
        self.assertIsNone(self.store.load())

    def test_daily_failure_keeps_consent_for_the_service(self):
        result = declare(self.store, _Sender(ok=False), _Clock(), "2.5.0", MODE_DAILY)
        self.assertTrue(result.recorded)
        stored = self.store.load()
        assert stored is not None
        self.assertEqual(stored.last_error, "unreachable")
        self.assertIsNone(stored.last_success)

    def test_invalid_choice_raises_before_any_send(self):
        sender = _Sender()
        with self.assertRaises(ValueError):
            declare(self.store, sender, _Clock(), "2.5.0", MODE_ONCE, "XX")
        self.assertEqual(sender.sent, [])

    def test_withdraw_sends_removal_and_erases_even_when_unreachable(self):
        declare(self.store, _Sender(), _Clock(), "2.5.0", MODE_DAILY, key_factory=lambda: _KEY)
        self.store.save_service_log(ServiceSendLog(last_attempt=_NOW))
        sender = _Sender(ok=False)
        result = withdraw(self.store, sender)
        self.assertTrue(result.was_declared)
        self.assertFalse(result.reception_reached)
        self.assertEqual(sender.sent, [{"cle": _KEY, "retrait": True}])
        self.assertIsNone(self.store.load())
        self.assertEqual(list((self.root / DECLARATION_DIR).glob("*.json")), [])

    def test_withdraw_without_declaration_sends_nothing(self):
        sender = _Sender()
        self.assertFalse(withdraw(self.store, sender).was_declared)
        self.assertEqual(sender.sent, [])

    def test_scheduled_send_waits_24h_after_the_interface_send(self):
        clock = _Clock()
        declare(self.store, _Sender(), clock, "2.5.0", MODE_DAILY, key_factory=lambda: _KEY)
        sender = _Sender()
        clock.current = _NOW + timedelta(hours=23)
        self.assertIsNone(send_scheduled(self.store, sender, clock, "2.5.0", {}))
        clock.current = _NOW + timedelta(hours=24)
        outcome = send_scheduled(self.store, sender, clock, "2.5.0", {})
        self.assertIsNotNone(outcome)
        self.assertEqual(len(sender.sent), 1)
        self.assertEqual(self.store.load_service_log().last_success, clock.current)
        # Echec le lendemain : essai note, pas de nouvel essai avant 24 h.
        failing = _Sender(ok=False)
        clock.current += timedelta(hours=24)
        self.assertFalse(send_scheduled(self.store, failing, clock, "2.5.0", {}).ok)  # type: ignore[union-attr]
        clock.current += timedelta(hours=1)
        self.assertIsNone(send_scheduled(self.store, failing, clock, "2.5.0", {}))
        self.assertEqual(len(failing.sent), 1)

    def test_scheduled_send_never_in_once_mode_or_with_do_not_track(self):
        clock = _Clock()
        declare(self.store, _Sender(), clock, "2.5.0", MODE_ONCE)
        clock.current += timedelta(days=3)
        self.assertIsNone(send_scheduled(self.store, _Sender(), clock, "2.5.0", {}))
        declare(self.store, _Sender(), clock, "2.5.0", MODE_DAILY)
        clock.current += timedelta(days=3)
        self.assertIsNone(send_scheduled(self.store, _Sender(), clock, "2.5.0", {"DO_NOT_TRACK": "1"}))

    def test_status_reports_the_latest_attempt(self):
        declare(self.store, _Sender(), _Clock(), "2.5.0", MODE_DAILY)
        self.store.save_service_log(ServiceSendLog(_NOW + timedelta(days=1), _NOW, "http-503"))
        status = declaration_status(self.store, {})
        self.assertEqual(status.last_success, _NOW)
        self.assertEqual(status.last_error, "http-503")
        self.assertIsNone(declaration_status(JsonDeclarationStore(self.root / "vide"), {}).declaration)

    def test_preview_shows_the_shape_of_a_key_not_yet_drawn(self):
        self.assertEqual(preview_payload(self.store, "2.5.0", MODE_ONCE, "", "")["cle"], "0" * 32)


class TestStore(_StoreCase):
    def test_round_trip_and_shared_modes(self):
        self.store.save(StoredDeclaration(Declaration(_KEY, MODE_DAILY, "EU", ""), _NOW, _NOW, None, "x"))
        self.store.save_service_log(ServiceSendLog(_NOW, _NOW, ""))
        stored = self.store.load()
        assert stored is not None
        self.assertEqual(stored.declaration.continent, "EU")
        self.assertEqual(stored.last_error, "x")
        directory = self.root / DECLARATION_DIR
        self.assertEqual(stat.S_IMODE(directory.stat().st_mode) & 0o775, 0o775)
        for name in ("declaration.json", "envois-service.json"):
            self.assertEqual(stat.S_IMODE((directory / name).stat().st_mode), 0o664)

    def test_damaged_files_read_as_absent(self):
        directory = self.root / DECLARATION_DIR
        directory.mkdir(parents=True)
        (directory / "declaration.json").write_text("{pas du json", encoding="utf-8")
        (directory / "envois-service.json").write_text("[]", encoding="utf-8")
        self.assertIsNone(self.store.load())
        self.assertEqual(self.store.load_service_log(), ServiceSendLog())


class _Handler(BaseHTTPRequestHandler):
    status = 204
    received: ClassVar[list[tuple[dict, dict]]] = []

    def do_POST(self):
        length = int(self.headers.get("Content-Length", "0"))
        _Handler.received.append((dict(self.headers), json.loads(self.rfile.read(length))))
        self.send_response(_Handler.status)
        self.send_header("Content-Length", "0")
        self.end_headers()

    def log_message(self, *_args):
        pass


class TestHttpsSender(unittest.TestCase):
    def setUp(self):
        _Handler.received = []
        self.server: HTTPServer | None = HTTPServer(("127.0.0.1", 0), _Handler)
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()
        self.port = self.server.server_address[1]
        self.url = f"http://127.0.0.1:{self.port}/compteur/"

    def tearDown(self):
        if self.server is not None:
            self.server.shutdown()
            self.server.server_close()

    def test_posts_json_with_user_agent(self):
        _Handler.status = 204
        outcome = HttpsDeclarationSender("2.5.0", self.url).send({"cle": _KEY, "version": "2.5.0", "envoi": "unique"})
        self.assertTrue(outcome.ok)
        headers, body = _Handler.received[0]
        self.assertEqual(body["envoi"], "unique")
        self.assertEqual(headers["Content-Type"], "application/json")
        self.assertEqual(headers["User-Agent"], "omega-serv/2.5.0")

    def test_http_error_and_unreachable_never_raise(self):
        _Handler.status = 503
        self.assertEqual(HttpsDeclarationSender("2.5.0", self.url).send({}).reason, "http-503")
        port = self.port
        assert self.server is not None
        self.server.shutdown()
        self.server.server_close()
        self.server = None  # port libere : plus personne n'ecoute
        outcome = HttpsDeclarationSender("2.5.0", f"http://127.0.0.1:{port}/", timeout=1).send({})
        self.assertEqual(outcome, SendOutcome(False, "unreachable"))


class _FakeChild:
    def __init__(self) -> None:
        self.running = True
        self.signals: list[int] = []

    def is_running(self) -> bool:
        return self.running

    def send_signal(self, sig: int) -> None:
        self.signals.append(sig)


class TestScheduler(_StoreCase):
    def _scheduler(self, environ: dict | None = None):
        self.mono = 1000.0
        self.spawned: list[_FakeChild] = []
        self.clock = _Clock()

        def spawn(_argv):
            child = _FakeChild()
            self.spawned.append(child)
            return child

        scheduler = DeclarationScheduler(["omega-serv"], self.store, now=self.clock.now, environ=environ or {},
                                         spawn=spawn, monotonic=lambda: self.mono)
        scheduler.start()
        return scheduler

    def test_nothing_before_one_minute_then_one_send_when_due(self):
        declare(self.store, _Sender(ok=False), _Clock(_NOW - timedelta(days=2)), "2.5.0", MODE_DAILY)
        scheduler = self._scheduler()
        scheduler.tick()
        self.assertEqual(self.spawned, [])
        self.mono += FIRST_CHECK_SECONDS
        scheduler.tick()
        self.assertEqual(len(self.spawned), 1)
        # L'envoi n'a rien pu ecrire : jamais relance avant 24 h depuis ce processus.
        self.spawned[0].running = False
        for _hour in range(23):
            self.mono += CHECK_EVERY_SECONDS
            scheduler.tick()
        self.assertEqual(len(self.spawned), 1)

    def test_not_declared_or_once_mode_never_spawns(self):
        scheduler = self._scheduler()
        self.mono += FIRST_CHECK_SECONDS
        scheduler.tick()
        declare(self.store, _Sender(), _Clock(_NOW - timedelta(days=2)), "2.5.0", MODE_ONCE)
        self.mono += CHECK_EVERY_SECONDS
        scheduler.tick()
        self.assertEqual(self.spawned, [])

    def test_stop_never_waits(self):
        declare(self.store, _Sender(ok=False), _Clock(_NOW - timedelta(days=2)), "2.5.0", MODE_DAILY)
        scheduler = self._scheduler()
        self.mono += FIRST_CHECK_SECONDS
        scheduler.tick()
        scheduler.stop()
        self.assertEqual(self.spawned[0].signals, [signal.SIGTERM])

    def test_companions_drive_every_member_and_skip_none(self):
        calls: list[str] = []

        class _Member:
            def start(self): calls.append("start")
            def tick(self): calls.append("tick")
            def reload(self): calls.append("reload")
            def stop(self): calls.append("stop")

        group = ServeCompanions(None, _Member(), _Member())
        group.start()
        group.tick()
        group.reload()
        group.stop()
        self.assertEqual(calls, ["start", "start", "tick", "tick", "reload", "reload", "stop", "stop"])


class TestCli(_StoreCase):
    def test_declare_without_yes_only_shows_the_message(self):
        container = DependencyContainer(project_root=self.root)
        args = argparse.Namespace(mode=MODE_ONCE, continent="EU", pays="FR", yes=False)
        output = io.StringIO()
        with contextlib.redirect_stdout(output):
            code = cmd_declaration_declare(args, container)
        self.assertEqual(code, 1)
        self.assertIn('"pays": "FR"', output.getvalue())
        self.assertFalse((self.root / DECLARATION_DIR).exists())

    def test_scheduled_send_is_a_server_process(self):
        self.assertTrue(is_server_process(["--config", "x.json", "declaration", "send-scheduled"]))
        self.assertFalse(is_server_process(["declaration", "status"]))

    def test_version_comes_from_pyproject(self):
        (self.root / "pyproject.toml").write_text('[project]\nversion = "9.8.7"\n', encoding="utf-8")
        self.assertEqual(application_version(self.root), "9.8.7")


if __name__ == "__main__":
    os.environ.pop("DO_NOT_TRACK", None)
    unittest.main()
