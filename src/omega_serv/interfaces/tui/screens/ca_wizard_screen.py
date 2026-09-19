"""Assistant CA locale (plan interface §7.3, TLS 6b) - enchaine
`certs generate-ca` -> `certs generate-csr` -> `certs sign-csr`, meme
sequence que la doc TLS §7.3/§7.4. La passphrase de la CA est ressaisie
a l'etape de signature (jamais conservee en memoire entre deux ecrans
distincts) - meme discipline que la CLI (`sign-csr --password` separe
de `generate-ca --password`). Chemins fixes de la CA
(`secure/certificates/ca/root-ca.{key,pem}`, `serial.txt`, `index.txt`)
identiques a la convention deja etablie cote CLI (cmd_certs_generate_ca)."""
from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING, cast

from textual.app import ComposeResult
from textual.containers import Container, Horizontal, VerticalScroll
from textual.widgets import Button, Footer, Header, Static

from omega_serv.application.config.load_config import load_config
from omega_serv.application.tls.generate_ca_certificate import generate_ca_certificate
from omega_serv.application.tls.generate_certificate_signing_request import (
    generate_certificate_signing_request,
)
from omega_serv.application.tls.sign_certificate_signing_request import (
    sign_certificate_signing_request,
)
from omega_serv.domain.security.tls.entities import VALID_KEY_TYPES, CaParams, CsrParams, KeyType
from omega_serv.domain.security.tls.exceptions import CertificateToolError
from omega_serv.interfaces.tui.screens._base import OmegaScreen
from omega_serv.interfaces.tui.screens.dynamic_form_screen import DynamicFormScreen

if TYPE_CHECKING:
    from collections.abc import Callable

    from omega_serv.application.tls.generate_ca_certificate import GenerateCaResult
    from omega_serv.application.tls.generate_certificate_signing_request import GenerateCsrResult
    from omega_serv.application.tls.sign_certificate_signing_request import SignCsrResult
    from omega_serv.bootstrap.container import DependencyContainer
    from omega_serv.ports.certificate_tool_port import CertificateToolPort


class CaWizardScreen(OmegaScreen):
    def __init__(self, *, container: DependencyContainer) -> None:
        super().__init__()
        self._container = container
        self._log: list[str] = []
        self._csr_path: str = ""

    def compose(self) -> ComposeResult:
        yield Header()
        with VerticalScroll(classes="omega-panel"):
            yield Static("ASSISTANT CA LOCALE", classes="omega-title")
            yield Static(
                "Enchaine generer la CA -> generer une CSR pour ce serveur -> "
                "signer la CSR avec la CA. Chaque etape demande confirmation.",
                classes="omega-hint",
            )
            yield Static("", id="wizard-log")
            with Horizontal(classes="omega-actions"):
                with Container(classes="omega-btn-frame"):
                    yield Button("1. Generer la CA", id="step-ca", variant="primary")
                with Container(classes="omega-btn-frame"):
                    yield Button("2. Generer la CSR", id="step-csr")
                with Container(classes="omega-btn-frame"):
                    yield Button("3. Signer la CSR", id="step-sign")
                with Container(classes="omega-btn-frame"):
                    yield Button("Retour", id="back")
        yield Footer()

    def _ca_dir(self) -> Path:
        return self._container.project_root / "secure" / "certificates" / "ca"

    def _append_log(self, line: str) -> None:
        self._log.append(line)
        self.query_one("#wizard-log", Static).update("\n".join(self._log))

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "back":
            self.dismiss()
            return
        if event.button.id == "step-ca":
            self.app.push_screen(
                DynamicFormScreen(
                    title="ETAPE 1 : GENERER LA CA",
                    fields=[
                        ("cn", "Nom commun (CN)", "OMEGA-SERV Root CA"),
                        ("org", "Organisation", "OMEGA-SERV"),
                        ("ou", "Unite organisationnelle", ""),
                        ("city", "Ville", ""),
                        ("region", "Region", ""),
                        ("country", "Pays", ""),
                        ("days", "Validite en jours", "3650"),
                        ("key_type", f"Type de cle ({'/'.join(sorted(VALID_KEY_TYPES))})", "rsa4096"),
                        ("password", "Passphrase de la cle CA (obligatoire)", ""),
                        ("password_confirm", "Confirmer la passphrase", ""),
                    ],
                    password_fields=frozenset({"password", "password_confirm"}),
                ),
                self._do_generate_ca,
            )
            return
        if event.button.id == "step-csr":
            self.app.push_screen(
                DynamicFormScreen(
                    title="ETAPE 2 : GENERER LA CSR DU SERVEUR",
                    fields=[
                        ("cn", "Nom commun (CN, ex: nom d'hote du serveur)", ""),
                        ("san_dns", "SAN DNS (separes par des virgules)", ""),
                        ("san_ip", "SAN IP (separees par des virgules)", ""),
                        ("org", "Organisation", "OMEGA-SERV"),
                        ("ou", "Unite organisationnelle", ""),
                        ("city", "Ville", ""),
                        ("region", "Region", ""),
                        ("country", "Pays", ""),
                        ("key_type", f"Type de cle ({'/'.join(sorted(VALID_KEY_TYPES))})", "rsa2048"),
                    ],
                ),
                self._do_generate_csr,
            )
            return
        if event.button.id == "step-sign":
            self.app.push_screen(
                DynamicFormScreen(
                    title="ETAPE 3 : SIGNER LA CSR",
                    fields=[
                        ("csr_path", "Chemin de la CSR a signer", self._csr_path),
                        ("password", "Passphrase de la cle CA", ""),
                        ("days", "Validite du certificat signe en jours", "365"),
                    ],
                    password_fields=frozenset({"password"}),
                ),
                self._do_sign_csr,
            )

    def _do_generate_ca(self, values: dict[str, str] | None) -> None:
        if values is None:
            return
        if values["password"] != values["password_confirm"]:
            self._append_log("Erreur : les deux saisies de passphrase ne correspondent pas.")
            return
        if not values["password"]:
            self._append_log("Erreur : la passphrase de la cle CA est obligatoire.")
            return
        key_type_text = values["key_type"].strip()
        if key_type_text not in VALID_KEY_TYPES:
            self._append_log(f"Erreur : type de cle invalide : {key_type_text!r}")
            return
        try:
            days = int(values["days"])
        except ValueError:
            self._append_log(f"Erreur : validite invalide : {values['days']!r}")
            return
        factory = self._container.certificate_tool_factory
        if factory is None:
            self._append_log("Generation indisponible dans cet environnement.")
            return

        params = CaParams(
            common_name=values["cn"], organization=values["org"], organizational_unit=values["ou"],
            city=values["city"], region=values["region"], country=values["country"],
            validity_days=days, key_type=cast(KeyType, key_type_text), key_password=values["password"],
        )
        ca_dir = self._ca_dir()
        backups_dir = self._container.project_root / "var" / "backups" / "certificates"
        self._append_log("Generation de la CA en cours...")
        self.query_one("#step-ca", Button).disabled = True
        self.run_worker(
            lambda: self._generate_ca_in_thread(params, ca_dir, backups_dir, factory),
            thread=True, exclusive=True,
        )

    def _generate_ca_in_thread(
        self, params: CaParams, ca_dir: Path, backups_dir: Path, factory: Callable[[], CertificateToolPort],
    ) -> None:
        try:
            result = generate_ca_certificate(
                params, ca_dir / "root-ca.key", ca_dir / "root-ca.pem", ca_dir / "serial.txt", ca_dir / "index.txt",
                factory(), self._container.filesystem, self._container.clock, backups_dir,
            )
        except CertificateToolError as exc:
            self.app.call_from_thread(self._finish_generate_ca, None, str(exc), ca_dir)
            return
        self.app.call_from_thread(self._finish_generate_ca, result, None, ca_dir)

    def _finish_generate_ca(self, result: GenerateCaResult | None, error: str | None, ca_dir: Path) -> None:
        self.query_one("#step-ca", Button).disabled = False
        if error is not None:
            self._append_log(f"Erreur : {error}")
            return
        assert result is not None  # garanti par construction : error XOR result
        self._append_log(result.message)
        if result.success:
            self._append_log(f"Importez {ca_dir / 'root-ca.pem'} dans le magasin de confiance des clients (doc TLS §7.4).")

    def _do_generate_csr(self, values: dict[str, str] | None) -> None:
        if values is None:
            return
        key_type_text = values["key_type"].strip()
        if key_type_text not in VALID_KEY_TYPES:
            self._append_log(f"Erreur : type de cle invalide : {key_type_text!r}")
            return
        factory = self._container.certificate_tool_factory
        load_result = load_config(self._container.configuration, self._container.config_file)
        if factory is None or not load_result.success or load_result.config is None:
            self._append_log("Generation indisponible (configuration ou outil manquant).")
            return

        params = CsrParams(
            common_name=values["cn"],
            san_dns=tuple(i.strip() for i in values["san_dns"].split(",") if i.strip()),
            san_ip=tuple(i.strip() for i in values["san_ip"].split(",") if i.strip()),
            organization=values["org"], organizational_unit=values["ou"],
            city=values["city"], region=values["region"], country=values["country"],
            key_type=cast(KeyType, key_type_text),
        )
        key_path = self._container.project_root / load_result.config.tls.private_key_path
        csr_path = key_path.with_suffix(".csr")
        backups_dir = self._container.project_root / "var" / "backups" / "certificates"
        self._append_log("Generation de la CSR en cours...")
        self.query_one("#step-csr", Button).disabled = True
        self.run_worker(
            lambda: self._generate_csr_in_thread(params, key_path, csr_path, backups_dir, factory),
            thread=True, exclusive=True,
        )

    def _generate_csr_in_thread(
        self, params: CsrParams, key_path: Path, csr_path: Path, backups_dir: Path,
        factory: Callable[[], CertificateToolPort],
    ) -> None:
        try:
            result = generate_certificate_signing_request(
                params, key_path, csr_path, factory(), self._container.filesystem, self._container.clock, backups_dir,
            )
        except CertificateToolError as exc:
            self.app.call_from_thread(self._finish_generate_csr, None, str(exc), csr_path)
            return
        self.app.call_from_thread(self._finish_generate_csr, result, None, csr_path)

    def _finish_generate_csr(self, result: GenerateCsrResult | None, error: str | None, csr_path: Path) -> None:
        self.query_one("#step-csr", Button).disabled = False
        if error is not None:
            self._append_log(f"Erreur : {error}")
            return
        assert result is not None  # garanti par construction : error XOR result
        self._append_log(result.message)
        if result.success:
            self._csr_path = str(csr_path)

    def _do_sign_csr(self, values: dict[str, str] | None) -> None:
        if values is None:
            return
        try:
            days = int(values["days"])
        except ValueError:
            self._append_log(f"Erreur : validite invalide : {values['days']!r}")
            return
        factory = self._container.certificate_tool_factory
        load_result = load_config(self._container.configuration, self._container.config_file)
        if factory is None or not load_result.success or load_result.config is None:
            self._append_log("Signature indisponible (configuration ou outil manquant).")
            return

        ca_dir = self._ca_dir()
        cert_path = self._container.project_root / load_result.config.tls.certificate_path
        chain_relative = load_result.config.tls.chain_path or "secure/certificates/server/fullchain.pem"
        fullchain_path = self._container.project_root / chain_relative
        backups_dir = self._container.project_root / "var" / "backups" / "certificates"
        tls_enabled = load_result.config.tls.enabled
        self._append_log("Signature de la CSR en cours...")
        self.query_one("#step-sign", Button).disabled = True
        self.run_worker(
            lambda: self._sign_csr_in_thread(
                Path(values["csr_path"]), ca_dir, values["password"], days, cert_path,
                fullchain_path, backups_dir, factory, tls_enabled,
            ),
            thread=True, exclusive=True,
        )

    def _sign_csr_in_thread(
        self, csr_path: Path, ca_dir: Path, password: str, days: int, cert_path: Path,
        fullchain_path: Path, backups_dir: Path, factory: Callable[[], CertificateToolPort], tls_enabled: bool,
    ) -> None:
        try:
            result = sign_certificate_signing_request(
                csr_path, ca_dir / "root-ca.key", ca_dir / "root-ca.pem", password,
                ca_dir / "serial.txt", ca_dir / "index.txt", days, cert_path,
                factory(), self._container.filesystem, self._container.clock, backups_dir,
                out_fullchain_path=fullchain_path,
            )
        except CertificateToolError as exc:
            self.app.call_from_thread(self._finish_sign_csr, None, str(exc), ca_dir, tls_enabled)
            return
        self.app.call_from_thread(self._finish_sign_csr, result, None, ca_dir, tls_enabled)

    def _finish_sign_csr(
        self, result: SignCsrResult | None, error: str | None, ca_dir: Path, tls_enabled: bool,
    ) -> None:
        self.query_one("#step-sign", Button).disabled = False
        if error is not None:
            self._append_log(f"Erreur : {error}")
            return
        assert result is not None  # garanti par construction : error XOR result
        self._append_log(result.message)
        if result.success:
            self._append_log(
                f"Importez {ca_dir / 'root-ca.pem'} dans le magasin de confiance des clients (doc TLS §7.4)."
            )
            if tls_enabled:
                self._append_log(
                    "TLS est actif : REDEMARRAGE COMPLET necessaire pour que le serveur serve "
                    "ce nouveau certificat (le contexte SSL en memoire ne se recharge jamais tout seul)."
                )
