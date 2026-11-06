"""Declaration anonyme d'utilisateur (OMEGA-SERV_ETUDE_TELEMETRIE.md §3b) : commandes et envoi quotidien.

- `omega-serv declaration status` : etat (traduit : c'est l'interface).
- `omega-serv declaration declare --mode unique|quotidien [--continent X] [--pays Y] --yes` : se
  declarer. Sans `--yes`, affiche seulement le message exact et la destination : la ligne de
  commande vaut accord, il faut donc le confirmer explicitement.
- `omega-serv declaration withdraw` : ne plus se declarer (l'entree est supprimee a la reception).
- `omega-serv declaration send-scheduled` : l'envoi quotidien lui-meme, lance par `serve` dans un
  processus a part. Messages vers journalctl : en francais (D18b, comme `serve`).
- `DeclarationScheduler` : utilise par `serve` (les trois modes). Ne fait jamais rien dans le
  serveur lui-meme : au plus une fois par heure, il lit deux petits fichiers et, si l'envoi est du,
  lance `send-scheduled` par posix_spawn (jamais un fil dans le superviseur, qui `fork`). Le
  serveur ne l'attend jamais : ni au demarrage, ni a l'arret."""
from __future__ import annotations

import argparse
import json
import os
import signal
import sys
import time
from collections.abc import Callable, Mapping, Sequence
from datetime import datetime
from pathlib import Path

from omega_serv.application.config.load_config import load_config
from omega_serv.application.declaration.use_cases import (
    declaration_status,
    declare,
    preview_payload,
    send_scheduled,
    withdraw,
)
from omega_serv.bootstrap.container import DependencyContainer
from omega_serv.core.i18n import _
from omega_serv.domain.declaration.countries import COUNTRY_CODES
from omega_serv.domain.declaration.model import (
    CONTINENTS,
    MODE_DAILY,
    MODES,
    OTHER,
    RECEPTION_URL,
    daily_send_due,
    do_not_track,
)
from omega_serv.infrastructure.declaration.https_sender import HttpsDeclarationSender
from omega_serv.infrastructure.process.child_process import SpawnedChild
from omega_serv.interfaces.cli.command_tree import add_command, add_group
from omega_serv.interfaces.cli.serve_native import log_error_line
from omega_serv.ports.declaration_port import DeclarationStorePort

FIRST_CHECK_SECONDS = 60.0
"""Premier controle une minute apres le demarrage : un demarrage n'attend jamais la reception."""
CHECK_EVERY_SECONDS = 3600.0
SPAWN_INTERVAL_SECONDS = 24 * 3600.0
"""Garde-fou en memoire : meme si le journal des envois ne peut pas etre ecrit, jamais plus d'un
envoi par 24 h depuis ce processus."""


def _when(value: datetime | None) -> str:
    return value.astimezone().strftime("%Y-%m-%d %H:%M") if value is not None else "-"


def cmd_declaration_status(args: argparse.Namespace, container: DependencyContainer) -> int:
    status = declaration_status(container.declaration_store, os.environ)
    if status.declaration is None:
        print(_("Non déclaré (aucune clé sur cette installation)."))
    else:
        declaration = status.declaration
        mode = _("chaque jour") if declaration.mode == MODE_DAILY else _("une seule fois")
        print(_("Déclaré utilisateur anonyme depuis le {date}.").format(date=_when(status.declared_at)))
        print(_("Envoi : {mode}").format(mode=mode))
        print(_("Clé : {key}").format(key=declaration.key))
        print(_("Continent : {continent}").format(continent=declaration.continent or "-"))
        print(_("Pays : {country}").format(country=declaration.country or "-"))
        print(_("Dernier envoi réussi : {date}").format(date=_when(status.last_success)))
        if status.last_error:
            print(_("Dernier essai : réception injoignable ({reason}).").format(reason=status.last_error))
    if status.do_not_track:
        print(_("DO_NOT_TRACK est défini : aucun envoi automatique."))
    print(_("Destination : {url}").format(url=RECEPTION_URL))
    return 0


def cmd_declaration_declare(args: argparse.Namespace, container: DependencyContainer) -> int:
    store = container.declaration_store
    version = container.app_version
    continent = args.continent or ""
    country = args.pays or ""
    payload = preview_payload(store, version, args.mode, continent, country)
    if not args.yes:
        print(_("Message qui sera envoyé à {url} :").format(url=RECEPTION_URL))
        print("  " + json.dumps(payload, ensure_ascii=False))
        print(_("Ajoutez --yes pour confirmer la déclaration."))
        return 1
    try:
        result = declare(store, HttpsDeclarationSender(version), container.clock, version,
                         args.mode, continent, country)
    except ValueError as error:
        print(_("Déclaration refusée : {error}").format(error=error), file=sys.stderr)
        return 2
    if result.ok:
        print(_("Merci ! Vous êtes déclaré utilisateur anonyme."))
        return 0
    if result.recorded:
        print(_("Réception injoignable ({reason}) : votre accord est gardé, le serveur réessaiera dans 24 h.")
              .format(reason=result.reason), file=sys.stderr)
        return 1
    print(_("Réception injoignable ({reason}) : rien n'a été enregistré, réessayez plus tard.")
          .format(reason=result.reason), file=sys.stderr)
    return 1


def cmd_declaration_withdraw(args: argparse.Namespace, container: DependencyContainer) -> int:
    result = withdraw(container.declaration_store, HttpsDeclarationSender(container.app_version))
    if not result.was_declared:
        print(_("Non déclaré : rien à retirer."))
        return 0
    if result.reception_reached:
        print(_("Vous n'êtes plus déclaré : votre entrée est supprimée et la clé effacée."))
    else:
        print(_("Clé effacée. Réception injoignable : votre entrée y disparaîtra seule "
                "(90 jours en envoi quotidien, 1 an en envoi unique)."))
    return 0


def cmd_declaration_send_scheduled(args: argparse.Namespace, container: DependencyContainer) -> int:
    """Processus lance par `serve` : un envoi au plus, puis fin. Une seule ligne au journal
    d'erreurs par serie d'echecs (rien tant que ca ne remarche pas)."""
    store = container.declaration_store
    previous_error = store.load_service_log().last_error
    version = container.app_version
    try:
        outcome = send_scheduled(store, HttpsDeclarationSender(version), container.clock, version, os.environ)
    except OSError as error:  # var/lib/declaration/ non inscriptible : jamais une erreur du service
        print(f"declaration anonyme : journal des envois non inscriptible ({error})", file=sys.stderr)
        return 0
    if outcome is None or outcome.ok or previous_error:
        return 0
    message = f"declaration anonyme : reception injoignable ({outcome.reason}) - nouvel essai dans 24 h"
    print(message, file=sys.stderr)
    result = load_config(container.configuration, args.config)
    if result.success and result.config is not None:
        log_error_line(container, result.config, message)
    return 0


class DeclarationScheduler:
    """Pilote l'envoi quotidien depuis `serve`. `tick()` est appele toutes les secondes par la
    boucle du serveur ; il ne fait presque toujours qu'une comparaison d'horloge."""

    def __init__(
        self,
        argv: Sequence[str],
        store: DeclarationStorePort,
        *,
        now: Callable[[], datetime],
        environ: Mapping[str, str] = os.environ,
        spawn: Callable[[Sequence[str]], SpawnedChild] = SpawnedChild.spawn,
        monotonic: Callable[[], float] = time.monotonic,
        log: Callable[[str], None] | None = None,
    ) -> None:
        self._argv = list(argv)
        self._store = store
        self._now = now
        self._environ = environ
        self._spawn = spawn
        self._monotonic = monotonic
        self._log = log or (lambda message: print(message, file=sys.stderr))
        self._child: SpawnedChild | None = None
        self._next_check = 0.0
        self._last_spawn: float | None = None

    def start(self) -> None:
        self._next_check = self._monotonic() + FIRST_CHECK_SECONDS

    def tick(self) -> None:
        if self._child is not None and not self._child.is_running():
            self._child = None
        now = self._monotonic()
        if now < self._next_check:
            return
        self._next_check = now + CHECK_EVERY_SECONDS
        if self._child is not None:
            return
        if self._last_spawn is not None and now - self._last_spawn < SPAWN_INTERVAL_SECONDS:
            return
        if not self._due():
            return
        try:
            self._child = self._spawn(self._argv)
        except OSError as error:
            self._log(f"declaration anonyme : lancement de l'envoi impossible ({error})")
        self._last_spawn = now

    def _due(self) -> bool:
        try:
            stored = self._store.load()
            log = self._store.load_service_log()
        except (OSError, ValueError):
            return False
        attempts = [t for t in (log.last_attempt, stored.last_attempt if stored else None) if t is not None]
        return daily_send_due(stored.declaration if stored else None, max(attempts) if attempts else None,
                              self._now(), do_not_track_set=do_not_track(self._environ))

    def reload(self) -> None:
        """Rien a relire : l'accord et le mode sont relus a chaque controle."""

    def stop(self) -> None:
        """Jamais attendu : un envoi en cours est simplement abandonne."""
        if self._child is not None:
            self._child.send_signal(signal.SIGTERM)
            self._child = None


def build_declaration_scheduler(container: DependencyContainer, config_path: Path) -> DeclarationScheduler:
    argv = [sys.executable, "-m", "omega_serv", "--config", str(config_path), "declaration", "send-scheduled"]
    return DeclarationScheduler(argv, container.declaration_store, now=container.clock.now)


class ServeCompanions:
    """Processus accompagnant `serve` (RIPOSTE, envoi quotidien), pilotes ensemble : meme contrat
    que RiposteChildPort (start, tick, reload, stop)."""

    def __init__(self, *members: object) -> None:
        self._members = [member for member in members if member is not None]

    def start(self) -> None:
        for member in self._members:
            member.start()  # type: ignore[attr-defined]

    def tick(self) -> None:
        for member in self._members:
            member.tick()  # type: ignore[attr-defined]

    def reload(self) -> None:
        for member in self._members:
            member.reload()  # type: ignore[attr-defined]

    def stop(self) -> None:
        for member in self._members:
            member.stop()  # type: ignore[attr-defined]


def _country_argument(value: str) -> str:
    return OTHER if value.lower() == OTHER else value.upper()


def add_declaration_parser(subparsers: argparse._SubParsersAction) -> None:
    declaration_sub = add_group(subparsers, "declaration", _(
        "Déclaration anonyme d'utilisateur (volontaire, désactivée par défaut)."), "declaration_command")
    add_command(declaration_sub, "status", _("Affiche l'état de la déclaration.")).set_defaults(
        func=cmd_declaration_status)
    declare_parser = add_command(declaration_sub, "declare", _(
        "Se déclarer utilisateur. Sans --yes, affiche seulement le message exact et sa destination."))
    declare_parser.add_argument("--mode", choices=MODES, required=True, help=_(
        "unique : une seule fois ; quotidien : chaque jour, envoyé par le serveur."))
    declare_parser.add_argument("--continent", choices=(*CONTINENTS, OTHER), default="", metavar=_("CODE"), help=_(
        "Continent (facultatif) : AF, AN, AS, EU, NA, OC, SA ou autre."))
    declare_parser.add_argument("--pays", choices=(*COUNTRY_CODES, OTHER), default="", type=_country_argument,
                                metavar=_("CODE"), help=_("Pays (facultatif) : code à deux lettres (FR, BE...) ou autre."))
    declare_parser.add_argument("--yes", action="store_true", help=_("Confirme l'envoi."))
    declare_parser.set_defaults(func=cmd_declaration_declare)
    add_command(declaration_sub, "withdraw", _(
        "Retire la déclaration (supprimée à la réception).")).set_defaults(func=cmd_declaration_withdraw)
    add_command(declaration_sub, "send-scheduled", _(
        "Envoi quotidien, lancé par serve (pas à utiliser à la main).")).set_defaults(func=cmd_declaration_send_scheduled)
