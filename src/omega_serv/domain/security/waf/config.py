# Copyright (c) 2026 kraynux - kraynux@proton.me - Licence MIT (voir fichier LICENSE)
"""Structure la configuration WAF brute (options["waf"].settings, un
dict ouvert - voir domain/config/option.py) en une forme typee.

Forme fixee par OMEGA-SERV_WAF_LUA_DEPERSONNALISATION.md, section
"Configuration WAF generique". Suit le meme patron que
domain/routing/alias.py::parse_alias_rules - une fonction pure de
parsing, pas de validation d'existence de fichiers ici (ca, c'est
application/config/validate_config.py, qui a acces au filesystem)."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Literal


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
class RateLimitConfig:
    enabled: bool = False
    algorithm: Literal["token_bucket"] = "token_bucket"
    global_: GlobalRateLimitConfig = field(default_factory=GlobalRateLimitConfig)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> RateLimitConfig:
        defaults = cls()
        return cls(
            enabled=bool(data.get("enabled", defaults.enabled)),
            algorithm=data.get("algorithm", defaults.algorithm),
            global_=GlobalRateLimitConfig.from_dict(data.get("global", {})),
        )


@dataclass(frozen=True)
class ReputationConfig:
    enabled: bool = False
    suspicious_threshold: int = 3
    window_seconds: int = 300
    auto_block: bool = False
    auto_block_duration_seconds: int = 3600
    auto_block_max_entries: int = 100

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
        )


@dataclass(frozen=True)
class BlocklistConfig:
    enabled: bool = True
    path: str = "secure/waf/blocklist.json"
    allow_temporary_entries: bool = True

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> BlocklistConfig:
        defaults = cls()
        return cls(
            enabled=bool(data.get("enabled", defaults.enabled)),
            path=data.get("path", defaults.path),
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
        exclusions=ExclusionsConfig.from_dict(settings.get("exclusions", {})),
        logging=WafLoggingConfig.from_dict(settings.get("logging", {})),
    )


def validate_waf_config(config: WafConfig) -> list[str]:
    """Validation structurelle pure (pas d'I/O - l'existence reelle des
    fichiers de regles/blocklist est verifiee par
    application/config/validate_config.py)."""
    errors: list[str] = []
    if config.engine != "python":
        errors.append(f"options.waf.engine invalide : {config.engine!r} (seul 'python' est supporte en V1)")
    if config.mode not in ("log-only", "block"):
        errors.append(f"options.waf.mode invalide : {config.mode!r}")
    if config.on_internal_error not in ("fail-open", "fail-closed"):
        errors.append(f"options.waf.on_internal_error invalide : {config.on_internal_error!r}")
    if config.inspect.decode_depth < 1:
        errors.append("options.waf.inspect.decode_depth doit etre >= 1")
    if config.inspect.body_max_inspect_bytes < 0:
        errors.append("options.waf.inspect.body_max_inspect_bytes doit etre >= 0")
    if config.scoring.block_threshold <= 0:
        errors.append("options.waf.scoring.block_threshold doit etre strictement positif")
    if not (100 <= config.scoring.response_status < 600):
        errors.append(f"options.waf.scoring.response_status invalide : {config.scoring.response_status}")
    if config.rate_limit.global_.requests <= 0:
        errors.append("options.waf.rate_limit.global.requests doit etre strictement positif")
    if config.rate_limit.global_.window_seconds <= 0:
        errors.append("options.waf.rate_limit.global.window_seconds doit etre strictement positif")
    if config.reputation.auto_block_max_entries < 0:
        errors.append("options.waf.reputation.auto_block_max_entries doit etre >= 0")
    if not config.rule_paths:
        errors.append("options.waf.rules.paths ne doit pas etre vide si le WAF est active")
    return errors
