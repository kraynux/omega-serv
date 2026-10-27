"""Regles d'audit pures (spec §26, plan corrige §5) : n'inspectent que
la configuration deja chargee (`OmegaServConfig`), aucun I/O. Les
regles qui touchent reellement le disque (permissions, certificat,
fichiers sensibles, taille de logs, unite systemd) vivent dans
infrastructure/security/*_rules.py."""
from __future__ import annotations

from collections.abc import Callable

from omega_serv.core.i18n import _
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
            rule_id="TLS-003", rule_name=_("Serveur bind sur toutes les interfaces"),
            severity=Severity.MEDIUM, category="tls",
            message=_("server.bind = {bind!r} (toutes interfaces)").format(bind=config.server.bind),
            recommendation=(
                _("Vérifier qu'un reverse proxy ou tls.mode='behind_proxy' est bien en place ; "
                "sinon restreindre server.bind à 127.0.0.1.")
            ),
            details={"bind": config.server.bind},
        )]
    return []


def _csp_candidates(config: OmegaServConfig, csp_policy: str) -> list[tuple[str, str]]:
    """(libelle, politique) a inspecter - la politique globale, PUIS
    chaque zone CSP configuree (security.csp_zones, retour utilisateur
    2026-10-10 : "regles conditionnelles pour des dossiers choisis").
    Une exception de zone reste toujours visible ici, jamais silencieuse
    - meme deliberee, elle doit apparaitre dans `audit security`."""
    candidates = [("globale", csp_policy)]
    candidates.extend((_("zone {path_prefix!r}").format(path_prefix=zone.path_prefix), zone.data) for zone in config.security.csp_zones)
    return candidates


def rule_csp_unsafe_inline(config: OmegaServConfig, csp_policy: str = DEFAULT_CSP_POLICY) -> list[AuditFinding]:
    """CSP-001. `csp_policy` reste parametrable (defaut : la constante
    reelle) pour rester testable sans monkeypatcher un module - les
    zones, elles, viennent toujours de `config` (jamais parametrables
    separement, une zone n'existe que dans la configuration)."""
    findings = []
    for label, policy in _csp_candidates(config, csp_policy):
        if "'unsafe-inline'" in policy:
            findings.append(AuditFinding(
                rule_id="CSP-001", rule_name=_("CSP contient unsafe-inline"),
                severity=Severity.MEDIUM, category="csp",
                message=_("La CSP {label} contient 'unsafe-inline'.").format(label=label),
                recommendation=_("Supprimer unsafe-inline, utiliser des hashes/nonces si nécessaire."),
                details={"csp": policy, "scope": label},
            ))
    return findings


def rule_csp_too_permissive(config: OmegaServConfig, csp_policy: str = DEFAULT_CSP_POLICY) -> list[AuditFinding]:
    """CSP-002 : directive avec une source generique (`*`), qui autorise
    n'importe quelle origine - annule l'interet meme de la CSP pour
    cette directive. Inspecte la politique globale et chaque zone CSP
    (meme raison que CSP-001 ci-dessus)."""
    findings = []
    for label, policy in _csp_candidates(config, csp_policy):
        permissive_directives = []
        for directive in policy.split(";"):
            directive = directive.strip()
            if not directive:
                continue
            name, _ignored, values = directive.partition(" ")
            if "*" in values.split():
                permissive_directives.append(name)
        if permissive_directives:
            findings.append(AuditFinding(
                rule_id="CSP-002", rule_name=_("CSP contient une directive trop permissive"),
                severity=Severity.MEDIUM, category="csp",
                message=_("CSP {label} - directive(s) avec source générique '*' : {value}").format(label=label, value=', '.join(permissive_directives)),
                recommendation=_("Remplacer '*' par une liste explicite d'origines de confiance."),
                details={"directives": permissive_directives, "scope": label},
            ))
    return findings


def rule_dangerous_methods(config: OmegaServConfig) -> list[AuditFinding]:
    """GEN-001."""
    enabled = _DANGEROUS_METHODS.intersection(set(config.security.allowed_methods))
    if enabled:
        return [AuditFinding(
            rule_id="GEN-001", rule_name=_("Méthodes HTTP dangereuses activées"),
            severity=Severity.HIGH, category="generic",
            message=_("Méthodes activées : {value}").format(value=', '.join(sorted(enabled))),
            recommendation=_("Restreindre security.allowed_methods à GET/HEAD/POST si possible."),
            details={"allowed_methods": list(config.security.allowed_methods)},
        )]
    return []


def rule_high_timeouts(config: OmegaServConfig) -> list[AuditFinding]:
    """GEN-002."""
    if config.server.read_timeout_seconds > _HIGH_TIMEOUT_THRESHOLD_SECONDS:
        return [AuditFinding(
            rule_id="GEN-002", rule_name=_("read_timeout_seconds élevé"),
            severity=Severity.MEDIUM, category="generic",
            message=(
                _("server.read_timeout_seconds = {read_timeout_seconds}s (recommandé <= {HIGH_TIMEOUT_THRESHOLD_SECONDS}s)").format(read_timeout_seconds=config.server.read_timeout_seconds, HIGH_TIMEOUT_THRESHOLD_SECONDS=_HIGH_TIMEOUT_THRESHOLD_SECONDS)
            ),
            recommendation=_("Réduire pour limiter l'impact d'un client lent (slowloris)."),
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
                rule_id="UPLOAD-001", rule_name=_("Zone d'upload sans restriction de type de fichier"),
                severity=Severity.MEDIUM, category="upload",
                message=(
                    _("Zone {url_prefix!r} accepte n'importe quel type de fichier (aucune policy.allowed_extensions ni policy.allowed_content_types).").format(url_prefix=zone.url_prefix)
                ),
                recommendation=(
                    _("Restreindre policy.allowed_extensions et/ou policy.allowed_content_types "
                    "à la liste minimale nécessaire pour cette zone.")
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
            rule_id="PROXY-001", rule_name=_("Vérification TLS upstream désactivée"),
            severity=Severity.HIGH, category="proxy",
            message=(
                _("Zone {url_prefix!r} : verify_upstream_tls=False sur un upstream HTTPS - le certificat présenté par le backend n'est jamais vérifié.").format(url_prefix=zone.url_prefix)
            ),
            recommendation=(
                _("Activer verify_upstream_tls (défaut) sauf nécessité réelle et documentée "
                "(backend interne en certificat auto-signé, réseau intermédiaire de confiance).")
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
