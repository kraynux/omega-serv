"""Ce que la TUI et la CLI font avec RIPOSTE (OMEGA-SERV_PLAN-DETAILLE_RIPOSTE.md §3.7, lot 5) - un seul
endroit pour les deux interfaces, jamais deux logiques divergentes :
- deposer des commandes (le processus RIPOSTE, seul ecrivain du registre, les execute en <= 1 s) et
  relever leurs resultats ;
- poser / lever l'arret d'urgence (drapeau d'etat, persistant, respecte meme processus arrete) ;
- modifier les politiques et les reglages dans la configuration principale (validation avant toute
  ecriture), puis demander au processus de relire (`reload`) ;
- simuler une situation saisie.
Les resultats sont des CODES (traduits par l'interface, interfaces/cli/riposte_text.py)."""
from __future__ import annotations

import copy
from dataclasses import dataclass, replace
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

from omega_serv.application.riposte.engine import STATE_EMERGENCY_STOP
from omega_serv.application.riposte.get_status import get_riposte_status
from omega_serv.application.riposte.measure import MeasureResult, measure
from omega_serv.application.riposte.safety import riposte_exempt_networks
from omega_serv.domain.config.entities import OmegaServConfig
from omega_serv.domain.config.option import Option
from omega_serv.domain.security.active_defense.config import (
    ActiveDefenseLoggingConfig,
    parse_active_defense_config,
)
from omega_serv.domain.security.riposte.actions import RiposteCommand
from omega_serv.domain.security.riposte.config import (
    TIER_CEILING_SECONDS,
    RiposteConfig,
    RipostePolicy,
    parse_riposte_config,
    validate_riposte_config,
)
from omega_serv.domain.security.riposte.decide import Decision, SafetyContext, decide
from omega_serv.domain.security.riposte.events import ObservedEvent
from omega_serv.domain.security.riposte.history import Episode, SourceHistory
from omega_serv.domain.security.waf.config import parse_waf_config
from omega_serv.ports.configuration_port import ConfigurationPort
from omega_serv.ports.riposte_store_port import RiposteStorePort

Commands = list[tuple[str, dict[str, Any]]]


# --- Lecture de la configuration ------------------------------------------------------------------


def riposte_config_of(config: OmegaServConfig) -> RiposteConfig:
    option = config.options.get("riposte")
    return parse_riposte_config(option.settings if option is not None else {})


def riposte_enabled(config: OmegaServConfig) -> bool:
    option = config.options.get("riposte")
    return option is not None and option.enabled


def decoy_profiles(config: OmegaServConfig) -> frozenset[str]:
    """Profils de leurre reellement disponibles (Active Defense actif) - validation des politiques."""
    option = config.options.get("active_defense")
    if option is None or not option.enabled:
        return frozenset()
    return frozenset(parse_active_defense_config(option.settings).deception.profiles)


def deception_available(config: OmegaServConfig) -> bool:
    option = config.options.get("active_defense")
    return option is not None and option.enabled and parse_active_defense_config(option.settings).deception.enabled


def journal_paths(config: OmegaServConfig, project_root: Path) -> tuple[Path, Path]:
    """(waf-alerts.log, security-events.jsonl) tels que les ECRIT le serveur - memes reglages."""
    waf_option = config.options.get("waf")
    waf_log = parse_waf_config(waf_option.settings if waf_option is not None else {}).logging.path
    ad_option = config.options.get("active_defense")
    security_log = (
        parse_active_defense_config(ad_option.settings).logging.security_events_path
        if ad_option is not None else ActiveDefenseLoggingConfig().security_events_path
    )
    return project_root / waf_log, project_root / security_log


def waf_enabled(config: OmegaServConfig) -> bool:
    option = config.options.get("waf")
    return option is not None and option.enabled


def database_path(config: OmegaServConfig, project_root: Path) -> Path:
    return project_root / riposte_config_of(config).database


# --- Commandes ------------------------------------------------------------------------------------


def submit_commands(store: RiposteStorePort, commands: Commands, now: datetime) -> list[int]:
    """Depose les commandes dans l'ordre. Peut lever OSError (base en lecture seule pour ce compte)."""
    return [store.add_command(kind, params, now) for kind, params in commands]


def process_running(store: RiposteStorePort, now: datetime) -> bool:
    return get_riposte_status(store, now).running


def finished_commands(store: RiposteStorePort, ids: list[int]) -> list[RiposteCommand]:
    """Les commandes deja executees (etat different de `pending`), dans l'ordre de depot."""
    done = []
    for command_id in ids:
        command = store.get_command(command_id)
        if command is not None and command.state != "pending":
            done.append(command)
    return done


def emergency_stop(store: RiposteStorePort, now: datetime, *, revoke: bool) -> list[int]:
    """Pose le drapeau (persistant, effet immediat meme processus arrete) ; `revoke` depose en plus la levee
    de toutes les actions en cours. Retourne les commandes deposees."""
    store.set_state(STATE_EMERGENCY_STOP, "1")
    store.append_audit(now, "emergency_stop", "revoke" if revoke else "let_finish")
    return submit_commands(store, [("revoke_all", {})], now) if revoke else []


def resume(store: RiposteStorePort, now: datetime) -> None:
    store.set_state(STATE_EMERGENCY_STOP, "0")
    store.append_audit(now, "resume", "")


def emergency_stop_active(store: RiposteStorePort) -> bool:
    return store.get_state(STATE_EMERGENCY_STOP) == "1"


# --- Politiques et reglages (configuration principale) -------------------------------------------


@dataclass(frozen=True)
class SaveResult:
    errors: tuple[str, ...] = ()
    unknown: bool = False
    """La politique visee n'existe pas (ou plus) dans la configuration."""

    @property
    def ok(self) -> bool:
        return not self.errors and not self.unknown


def required_risks(policy: RipostePolicy) -> tuple[str, ...]:
    """Risques a confirmer explicitement (topo §6.5 : confirmation nommee « moins prudent que la norme »)."""
    risks = []
    durations = list(policy.tiers_seconds or ())
    if policy.action == "decoy":
        durations.append(policy.decoy_duration_seconds)
    if any(d > TIER_CEILING_SECONDS for d in durations):
        risks.append("long_duration")
    if policy.min_ad_level == "suspicious":
        risks.append("suspicious_level")
    return tuple(risks)


def _settings(config: OmegaServConfig) -> dict[str, Any]:
    option = config.options.get("riposte")
    return copy.deepcopy(dict(option.settings)) if option is not None else {}


def _save_settings(repository: ConfigurationPort, path: Path, config: OmegaServConfig,
                   settings: dict[str, Any], *, check: bool) -> SaveResult:
    if check:
        problems = validate_riposte_config(parse_riposte_config(settings), decoy_profile_names=decoy_profiles(config))
        if problems:
            return SaveResult(errors=tuple(problems))
    option = config.options.get("riposte") or Option(name="riposte", enabled=False, settings={})
    new_config = replace(config, options={**config.options, "riposte": replace(option, settings=settings)})
    repository.save(path, new_config)
    return SaveResult()


def _with_policy(config: OmegaServConfig, policy: RipostePolicy, replaces: str | None) -> dict[str, Any] | None:
    settings = _settings(config)
    policies = [p for p in settings.get("policies", []) if isinstance(p, dict)]
    data = policy.to_dict()
    if replaces is None:
        policies.append(data)
    else:
        index = next((i for i, p in enumerate(policies) if p.get("id") == replaces), None)
        if index is None:
            return None
        policies[index] = data
    settings["policies"] = policies
    return settings


def policy_problems(config: OmegaServConfig, policy: RipostePolicy, *, replaces: str | None = None) -> SaveResult:
    """Ce que `save_policy` refuserait, sans rien ecrire (avant la confirmation finale du formulaire)."""
    settings = _with_policy(config, policy, replaces)
    if settings is None:
        return SaveResult(unknown=True)
    problems = validate_riposte_config(parse_riposte_config(settings), decoy_profile_names=decoy_profiles(config))
    return SaveResult(errors=tuple(problems))


def save_policy(repository: ConfigurationPort, path: Path, config: OmegaServConfig, policy: RipostePolicy,
                *, replaces: str | None = None) -> SaveResult:
    """Ajoute la politique, ou remplace celle d'identifiant `replaces` (meme place dans la liste)."""
    settings = _with_policy(config, policy, replaces)
    if settings is None:
        return SaveResult(unknown=True)
    return _save_settings(repository, path, config, settings, check=True)


def set_policy_enabled(repository: ConfigurationPort, path: Path, config: OmegaServConfig, policy_id: str,
                       enabled: bool) -> SaveResult:
    """Desactiver ne valide pas (on doit toujours pouvoir couper une regle, meme si un profil de leurre a
    disparu entre-temps) ; activer valide."""
    settings = _settings(config)
    target = next((p for p in settings.get("policies", []) if isinstance(p, dict) and p.get("id") == policy_id), None)
    if target is None:
        return SaveResult(unknown=True)
    target["enabled"] = enabled
    return _save_settings(repository, path, config, settings, check=enabled)


def remove_policy(repository: ConfigurationPort, path: Path, config: OmegaServConfig, policy_id: str) -> SaveResult:
    """Ses actions passees restent dans l'historique, sous son identifiant (topo §6.7)."""
    settings = _settings(config)
    policies = [p for p in settings.get("policies", []) if isinstance(p, dict)]
    remaining = [p for p in policies if p.get("id") != policy_id]
    if len(remaining) == len(policies):
        return SaveResult(unknown=True)
    settings["policies"] = remaining
    return _save_settings(repository, path, config, settings, check=False)


@dataclass(frozen=True)
class GlobalSettings:
    tiers_seconds: tuple[int, ...]
    recidive_window_seconds: int
    episode_gap_seconds: int
    history_retention_seconds: int
    max_active_bans: int
    exemptions: tuple[str, ...]


def save_global_settings(repository: ConfigurationPort, path: Path, config: OmegaServConfig,
                         values: GlobalSettings) -> SaveResult:
    settings = _settings(config)
    settings.update({
        "tiers_seconds": list(values.tiers_seconds),
        "recidive_window_seconds": values.recidive_window_seconds,
        "episode_gap_seconds": values.episode_gap_seconds,
        "history_retention_seconds": values.history_retention_seconds,
        "max_active_bans": values.max_active_bans,
        "exemptions": list(values.exemptions),
    })
    return _save_settings(repository, path, config, settings, check=True)


def unique_policy_id(base: str, existing: set[str]) -> str:
    """`base`, sinon `base-2`, `base-3`... (copie d'une politique, scenario charge deux fois)."""
    if base not in existing:
        return base
    index = 2
    while f"{base}-{index}"[:64] in existing:
        index += 1
    return f"{base}-{index}"[:64]


# --- Simulation d'une situation saisie -------------------------------------------------------------


def simulate_situation(
    config: OmegaServConfig, *, ip: str, attack_class: str, level: str | None, returns: int, decoy_hits: int,
    now: datetime,
) -> Decision:
    """Decision expliquee avec la configuration reelle - rien n'est applique ni ecrit. `returns` episodes
    separes par un silence plus long que `episode_gap_seconds`, le dernier en cours."""
    riposte = riposte_config_of(config)
    count = max(1, returns)
    spacing = timedelta(seconds=riposte.episode_gap_seconds + 60)
    episodes = []
    for i in range(count):
        started = now - spacing * (count - 1 - i)
        current = i == count - 1
        episodes.append(Episode(
            started_at=started, last_seen_at=started, attacks=1, attack_classes=(attack_class,),
            max_level=level if current else None, decoy_hits=decoy_hits if current else 0,
        ))
    history = SourceHistory(ip, episodes=tuple(episodes))
    event = ObservedEvent(source="waf", event_id="simulation", kind="attack", timestamp=now, remote_ip=ip,
                          attack_class=attack_class, score=10)
    return decide(history, event, riposte, SafetyContext(riposte_exempt_networks(config, riposte)), now)


def single_policy_config(riposte: RiposteConfig, policy: RipostePolicy) -> RiposteConfig:
    """Configuration de mesure : les reglages globaux reels, cette seule politique, activee."""
    return replace(riposte, policies=(replace(policy, enabled=True),))


def measure_policy(config: OmegaServConfig, policy: RipostePolicy, events: list[ObservedEvent],
                   now: datetime, *, days: int | None = 7) -> MeasureResult:
    """« Mesurer » (topo §6.5) : la politique seule, avec les reglages globaux et exclusions reels."""
    riposte = riposte_config_of(config)
    since = now - timedelta(days=days) if days else None
    return measure(events, single_policy_config(riposte, policy), riposte_exempt_networks(config, riposte), since=since)
