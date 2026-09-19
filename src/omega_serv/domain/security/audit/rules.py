"""Regles d'audit pures (spec §26, plan corrige §5) : n'inspectent que
la configuration deja chargee (`OmegaServConfig`), aucun I/O. Les
regles qui touchent reellement le disque (permissions, certificat,
fichiers sensibles, taille de logs, unite systemd) vivent dans
infrastructure/security/*_rules.py."""
from __future__ import annotations

from collections.abc import Callable

from omega_serv.domain.config.entities import OmegaServConfig
from omega_serv.domain.routing.proxy_zone import parse_proxy_zones
from omega_serv.domain.routing.upload_zone import parse_upload_zone_rules
from omega_serv.domain.security.audit.entities import AuditFinding, Severity
from omega_serv.domain.security.csp import DEFAULT_CSP_POLICY

AuditRule = Callable[[OmegaServConfig], list[AuditFinding]]

_DANGEROUS_METHODS = frozenset({"TRACE", "TRACK", "CONNECT", "DELETE", "PUT"})
_HIGH_TIMEOUT_THRESHOLD_SECONDS = 60


def rule_public_bind(config: OmegaServConfig) -> list[AuditFinding]:
    """TLS-003. Avertissement consultatif, jamais bloquant : un bind
    0.0.0.0 est legitime derriere un reverse proxy (tls.mode ==
    'behind_proxy')."""
    if config.server.bind in ("0.0.0.0", "::"):
        return [AuditFinding(
            rule_id="TLS-003", rule_name="Serveur bind sur toutes les interfaces",
            severity=Severity.MEDIUM, category="tls",
            message=f"server.bind = {config.server.bind!r} (toutes interfaces)",
            recommendation=(
                "Verifier qu'un reverse proxy ou tls.mode='behind_proxy' est bien en place ; "
                "sinon restreindre server.bind a 127.0.0.1."
            ),
            details={"bind": config.server.bind},
        )]
    return []


def rule_csp_unsafe_inline(config: OmegaServConfig, csp_policy: str = DEFAULT_CSP_POLICY) -> list[AuditFinding]:
    """CSP-001. La CSP de ce projet est globale uniquement
    (domain/security/csp.py::DEFAULT_CSP_POLICY, pas de CSP par zone) -
    cette regle inspecte donc la seule politique existante. `csp_policy`
    reste parametrable (defaut : la constante reelle) pour rester
    testable sans monkeypatcher un module."""
    if "'unsafe-inline'" in csp_policy:
        return [AuditFinding(
            rule_id="CSP-001", rule_name="CSP contient unsafe-inline",
            severity=Severity.MEDIUM, category="csp",
            message="La CSP par defaut contient 'unsafe-inline'.",
            recommendation="Supprimer unsafe-inline, utiliser des hashes/nonces si necessaire.",
            details={"csp": csp_policy},
        )]
    return []


def rule_csp_too_permissive(config: OmegaServConfig, csp_policy: str = DEFAULT_CSP_POLICY) -> list[AuditFinding]:
    """CSP-002 : directive avec une source generique (`*`), qui autorise
    n'importe quelle origine - annule l'interet meme de la CSP pour
    cette directive."""
    permissive_directives = []
    for directive in csp_policy.split(";"):
        directive = directive.strip()
        if not directive:
            continue
        name, _, values = directive.partition(" ")
        if "*" in values.split():
            permissive_directives.append(name)
    if permissive_directives:
        return [AuditFinding(
            rule_id="CSP-002", rule_name="CSP contient une directive trop permissive",
            severity=Severity.MEDIUM, category="csp",
            message=f"Directive(s) avec source generique '*' : {', '.join(permissive_directives)}",
            recommendation="Remplacer '*' par une liste explicite d'origines de confiance.",
            details={"directives": permissive_directives},
        )]
    return []


def rule_dangerous_methods(config: OmegaServConfig) -> list[AuditFinding]:
    """GEN-001."""
    enabled = _DANGEROUS_METHODS.intersection(set(config.security.allowed_methods))
    if enabled:
        return [AuditFinding(
            rule_id="GEN-001", rule_name="Methodes HTTP dangereuses activees",
            severity=Severity.HIGH, category="generic",
            message=f"Methodes activees : {', '.join(sorted(enabled))}",
            recommendation="Restreindre security.allowed_methods a GET/HEAD/POST si possible.",
            details={"allowed_methods": list(config.security.allowed_methods)},
        )]
    return []


def rule_high_timeouts(config: OmegaServConfig) -> list[AuditFinding]:
    """GEN-002."""
    if config.server.read_timeout_seconds > _HIGH_TIMEOUT_THRESHOLD_SECONDS:
        return [AuditFinding(
            rule_id="GEN-002", rule_name="read_timeout_seconds eleve",
            severity=Severity.MEDIUM, category="generic",
            message=(
                f"server.read_timeout_seconds = {config.server.read_timeout_seconds}s "
                f"(recommande <= {_HIGH_TIMEOUT_THRESHOLD_SECONDS}s)"
            ),
            recommendation="Reduire pour limiter l'impact d'un client lent (slowloris).",
            details={"read_timeout_seconds": config.server.read_timeout_seconds},
        )]
    return []


def rule_upload_zones_without_type_restriction(config: OmegaServConfig) -> list[AuditFinding]:
    """UPLOAD-001. Une zone d'upload sans `allowed_extensions` NI
    `allowed_content_types` accepte n'importe quel fichier - un risque
    d'hygiene reel independamment de la ou le fichier est stocke
    (webroot ou non), donc verifiable sans I/O (contrairement a "le
    stockage est-il sous webroot", qui exige une resolution de chemin
    reelle et n'est pas traite ici, voir plan corrige §5.6)."""
    upload_option = config.options.get("upload")
    if upload_option is None or not upload_option.enabled:
        return []

    findings: list[AuditFinding] = []
    for zone in parse_upload_zone_rules(upload_option.settings.get("zones", [])):
        if not zone.policy.allowed_extensions and not zone.policy.allowed_content_types:
            findings.append(AuditFinding(
                rule_id="UPLOAD-001", rule_name="Zone d'upload sans restriction de type de fichier",
                severity=Severity.MEDIUM, category="upload",
                message=(
                    f"Zone {zone.url_prefix!r} accepte n'importe quel type de fichier "
                    "(aucune policy.allowed_extensions ni policy.allowed_content_types)."
                ),
                recommendation=(
                    "Restreindre policy.allowed_extensions et/ou policy.allowed_content_types "
                    "a la liste minimale necessaire pour cette zone."
                ),
                details={"url_prefix": zone.url_prefix, "storage_path": zone.storage_path},
            ))
    return findings


def rule_reverse_proxy_upstream_tls_unverified(config: OmegaServConfig) -> list[AuditFinding]:
    """PROXY-001. Une zone `options.reverse_proxy` avec
    `verify_upstream_tls=False` accepte n'importe quel certificat
    presente par l'upstream HTTPS - MITM possible sur le reseau
    intermediaire si celui-ci n'est pas de confiance (OMEGA-SERV_PLAN-
    DETAILLE_REVERSE_PROXY.md §5.3, §6). Ne signale une zone que si elle
    a au moins un upstream reellement en HTTPS (`use_tls=True`) - une
    zone HTTP pure n'est jamais concernee par ce reglage."""
    proxy_option = config.options.get("reverse_proxy")
    if proxy_option is None or not proxy_option.enabled:
        return []

    findings: list[AuditFinding] = []
    for zone in parse_proxy_zones(proxy_option.settings.get("zones", [])):
        if zone.verify_upstream_tls:
            continue
        if not any(upstream.use_tls for upstream in zone.upstreams):
            continue
        findings.append(AuditFinding(
            rule_id="PROXY-001", rule_name="Verification TLS upstream desactivee",
            severity=Severity.HIGH, category="proxy",
            message=(
                f"Zone {zone.url_prefix!r} : verify_upstream_tls=False sur un upstream HTTPS - "
                "le certificat presente par le backend n'est jamais verifie."
            ),
            recommendation=(
                "Activer verify_upstream_tls (defaut) sauf necessite reelle et documentee "
                "(backend interne en certificat auto-signe, reseau intermediaire de confiance)."
            ),
            details={"url_prefix": zone.url_prefix},
        ))
    return findings


PURE_RULES: tuple[AuditRule, ...] = (
    rule_public_bind,
    rule_csp_unsafe_inline,
    rule_csp_too_permissive,
    rule_dangerous_methods,
    rule_high_timeouts,
    rule_upload_zones_without_type_restriction,
    rule_reverse_proxy_upstream_tls_unverified,
)
