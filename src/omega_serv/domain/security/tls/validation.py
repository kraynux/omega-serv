"""Regles de coherence TLS/HSTS pures (doc TLS §2, §13, §21 ; plan de
developpement §6 "Portes de validation bloquantes TLS"). Toutes les
fonctions ici prennent des FAITS deja rassembles (permissions lues,
certificat deja parse, correspondance cle/certificat deja verifiee) -
jamais d'I/O : le rassemblement des faits est une responsabilite
d'application/infrastructure (voir application/tls/validate_tls_environment.py)."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from omega_serv.core.i18n import _
from omega_serv.domain.security.tls.entities import (
    VALID_KEY_TYPES,
    CaParams,
    CertificateInfo,
    CsrParams,
    SelfSignedCertParams,
)

_LOCAL_BIND_HOSTS = frozenset({"127.0.0.1", "::1", "localhost"})
_VALID_TLS_VERSIONS = ("TLS1.2", "TLS1.3")
_VALID_TLS_MODES = ("direct", "behind_proxy")


def validate_tls_config_structure(
    enabled: bool,
    mode: str,
    min_version: str,
    max_version: str,
    certificate_path: str,
    private_key_path: str,
) -> list[str]:
    """Validation structurelle pure (mode/versions/chemins non vides) -
    distincte des portes de demarrage bloquantes ci-dessous, qui
    exigent des faits lus sur le disque reel."""
    errors: list[str] = []
    if mode not in _VALID_TLS_MODES:
        errors.append(_("tls.mode invalide : {mode!r} (attendu : {VALID_TLS_MODES})").format(mode=mode, VALID_TLS_MODES=_VALID_TLS_MODES))
    if min_version not in _VALID_TLS_VERSIONS or max_version not in _VALID_TLS_VERSIONS:
        errors.append(_("tls.protocols min/max_version invalide (attendu : {VALID_TLS_VERSIONS})").format(VALID_TLS_VERSIONS=_VALID_TLS_VERSIONS))
    elif _VALID_TLS_VERSIONS.index(min_version) > _VALID_TLS_VERSIONS.index(max_version):
        errors.append(_("tls.protocols.min_version ({min_version}) ne peut pas être supérieur à max_version ({max_version})").format(min_version=min_version, max_version=max_version))
    if enabled and mode == "direct":
        if not certificate_path:
            errors.append(_("tls.certificate.certificate_path ne peut pas être vide quand tls est actif en mode direct"))
        if not private_key_path:
            errors.append(_("tls.certificate.private_key_path ne peut pas être vide quand tls est actif en mode direct"))
    return errors


def validate_self_signed_params(params: SelfSignedCertParams) -> list[str]:
    errors: list[str] = []
    if not params.common_name:
        errors.append(_("common_name (CN) ne peut pas être vide"))
    if not params.san_dns and not params.san_ip:
        errors.append(_("au moins un SAN (DNS ou IP) est requis - le CN seul n'est plus suffisant (doc TLS §6.2)"))
    if params.validity_days <= 0:
        errors.append(_("validity_days doit être strictement positif"))
    if params.key_type not in VALID_KEY_TYPES:
        errors.append(_("key_type invalide : {key_type!r} (attendu : {value})").format(key_type=params.key_type, value=sorted(VALID_KEY_TYPES)))
    return errors


def validate_ca_params(params: CaParams) -> list[str]:
    """Doc TLS §7.3 etape 3 : "demander et confirmer une passphrase pour
    la cle de CA" - contrairement au certificat auto-signe, la passphrase
    n'est pas optionnelle ici (§7.2 : la cle de CA est "l'element le plus
    sensible", la proteger par passphrase n'est pas une simple option)."""
    errors: list[str] = []
    if not params.common_name:
        errors.append(_("common_name (CN) ne peut pas être vide"))
    if not params.key_password:
        errors.append(_("key_password est obligatoire pour une CA locale (doc TLS §7.2/§7.3)"))
    if params.validity_days <= 0:
        errors.append(_("validity_days doit être strictement positif"))
    if params.key_type not in VALID_KEY_TYPES:
        errors.append(_("key_type invalide : {key_type!r} (attendu : {value})").format(key_type=params.key_type, value=sorted(VALID_KEY_TYPES)))
    return errors


def validate_csr_params(params: CsrParams) -> list[str]:
    errors: list[str] = []
    if not params.common_name:
        errors.append(_("common_name (CN) ne peut pas être vide"))
    if not params.san_dns and not params.san_ip:
        errors.append(_("au moins un SAN (DNS ou IP) est requis - le CN seul n'est plus suffisant (doc TLS §6.2)"))
    if params.key_type not in VALID_KEY_TYPES:
        errors.append(_("key_type invalide : {key_type!r} (attendu : {value})").format(key_type=params.key_type, value=sorted(VALID_KEY_TYPES)))
    return errors


@dataclass(frozen=True)
class TlsStartupFacts:
    """Faits deja rassembles necessaires aux portes de demarrage
    bloquantes (plan de developpement §6). `private_key_mode=None` et
    `certificate_info=None` signifient "fichier absent", deja signale
    par ailleurs (application/config/validate_config.py, existence de
    fichier) - ce module ne re-signale pas l'absence, seulement la
    coherence de ce qui existe."""
    tls_enabled: bool
    tls_mode: str
    bind_host: str
    private_key_mode: int | None
    certificate_info: CertificateInfo | None
    keys_match: bool | None
    hsts_enabled: bool
    self_signed_public_bind_confirmed: bool
    now: datetime


def validate_tls_startup(facts: TlsStartupFacts) -> list[str]:
    """Chaque erreur retournee est un refus de demarrage (pas un simple
    avertissement) - voir plan de developpement §6, liste exacte des
    portes bloquantes TLS."""
    errors: list[str] = []

    if facts.hsts_enabled and not facts.tls_enabled:
        errors.append(_("security.hsts_enabled actif alors que tls.enabled est désactivé (doc TLS §13)"))

    if not facts.tls_enabled or facts.tls_mode != "direct":
        return errors

    if facts.private_key_mode is not None and facts.private_key_mode & 0o077:
        errors.append(
            _("clé privée TLS lisible par le groupe ou les autres (mode {value}, attendu 0600 ou plus strict - doc TLS §4.1/§21)").format(value=oct(facts.private_key_mode))
        )

    if facts.certificate_info is not None:
        if facts.certificate_info.is_expired(facts.now):
            errors.append(_("certificat TLS expiré depuis le {value}").format(value=facts.certificate_info.not_after.isoformat()))

        if (
            facts.certificate_info.is_self_signed
            and facts.bind_host not in _LOCAL_BIND_HOSTS
            and not facts.self_signed_public_bind_confirmed
        ):
            errors.append(
                _("certificat auto-signé avec bind public ({bind_host}) sans confirmation explicite (doc TLS §6.1/§21 - réserver l'auto-signé au local/interne, ou confirmer explicitement)").format(bind_host=facts.bind_host)
            )

    if facts.keys_match is False:
        errors.append(_("la clé privée TLS ne correspond pas au certificat configuré"))

    return errors


@dataclass(frozen=True)
class CertificateImportFacts:
    """Faits deja rassembles pour valider un import de certificat externe
    (doc TLS §9.1) - meme patron que `TlsStartupFacts` ci-dessus : ce
    module ne fait jamais d'I/O, `application/tls/import_certificate.py`
    rassemble ces faits avant d'appeler `validate_certificate_import`.

    La correspondance SAN/nom d'hote reellement utilise (doc TLS §9.1,
    dernier point) N'EST PAS verifiee ici deliberement : ce cas d'usage
    est generique (n'importe quel couple cle/certificat), il ne connait
    pas le `server_name`/bind attendu - cette verification specifique
    reste a la charge de l'appelant (assistant TLS) qui, lui, connait la
    configuration cible."""
    source_key_exists: bool
    source_cert_exists: bool
    source_chain_path_given: bool
    source_chain_exists: bool
    keys_match: bool | None
    certificate_info: CertificateInfo | None
    now: datetime


def validate_certificate_import(facts: CertificateImportFacts) -> list[str]:
    errors: list[str] = []
    if not facts.source_key_exists:
        errors.append(_("la clé privée source est introuvable"))
    if not facts.source_cert_exists:
        errors.append(_("le certificat source est introuvable"))
    if facts.source_chain_path_given and not facts.source_chain_exists:
        errors.append(_("le fichier de chaîne intermédiaire indique est introuvable"))
    if facts.keys_match is False:
        errors.append(_("la clé privée et le certificat fournis ne correspondent pas"))
    if facts.certificate_info is not None and facts.certificate_info.is_expired(facts.now):
        errors.append(_("le certificat fourni est déjà expiré depuis le {value}").format(value=facts.certificate_info.not_after.isoformat()))
    return errors
