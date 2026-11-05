"""Commandes RIPOSTE qui AGISSENT (OMEGA-SERV_PLAN-DETAILLE_RIPOSTE.md §3.7, §9.1, lot 4) : actions (liste,
detail, levee, levee + exemption, « ne pas compter dans la recidive »), regles (activer, desactiver avec
ou sans levee), memoire d'une source, exemptions, arret d'urgence et reprise.

Principe « voir, choisir, actionner » : la CLI ne touche jamais au registre des actions. Elle DEPOSE une
commande dans la base, executee par le processus RIPOSTE en <= 1 s ; elle attend le resultat quelques
secondes et l'affiche. Processus arrete : la commande attend son prochain demarrage (dit a l'ecran).
L'arret d'urgence est un drapeau pose directement : persistant, respecte meme processus arrete.
Textes traduits (commandes d'interface, jamais lancees par `serve`)."""
from __future__ import annotations

import argparse
import sys
import time
from typing import Any

from omega_serv.application.config.load_config import load_config
from omega_serv.application.riposte.console import (
    emergency_stop,
    emergency_stop_active,
    finished_commands,
    process_running,
    resume,
    riposte_enabled,
    set_policy_enabled,
    submit_commands,
)
from omega_serv.bootstrap.container import DependencyContainer
from omega_serv.core.i18n import _
from omega_serv.domain.config.entities import OmegaServConfig
from omega_serv.domain.security.riposte.actions import EXEMPT_DURATIONS, RiposteAction
from omega_serv.domain.security.riposte.config import parse_riposte_config
from omega_serv.infrastructure.persistence.sqlite_riposte_connection import open_riposte_connection
from omega_serv.infrastructure.persistence.sqlite_riposte_store import SqliteRiposteStore
from omega_serv.interfaces.cli.riposte_text import (
    action_detail_label,
    action_label,
    action_state_label,
    command_result_text,
    finished_by_label,
)

WAIT_SECONDS = 3.0
_POLL_SECONDS = 0.2


def _load(args: argparse.Namespace, container: DependencyContainer) -> OmegaServConfig | None:
    result = load_config(container.configuration, args.config)
    if not result.success or result.config is None:
        print(_("Configuration illisible : ") + "; ".join(result.errors), file=sys.stderr)
        return None
    return result.config


def _database(config: OmegaServConfig, container: DependencyContainer) -> Any:
    option = config.options.get("riposte")
    return container.project_root / parse_riposte_config(option.settings if option is not None else {}).database


def _open(config: OmegaServConfig, container: DependencyContainer, *, write: bool) -> SqliteRiposteStore | None:
    """`write` : depot d'une commande - jamais de creation de base (elle appartient au service)."""
    try:
        connection = open_riposte_connection(_database(config, container), read_only=not write, create=False)
    except FileNotFoundError:
        print(_("RIPOSTE n'a encore jamais été lancé sur cette instance."))
        return None
    except OSError as error:
        print(_("Base RIPOSTE illisible : {error}").format(error=error), file=sys.stderr)
        if write:
            print(_("Droits d'écriture sur la base requis (groupe du service omega-serv)."), file=sys.stderr)
        return None
    return SqliteRiposteStore(connection)


def _submit(store: SqliteRiposteStore, container: DependencyContainer, commands: list[tuple[str, dict[str, Any]]],
            *, wait: float = WAIT_SECONDS) -> int:
    """Depose les commandes (dans l'ordre), attend leur execution et affiche les resultats."""
    try:
        ids = submit_commands(store, commands, container.clock.now())
    except OSError as error:
        print(_("Commande non déposée : {error}").format(error=error), file=sys.stderr)
        return 1
    return _wait_and_print(store, container, ids, wait=wait)


def _wait_and_print(store: SqliteRiposteStore, container: DependencyContainer, ids: list[int],
                    *, wait: float = WAIT_SECONDS) -> int:
    if not process_running(store, container.clock.now()):
        print(_("RIPOSTE est arrêté : la commande sera exécutée à son prochain démarrage."))
        return 0
    deadline = time.monotonic() + wait
    shown: set[int] = set()
    failed = False
    while len(shown) < len(ids) and time.monotonic() < deadline:
        for command in finished_commands(store, ids):
            if command.id not in shown:
                shown.add(command.id)
                print(command_result_text(command.result, command.result_params))
                failed = failed or command.state == "failed"
        if len(shown) < len(ids):
            time.sleep(_POLL_SECONDS)
    if len(shown) < len(ids):
        print(_("Commande déposée, pas encore exécutée : vérifier avec « riposte actions list »."))
    return 1 if failed else 0


def _action_line(action: RiposteAction) -> str:
    tier = _(" palier {n}").format(n=action.tier_index + 1) if action.tier_index is not None else ""
    end = action.finished_at if action.finished_at is not None and not action.in_progress else action.ends_at
    return _("{id}  {ip}  {action}{tier}  [{policy}]  {state} - jusqu'au {end}").format(
        id=action.id, ip=action.ip, action=action_label(action.kind), tier=tier, policy=action.policy_id,
        state=action_state_label(action.state), end=end.isoformat(timespec="seconds"))


def cmd_riposte_actions_list(args: argparse.Namespace, container: DependencyContainer) -> int:
    config = _load(args, container)
    if config is None:
        return 1
    store = _open(config, container, write=False)
    if store is None:
        return 0
    actions = store.list_actions(in_progress=not args.finished, limit=args.limit, ip=args.ip)
    if not actions:
        print(_("Aucune action terminée.") if args.finished else _("Aucune action en cours."))
    for action in actions:
        print(_action_line(action))
    if emergency_stop_active(store):
        print(_("Arrêt d'urgence : ACTIF"))
    return 0


def cmd_riposte_actions_show(args: argparse.Namespace, container: DependencyContainer) -> int:
    config = _load(args, container)
    if config is None:
        return 1
    store = _open(config, container, write=False)
    if store is None:
        return 0
    action = store.get_action(args.id)
    if action is None:
        print(command_result_text("unknown_action", {"action_id": args.id}))
        return 1
    print(_action_line(action))
    print("  " + _("Créée le {when} (événement {event})").format(
        when=action.created_at.isoformat(timespec="seconds"), event=action.event_id or "-"))
    if action.decoy_profile:
        print("  " + _("Leurre {profile} pour : {subjects}").format(
            profile=action.decoy_profile, subjects=", ".join(action.subject_ids) or "-"))
    if action.finished_at is not None:
        print("  " + _("Terminée le {when} : {by}").format(
            when=action.finished_at.isoformat(timespec="seconds"), by=finished_by_label(action.finished_by)))
    if action.detail:
        print("  " + action_detail_label(action.detail))
    if not action.counts_for_recidive:
        print("  " + _("Ne compte pas dans la récidive."))
    return 0


def cmd_riposte_actions_revoke(args: argparse.Namespace, container: DependencyContainer) -> int:
    config = _load(args, container)
    if config is None:
        return 1
    store = _open(config, container, write=True)
    if store is None:
        return 1
    return _submit(store, container, [("revoke", {
        "action_id": args.id, "exempt": args.exempt, "not_recidive": bool(args.not_recidive),
    })])


def cmd_riposte_actions_not_recidive(args: argparse.Namespace, container: DependencyContainer) -> int:
    config = _load(args, container)
    if config is None:
        return 1
    store = _open(config, container, write=True)
    if store is None:
        return 1
    return _submit(store, container, [("not_recidive", {"action_id": args.id})])


def _set_policy_enabled(args: argparse.Namespace, container: DependencyContainer, enabled: bool) -> int:
    config = _load(args, container)
    if config is None:
        return 1
    saved = set_policy_enabled(container.configuration, args.config, config, args.id, enabled)
    if saved.unknown:
        print(_("Politique inconnue : {id}").format(id=args.id), file=sys.stderr)
        return 1
    if saved.errors:
        print(_("Configuration RIPOSTE invalide : ") + "; ".join(saved.errors), file=sys.stderr)
        return 1
    print((_("Politique {id} activée.") if enabled else _("Politique {id} désactivée.")).format(id=args.id))
    if not riposte_enabled(config):
        return 0
    store = _open(config, container, write=True)
    if store is None:
        return 0
    commands: list[tuple[str, dict[str, Any]]] = [("reload", {})]
    if not enabled and getattr(args, "revoke", False):
        commands.append(("revoke_policy", {"policy_id": args.id}))
    elif not enabled:
        print(_("Les actions déjà en cours de cette politique vont jusqu'à leur échéance (« --revoke » pour les lever)."))
    return _submit(store, container, commands)


def cmd_riposte_policies_enable(args: argparse.Namespace, container: DependencyContainer) -> int:
    return _set_policy_enabled(args, container, True)


def cmd_riposte_policies_disable(args: argparse.Namespace, container: DependencyContainer) -> int:
    return _set_policy_enabled(args, container, False)


def cmd_riposte_sources_forget(args: argparse.Namespace, container: DependencyContainer) -> int:
    config = _load(args, container)
    if config is None:
        return 1
    store = _open(config, container, write=True)
    if store is None:
        return 1
    return _submit(store, container, [("forget_source", {"ip": args.ip})])


def cmd_riposte_exemptions_list(args: argparse.Namespace, container: DependencyContainer) -> int:
    config = _load(args, container)
    if config is None:
        return 1
    store = _open(config, container, write=False)
    if store is None:
        return 0
    exemptions = store.list_exemptions()
    if not exemptions:
        print(_("Aucune exemption ajoutée (les exclusions de la configuration s'appliquent toujours)."))
    for exemption in exemptions:
        print(_("{network}  jusqu'au {until}  (action {action})").format(
            network=exemption.network,
            until=exemption.until.isoformat(timespec="seconds") if exemption.until else _("retrait manuel"),
            action=exemption.origin_action_id or "-"))
    return 0


def cmd_riposte_exemptions_remove(args: argparse.Namespace, container: DependencyContainer) -> int:
    config = _load(args, container)
    if config is None:
        return 1
    store = _open(config, container, write=True)
    if store is None:
        return 1
    return _submit(store, container, [("remove_exemption", {"network": args.network})])


def cmd_riposte_stop(args: argparse.Namespace, container: DependencyContainer) -> int:
    config = _load(args, container)
    if config is None:
        return 1
    store = _open(config, container, write=True)
    if store is None:
        return 1
    ids = emergency_stop(store, container.clock.now(), revoke=args.revoke)
    print(_("Arrêt d'urgence ACTIF : aucune nouvelle action, même après un redémarrage, jusqu'à « riposte resume »."))
    if args.revoke:
        return _wait_and_print(store, container, ids)
    print(_("Les actions en cours vont jusqu'à leur échéance (« --revoke » pour les lever)."))
    return 0


def cmd_riposte_resume(args: argparse.Namespace, container: DependencyContainer) -> int:
    config = _load(args, container)
    if config is None:
        return 1
    store = _open(config, container, write=True)
    if store is None:
        return 1
    resume(store, container.clock.now())
    print(_("Arrêt d'urgence levé : RIPOSTE reprend ses décisions."))
    return 0


def register(riposte_sub: argparse._SubParsersAction, policies: argparse._SubParsersAction,
             sources: argparse._SubParsersAction) -> None:
    actions = riposte_sub.add_parser("actions").add_subparsers(dest="riposte_actions_command", required=True)
    actions_list = actions.add_parser("list")
    actions_list.add_argument("--finished", action="store_true")
    actions_list.add_argument("--ip", default=None)
    actions_list.add_argument("--limit", type=int, default=50)
    actions_list.set_defaults(func=cmd_riposte_actions_list)
    actions_show = actions.add_parser("show")
    actions_show.add_argument("id")
    actions_show.set_defaults(func=cmd_riposte_actions_show)
    actions_revoke = actions.add_parser("revoke")
    actions_revoke.add_argument("id")
    actions_revoke.add_argument("--exempt", default=None, choices=tuple(EXEMPT_DURATIONS))
    actions_revoke.add_argument("--not-recidive", action="store_true")
    actions_revoke.set_defaults(func=cmd_riposte_actions_revoke)
    actions_not_recidive = actions.add_parser("not-recidive")
    actions_not_recidive.add_argument("id")
    actions_not_recidive.set_defaults(func=cmd_riposte_actions_not_recidive)

    enable = policies.add_parser("enable")
    enable.add_argument("id")
    enable.set_defaults(func=cmd_riposte_policies_enable)
    disable = policies.add_parser("disable")
    disable.add_argument("id")
    disable.add_argument("--revoke", action="store_true")
    disable.set_defaults(func=cmd_riposte_policies_disable)

    forget = sources.add_parser("forget")
    forget.add_argument("ip")
    forget.set_defaults(func=cmd_riposte_sources_forget)

    exemptions = riposte_sub.add_parser("exemptions").add_subparsers(dest="riposte_exemptions_command", required=True)
    exemptions.add_parser("list").set_defaults(func=cmd_riposte_exemptions_list)
    exemptions_remove = exemptions.add_parser("remove")
    exemptions_remove.add_argument("network")
    exemptions_remove.set_defaults(func=cmd_riposte_exemptions_remove)

    stop = riposte_sub.add_parser("stop")
    stop.add_argument("--revoke", action="store_true")
    stop.set_defaults(func=cmd_riposte_stop)
    riposte_sub.add_parser("resume").set_defaults(func=cmd_riposte_resume)
