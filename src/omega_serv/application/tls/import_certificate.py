"""Cas d'usage "importer un certificat deja emis ailleurs" (doc TLS §9,
documente depuis le debut du perimetre TLS mais jamais implemente -
comble ce trou independamment de toute source particuliere : CA
d'entreprise, certificat achete, ou - premier vrai consommateur, voir
OMEGA-SERV_PLAN-DETAILLE_TLS_AUTO.md - sortie de Certbot copiee par un
hook de renouvellement).

Meme structure que generate_self_signed.py : sauvegarde les fichiers
CIBLES existants avant remplacement (doc TLS §9.2), positionne les
permissions (0600 cle / 0644 certificat, doc TLS §4.1), jamais une
ecriture sans validation prealable (doc TLS §9.1)."""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from omega_serv.domain.security.tls.validation import (
    CertificateImportFacts,
    validate_certificate_import,
)
from omega_serv.ports.certificate_tool_port import CertificateToolPort
from omega_serv.ports.clock_port import ClockPort
from omega_serv.ports.filesystem_port import FilesystemPort


@dataclass(frozen=True)
class ImportCertificateResult:
    success: bool
    message: str


def import_certificate(
    source_key_path: Path,
    source_cert_path: Path,
    dest_key_path: Path,
    dest_cert_path: Path,
    tool: CertificateToolPort,
    filesystem: FilesystemPort,
    clock: ClockPort,
    backups_dir: Path,
    source_chain_path: Path | None = None,
) -> ImportCertificateResult:
    """`source_chain_path` (intermediaire separe, cas d'une autorite qui
    ne fournit pas deja un fullchain pret a l'emploi - PAS le cas
    Certbot, dont `fullchain.pem` est deja complet, passe directement en
    `source_cert_path`) : jamais copie a part - `ssl_context_builder.py::
    build_ssl_context` ne charge qu'UN SEUL fichier de certificat
    (`ssl.SSLContext.load_cert_chain`), un fichier de chaine isole ne
    serait lu par rien. Concatene donc via `tool.build_fullchain()` (deja
    utilise doc TLS §7.3 etape 8) directement a `dest_cert_path`."""
    source_key_exists = filesystem.exists(source_key_path)
    source_cert_exists = filesystem.exists(source_cert_path)
    source_chain_exists = source_chain_path is not None and filesystem.exists(source_chain_path)

    keys_match = (
        tool.keys_match(source_key_path, source_cert_path)
        if source_key_exists and source_cert_exists
        else None
    )
    certificate_info = tool.inspect_certificate(source_cert_path) if source_cert_exists else None

    facts = CertificateImportFacts(
        source_key_exists=source_key_exists,
        source_cert_exists=source_cert_exists,
        source_chain_path_given=source_chain_path is not None,
        source_chain_exists=source_chain_exists,
        keys_match=keys_match,
        certificate_info=certificate_info,
        now=clock.now(),
    )
    errors = validate_certificate_import(facts)
    if errors:
        return ImportCertificateResult(False, "; ".join(errors))

    existing_targets = [p for p in (dest_key_path, dest_cert_path) if filesystem.exists(p)]
    if existing_targets:
        backup_dir = backups_dir / clock.now().strftime("%Y%m%d-%H%M%S")
        for target in existing_targets:
            filesystem.copy_file(target, backup_dir / target.name)

    filesystem.copy_file(source_key_path, dest_key_path)
    if source_chain_path is not None:
        tool.build_fullchain(source_cert_path, source_chain_path, dest_cert_path)
    else:
        filesystem.copy_file(source_cert_path, dest_cert_path)
    filesystem.set_file_mode(dest_key_path, 0o600)
    filesystem.set_file_mode(dest_cert_path, 0o644)

    return ImportCertificateResult(
        True, f"Certificat importe : {dest_cert_path} (cle : {dest_key_path}, mode 0600)",
    )
