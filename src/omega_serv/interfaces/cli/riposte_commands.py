"""Commandes RIPOSTE et supervision du processus (OMEGA-SERV_PLAN-DETAILLE_RIPOSTE.md §3.1, §6, lot 2).

- `omega-serv riposte run` : le processus RIPOSTE lui-meme (lance par `serve`, utilisable seul pour
  le diagnostic). Messages vers journalctl : en francais (D18b, comme `serve`).
- `omega-serv riposte status` : etat lu dans la base, en lecture seule (traduit : c'est l'interface).
- `RiposteChildSupervisor` : utilise par `serve` (mode simple ET mode boost) pour lancer, surveiller,
  relancer (avec garde-fou), recharger et arreter le processus. Une panne de RIPOSTE n'arrete jamais
  le serveur web : passe le garde-fou, c'est RIPOSTE seul qui reste arrete."""
from __future__ import annotations

import argparse
import os
import signal
import sys
import time
from collections.abc import Callable, Sequence
from datetime import datetime
from pathlib import Path
from types import FrameType

from omega_serv.application.config.load_config import load_config
from omega_serv.application.riposte.actuator import ActionTargets, RiposteActuator
from omega_serv.application.riposte.commands import RiposteCommandRunner
from omega_serv.application.riposte.console import (
    decoy_profiles,
    journal_paths,
    riposte_config_of,
    riposte_enabled,
)
from omega_serv.application.riposte.engine import RiposteEngine
from omega_serv.application.riposte.follow_journals import JournalSource
from omega_serv.application.riposte.get_status import get_riposte_status
from omega_serv.application.riposte.run_riposte import run_riposte
from omega_serv.application.riposte.safety import riposte_exempt_networks
from omega_serv.application.server.start_server import build_blocklist_port
from omega_serv.bootstrap.container import DependencyContainer
from omega_serv.core.i18n import _
from omega_serv.domain.config.entities import OmegaServConfig
from omega_serv.domain.security.active_defense.config import (
    parse_active_defense_config,
)
from omega_serv.domain.security.riposte.config import parse_riposte_config, validate_riposte_config
from omega_serv.domain.security.riposte.events import (
    parse_security_event_line,
    parse_waf_alert_line,
)
from omega_serv.infrastructure.persistence.sqlite_active_defense_connection import (
    open_active_defense_connection,
)
from omega_serv.infrastructure.persistence.sqlite_deception_assignment_repository import (
    SqliteDeceptionAssignmentRepository,
)
from omega_serv.infrastructure.persistence.sqlite_riposte_connection import open_riposte_connection
from omega_serv.infrastructure.persistence.sqlite_riposte_store import SqliteRiposteStore
from omega_serv.infrastructure.process.child_process import SpawnedChild
from omega_serv.infrastructure.riposte.log_follower import LogFollower
from omega_serv.infrastructure.riposte.process_lock import ProcessLock
from omega_serv.interfaces.cli.riposte_text import format_status

RESTART_WINDOW_SECONDS = 60.0
MAX_RESTARTS_IN_WINDOW = 5
STOP_GRACE_SECONDS = 5.0
LOCK_RELATIVE_PATH = Path("var") / "run" / "riposte.lock"
RECONCILE_SECONDS = 60.0


class RiposteChildSupervisor:
    """Pilote le processus `riposte run`. `tick()` est appele regulierement par le serveur
    (toutes les secondes) ; jamais bloquant hors de `stop()`."""

    def __init__(
        self,
        argv: Sequence[str],
        *,
        spawn: Callable[[Sequence[str]], SpawnedChild] = SpawnedChild.spawn,
        monotonic: Callable[[], float] = time.monotonic,
        log: Callable[[str], None] | None = None,
    ) -> None:
        self._argv = list(argv)
        self._spawn = spawn
        self._monotonic = monotonic
        self._log = log or (lambda message: print(message, file=sys.stderr))
        self._child: SpawnedChild | None = None
        self._deaths: list[float] = []
        self.gave_up = False

    def start(self) -> None:
        try:
            self._child = self._spawn(self._argv)
        except OSError as error:
            self._log(f"RIPOSTE : lancement impossible ({error}) - le serveur web continue sans RIPOSTE")
            self.gave_up = True
            return
        print(f"RIPOSTE lance (PID {self._child.pid})")

    def tick(self) -> None:
        if self.gave_up or self._child is None or self._child.is_running():
            return
        now = self._monotonic()
        self._deaths[:] = [t for t in self._deaths if now - t < RESTART_WINDOW_SECONDS] + [now]
        if len(self._deaths) > MAX_RESTARTS_IN_WINDOW:
            self._log(
                f"RIPOSTE arrete {len(self._deaths)} fois en {int(RESTART_WINDOW_SECONDS)} s : plus de relance "
                "(le serveur web continue ; voir les messages de RIPOSTE ci-dessus)"
            )
            self.gave_up = True
            self._child = None
            return
        self._log(f"RIPOSTE (PID {self._child.pid}) arrete de facon inattendue : relance")
        self.start()

    def reload(self) -> None:
        if self._child is not None:
            self._child.send_signal(signal.SIGHUP)

    def stop(self) -> None:
        if self._child is not None:
            self._child.stop(STOP_GRACE_SECONDS)
            self._child = None


def build_riposte_supervisor(config: OmegaServConfig, config_path: Path) -> RiposteChildSupervisor | None:
    """Rien si RIPOSTE est desactive (defaut) : aucun processus, aucun fichier."""
    if not riposte_enabled(config):
        return None
    argv = [sys.executable, "-m", "omega_serv", "--config", str(config_path), "riposte", "run"]
    return RiposteChildSupervisor(argv)


def cmd_riposte_run(args: argparse.Namespace, container: DependencyContainer) -> int:
    # Sous un gestionnaire de service, stdout n'est pas un terminal : sans cela, les messages
    # n'arriveraient dans journalctl qu'a l'arret (meme correctif que `serve`, 2026-10-26).
    for stream in (sys.stdout, sys.stderr):
        reconfigure = getattr(stream, "reconfigure", None)
        if reconfigure is not None:
            reconfigure(line_buffering=True)
    result = load_config(container.configuration, args.config)
    if not result.success or result.config is None:
        print("RIPOSTE : configuration illisible - " + "; ".join(result.errors), file=sys.stderr)
        return 1
    config = result.config
    if not riposte_enabled(config):
        print("RIPOSTE desactive (options.riposte) : rien a faire")
        return 0
    riposte_config = parse_riposte_config(config.options["riposte"].settings)
    errors = validate_riposte_config(riposte_config, decoy_profile_names=decoy_profiles(config))
    if errors:
        print("RIPOSTE : configuration invalide - " + "; ".join(errors), file=sys.stderr)
        return 1
    root = container.project_root
    waf_option = config.options.get("waf")
    if waf_option is None or not waf_option.enabled:
        print("RIPOSTE : WAF inactif - aucune attaque ne sera vue, les actions de ban restent sans effet", file=sys.stderr)

    lock = ProcessLock(root / LOCK_RELATIVE_PATH)
    if not lock.acquire():
        print("RIPOSTE deja lance pour cette instance (verrou var/run/riposte.lock tenu)", file=sys.stderr)
        return 1
    stop_requested = False
    reload_requested = False

    def _request_stop(_signum: int, _frame: FrameType | None) -> None:
        nonlocal stop_requested
        stop_requested = True

    def _request_reload(_signum: int, _frame: FrameType | None) -> None:
        nonlocal reload_requested
        reload_requested = True  # traite dans la boucle (on_tick), jamais dans le gestionnaire de signal

    signal.signal(signal.SIGTERM, _request_stop)
    signal.signal(signal.SIGINT, _request_stop)
    signal.signal(signal.SIGHUP, _request_reload)
    try:
        connection = open_riposte_connection(root / riposte_config.database)
    except OSError as error:
        lock.release()
        print(f"RIPOSTE : base inaccessible ({error})", file=sys.stderr)
        return 1
    targets = _Targets(container)
    try:
        store = SqliteRiposteStore(connection)
        waf_log, security_log = journal_paths(config, root)
        sources = [
            JournalSource("waf", LogFollower(waf_log, store.get_position("waf")), parse_waf_alert_line),
            JournalSource("security", LogFollower(security_log, store.get_position("security")),
                          parse_security_event_line),
        ]
        actuator = RiposteActuator(store, targets.build(config))
        engine = RiposteEngine(store, riposte_config, riposte_exempt_networks(config, riposte_config),
                               actuator=actuator, clock=container.clock)

        def _reload() -> str | None:
            """None si la nouvelle configuration est appliquee, sinon le code du refus."""
            reloaded = load_config(container.configuration, args.config)
            if not reloaded.success or reloaded.config is None or not riposte_enabled(reloaded.config):
                print("RIPOSTE : rechargement REFUSE (configuration illisible ou RIPOSTE desactive) - "
                      "les politiques precedentes restent actives", file=sys.stderr)
                return "config_unreadable"
            new_config = parse_riposte_config(reloaded.config.options["riposte"].settings)
            problems = validate_riposte_config(new_config, decoy_profile_names=decoy_profiles(reloaded.config))
            if problems:
                print("RIPOSTE : rechargement REFUSE - " + "; ".join(problems), file=sys.stderr)
                return "config_invalid"
            engine.update_config(new_config, riposte_exempt_networks(reloaded.config, new_config))
            actuator.update_targets(targets.build(reloaded.config))
            print(f"RIPOSTE : politiques rechargees ({len(new_config.policies)})")
            return None

        commands = RiposteCommandRunner(store, actuator, container.clock, reload=_reload)
        last_reconcile = time.monotonic()

        def _tick() -> None:
            nonlocal reload_requested, last_reconcile
            if reload_requested:
                reload_requested = False
                _reload()
            commands.run_pending()
            if time.monotonic() - last_reconcile >= RECONCILE_SECONDS:
                last_reconcile = time.monotonic()
                _report_reconcile(actuator.reconcile(container.clock.now()))

        def _maintenance(now: datetime) -> None:
            engine.maintenance(now)
            commands.maintenance(now)

        # Avant le premier evenement : etat reel des actions (arret brutal, levees faites hors RIPOSTE).
        _report_reconcile(actuator.reconcile(container.clock.now()))
        print(f"RIPOSTE demarre (PID {os.getpid()}) - suivi de {waf_log} et {security_log} - "
              f"{len(riposte_config.policies)} politique(s)")
        if store.get_state("emergency_stop") == "1":
            print("RIPOSTE : ARRET D'URGENCE ACTIF - aucune nouvelle action jusqu'a « riposte resume »")
        run_riposte(
            sources, store, container.clock,
            should_stop=lambda: stop_requested, sleep=time.sleep,
            report_error=lambda message: print(message, file=sys.stderr), pid=os.getpid(),
            on_events=engine.handle, on_tick=_tick, maintenance=_maintenance,
            extra_stats=lambda: {"decisions": dict(engine.decisions), "actions": dict(engine.actions)},
        )
        print("RIPOSTE arrete")
        return 0
    finally:
        targets.close()
        connection.close()
        lock.release()


def _report_reconcile(counts: dict[str, int]) -> None:
    if counts:
        print("RIPOSTE : reconciliation des actions - " + ", ".join(f"{k} {v}" for k, v in sorted(counts.items())))


class _Targets:
    """Blocklist et affectations de leurres sur lesquelles RIPOSTE agit, reconstruites au rechargement.
    Le leurre passe par la base Active Defense (ecriture courte, comme la CLI `deception`)."""

    def __init__(self, container: DependencyContainer) -> None:
        self._container = container
        self._ad_connection: object | None = None

    def build(self, config: OmegaServConfig) -> ActionTargets:
        self.close()
        root = self._container.project_root
        blocklist = (
            build_blocklist_port(config, root, self._container.filesystem, self._container.clock)
            if config.option_enabled("waf") else None
        )
        deception = None
        ad_option = config.options.get("active_defense")
        if ad_option is not None and ad_option.enabled:
            ad_config = parse_active_defense_config(ad_option.settings)
            if ad_config.deception.enabled:
                try:
                    connection = open_active_defense_connection(root / ad_config.storage.database, lock_timeout=1.0)
                except OSError as error:
                    print(f"RIPOSTE : base Active Defense inaccessible ({error}) - les leurres echoueront",
                          file=sys.stderr)
                else:
                    self._ad_connection = connection
                    deception = SqliteDeceptionAssignmentRepository(connection)
        riposte = riposte_config_of(config)
        network_log = None
        if riposte.network_ban_log and any(p.enabled and p.action == "local_and_network_ban" for p in riposte.policies):
            log_path = root / riposte.decisions_log_path
            logger = self._container.logger

            def network_log(line: str) -> None:
                logger.append_line(log_path, line)
        return ActionTargets(blocklist=blocklist, deception=deception, network_log=network_log)

    def close(self) -> None:
        connection, self._ad_connection = self._ad_connection, None
        close = getattr(connection, "close", None)
        if close is not None:
            close()


def cmd_riposte_status(args: argparse.Namespace, container: DependencyContainer) -> int:
    result = load_config(container.configuration, args.config)
    if not result.success or result.config is None:
        print(_("Configuration illisible : ") + "; ".join(result.errors), file=sys.stderr)
        return 1
    config = result.config
    if not riposte_enabled(config):
        print(_("RIPOSTE est désactivé (options.riposte)."))
    waf_option = config.options.get("waf")
    if waf_option is None or not waf_option.enabled:
        print(_("Activer le WAF pour les actions de ban : sans WAF, RIPOSTE ne voit aucune attaque."))
    riposte_config = parse_riposte_config(config.options["riposte"].settings) if "riposte" in config.options else None
    database = container.project_root / (riposte_config.database if riposte_config else "var/lib/riposte.sqlite3")
    try:
        connection = open_riposte_connection(database, read_only=True)
    except FileNotFoundError:
        print(_("RIPOSTE n'a encore jamais été lancé sur cette instance."))
        return 0
    except OSError as error:
        print(_("Base RIPOSTE illisible : {error}").format(error=error), file=sys.stderr)
        return 1
    try:
        store = SqliteRiposteStore(connection)
        status = get_riposte_status(store, container.clock.now())
        in_progress = store.count_in_progress(bans_only=False)
        bans = store.count_in_progress(bans_only=True)
    finally:
        connection.close()
    for line in format_status(status, in_progress, bans):
        print(line)
    return 0
