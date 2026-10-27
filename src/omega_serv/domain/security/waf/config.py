"""Structure la configuration WAF brute (options["waf"].settings, un
dict ouvert - voir domain/config/option.py) en une forme typee.

Forme fixee par OMEGA-SERV_WAF_LUA_DEPERSONNALISATION.md, section
"Configuration WAF generique". Suit le meme patron que
domain/routing/alias.py::parse_alias_rules - une fonction pure de
parsing, pas de validation d'existence de fichiers ici (ca, c'est
application/config/validate_config.py, qui a acces au filesystem)."""
from __future__ import annotations

import ipaddress
from dataclasses import dataclass, field
from typing import Any, Literal

from omega_serv.core.i18n import _
from omega_serv.domain.security.waf.entities import KeywordListDefinition
from omega_serv.domain.security.waf.keyword_list import (
    parse_keyword_list_definition,
    validate_keyword_list_definitions,
)
from omega_serv.domain.security.waf.reputation import (
    DEFAULT_NEVER_AUTO_BLOCK,
    validate_never_auto_block,
)


@dataclass(frozen=True)
class InspectConfig:
    path: bool = True
    query: bool = True
    headers: bool = False
    body_methods: tuple[str, ...] = ("POST", "PUT", "PATCH")
    body_max_inspect_bytes: int = 65536
    decode_depth: int = 2

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> InspectConfig:
        defaults = cls()
        return cls(
            path=bool(data.get("path", defaults.path)),
            query=bool(data.get("query", defaults.query)),
            headers=bool(data.get("headers", defaults.headers)),
            body_methods=tuple(data.get("body_methods", defaults.body_methods)),
            body_max_inspect_bytes=int(data.get("body_max_inspect_bytes", defaults.body_max_inspect_bytes)),
            decode_depth=int(data.get("decode_depth", defaults.decode_depth)),
        )


@dataclass(frozen=True)
class ScoringConfig:
    block_threshold: int = 5
    high_score_threshold: int = 8
    response_status: int = 403

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> ScoringConfig:
        defaults = cls()
        return cls(
            block_threshold=int(data.get("block_threshold", defaults.block_threshold)),
            high_score_threshold=int(data.get("high_score_threshold", defaults.high_score_threshold)),
            response_status=int(data.get("response_status", defaults.response_status)),
        )


@dataclass(frozen=True)
class GlobalRateLimitConfig:
    key: str = "client_ip"
    requests: int = 60
    window_seconds: int = 60
    response_status: int = 429

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> GlobalRateLimitConfig:
        defaults = cls()
        return cls(
            key=data.get("key", defaults.key),
            requests=int(data.get("requests", defaults.requests)),
            window_seconds=int(data.get("window_seconds", defaults.window_seconds)),
            response_status=int(data.get("response_status", defaults.response_status)),
        )


@dataclass(frozen=True)
class PathRateLimitPolicy:
    """Regle de debit d'un dossier (OMEGA-SERV_ETUDE_RATE_LIMIT_EXCLUSIONS.md,
    D1/D2) : REMPLACE la limite globale pour ce prefixe, compteur propre.
    `requests == 0` = illimite (aucun comptage)."""
    prefix: str
    requests: int
    window_seconds: int = 60

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> PathRateLimitPolicy:
        return cls(
            prefix=str(data.get("prefix", "")),
            requests=int(data.get("requests", 0)),
            window_seconds=int(data.get("window_seconds", 60)),
        )


@dataclass(frozen=True)
class SourceRateLimitPolicy:
    """Regle de debit d'une IP/d'un reseau (D1/D2) ; `trusted` = source sure,
    jamais bannie pour un depassement de debit (D4)."""
    network: str
    requests: int
    window_seconds: int = 60
    trusted: bool = False

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> SourceRateLimitPolicy:
        return cls(
            network=str(data.get("network", "")),
            requests=int(data.get("requests", 0)),
            window_seconds=int(data.get("window_seconds", 60)),
            trusted=bool(data.get("trusted", False)),
        )


@dataclass(frozen=True)
class RateLimitConfig:
    enabled: bool = False
    algorithm: Literal["token_bucket"] = "token_bucket"
    global_: GlobalRateLimitConfig = field(default_factory=GlobalRateLimitConfig)
    path_policies: tuple[PathRateLimitPolicy, ...] = ()
    source_policies: tuple[SourceRateLimitPolicy, ...] = ()

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> RateLimitConfig:
        defaults = cls()
        return cls(
            enabled=bool(data.get("enabled", defaults.enabled)),
            algorithm=data.get("algorithm", defaults.algorithm),
            global_=GlobalRateLimitConfig.from_dict(data.get("global", {})),
            path_policies=tuple(PathRateLimitPolicy.from_dict(d) for d in data.get("path_policies", [])),
            source_policies=tuple(SourceRateLimitPolicy.from_dict(d) for d in data.get("source_policies", [])),
        )


@dataclass(frozen=True)
class ReputationConfig:
    enabled: bool = False
    suspicious_threshold: int = 3
    window_seconds: int = 300
    auto_block: bool = False
    auto_block_duration_seconds: int = 3600
    auto_block_max_entries: int = 100
    # Reseaux jamais bannis automatiquement (OMEGA-SERV_PLAN-DETAILLE_
    # SENSITIVE_PATHS.md §3.13) - voir reputation.py::DEFAULT_NEVER_AUTO_BLOCK.
    never_auto_block: tuple[str, ...] = DEFAULT_NEVER_AUTO_BLOCK

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> ReputationConfig:
        defaults = cls()
        return cls(
            enabled=bool(data.get("enabled", defaults.enabled)),
            suspicious_threshold=int(data.get("suspicious_threshold", defaults.suspicious_threshold)),
            window_seconds=int(data.get("window_seconds", defaults.window_seconds)),
            auto_block=bool(data.get("auto_block", defaults.auto_block)),
            auto_block_duration_seconds=int(
                data.get("auto_block_duration_seconds", defaults.auto_block_duration_seconds)
            ),
            auto_block_max_entries=int(data.get("auto_block_max_entries", defaults.auto_block_max_entries)),
            never_auto_block=tuple(str(n) for n in data.get("never_auto_block", defaults.never_auto_block)),
        )


# Blocklists : etat ECRIT par le serveur pendant qu'il tourne (auto-ban), donc
# sous var/ - le seul dossier inscriptible par le service systemd
# (ReadWritePaths) et deja partage avec son groupe. Avant le 2026-10-18 :
# secure/waf/, en lecture seule pour le service - un auto-ban n'y etait JAMAIS
# enregistre (OMEGA-SERV_PLAN-DETAILLE_SENSITIVE_PATHS.md, apres l'incident
# craftdark). Les anciens fichiers sont repris une fois au premier demarrage
# (application/security/blocklist_location.py).
DEFAULT_BLOCKLIST_PATH = "var/lib/waf/blocklist.json"
LEGACY_BLOCKLIST_PATH = "secure/waf/blocklist.json"
DEFAULT_MAGNET_BLOCKLIST_FILE = "var/lib/waf/magnet-blocklist.txt"
LEGACY_MAGNET_BLOCKLIST_FILE = "secure/waf/magnet-blocklist.txt"


def _relocated(value: str, legacy: str, default: str) -> str:
    """L'ANCIEN chemin par defaut, meme enregistre en toutes lettres, vaut le
    nouveau : l'ecran WAF Magnet enregistre toujours ses 5 chemins, donc chaque
    installation existante porte `secure/waf/magnet-blocklist.txt` dans sa config
    sans l'avoir jamais choisi - et ce chemin n'est pas inscriptible par le
    service systemd. Tout autre chemin personnalise est garde tel quel."""
    return default if value == legacy else value


@dataclass(frozen=True)
class BlocklistConfig:
    enabled: bool = True
    path: str = DEFAULT_BLOCKLIST_PATH
    allow_temporary_entries: bool = True

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> BlocklistConfig:
        defaults = cls()
        return cls(
            enabled=bool(data.get("enabled", defaults.enabled)),
            path=_relocated(data.get("path", defaults.path), LEGACY_BLOCKLIST_PATH, DEFAULT_BLOCKLIST_PATH),
            allow_temporary_entries=bool(data.get("allow_temporary_entries", defaults.allow_temporary_entries)),
        )


@dataclass(frozen=True)
class ExclusionsConfig:
    extensions: tuple[str, ...] = ()
    path_prefixes: tuple[str, ...] = ("/healthz",)
    do_not_inspect_body_path_prefixes: tuple[str, ...] = ()

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> ExclusionsConfig:
        defaults = cls()
        return cls(
            extensions=tuple(data.get("extensions", defaults.extensions)),
            path_prefixes=tuple(data.get("path_prefixes", defaults.path_prefixes)),
            do_not_inspect_body_path_prefixes=tuple(
                data.get("do_not_inspect_body_path_prefixes", defaults.do_not_inspect_body_path_prefixes)
            ),
        )


@dataclass(frozen=True)
class MagnetPathsConfig:
    """Chemins personnalises injectes dans le script magnet comme table
    globale Lua `omega_magnet_paths` (voir infrastructure/waf/
    lua_waf_adapter.py) - permet de DISSOCIER les chemins personnels
    d'un script importe (ex. `/etc/blocklist.txt` en dur) sans jamais
    modifier le fichier original de l'operateur : seule une COPIE
    adaptee (secure/waf/scripts/) lit `omega_magnet_paths`, avec un
    repli sur son propre chemin en dur si la table est absente.

    Les 5 defauts ci-dessous sont ceux attendus par la copie adaptee du
    script de reference livree avec omega-serv - un AUTRE script importe
    n'a aucune raison d'utiliser ces memes 5 noms de champs ni la table
    `omega_magnet_paths` elle-meme (ca reste un choix d'adaptation
    propre a CE script, pas un contrat generique - voir
    OMEGA-SERV_WAF_LUA_DEPERSONNALISATION.md, "limite assumee : la
    dissociation des chemins reste manuelle, script par script")."""
    blocklist_file: str = DEFAULT_MAGNET_BLOCKLIST_FILE
    rules_dir: str = "secure/waf/magnet-rules.d/"
    alerts_log: str = "var/log/waf-magnet-alerts.log"
    blocklist_log: str = "var/log/waf-magnet-blocklist.log"
    rate_store_file: str = "var/cache/waf-magnet-rate-store.lua"

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> MagnetPathsConfig:
        defaults = cls()
        return cls(
            blocklist_file=_relocated(
                data.get("blocklist_file", defaults.blocklist_file),
                LEGACY_MAGNET_BLOCKLIST_FILE, DEFAULT_MAGNET_BLOCKLIST_FILE,
            ),
            rules_dir=data.get("rules_dir", defaults.rules_dir),
            alerts_log=data.get("alerts_log", defaults.alerts_log),
            blocklist_log=data.get("blocklist_log", defaults.blocklist_log),
            rate_store_file=data.get("rate_store_file", defaults.rate_store_file),
        )


@dataclass(frozen=True)
class MagnetConfig:
    """Script WAF complementaire type "magnet" (OMEGA-SERV_ETUDE_INCLUDE_
    ET_MAGNET_LUA.md §5) : jamais un remplacement du moteur natif, un
    renfort optionnel evalue EN PLUS (domain/security/waf/
    combine_decisions.py decide de la priorite). `script` vide = utilise
    `paths.waf_script` comme defaut (resolu par
    application/server/start_server.py, qui a acces aux deux sections de
    la configuration - ce module ne connait que `options.waf`, jamais
    `paths`).

    Revision "import d'un WAF externe" (pas une implementation de plus -
    voir infrastructure/waf/lua_waf_adapter.py) : le script importe est
    execute via un pont `lighty.*` compatible mod_magnet, jamais un
    contrat `inspect(req)` propre a omega-serv."""
    enabled: bool = False
    script: str = ""
    timeout_ms: int = 50
    on_error: Literal["ignore", "fail-closed"] = "ignore"
    paths: MagnetPathsConfig = field(default_factory=MagnetPathsConfig)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> MagnetConfig:
        defaults = cls()
        return cls(
            enabled=bool(data.get("enabled", defaults.enabled)),
            script=data.get("script", defaults.script),
            timeout_ms=int(data.get("timeout_ms", defaults.timeout_ms)),
            on_error=data.get("on_error", defaults.on_error),
            paths=MagnetPathsConfig.from_dict(data.get("paths", {})),
        )


@dataclass(frozen=True)
class WafLoggingConfig:
    path: str = "var/log/waf-alerts.log"
    format: Literal["jsonl"] = "jsonl"
    include_body_excerpt: bool = False
    body_excerpt_max_bytes: int = 0
    mask_headers: tuple[str, ...] = ("authorization", "cookie", "set-cookie", "x-api-key")
    max_user_agent_chars: int = 120
    max_path_chars: int = 2048

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> WafLoggingConfig:
        defaults = cls()
        return cls(
            path=data.get("path", defaults.path),
            format=data.get("format", defaults.format),
            include_body_excerpt=bool(data.get("include_body_excerpt", defaults.include_body_excerpt)),
            body_excerpt_max_bytes=int(data.get("body_excerpt_max_bytes", defaults.body_excerpt_max_bytes)),
            mask_headers=tuple(h.lower() for h in data.get("mask_headers", defaults.mask_headers)),
            max_user_agent_chars=int(data.get("max_user_agent_chars", defaults.max_user_agent_chars)),
            max_path_chars=int(data.get("max_path_chars", defaults.max_path_chars)),
        )


@dataclass(frozen=True)
class WafConfig:
    """Forme complete de options["waf"].settings - voir doc WAF,
    section "Configuration WAF generique" pour l'exemple JSON source."""
    engine: Literal["python"] = "python"
    mode: Literal["log-only", "block"] = "log-only"
    on_internal_error: Literal["fail-open", "fail-closed"] = "fail-open"
    inspect: InspectConfig = field(default_factory=InspectConfig)
    scoring: ScoringConfig = field(default_factory=ScoringConfig)
    rate_limit: RateLimitConfig = field(default_factory=RateLimitConfig)
    reputation: ReputationConfig = field(default_factory=ReputationConfig)
    blocklist: BlocklistConfig = field(default_factory=BlocklistConfig)
    rule_paths: tuple[str, ...] = ()
    keyword_lists: tuple[KeywordListDefinition, ...] = ()
    magnet: MagnetConfig = field(default_factory=MagnetConfig)
    exclusions: ExclusionsConfig = field(default_factory=ExclusionsConfig)
    logging: WafLoggingConfig = field(default_factory=WafLoggingConfig)


def parse_waf_config(settings: dict[str, Any]) -> WafConfig:
    """`settings` est deja options["waf"] SANS la cle "enabled" (retiree
    par Option.from_dict, voir domain/config/option.py)."""
    defaults = WafConfig()
    rules = settings.get("rules", {})
    return WafConfig(
        engine=settings.get("engine", defaults.engine),
        mode=settings.get("mode", defaults.mode),
        on_internal_error=settings.get("on_internal_error", defaults.on_internal_error),
        inspect=InspectConfig.from_dict(settings.get("inspect", {})),
        scoring=ScoringConfig.from_dict(settings.get("scoring", {})),
        rate_limit=RateLimitConfig.from_dict(settings.get("rate_limit", {})),
        reputation=ReputationConfig.from_dict(settings.get("reputation", {})),
        blocklist=BlocklistConfig.from_dict(settings.get("blocklist", {})),
        rule_paths=tuple(rules.get("paths", defaults.rule_paths)),
        keyword_lists=tuple(
            parse_keyword_list_definition(d) for d in rules.get("keyword_lists", [])
        ),
        magnet=MagnetConfig.from_dict(settings.get("magnet", {})),
        exclusions=ExclusionsConfig.from_dict(settings.get("exclusions", {})),
        logging=WafLoggingConfig.from_dict(settings.get("logging", {})),
    )


def validate_waf_config(config: WafConfig) -> list[str]:
    """Validation structurelle pure (pas d'I/O - l'existence reelle des
    fichiers de regles/blocklist est verifiee par
    application/config/validate_config.py)."""
    errors: list[str] = []
    if config.engine != "python":
        errors.append(_("options.waf.engine invalide : {engine!r} (seul 'python' est supporte en V1)").format(engine=config.engine))
    if config.mode not in ("log-only", "block"):
        errors.append(_("options.waf.mode invalide : {mode!r}").format(mode=config.mode))
    if config.on_internal_error not in ("fail-open", "fail-closed"):
        errors.append(_("options.waf.on_internal_error invalide : {on_internal_error!r}").format(on_internal_error=config.on_internal_error))
    if config.magnet.on_error not in ("ignore", "fail-closed"):
        errors.append(_("options.waf.magnet.on_error invalide : {on_error!r}").format(on_error=config.magnet.on_error))
    if config.magnet.timeout_ms <= 0:
        errors.append(_("options.waf.magnet.timeout_ms doit être strictement positif"))
    if config.inspect.decode_depth < 1:
        errors.append(_("options.waf.inspect.decode_depth doit être >= 1"))
    if config.inspect.body_max_inspect_bytes < 0:
        errors.append(_("options.waf.inspect.body_max_inspect_bytes doit être >= 0"))
    if config.scoring.block_threshold <= 0:
        errors.append(_("options.waf.scoring.block_threshold doit être strictement positif"))
    if not (100 <= config.scoring.response_status < 600):
        errors.append(_("options.waf.scoring.response_status invalide : {response_status}").format(response_status=config.scoring.response_status))
    errors.extend(validate_rate_limit_config(config.rate_limit))
    if config.reputation.auto_block_max_entries < 0:
        errors.append(_("options.waf.reputation.auto_block_max_entries doit être >= 0"))
    if not config.rule_paths and not config.keyword_lists:
        errors.append(
            _("options.waf.rules.paths et options.waf.rules.keyword_lists ne peuvent pas être "
            "tous les deux vides si le WAF est activé")
        )
    errors.extend(validate_keyword_list_definitions(config.keyword_lists))
    errors.extend(validate_never_auto_block(config.reputation.never_auto_block))
    return errors


def validate_rate_limit_config(rate_limit: RateLimitConfig) -> list[str]:
    """Partie debit de `validate_waf_config`, appelable seule (ecran
    Exclusions et debit : une config invalide AILLEURS ne doit pas empecher
    de regler le debit)."""
    errors: list[str] = []
    if rate_limit.global_.requests <= 0:
        errors.append(_("options.waf.rate_limit.global.requests doit être strictement positif"))
    if rate_limit.global_.window_seconds <= 0:
        errors.append(_("options.waf.rate_limit.global.window_seconds doit être strictement positif"))
    errors.extend(validate_rate_limit_policies(rate_limit))
    return errors


def validate_rate_limit_policies(rate_limit: RateLimitConfig) -> list[str]:
    errors: list[str] = []
    for policy in rate_limit.path_policies:
        if not policy.prefix.startswith("/"):
            errors.append(_("options.waf.rate_limit.path_policies : préfixe invalide (doit commencer par /) : {prefix!r}").format(prefix=policy.prefix))
        if policy.requests < 0:
            errors.append(_("options.waf.rate_limit.path_policies : requests doit être >= 0 ({prefix})").format(prefix=policy.prefix))
        if policy.window_seconds <= 0:
            errors.append(_("options.waf.rate_limit.path_policies : window_seconds doit être strictement positif ({prefix})").format(prefix=policy.prefix))
    for source in rate_limit.source_policies:
        try:
            ipaddress.ip_network(source.network, strict=False)
        except ValueError:
            errors.append(_("options.waf.rate_limit.source_policies : réseau invalide : {network!r}").format(network=source.network))
        if source.requests < 0:
            errors.append(_("options.waf.rate_limit.source_policies : requests doit être >= 0 ({network})").format(network=source.network))
        if source.window_seconds <= 0:
            errors.append(_("options.waf.rate_limit.source_policies : window_seconds doit être strictement positif ({network})").format(network=source.network))
    return errors


def with_reputation_enabled_for_lists(settings: dict[str, Any]) -> tuple[dict[str, Any], tuple[str, ...]]:
    """Decision utilisateur 2026-10-18 (OMEGA-SERV_PLAN-DETAILLE_SENSITIVE_
    PATHS.md, lot 2.2) : les valeurs par defaut du code restent INCHANGEES
    (reputation et auto_block desactives) - jamais un changement de
    comportement silencieux d'une instance existante a la mise a jour. C'est
    l'action EXPLICITE "charger une liste" (assistant WAF Custom, lot 6) qui
    active la reputation et l'auto-ban s'ils sont eteints, sans quoi la
    recidive par liste (§3.12) ne ferait rien.

    Fonction pure : renvoie une COPIE de `options.waf` (settings) et la liste
    des changements effectues (vide = rien a faire), a afficher tels quels a
    l'utilisateur. Les autres reglages de `reputation` sont conserves."""
    reputation = dict(settings.get("reputation") or {})
    changes: list[str] = []
    if not reputation.get("enabled", ReputationConfig.enabled):
        reputation["enabled"] = True
        changes.append(_("réputation activée (récidive comptée par IP)"))
    if not reputation.get("auto_block", ReputationConfig.auto_block):
        reputation["auto_block"] = True
        changes.append(_("auto-ban activé (blocklist temporaire, réponse 451)"))
    if not changes:
        return settings, ()
    return {**settings, "reputation": reputation}, tuple(changes)
