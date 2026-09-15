# Copyright (c) 2026 kraynux - kraynux@proton.me - Licence MIT (voir fichier LICENSE)
"""Entites pures TLS (OMEGA-SERV_TLS_CERTIFICATS.md §2 : "domain/ :
Entites pures : CertificateInfo, TlsConfiguration, CertificateStatus,
regles de coherence TLS/HSTS"). Perimetre verrouille (6a+6b, voir
OMEGA-SERV_PLAN_DEVELOPPEMENT.md §3 Phase 6) : certificat auto-signe et
CA locale - CSR pour autorite externe, mTLS (6c), OCSP/ACME (6d)
restent hors perimetre V1."""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Literal

KeyType = Literal["rsa2048", "rsa4096", "ecdsa-p256", "ecdsa-p384"]
VALID_KEY_TYPES: frozenset[str] = frozenset({"rsa2048", "rsa4096", "ecdsa-p256", "ecdsa-p384"})


@dataclass(frozen=True)
class SelfSignedCertParams:
    """Parametres d'un certificat auto-signe (doc TLS §6.2) - le CN/SAN
    sont obligatoires, jamais devines : "les SAN sont obligatoires dans
    les usages modernes, le CN seul ne doit pas etre considere comme
    suffisant" (doc TLS §6.2)."""
    common_name: str
    san_dns: tuple[str, ...] = ()
    san_ip: tuple[str, ...] = ()
    organization: str = "OMEGA-SERV"
    organizational_unit: str = ""
    city: str = ""
    region: str = ""
    country: str = ""
    validity_days: int = 365
    key_type: KeyType = "rsa2048"
    key_password: str | None = None


@dataclass(frozen=True)
class CaParams:
    """Parametres de creation d'une autorite de certification locale
    (doc TLS §7.3 etapes 1-4). Validite longue par defaut (5-10 ans,
    §7.1) et passphrase de cle **obligatoire** (§7.2 : "l'element le
    plus sensible... doit etre chiffree par passphrase si possible") -
    seule differences reelles avec SelfSignedCertParams, san_dns/san_ip
    n'ont pas de sens pour un certificat racine de CA."""
    common_name: str
    organization: str = "OMEGA-SERV"
    organizational_unit: str = ""
    city: str = ""
    region: str = ""
    country: str = ""
    validity_days: int = 3650
    key_type: KeyType = "rsa4096"
    key_password: str = ""


@dataclass(frozen=True)
class CsrParams:
    """Parametres d'une demande de signature de certificat (CSR, doc TLS
    §7.3 etape 6) - meme forme que SelfSignedCertParams sans validity_days
    ni key_password (la CSR n'est pas elle-meme un certificat signe, sa
    duree de validite est decidee au moment de la signature)."""
    common_name: str
    san_dns: tuple[str, ...] = ()
    san_ip: tuple[str, ...] = ()
    organization: str = "OMEGA-SERV"
    organizational_unit: str = ""
    city: str = ""
    region: str = ""
    country: str = ""
    key_type: KeyType = "rsa2048"


@dataclass(frozen=True)
class CertificateInfo:
    """Resultat de l'inspection d'un certificat X.509 deja sur disque
    (doc TLS §10, "Verification des certificats"). Construit par
    infrastructure/tls/ (parsing openssl), jamais par du code domain -
    ce module ne fait que representer la donnee et raisonner dessus."""
    subject: str
    issuer: str
    not_before: datetime
    not_after: datetime
    san_dns: tuple[str, ...] = field(default_factory=tuple)
    san_ip: tuple[str, ...] = field(default_factory=tuple)
    key_type: str = ""
    key_bits: int | None = None
    signature_algorithm: str = ""

    @property
    def is_self_signed(self) -> bool:
        return self.subject == self.issuer

    def days_remaining(self, now: datetime) -> int:
        return (self.not_after - now).days

    def is_expired(self, now: datetime) -> bool:
        return now >= self.not_after
