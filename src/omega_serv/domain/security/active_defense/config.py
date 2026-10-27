"""Structure options["active_defense"].settings en une forme typee -
meme patron exact que domain/security/waf/config.py (fonctions
parse_*/validate_* module-level, pas de from_dict/validate sur la
classe top-level, dataclasses imbriquees avec from_dict pour les
sous-sections). Forme fixee par plan_active_defense_omega_serv.md,
section "Configuration et activation"."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Literal

from omega_serv.core.i18n import _
from omega_serv.domain.routing.proxy_zone import ProxyZone, UpstreamTarget
from omega_serv.domain.security.active_defense.value_objects import (
    KNOWN_ACTION_TYPES,
    KNOWN_ATTACK_CLASSES,
    KNOWN_FIXTURE_PROFILE_NAMES,
)


@dataclass(frozen=True)
class ActiveDefenseStorageConfig:
    database: str = "var/lib/active-defense.sqlite3"
    export_dir: str = "var/lib/active-defense/exports"

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> ActiveDefenseStorageConfig:
        defaults = cls()
        return cls(
            database=data.get("database", defaults.database),
            export_dir=data.get("export_dir", defaults.export_dir),
        )


@dataclass(frozen=True)
class ActiveDefenseLoggingConfig:
    enhanced_capture: bool = False
    capture_request_body: bool = False
    max_body_bytes: int = 4096
    redact_fields: tuple[str, ...] = ("password", "token", "authorization", "cookie")
    log_path: str = "var/log/active-defense-enriched.jsonl"
    """Chemin du journal enrichi (action "enrich_log", Phase 4) - absent
    de l'exemple JSON d'origine du plan, ajoute pendant l'implementation
    (meme raison que `contained_score` en Phase 1) : le plan decrit le
    CONTENU de la journalisation enrichie sans jamais lui donner de
    chemin de fichier dedie, alors que "separer les logs de deception
    des logs de production" est explicitement une regle du plan.
    Relatif a project_root, meme convention que storage.database."""

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> ActiveDefenseLoggingConfig:
        defaults = cls()
        return cls(
            enhanced_capture=bool(data.get("enhanced_capture", defaults.enhanced_capture)),
            capture_request_body=bool(data.get("capture_request_body", defaults.capture_request_body)),
            max_body_bytes=int(data.get("max_body_bytes", defaults.max_body_bytes)),
            redact_fields=tuple(data.get("redact_fields", defaults.redact_fields)),
            log_path=data.get("log_path", defaults.log_path),
        )


@dataclass(frozen=True)
class DeceptionProfileConfig:
    enabled: bool = True
    match_attack_classes: tuple[str, ...] = ()
    isolation_level: Literal["fixture", "proxy"] = "fixture"
    reverse_proxy_zone_name: str | None = None

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> DeceptionProfileConfig:
        defaults = cls()
        return cls(
            enabled=bool(data.get("enabled", defaults.enabled)),
            match_attack_classes=tuple(data.get("match_attack_classes", defaults.match_attack_classes)),
            isolation_level=data.get("isolation_level", defaults.isolation_level),
            reverse_proxy_zone_name=data.get("reverse_proxy_zone_name", defaults.reverse_proxy_zone_name),
        )


def _decoy_zone_from_dict(name: str, data: dict[str, Any]) -> ProxyZone:
    """`ProxyZone` reutilise tel quel (plan §"Routage vers les leurres" :
    "jamais un nouveau protocole de routage inter-instance a inventer") -
    mais `url_prefix` sert ici de simple IDENTIFIANT de zone (le nom
    choisi par l'utilisateur), jamais un vrai prefixe de chemin
    ecoutant sur des requetes de production : une zone leurre n'est
    JAMAIS selectionnee par `resolve_proxy_zone()` (correspondance de
    chemin), seulement par nom, via `DeceptionProfileConfig.
    reverse_proxy_zone_name` (voir "Niveau 2" du plan)."""
    return ProxyZone(
        url_prefix=name,
        upstreams=tuple(
            UpstreamTarget(
                host=u.get("host", ""), port=int(u.get("port", 0)), use_tls=bool(u.get("use_tls", False)),
            )
            for u in data.get("upstreams", [])
        ),
        connect_timeout_seconds=float(data.get("connect_timeout_seconds", 5.0)),
        read_timeout_seconds=float(data.get("read_timeout_seconds", 30.0)),
        verify_upstream_tls=bool(data.get("verify_upstream_tls", True)),
    )


@dataclass(frozen=True)
class DeceptionConfig:
    enabled: bool = False
    fallback: Literal["pass_through", "reject"] = "pass_through"
    assignments_ttl_seconds: int = 7200
    profiles: dict[str, DeceptionProfileConfig] = field(default_factory=dict)
    decoy_zones: dict[str, ProxyZone] = field(default_factory=dict)
    """Niveau 2 (plan Phase 5, "Routage vers les leurres") - cibles
    upstream reellement isolees, adressees par NOM (jamais par
    correspondance de chemin comme `options.reverse_proxy.zones`) et
    JAMAIS lues depuis `options.reverse_proxy` : une zone de production
    ne peut donc jamais etre accidentellement reutilisee comme cible de
    deception par simple partage de nom, les deux listes vivent dans
    des espaces de configuration entierement separes (verification
    complementaire par collision d'upstream reel, voir domain/config/
    validation.py)."""

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> DeceptionConfig:
        defaults = cls()
        raw_profiles = data.get("profiles", {})
        raw_decoy_zones = data.get("decoy_zones", {})
        return cls(
            enabled=bool(data.get("enabled", defaults.enabled)),
            fallback=data.get("fallback", defaults.fallback),
            assignments_ttl_seconds=int(data.get("assignments_ttl_seconds", defaults.assignments_ttl_seconds)),
            profiles={name: DeceptionProfileConfig.from_dict(value) for name, value in raw_profiles.items()},
            decoy_zones={name: _decoy_zone_from_dict(name, value) for name, value in raw_decoy_zones.items()},
        )


@dataclass(frozen=True)
class SlowdownConfig:
    enabled: bool = True
    minimum_ms: int = 250
    maximum_ms: int = 1500
    jitter_ms: int = 200

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> SlowdownConfig:
        defaults = cls()
        return cls(
            enabled=bool(data.get("enabled", defaults.enabled)),
            minimum_ms=int(data.get("minimum_ms", defaults.minimum_ms)),
            maximum_ms=int(data.get("maximum_ms", defaults.maximum_ms)),
            jitter_ms=int(data.get("jitter_ms", defaults.jitter_ms)),
        )


@dataclass(frozen=True)
class WarModeThresholds:
    suspicious_score: int = 30
    hostile_score: int = 60
    incident_score: int = 70
    contained_score: int = 80
    """Absent de l'exemple YAML d'origine du plan mais present dans son
    "exemple de logique metier" ("seuil 80 : contained, si une action
    de ban est deja connue") - ajoute ici pour que ThreatLevel.contained
    (domain/security/active_defense/policies.py::qualify_threat_level)
    soit reellement configurable comme les 3 autres seuils, jamais code
    en dur."""

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> WarModeThresholds:
        defaults = cls()
        return cls(
            suspicious_score=int(data.get("suspicious_score", defaults.suspicious_score)),
            hostile_score=int(data.get("hostile_score", defaults.hostile_score)),
            incident_score=int(data.get("incident_score", defaults.incident_score)),
            contained_score=int(data.get("contained_score", defaults.contained_score)),
        )


@dataclass(frozen=True)
class WarModeRateLimitConfig:
    """Absent de l'exemple JSON d'origine du plan (Phase 4, action
    "rate_limit" listee dans ActionType sans jamais recevoir son propre
    bloc de reglages, contrairement a "delay"/`slowdown` qui en a un
    complet) - ajoute pendant l'implementation, meme raison que
    `contained_score` en Phase 1. Reutilise le RateLimitPort deja livre
    par le WAF (`ports/rate_limit_port.py`), sous une cle distincte par
    source (`active-defense:{subject_id}`), jamais un second mecanisme
    de limitation parallele."""
    requests: int = 5
    window_seconds: int = 60

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> WarModeRateLimitConfig:
        defaults = cls()
        return cls(
            requests=int(data.get("requests", defaults.requests)),
            window_seconds=int(data.get("window_seconds", defaults.window_seconds)),
        )


@dataclass(frozen=True)
class WarModeConfig:
    enabled: bool = False
    scope: Literal["source", "instance"] = "source"
    actions: tuple[str, ...] = ("redirect_to_decoy", "enrich_log", "delay", "create_incident")
    """Correction faite en implementant la Phase 4 : le defaut d'origine
    (copie de l'exemple JSON du plan, §"Configuration et activation")
    utilisait "assign_deception", qui n'a jamais ete une valeur de
    `ActionType` (value_objects.py, Phase 0 - la valeur reelle est
    "redirect_to_decoy") - incoherence dormante jamais detectee avant
    que `war_mode.actions` ne soit reellement valide (voir
    KNOWN_ACTION_TYPES ci-dessus, ajoute en meme temps)."""
    thresholds: WarModeThresholds = field(default_factory=WarModeThresholds)
    slowdown: SlowdownConfig = field(default_factory=SlowdownConfig)
    rate_limit: WarModeRateLimitConfig = field(default_factory=WarModeRateLimitConfig)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> WarModeConfig:
        defaults = cls()
        return cls(
            enabled=bool(data.get("enabled", defaults.enabled)),
            scope=data.get("scope", defaults.scope),
            actions=tuple(data.get("actions", defaults.actions)),
            thresholds=WarModeThresholds.from_dict(data.get("thresholds", {})),
            slowdown=SlowdownConfig.from_dict(data.get("slowdown", {})),
            rate_limit=WarModeRateLimitConfig.from_dict(data.get("rate_limit", {})),
        )


IOC_EXPORT_FORMATS = ("json", "csv", "markdown", "stix", "misp")
"""Formats d'export d'un incident. stix = bundle STIX 2.1, misp = evenement MISP (JSON a importer
par l'interface de MISP) : fichiers locaux, jamais envoyes (plan Active Defense, « l'export est
local, explicite et revisable »)."""
IOC_TLP_LEVELS = ("white", "green", "amber", "red")


@dataclass(frozen=True)
class IoCConfig:
    enabled: bool = False
    auto_export_on_close: bool = True
    formats: tuple[str, ...] = ("json", "csv", "markdown")
    share_policy: Literal["local_only", "manual_export"] = "local_only"
    minimum_confidence: int = 70
    tlp: str = "amber"
    """Marquage de diffusion des exports STIX 2.1 / MISP (TLP 1.0 : white, green, amber, red).
    AMBER par defaut, jamais WHITE (OMEGA-SERV_ETUDE_ACTIVE_DEFENSE_STIX_MISP_CHARGE.md, Q2)."""

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> IoCConfig:
        defaults = cls()
        return cls(
            enabled=bool(data.get("enabled", defaults.enabled)),
            auto_export_on_close=bool(data.get("auto_export_on_close", defaults.auto_export_on_close)),
            formats=tuple(data.get("formats", defaults.formats)),
            share_policy=data.get("share_policy", defaults.share_policy),
            minimum_confidence=int(data.get("minimum_confidence", defaults.minimum_confidence)),
            tlp=str(data.get("tlp", defaults.tlp)).lower(),
        )


@dataclass(frozen=True)
class ActiveDefenseConfig:
    """Forme complete de options["active_defense"].settings - voir
    plan_active_defense_omega_serv.md, section "Configuration et
    activation" pour l'exemple JSON source."""
    mode: Literal["monitor", "enforce"] = "monitor"
    state_ttl_seconds: int = 7200
    storage: ActiveDefenseStorageConfig = field(default_factory=ActiveDefenseStorageConfig)
    logging: ActiveDefenseLoggingConfig = field(default_factory=ActiveDefenseLoggingConfig)
    deception: DeceptionConfig = field(default_factory=DeceptionConfig)
    war_mode: WarModeConfig = field(default_factory=WarModeConfig)
    ioc: IoCConfig = field(default_factory=IoCConfig)


def parse_active_defense_config(settings: dict[str, Any]) -> ActiveDefenseConfig:
    """`settings` est deja options["active_defense"] SANS la cle
    "enabled" (retiree par Option.from_dict, voir domain/config/option.py)."""
    defaults = ActiveDefenseConfig()
    return ActiveDefenseConfig(
        mode=settings.get("mode", defaults.mode),
        state_ttl_seconds=int(settings.get("state_ttl_seconds", defaults.state_ttl_seconds)),
        storage=ActiveDefenseStorageConfig.from_dict(settings.get("storage", {})),
        logging=ActiveDefenseLoggingConfig.from_dict(settings.get("logging", {})),
        deception=DeceptionConfig.from_dict(settings.get("deception", {})),
        war_mode=WarModeConfig.from_dict(settings.get("war_mode", {})),
        ioc=IoCConfig.from_dict(settings.get("ioc", {})),
    )


def validate_active_defense_config(config: ActiveDefenseConfig) -> list[str]:
    """Validation structurelle pure (pas d'I/O - meme convention que
    validate_waf_config)."""
    errors: list[str] = []
    if config.mode not in ("monitor", "enforce"):
        errors.append(_("options.active_defense.mode invalide : {mode!r}").format(mode=config.mode))
    if config.state_ttl_seconds <= 0:
        errors.append(_("options.active_defense.state_ttl_seconds doit être strictement positif"))
    if config.deception.fallback not in ("pass_through", "reject"):
        errors.append(_("options.active_defense.deception.fallback invalide : {fallback!r}").format(fallback=config.deception.fallback))
    if config.deception.assignments_ttl_seconds <= 0:
        errors.append(_("options.active_defense.deception.assignments_ttl_seconds doit être strictement positif"))
    for name, profile in config.deception.profiles.items():
        if profile.isolation_level == "proxy":
            if not profile.reverse_proxy_zone_name:
                errors.append(
                    _("options.active_defense.deception.profiles.{name}.reverse_proxy_zone_name requis quand isolation_level == 'proxy'").format(name=name)
                )
            elif profile.reverse_proxy_zone_name not in config.deception.decoy_zones:
                errors.append(
                    _("options.active_defense.deception.profiles.{name}.reverse_proxy_zone_name {reverse_proxy_zone_name!r} n'existe pas dans options.active_defense.deception.decoy_zones (Niveau 2, Phase 5)").format(name=name, reverse_proxy_zone_name=profile.reverse_proxy_zone_name)
                )
        elif name not in KNOWN_FIXTURE_PROFILE_NAMES:
            errors.append(
                _("options.active_defense.deception.profiles.{name} : nom de profil inconnu pour isolation_level == 'fixture' (attendu : {value}) - ce leurre ne se déclenchera jamais tant que le nom ne correspond pas exactement").format(name=name, value=', '.join(sorted(KNOWN_FIXTURE_PROFILE_NAMES)))
            )
        for attack_class in profile.match_attack_classes:
            if attack_class not in KNOWN_ATTACK_CLASSES:
                errors.append(
                    _("options.active_defense.deception.profiles.{name}.match_attack_classes contient une valeur inconnue : {attack_class!r}").format(name=name, attack_class=attack_class)
                )
    if config.war_mode.scope not in ("source", "instance"):
        errors.append(_("options.active_defense.war_mode.scope invalide : {scope!r}").format(scope=config.war_mode.scope))
    for action in config.war_mode.actions:
        if action not in KNOWN_ACTION_TYPES:
            errors.append(_("options.active_defense.war_mode.actions contient une valeur inconnue : {action!r}").format(action=action))
    if config.war_mode.rate_limit.requests <= 0:
        errors.append(_("options.active_defense.war_mode.rate_limit.requests doit être strictement positif"))
    if config.war_mode.rate_limit.window_seconds <= 0:
        errors.append(_("options.active_defense.war_mode.rate_limit.window_seconds doit être strictement positif"))
    thresholds = config.war_mode.thresholds
    if not (0 <= thresholds.suspicious_score <= thresholds.hostile_score <= thresholds.incident_score):
        errors.append(
            _("options.active_defense.war_mode.thresholds doit vérifier "
            "0 <= suspicious_score <= hostile_score <= incident_score")
        )
    if thresholds.contained_score < thresholds.hostile_score:
        errors.append(
            _("options.active_defense.war_mode.thresholds.contained_score doit être >= hostile_score")
        )
    if config.war_mode.slowdown.minimum_ms > config.war_mode.slowdown.maximum_ms:
        errors.append(_("options.active_defense.war_mode.slowdown.minimum_ms doit être <= maximum_ms"))
    if config.ioc.share_policy not in ("local_only", "manual_export"):
        errors.append(_("options.active_defense.ioc.share_policy invalide : {share_policy!r}").format(share_policy=config.ioc.share_policy))
    if not (0 <= config.ioc.minimum_confidence <= 100):
        errors.append(_("options.active_defense.ioc.minimum_confidence doit être entre 0 et 100"))
    unknown_formats = [f for f in config.ioc.formats if f not in IOC_EXPORT_FORMATS]
    if unknown_formats:
        errors.append(_("options.active_defense.ioc.formats : format(s) inconnu(s) {formats} (attendus : {allowed})").format(
            formats=", ".join(unknown_formats), allowed=", ".join(IOC_EXPORT_FORMATS),
        ))
    if config.ioc.tlp not in IOC_TLP_LEVELS:
        errors.append(_("options.active_defense.ioc.tlp invalide : {tlp!r} (attendus : {allowed})").format(
            tlp=config.ioc.tlp, allowed=", ".join(IOC_TLP_LEVELS),
        ))
    for zone_name, decoy_zone in config.deception.decoy_zones.items():
        reason = validate_decoy_zone(decoy_zone)
        if reason is not None:
            errors.append(_("options.active_defense.deception.decoy_zones.{zone_name} : {reason}").format(zone_name=zone_name, reason=reason))
    return errors


def validate_decoy_zone(zone: ProxyZone) -> str | None:
    """Memes invariants que `domain.routing.proxy_zone.validate_proxy_zone`
    (au moins un upstream valide, delais positifs) SAUF la contrainte
    `url_prefix.startswith("/")` : ici `url_prefix` porte simplement le
    NOM de la zone leurre (voir `_decoy_zone_from_dict`), jamais un
    prefixe de chemin HTTP reel - reutiliser `validate_proxy_zone` tel
    quel rejetterait a tort un nom de zone qui ne commence pas par '/'."""
    if not zone.upstreams:
        return _("au moins un upstream est requis (zone leurre {url_prefix!r})").format(url_prefix=zone.url_prefix)
    for upstream in zone.upstreams:
        if not upstream.host:
            return _("host d'upstream vide (zone leurre {url_prefix!r})").format(url_prefix=zone.url_prefix)
        if not (1 <= upstream.port <= 65535):
            return _("port d'upstream invalide : {port!r} (zone leurre {url_prefix!r})").format(port=upstream.port, url_prefix=zone.url_prefix)
    if zone.connect_timeout_seconds <= 0:
        return _("connect_timeout_seconds doit être strictement positif (zone leurre {url_prefix!r})").format(url_prefix=zone.url_prefix)
    if zone.read_timeout_seconds <= 0:
        return _("read_timeout_seconds doit être strictement positif (zone leurre {url_prefix!r})").format(url_prefix=zone.url_prefix)
    return None
