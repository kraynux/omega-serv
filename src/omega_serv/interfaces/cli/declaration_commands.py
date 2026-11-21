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
import sys
from datetime import datetime
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from omega_serv.bootstrap.container import DependencyContainer

from omega_serv.domain.services.python_command import python_module_argv
from omega_serv.interfaces.cli.declaration_scheduler import DeclarationScheduler


def _when(value: datetime | None) -> str:
    return value.astimezone().strftime("%Y-%m-%d %H:%M") if value is not None else "-"


def cmd_declaration_status(args: argparse.Namespace, container: DependencyContainer) -> int:
    from omega_serv.application.declaration.use_cases import declaration_status
    from omega_serv.core.i18n import _
    from omega_serv.domain.declaration.model import MODE_DAILY, RECEPTION_URL
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
    from omega_serv.application.declaration.use_cases import declare, preview_payload
    from omega_serv.core.i18n import _
    from omega_serv.domain.declaration.model import RECEPTION_URL
    from omega_serv.infrastructure.declaration.https_sender import HttpsDeclarationSender
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
    from omega_serv.application.declaration.use_cases import withdraw
    from omega_serv.core.i18n import _
    from omega_serv.infrastructure.declaration.https_sender import HttpsDeclarationSender
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
    from omega_serv.application.config.load_config import load_config
    from omega_serv.application.declaration.use_cases import send_scheduled
    from omega_serv.infrastructure.declaration.https_sender import HttpsDeclarationSender
    from omega_serv.interfaces.cli.serve_native import log_error_line
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


def build_declaration_scheduler(container: DependencyContainer, config_path: Path) -> DeclarationScheduler:
    argv = python_module_argv(sys.executable, "omega_serv", "--config", str(config_path), "declaration", "send-scheduled")
    return DeclarationScheduler(argv, container.declaration_store, now=container.clock.now)


def _country_argument(value: str) -> str:
    from omega_serv.domain.declaration.model import OTHER
    return OTHER if value.lower() == OTHER else value.upper()


def add_declaration_parser(subparsers: argparse._SubParsersAction) -> None:
    from omega_serv.core.i18n import _
    from omega_serv.domain.declaration.countries import COUNTRY_CODES
    from omega_serv.domain.declaration.model import CONTINENTS, MODES, OTHER
    from omega_serv.interfaces.cli.command_tree import add_command, add_group
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
