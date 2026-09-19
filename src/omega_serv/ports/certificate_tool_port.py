"""Contrat d'outillage certificat (doc TLS §2 : "ports/ :
CertificateToolPort"). Perimetre 6a+6b : generation auto-signee,
inspection, et CA locale (creation de CA, CSR, signature, revocation) -
CSR pour autorite externe, mTLS restent hors V1, voir
OMEGA-SERV_PLAN_DEVELOPPEMENT.md §3 Phase 6."""
from __future__ import annotations

from pathlib import Path
from typing import Protocol

from omega_serv.domain.security.tls.entities import (
    CaParams,
    CertificateInfo,
    CsrParams,
    SelfSignedCertParams,
)


class CertificateToolPort(Protocol):
    def generate_self_signed(self, params: SelfSignedCertParams, key_path: Path, cert_path: Path) -> None:
        ...

    def inspect_certificate(self, cert_path: Path) -> CertificateInfo:
        ...

    def keys_match(self, key_path: Path, cert_path: Path) -> bool:
        ...

    def generate_ca(
        self, params: CaParams, key_path: Path, cert_path: Path, serial_path: Path, index_path: Path
    ) -> None:
        """Cle+certificat racine auto-signes CA:true, et initialisation
        du suivi de serie/index (doc TLS §7.3 etapes 1-5)."""
        ...

    def generate_csr(self, params: CsrParams, key_path: Path, csr_path: Path) -> None:
        """Cle serveur + CSR (doc TLS §7.3 etape 6)."""
        ...

    def sign_csr(
        self,
        csr_path: Path,
        ca_key_path: Path,
        ca_cert_path: Path,
        ca_key_password: str,
        serial_path: Path,
        index_path: Path,
        validity_days: int,
        out_cert_path: Path,
    ) -> None:
        """Signe la CSR avec la CA locale, extension serverAuth (doc TLS
        §7.3 etape 7)."""
        ...

    def build_fullchain(self, cert_path: Path, ca_cert_path: Path, fullchain_path: Path) -> None:
        """Concatene certificat serveur + certificat CA (doc TLS §7.3
        etape 8, "fullchain.pem selon le besoin du runtime TLS")."""
        ...

    def revoke_certificate(
        self, cert_path: Path, ca_key_path: Path, ca_cert_path: Path, ca_key_password: str, index_path: Path
    ) -> None:
        """Marque le certificat comme revoque dans l'index de la CA
        (doc TLS §5, menu "Revoquer un certificat (CA locale)") - pas de
        distribution CRL complete en V1, seulement le suivi index.txt."""
        ...
