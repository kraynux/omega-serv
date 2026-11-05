"""Configuration RIPOSTE (OMEGA-SERV_PLAN-DETAILLE_RIPOSTE.md §3.4, lot 2) - forme de
`options["riposte"].settings` dans la configuration principale (decision utilisateur Q1 :
sauvegardes, profils, `config check`, rechargement SIGHUP, comme options.active_defense).

Toutes les durees sont des SECONDES entieres (meme convention que state_ttl_seconds,
auto_block_duration_seconds) ; l'interface les affiche en heures/jours.

Defauts (topo §7.1, valides le 2026-11-01) : paliers 1 h / 6 h / 24 h / 7 j, fenetre de
recidive 30 j, silence entre deux episodes 1 h, historique 90 j, 100 bans RIPOSTE simultanes
au plus, portee IP seule. Module desactive par defaut : rien ne se passe sans politique.
Pur : aucune I/O."""
from __future__ import annotations

import ipaddress
import re
from dataclasses import dataclass, field
from typing import Any, Literal

from omega_serv.core.i18n import _
from omega_serv.domain.security.active_defense.value_objects import (
    KNOWN_ATTACK_CLASSES,
    ThreatLevel,
)

HOUR = 3600
DAY = 24 * HOUR

DEFAULT_TIERS_SECONDS: tuple[int, ...] = (HOUR, 6 * HOUR, DAY, 7 * DAY)
TIER_CEILING_SECONDS = 7 * DAY
"""Au-dela, une politique doit porter le risque confirme `long_duration` (confirmation « moins
prudent que la norme » de l'interface, topo §6.5) - sinon la configuration est refusee."""

MAX_ACTIVE_BANS_LIMIT = 10_000
"""Borne absolue de `max_active_bans` (plan §3.8 : bornes absolues, jamais seulement configurables)."""

RiposteAction = Literal["local_ban", "decoy", "local_and_network_ban"]
KNOWN_RIPOSTE_ACTIONS: frozenset[str] = frozenset({"local_ban", "decoy", "local_and_network_ban"})

RiposteScope = Literal["ip"]
KNOWN_SCOPES: frozenset[str] = frozenset({"ip"})
"""V1 : IP seule (plan §1.2) - la portee reseau viendra avec sa propre confirmation."""

KNOWN_CONFIRMED_RISKS: frozenset[str] = frozenset({"long_duration", "suspicious_level"})
"""Risques qu'une politique peut porter apres confirmation explicite (topo §6.5) :
`long_duration` = palier au-dela de 7 j ; `suspicious_level` = reagir des le niveau
« suspicious » d'Active Defense (plus tot, plus de faux positifs)."""

KNOWN_AD_LEVELS: frozenset[str] = frozenset({"normal", "suspicious", "hostile", "contained"})
POLICY_ID_PATTERN = re.compile(r"^[a-z0-9][a-z0-9-]{0,63}$")
_POLICIES_KEY = "options.riposte.policies"


@dataclass(frozen=True)
class RipostePolicy:
    """Une politique (plan §3.4). `origin` garde seulement la trace du point de depart dans le
    formulaire (« scenario:<id> », « copy:<id> », « custom ») - jamais relu pour decider."""
    id: str
    name: str
    enabled: bool = True
    origin: str = "custom"
    min_ad_level: ThreatLevel | None = None
    attack_classes: tuple[str, ...] = ()
    returns: int = 1
    within_seconds: int = 30 * DAY
    decoy_hits: int = 0
    """Visites de leurre minimales dans l'episode en cours (0 = condition ignoree)."""
    action: RiposteAction = "local_ban"
    tiers_seconds: tuple[int, ...] | None = None
    """None = paliers globaux (`RiposteConfig.tiers_seconds`)."""
    decoy_profile: str | None = None
    decoy_duration_seconds: int = DAY
    scope: RiposteScope = "ip"
    max_active_per_source: int = 1
    confirmed_risks: tuple[str, ...] = ()

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> RipostePolicy:
        defaults = cls(id="", name="")
        when = data.get("when", {})
        then = data.get("then", {})
        limits = data.get("limits", {})
        tiers = then.get("tiers_seconds")
        return cls(
            id=str(data.get("id", "")),
            name=str(data.get("name", "")),
            enabled=bool(data.get("enabled", defaults.enabled)),
            origin=str(data.get("origin", defaults.origin)),
            min_ad_level=when.get("min_ad_level"),
            attack_classes=tuple(when.get("attack_classes", ())),
            returns=int(when.get("returns", defaults.returns)),
            within_seconds=int(when.get("within_seconds", defaults.within_seconds)),
            decoy_hits=int(when.get("decoy_hits", defaults.decoy_hits)),
            action=then.get("action", defaults.action),
            tiers_seconds=None if tiers is None else tuple(int(t) for t in tiers),
            decoy_profile=then.get("decoy_profile"),
            decoy_duration_seconds=int(then.get("decoy_duration_seconds", defaults.decoy_duration_seconds)),
            scope=data.get("scope", defaults.scope),
            max_active_per_source=int(limits.get("max_active_per_source", defaults.max_active_per_source)),
            confirmed_risks=tuple(data.get("confirmed_risks", ())),
        )

    def to_dict(self) -> dict[str, Any]:
        """Forme JSON stable (enregistrement par la TUI / la CLI) - inverse exact de from_dict."""
        then: dict[str, Any] = {"action": self.action}
        if self.tiers_seconds is not None:
            then["tiers_seconds"] = list(self.tiers_seconds)
        if self.decoy_profile is not None:
            then["decoy_profile"] = self.decoy_profile
            then["decoy_duration_seconds"] = self.decoy_duration_seconds
        when: dict[str, Any] = {"returns": self.returns, "within_seconds": self.within_seconds}
        if self.min_ad_level is not None:
            when["min_ad_level"] = self.min_ad_level
        if self.attack_classes:
            when["attack_classes"] = list(self.attack_classes)
        if self.decoy_hits:
            when["decoy_hits"] = self.decoy_hits
        data: dict[str, Any] = {
            "id": self.id, "name": self.name, "enabled": self.enabled, "origin": self.origin,
            "when": when, "then": then, "scope": self.scope,
            "limits": {"max_active_per_source": self.max_active_per_source},
        }
        if self.confirmed_risks:
            data["confirmed_risks"] = list(self.confirmed_risks)
        return data


@dataclass(frozen=True)
class RiposteConfig:
    tiers_seconds: tuple[int, ...] = DEFAULT_TIERS_SECONDS
    recidive_window_seconds: int = 30 * DAY
    episode_gap_seconds: int = HOUR
    history_retention_seconds: int = 90 * DAY
    max_active_bans: int = 100
    exemptions: tuple[str, ...] = ()
    """Ajouts aux exclusions du WAF (never_auto_block), qui s'appliquent TOUJOURS en plus."""
    network_ban_log: bool = True
    """Ecrit riposte-decisions.jsonl pour les jails omega-jail (actions `local_and_network_ban`)."""
    database: str = "var/lib/riposte.sqlite3"
    decisions_log_path: str = "var/log/riposte-decisions.jsonl"
    policies: tuple[RipostePolicy, ...] = field(default_factory=tuple)


def parse_riposte_config(settings: dict[str, Any]) -> RiposteConfig:
    """`settings` = options["riposte"] SANS la cle "enabled" (retiree par Option.from_dict)."""
    defaults = RiposteConfig()
    return RiposteConfig(
        tiers_seconds=tuple(int(t) for t in settings.get("tiers_seconds", defaults.tiers_seconds)),
        recidive_window_seconds=int(settings.get("recidive_window_seconds", defaults.recidive_window_seconds)),
        episode_gap_seconds=int(settings.get("episode_gap_seconds", defaults.episode_gap_seconds)),
        history_retention_seconds=int(settings.get("history_retention_seconds", defaults.history_retention_seconds)),
        max_active_bans=int(settings.get("max_active_bans", defaults.max_active_bans)),
        exemptions=tuple(settings.get("exemptions", defaults.exemptions)),
        network_ban_log=bool(settings.get("network_ban_log", defaults.network_ban_log)),
        database=str(settings.get("database", defaults.database)),
        decisions_log_path=str(settings.get("decisions_log_path", defaults.decisions_log_path)),
        policies=tuple(RipostePolicy.from_dict(p) for p in settings.get("policies", ())),
    )


def _validate_tiers(tiers: tuple[int, ...], label: str, *, long_duration_confirmed: bool) -> list[str]:
    errors: list[str] = []
    if not tiers:
        return [_("{label} : au moins un palier est requis").format(label=label)]
    if any(t <= 0 for t in tiers):
        errors.append(_("{label} : chaque palier doit être strictement positif").format(label=label))
    if list(tiers) != sorted(tiers):
        errors.append(_("{label} : les paliers doivent être croissants").format(label=label))
    if max(tiers) > TIER_CEILING_SECONDS and not long_duration_confirmed:
        errors.append(_("{label} : palier au-delà de 7 jours sans confirmation (long_duration)").format(label=label))
    return errors


def validate_riposte_config(config: RiposteConfig, *, decoy_profile_names: frozenset[str] = frozenset()) -> list[str]:
    """Validation structurelle pure. `decoy_profile_names` = profils de leurre reellement
    configures dans Active Defense (fournis par l'appelant : le domaine RIPOSTE ne lit pas la
    configuration d'un autre module)."""
    errors = _validate_tiers(config.tiers_seconds, "options.riposte.tiers_seconds", long_duration_confirmed=False)
    for name, value in (
        ("recidive_window_seconds", config.recidive_window_seconds),
        ("episode_gap_seconds", config.episode_gap_seconds),
        ("history_retention_seconds", config.history_retention_seconds),
    ):
        if value <= 0:
            errors.append(_("options.riposte.{name} doit être strictement positif").format(name=name))
    if not 1 <= config.max_active_bans <= MAX_ACTIVE_BANS_LIMIT:
        errors.append(_("options.riposte.max_active_bans doit être entre 1 et {limit}").format(limit=MAX_ACTIVE_BANS_LIMIT))
    for network in config.exemptions:
        try:
            ipaddress.ip_network(network, strict=False)
        except ValueError:
            errors.append(_("options.riposte.exemptions : réseau invalide {network!r}").format(network=network))
    seen_ids: set[str] = set()
    for policy in config.policies:
        errors.extend(_validate_policy(policy, decoy_profile_names))
        if policy.id in seen_ids:
            errors.append(_("options.riposte.policies : identifiant en double {id!r}").format(id=policy.id))
        seen_ids.add(policy.id)
    return errors


def _validate_policy(policy: RipostePolicy, decoy_profile_names: frozenset[str]) -> list[str]:
    label = _POLICIES_KEY + "[" + (policy.id or "?") + "]"  # chemin de configuration, jamais traduit
    errors: list[str] = []
    if not POLICY_ID_PATTERN.match(policy.id):
        errors.append(_("{label} : identifiant invalide (minuscules, chiffres et tirets)").format(label=label))
    if not policy.name.strip():
        errors.append(_("{label} : nom requis").format(label=label))
    unknown_risks = set(policy.confirmed_risks) - KNOWN_CONFIRMED_RISKS
    if unknown_risks:
        errors.append(_("{label} : risque confirmé inconnu {risks}").format(label=label, risks=sorted(unknown_risks)))
    if policy.min_ad_level is not None:
        if policy.min_ad_level not in KNOWN_AD_LEVELS:
            errors.append(_("{label} : niveau Active Defense inconnu {level!r}").format(label=label, level=policy.min_ad_level))
        elif policy.min_ad_level == "suspicious" and "suspicious_level" not in policy.confirmed_risks:
            errors.append(_("{label} : niveau « suspicious » sans confirmation (suspicious_level)").format(label=label))
    for attack_class in policy.attack_classes:
        if attack_class not in KNOWN_ATTACK_CLASSES:
            errors.append(_("{label} : classe d'attaque inconnue {value!r}").format(label=label, value=attack_class))
    if policy.returns < 1:
        errors.append(_("{label} : « retours » doit valoir au moins 1").format(label=label))
    if policy.decoy_hits < 0:
        errors.append(_("{label} : le nombre de visites de leurre ne peut pas être négatif").format(label=label))
    if policy.within_seconds <= 0:
        errors.append(_("{label} : la fenêtre doit être strictement positive").format(label=label))
    if policy.action not in KNOWN_RIPOSTE_ACTIONS:
        errors.append(_("{label} : action inconnue {action!r}").format(label=label, action=policy.action))
    if policy.scope not in KNOWN_SCOPES:
        errors.append(_("{label} : portée non prise en charge {scope!r} (IP seule)").format(label=label, scope=policy.scope))
    if policy.max_active_per_source < 1:
        errors.append(_("{label} : max_active_per_source doit valoir au moins 1").format(label=label))
    if policy.tiers_seconds is not None:
        errors.extend(_validate_tiers(
            policy.tiers_seconds, label, long_duration_confirmed="long_duration" in policy.confirmed_risks,
        ))
    if policy.action == "decoy":
        if policy.decoy_profile is None:
            errors.append(_("{label} : profil de leurre requis pour l'action « leurre »").format(label=label))
        elif policy.decoy_profile not in decoy_profile_names:
            errors.append(_("{label} : profil de leurre inconnu {profile!r}").format(label=label, profile=policy.decoy_profile))
        if policy.decoy_duration_seconds <= 0:
            errors.append(_("{label} : la durée du leurre doit être strictement positive").format(label=label))
        elif policy.decoy_duration_seconds > TIER_CEILING_SECONDS and "long_duration" not in policy.confirmed_risks:
            errors.append(_("{label} : durée du leurre au-delà de 7 jours sans confirmation (long_duration)").format(label=label))
    return errors
