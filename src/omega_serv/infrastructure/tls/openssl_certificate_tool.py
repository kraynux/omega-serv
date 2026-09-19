"""Implementation reelle de CertificateToolPort via l'executable
`openssl` en subprocess (doc TLS §2 : "Appels OpenSSL, lecture X.509").
Perimetre 6a+6b : certificat auto-signe (RSA 2048/4096, ECDSA P-256/
P-384) et CA locale (creation, CSR, signature, revocation) - CSR pour
autorite externe, mTLS restent hors V1.

CA locale : jamais le systeme complet `openssl ca` + fichier de
configuration (dir/database/serial declares dans un openssl.cnf) - trop
lourd pour le besoin reel. A la place, un flux `openssl req -x509`
(creation CA) + `openssl x509 -req -CA/-CAkey/-CAserial` (signature,
approche moderne sans openssl.cnf) avec un suivi serial.txt/index.txt
tenu directement par ce module en Python, format proche mais simplifie
de celui d'openssl (colonnes : statut, expiration, serie, sujet) -
suffisant pour "lister/revoquer un certificat signe" (doc TLS §7.2/§7.3),
jamais une vraie distribution CRL.

Toutes les invocations passent par ProcessRunnerPort (jamais
`subprocess` directement ici non plus - seul `subprocess_runner.py`
touche `subprocess`, ce module ne connait que le port)."""
from __future__ import annotations

import hashlib
import re
from datetime import datetime, timezone
from pathlib import Path

from omega_serv.domain.security.tls.entities import (
    CaParams,
    CertificateInfo,
    CsrParams,
    SelfSignedCertParams,
)
from omega_serv.domain.security.tls.exceptions import CertificateToolError
from omega_serv.ports.process_runner_port import ProcessRunnerPort

_KEY_TYPE_ARGS: dict[str, tuple[str, ...]] = {
    "rsa2048": ("-newkey", "rsa:2048"),
    "rsa4096": ("-newkey", "rsa:4096"),
    "ecdsa-p256": ("-newkey", "ec", "-pkeyopt", "ec_paramgen_curve:prime256v1"),
    "ecdsa-p384": ("-newkey", "ec", "-pkeyopt", "ec_paramgen_curve:secp384r1"),
}

_SUBJECT_FIELDS: tuple[tuple[str, str], ...] = (
    ("common_name", "CN"),
    ("organization", "O"),
    ("organizational_unit", "OU"),
    ("city", "L"),
    ("region", "ST"),
    ("country", "C"),
)


def _build_subject(params: SelfSignedCertParams | CaParams | CsrParams) -> str:
    parts = []
    for field_name, dn_key in _SUBJECT_FIELDS:
        value = getattr(params, field_name)
        if value:
            parts.append(f"{dn_key}={value}")
    return "/" + "/".join(parts)


def _build_san(params: SelfSignedCertParams | CsrParams) -> str:
    entries = [f"DNS:{d}" for d in params.san_dns] + [f"IP:{ip}" for ip in params.san_ip]
    return "subjectAltName=" + ",".join(entries)


class OpensslCertificateTool:
    def __init__(self, process_runner: ProcessRunnerPort):
        self._runner = process_runner

    def generate_self_signed(self, params: SelfSignedCertParams, key_path: Path, cert_path: Path) -> None:
        key_path.parent.mkdir(parents=True, exist_ok=True)
        cert_path.parent.mkdir(parents=True, exist_ok=True)

        args = [
            "openssl", "req", "-x509", "-sha256",
            "-days", str(params.validity_days),
            *_KEY_TYPE_ARGS[params.key_type],
            "-keyout", str(key_path),
            "-out", str(cert_path),
            "-subj", _build_subject(params),
            "-addext", _build_san(params),
        ]
        if params.key_password:
            args += ["-passout", f"pass:{params.key_password}"]
        else:
            args += ["-nodes"]

        result = self._runner.run(args, timeout=60)
        if not result.ok:
            raise CertificateToolError(f"echec de generation du certificat auto-signe : {result.stderr.strip()}")

    def inspect_certificate(self, cert_path: Path) -> CertificateInfo:
        result = self._runner.run(
            ["openssl", "x509", "-in", str(cert_path), "-noout", "-subject", "-issuer", "-startdate", "-enddate", "-text"],
            timeout=15,
        )
        if not result.ok:
            raise CertificateToolError(f"echec de lecture du certificat {cert_path} : {result.stderr.strip()}")

        return _parse_certificate_text(result.stdout)

    def keys_match(self, key_path: Path, cert_path: Path) -> bool:
        key_result = self._runner.run(["openssl", "pkey", "-in", str(key_path), "-pubout"], timeout=15)
        if not key_result.ok:
            raise CertificateToolError(f"echec de lecture de la cle privee {key_path} : {key_result.stderr.strip()}")

        cert_result = self._runner.run(["openssl", "x509", "-in", str(cert_path), "-pubkey", "-noout"], timeout=15)
        if not cert_result.ok:
            raise CertificateToolError(f"echec de lecture du certificat {cert_path} : {cert_result.stderr.strip()}")

        key_digest = hashlib.sha256(key_result.stdout.encode("ascii")).hexdigest()
        cert_digest = hashlib.sha256(cert_result.stdout.encode("ascii")).hexdigest()
        return key_digest == cert_digest

    def generate_ca(
        self, params: CaParams, key_path: Path, cert_path: Path, serial_path: Path, index_path: Path
    ) -> None:
        key_path.parent.mkdir(parents=True, exist_ok=True)
        cert_path.parent.mkdir(parents=True, exist_ok=True)
        serial_path.parent.mkdir(parents=True, exist_ok=True)
        index_path.parent.mkdir(parents=True, exist_ok=True)

        args = [
            "openssl", "req", "-x509", "-sha256",
            "-days", str(params.validity_days),
            *_KEY_TYPE_ARGS[params.key_type],
            "-keyout", str(key_path),
            "-out", str(cert_path),
            "-subj", _build_subject(params),
            "-passout", f"pass:{params.key_password}",
            "-addext", "basicConstraints=critical,CA:true",
            "-addext", "keyUsage=critical,keyCertSign,cRLSign",
        ]
        result = self._runner.run(args, timeout=120)
        if not result.ok:
            raise CertificateToolError(f"echec de generation de la CA locale : {result.stderr.strip()}")

        serial_path.write_text("1000\n")
        index_path.write_text("")

    def generate_csr(self, params: CsrParams, key_path: Path, csr_path: Path) -> None:
        key_path.parent.mkdir(parents=True, exist_ok=True)
        csr_path.parent.mkdir(parents=True, exist_ok=True)

        args = [
            "openssl", "req", "-new", "-nodes",
            *_KEY_TYPE_ARGS[params.key_type],
            "-keyout", str(key_path),
            "-out", str(csr_path),
            "-subj", _build_subject(params),
            "-addext", _build_san(params),
        ]
        result = self._runner.run(args, timeout=60)
        if not result.ok:
            raise CertificateToolError(f"echec de generation de la CSR : {result.stderr.strip()}")

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
        out_cert_path.parent.mkdir(parents=True, exist_ok=True)

        ext_file = out_cert_path.with_suffix(".ext.cnf")
        ext_file.write_text("basicConstraints=CA:FALSE\nextendedKeyUsage=serverAuth\n")
        try:
            args = [
                "openssl", "x509", "-req", "-sha256",
                "-in", str(csr_path),
                "-CA", str(ca_cert_path),
                "-CAkey", str(ca_key_path),
                "-passin", f"pass:{ca_key_password}",
                "-CAserial", str(serial_path),
                "-copy_extensions", "copy",
                "-extfile", str(ext_file),
                "-days", str(validity_days),
                "-out", str(out_cert_path),
            ]
            result = self._runner.run(args, timeout=60)
        finally:
            ext_file.unlink(missing_ok=True)
        if not result.ok:
            raise CertificateToolError(f"echec de signature de la CSR : {result.stderr.strip()}")

        self._append_index_entry(index_path, out_cert_path)

    def build_fullchain(self, cert_path: Path, ca_cert_path: Path, fullchain_path: Path) -> None:
        fullchain_path.parent.mkdir(parents=True, exist_ok=True)
        fullchain_path.write_text(cert_path.read_text() + ca_cert_path.read_text())

    def revoke_certificate(
        self, cert_path: Path, ca_key_path: Path, ca_cert_path: Path, ca_key_password: str, index_path: Path
    ) -> None:
        verify_result = self._runner.run(
            ["openssl", "verify", "-CAfile", str(ca_cert_path), str(cert_path)], timeout=15
        )
        if not verify_result.ok:
            raise CertificateToolError(
                f"le certificat {cert_path} n'est pas signe par cette CA, revocation refusee : "
                f"{verify_result.stderr.strip()}"
            )
        serial = self._read_serial(cert_path)
        if not index_path.exists():
            raise CertificateToolError(f"index de la CA introuvable : {index_path}")

        now = datetime.now(timezone.utc).strftime("%y%m%d%H%M%SZ")
        lines = index_path.read_text().splitlines()
        updated = []
        found = False
        for line in lines:
            fields = line.split("\t")
            if len(fields) >= 4 and fields[3] == serial and fields[0] == "V":
                fields[0] = "R"
                fields[2] = now
                updated.append("\t".join(fields))
                found = True
            else:
                updated.append(line)
        if not found:
            raise CertificateToolError(f"aucune entree valide pour le numero de serie {serial} dans {index_path}")
        index_path.write_text("\n".join(updated) + "\n")

    def _read_serial(self, cert_path: Path) -> str:
        result = self._runner.run(["openssl", "x509", "-in", str(cert_path), "-noout", "-serial"], timeout=15)
        if not result.ok:
            raise CertificateToolError(f"echec de lecture du certificat {cert_path} : {result.stderr.strip()}")
        return result.stdout.strip().removeprefix("serial=")

    def _append_index_entry(self, index_path: Path, cert_path: Path) -> None:
        info = self.inspect_certificate(cert_path)
        expiry = info.not_after.strftime("%y%m%d%H%M%SZ")
        serial = self._read_serial(cert_path)
        line = f"V\t{expiry}\t\t{serial}\t{info.subject}\n"
        with index_path.open("a") as f:
            f.write(line)


def _parse_openssl_date(raw: str) -> datetime:
    return datetime.strptime(raw.strip().removesuffix(" GMT"), "%b %d %H:%M:%S %Y").replace(tzinfo=timezone.utc)


def _parse_certificate_text(text: str) -> CertificateInfo:
    subject_match = re.search(r"^subject=(.+)$", text, re.MULTILINE)
    issuer_match = re.search(r"^issuer=(.+)$", text, re.MULTILINE)
    not_before_match = re.search(r"^notBefore=(.+)$", text, re.MULTILINE)
    not_after_match = re.search(r"^notAfter=(.+)$", text, re.MULTILINE)
    if not (subject_match and issuer_match and not_before_match and not_after_match):
        raise CertificateToolError("sortie openssl inattendue : champs subject/issuer/dates introuvables")

    san_match = re.search(r"X509v3 Subject Alternative Name:\s*\n\s*(.+)", text)
    san_dns: list[str] = []
    san_ip: list[str] = []
    if san_match:
        for entry in san_match.group(1).split(", "):
            entry = entry.strip()
            if entry.startswith("DNS:"):
                san_dns.append(entry.removeprefix("DNS:"))
            elif entry.startswith("IP Address:"):
                san_ip.append(entry.removeprefix("IP Address:"))

    key_algo_match = re.search(r"Public Key Algorithm:\s*(\S+)", text)
    key_bits_match = re.search(r"Public-Key:\s*\((\d+)\s*bit\)", text)
    sig_algo_match = re.search(r"Signature Algorithm:\s*(\S+)", text)

    return CertificateInfo(
        subject=subject_match.group(1).strip(),
        issuer=issuer_match.group(1).strip(),
        not_before=_parse_openssl_date(not_before_match.group(1)),
        not_after=_parse_openssl_date(not_after_match.group(1)),
        san_dns=tuple(san_dns),
        san_ip=tuple(san_ip),
        key_type=key_algo_match.group(1) if key_algo_match else "",
        key_bits=int(key_bits_match.group(1)) if key_bits_match else None,
        signature_algorithm=sig_algo_match.group(1) if sig_algo_match else "",
    )
