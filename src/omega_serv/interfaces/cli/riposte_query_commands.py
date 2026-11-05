"""Commandes de consultation RIPOSTE (OMEGA-SERV_PLAN-DETAILLE_RIPOSTE.md §6, lot 3) : scenarios, politiques,
simulation, mesure, sources et decisions. Aucune n'ecrit quoi que ce soit (base ouverte en lecture seule,
mesure et simulation en memoire). Textes traduits (commandes d'interface, jamais lancees par `serve`)."""
from __future__ import annotations

import argparse
import sys
from datetime import timedelta

from omega_serv.application.config.load_config import load_config
from omega_serv.application.riposte.console import (
    journal_paths,
    simulate_situation,
    single_policy_config,
)
from omega_serv.application.riposte.measure import measure
from omega_serv.application.services.resolve_current_service_name import resolve_current_service_name
from omega_serv.application.riposte.safety import riposte_exempt_networks
from omega_serv.bootstrap.container import DependencyContainer
from omega_serv.core.i18n import _
from omega_serv.domain.config.entities import OmegaServConfig
from omega_serv.domain.security.riposte.config import (
    RiposteConfig,
    parse_riposte_config,
)
from omega_serv.domain.security.riposte.scenarios import SCENARIOS, find_scenario
from omega_serv.infrastructure.persistence.sqlite_riposte_connection import open_riposte_connection
from omega_serv.infrastructure.persistence.sqlite_riposte_store import SqliteRiposteStore
from omega_serv.infrastructure.riposte.journal_events import read_journal_events
from omega_serv.interfaces.cli.riposte_action_commands import register as register_actions
from omega_serv.interfaces.cli.riposte_text import (
    action_label,
    format_decision,
    format_measure,
    policy_lines,
    status_label,
)


def _load(args: argparse.Namespace, container: DependencyContainer) -> tuple[OmegaServConfig, RiposteConfig] | None:
    result = load_config(container.configuration, args.config)
    if not result.success or result.config is None:
        print(_("Configuration illisible : ") + "; ".join(result.errors), file=sys.stderr)
        return None
    option = result.config.options.get("riposte")
    return result.config, parse_riposte_config(option.settings if option is not None else {})


def cmd_riposte_scenarios_list(args: argparse.Namespace, container: DependencyContainer) -> int:
    for scenario in SCENARIOS:
        print(scenario.id.ljust(22) + " " + scenario.name)
    return 0


def cmd_riposte_scenarios_show(args: argparse.Namespace, container: DependencyContainer) -> int:
    scenario = find_scenario(args.id)
    if scenario is None:
        print(_("Scénario inconnu : {id}").format(id=args.id), file=sys.stderr)
        return 1
    print(scenario.name)
    print(_("Pour qui : {text}").format(text=scenario.for_whom))
    print(_("Ce qu'il fait : {text}").format(text=scenario.what_it_does))
    print(_("Ce qu'il ne fait pas : {text}").format(text=scenario.what_it_does_not))
    for line in policy_lines(scenario.policy, RiposteConfig()):
        print(line)
    return 0


def cmd_riposte_policies_list(args: argparse.Namespace, container: DependencyContainer) -> int:
    loaded = _load(args, container)
    if loaded is None:
        return 1
    _config, riposte = loaded
    if not riposte.policies:
        print(_("Aucune politique. Voir « riposte scenarios list » pour partir d'un scénario prêt."))
    for policy in riposte.policies:
        marker = "+" if policy.enabled else "-"
        print(marker + " " + policy.id.ljust(22) + " " + policy.name + "  [" + action_label(policy.action) + "]")
    return 0


def cmd_riposte_policies_show(args: argparse.Namespace, container: DependencyContainer) -> int:
    loaded = _load(args, container)
    if loaded is None:
        return 1
    _config, riposte = loaded
    policy = next((p for p in riposte.policies if p.id == args.id), None)
    if policy is None:
        print(_("Politique inconnue : {id}").format(id=args.id), file=sys.stderr)
        return 1
    service = resolve_current_service_name(container.instance_registry, container.filesystem,
                                           container.settings_store, container.project_root)
    for line in policy_lines(policy, riposte, service):
        print(line)
    return 0


def cmd_riposte_simulate(args: argparse.Namespace, container: DependencyContainer) -> int:
    """Decision expliquee pour une situation saisie, avec la configuration reelle - rien n'est applique."""
    loaded = _load(args, container)
    if loaded is None:
        return 1
    config, _riposte = loaded
    decision = simulate_situation(config, ip=args.ip, attack_class=args.attack_class, level=args.level,
                                  returns=args.returns, decoy_hits=args.decoy_hits, now=container.clock.now())
    print(_("Simulation (rien n'est appliqué) :"))
    for line in format_decision(decision):
        print(line)
    return 0


def cmd_riposte_measure(args: argparse.Namespace, container: DependencyContainer) -> int:
    """`<id>` = une politique de la configuration, ou `scenario:<id>` pour mesurer un scenario avant de l'ajouter."""
    loaded = _load(args, container)
    if loaded is None:
        return 1
    config, riposte = loaded
    if args.id.startswith("scenario:"):
        scenario = find_scenario(args.id.split(":", 1)[1])
        policy = scenario.policy if scenario is not None else None
    else:
        policy = next((p for p in riposte.policies if p.id == args.id), None)
    if policy is None:
        print(_("Politique ou scénario inconnu : {id}").format(id=args.id), file=sys.stderr)
        return 1
    single = single_policy_config(riposte, policy)
    waf_log, security_log = journal_paths(config, container.project_root)
    events = read_journal_events(waf_log, security_log)
    since = container.clock.now() - timedelta(days=args.days) if args.days else None
    for line in format_measure(measure(events, single, riposte_exempt_networks(config, riposte), since=since)):
        print(line)
    return 0


def _open_store(args: argparse.Namespace, container: DependencyContainer, riposte: RiposteConfig) -> SqliteRiposteStore | None:
    try:
        return SqliteRiposteStore(open_riposte_connection(container.project_root / riposte.database, read_only=True))
    except FileNotFoundError:
        print(_("RIPOSTE n'a encore jamais été lancé sur cette instance."))
    except OSError as error:
        print(_("Base RIPOSTE illisible : {error}").format(error=error), file=sys.stderr)
    return None


def cmd_riposte_sources_list(args: argparse.Namespace, container: DependencyContainer) -> int:
    loaded = _load(args, container)
    if loaded is None:
        return 1
    store = _open_store(args, container, loaded[1])
    if store is None:
        return 0
    rows = store.list_sources(args.limit)
    if not rows:
        print(_("Aucune source suivie pour l'instant."))
    for history, updated_at in rows:
        print(_("{ip}  {episodes} épisode(s), {actions} action(s), dernière activité {when}").format(
            ip=history.ip, episodes=len(history.episodes), actions=len(history.actions),
            when=updated_at.isoformat(timespec="seconds")))
    return 0


def cmd_riposte_sources_show(args: argparse.Namespace, container: DependencyContainer) -> int:
    loaded = _load(args, container)
    if loaded is None:
        return 1
    store = _open_store(args, container, loaded[1])
    if store is None:
        return 0
    history = store.get_source(args.ip)
    if history is None:
        print(_("Source inconnue de RIPOSTE : {ip}").format(ip=args.ip))
        return 0
    print(_("Source {ip}").format(ip=history.ip))
    for episode in history.episodes:
        print("  " + _("Épisode du {start} au {end} : {attacks} attaque(s) [{classes}], leurres {decoys}, refus blocklist "
                       "{blocked}{level}{acted}").format(
            start=episode.started_at.isoformat(timespec="seconds"), end=episode.last_seen_at.isoformat(timespec="seconds"),
            attacks=episode.attacks, classes=", ".join(episode.attack_classes) or "-", decoys=episode.decoy_hits,
            blocked=episode.blocklist_hits,
            level=_(", niveau {level}").format(level=episode.max_level) if episode.max_level else "",
            acted=_(", action décidée") if episode.action_taken else ""))
    for action in history.actions:
        print("  " + _("Action {policy} palier {tier} du {start} au {end}").format(
            policy=action.policy_id, tier=action.tier_index + 1, start=action.taken_at.isoformat(timespec="seconds"),
            end=action.ends_at.isoformat(timespec="seconds")))
    return 0


def cmd_riposte_decisions_list(args: argparse.Namespace, container: DependencyContainer) -> int:
    loaded = _load(args, container)
    if loaded is None:
        return 1
    store = _open_store(args, container, loaded[1])
    if store is None:
        return 0
    rows = store.list_decisions(args.limit, ip=args.ip)
    if not rows:
        print(_("Aucune décision enregistrée."))
    for decision, applied in rows:
        print(_("{when}  {ip}  {status}{policy}{applied}").format(
            when=decision.decided_at.isoformat(timespec="seconds"), ip=decision.ip, status=status_label(decision.status),
            policy=f"  [{decision.policy_id}]" if decision.policy_id else "",
            applied="" if applied else _("  (non appliquée)") if decision.status == "matched" else ""))
        if args.explain:
            for line in format_decision(decision)[1:]:
                print("    " + line.strip())
    return 0


def register(riposte_sub: argparse._SubParsersAction) -> None:
    scenarios = riposte_sub.add_parser("scenarios").add_subparsers(dest="riposte_scenarios_command", required=True)
    scenarios.add_parser("list").set_defaults(func=cmd_riposte_scenarios_list)
    show_scenario = scenarios.add_parser("show")
    show_scenario.add_argument("id")
    show_scenario.set_defaults(func=cmd_riposte_scenarios_show)

    policies = riposte_sub.add_parser("policies").add_subparsers(dest="riposte_policies_command", required=True)
    policies.add_parser("list").set_defaults(func=cmd_riposte_policies_list)
    show_policy = policies.add_parser("show")
    show_policy.add_argument("id")
    show_policy.set_defaults(func=cmd_riposte_policies_show)

    simulate = riposte_sub.add_parser("simulate")
    simulate.add_argument("--ip", required=True)
    simulate.add_argument("--class", dest="attack_class", default="scan")
    simulate.add_argument("--level", default=None, choices=("normal", "suspicious", "hostile", "contained"))
    simulate.add_argument("--returns", type=int, default=1)
    simulate.add_argument("--decoy-hits", type=int, default=0)
    simulate.set_defaults(func=cmd_riposte_simulate)

    measure_parser = riposte_sub.add_parser("measure")
    measure_parser.add_argument("id")
    measure_parser.add_argument("--days", type=int, default=7)
    measure_parser.set_defaults(func=cmd_riposte_measure)

    sources = riposte_sub.add_parser("sources").add_subparsers(dest="riposte_sources_command", required=True)
    sources_list = sources.add_parser("list")
    sources_list.add_argument("--limit", type=int, default=50)
    sources_list.set_defaults(func=cmd_riposte_sources_list)
    sources_show = sources.add_parser("show")
    sources_show.add_argument("ip")
    sources_show.set_defaults(func=cmd_riposte_sources_show)

    decisions = riposte_sub.add_parser("decisions").add_subparsers(dest="riposte_decisions_command", required=True)
    decisions_list = decisions.add_parser("list")
    decisions_list.add_argument("--limit", type=int, default=50)
    decisions_list.add_argument("--ip", default=None)
    decisions_list.add_argument("--explain", action="store_true")
    decisions_list.set_defaults(func=cmd_riposte_decisions_list)

    register_actions(riposte_sub, policies, sources)

