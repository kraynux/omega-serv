"""Sous-ecran Statut TLS (plan interface §7.3, `certs show`/`certs
check-expiry` - meme fonction sous-jacente cote CLI, `_cmd_certs_inspect`,
donc un seul ecran ici plutot que deux). Injecte via
container.certificate_tool_factory (bootstrap/container.py) : construire
un CertificateToolPort touche subprocess, interdit a interfaces.tui/."""
from __future__ import annotations

from typing import TYPE_CHECKING

from textual.app import ComposeResult
from textual.containers import Container, Horizontal, VerticalScroll
from textual.widgets import Button, Footer, Header, Static

from omega_serv.application.config.load_config import load_config
from omega_serv.application.tls.inspect_certificate import inspect_certificate_report
from omega_serv.core.i18n import _
from omega_serv.domain.security.tls.exceptions import CertificateToolError
from omega_serv.interfaces.tui.screens._base import OmegaScreen

if TYPE_CHECKING:
    from omega_serv.bootstrap.container import DependencyContainer


class TlsStatusScreen(OmegaScreen):
    def __init__(self, *, container: DependencyContainer) -> None:
        super().__init__()
        self._container = container

    def compose(self) -> ComposeResult:
        yield Header()
        with VerticalScroll(classes="omega-panel"):
            yield Static(_("STATUT TLS"), classes="omega-title")
            yield Static("", id="status-text")
            with Horizontal(classes="omega-actions"):
                with Container(classes="omega-btn-frame"):
                    yield Button(_("Rafraîchir"), id="refresh", variant="primary")
                with Container(classes="omega-btn-frame"):
                    yield Button(_("Retour"), id="back")
        yield Footer()

    def on_mount(self) -> None:
        self._refresh()

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "back":
            self.dismiss()
            return
        if event.button.id == "refresh":
            self._refresh()

    def _refresh(self) -> None:
        result_widget = self.query_one("#status-text", Static)
        load_result = load_config(self._container.configuration, self._container.config_file)
        if not load_result.success or load_result.config is None:
            result_widget.update(_("Erreur de configuration : ") + "; ".join(load_result.errors))
            return

        factory = self._container.certificate_tool_factory
        if factory is None:
            result_widget.update(_("Inspection indisponible dans cet environnement."))
            return

        cert_path = self._container.project_root / load_result.config.tls.certificate_path
        key_path = self._container.project_root / load_result.config.tls.private_key_path
        if not self._container.filesystem.exists(cert_path):
            result_widget.update(_("Aucun certificat trouvé : {cert_path}").format(cert_path=cert_path))
            return

        try:
            report = inspect_certificate_report(
                cert_path, key_path, factory(), self._container.filesystem, self._container.clock
            )
        except CertificateToolError as exc:
            result_widget.update(_("Erreur : {exc}").format(exc=exc))
            return

        info = report.info
        lines = [
            _("Sujet : {subject}").format(subject=info.subject),
            _("Émetteur : {issuer}").format(issuer=info.issuer),
            _("Début de validité : {value}").format(value=info.not_before.isoformat()),
            _("Fin de validité : {value}").format(value=info.not_after.isoformat()),
            _("Jours restants : {days_remaining}").format(days_remaining=report.days_remaining),
            _("Type de clé : {key_type} ({key_bits} bits)").format(key_type=info.key_type, key_bits=info.key_bits) if info.key_bits else _("Type de clé : {key_type}").format(key_type=info.key_type),
            _("Algorithme de signature : {signature_algorithm}").format(signature_algorithm=info.signature_algorithm),
        ]
        if info.san_dns or info.san_ip:
            lines.append(_("SAN :"))
            lines.extend(_("  - DNS:{dns}").format(dns=dns) for dns in info.san_dns)
            lines.extend(f"  - IP:{ip}" for ip in info.san_ip)
        lines.append("")
        lines.append(_("[{value}] Certificat {value2}").format(value=_('ERREUR') if report.is_expired else _('OK'), value2=_('expiré') if report.is_expired else _('non expiré')))
        if report.key_matches is not None:
            lines.append(_("[{value}] Clé privée {value2}").format(value=_('OK') if report.key_matches else _('ERREUR'), value2=_('correspondante') if report.key_matches else _('NE correspond PAS')))
        if report.key_mode is not None:
            strict = not (report.key_mode & 0o077)
            lines.append(_("[{value}] Permissions clé privée : {value2}").format(value=_('OK') if strict else _('ERREUR'), value2=oct(report.key_mode)))
        if info.is_self_signed:
            lines.append(_("[AVERTISSEMENT] Certificat auto-signé, non approuvé par défaut par les navigateurs"))
        if report.expiring_soon and not report.is_expired:
            lines.append(_("[AVERTISSEMENT] Certificat bientôt expiré ({days_remaining} jours restants)").format(days_remaining=report.days_remaining))
        result_widget.update("\n".join(lines))
