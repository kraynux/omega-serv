"""Alertes locales du panneau web (etude modules, module 1 ; decisions de l'auteur du 2026-11-17 : locales
seulement, aucun envoi). Ouvert depuis Instances -> Configuration distante -> Alertes : seuils de chaque regle (vide =
regle coupee), maintenance (aucune nouvelle alerte pendant 1 h ou 24 h) et alertes en cours. Les alertes sont evaluees
par le processus d'administration : il faut l'administration web active (en boucle locale suffit)."""
from __future__ import annotations

import time
from dataclasses import replace
from typing import TYPE_CHECKING

from textual.app import ComposeResult
from textual.containers import Container, Horizontal, VerticalScroll
from textual.widgets import Button, Footer, Header, Input, Static

from omega_serv.application.config.load_config import load_config
from omega_serv.core.i18n import _
from omega_serv.domain.admin_web.alerts import (
    RULES,
    RULES_BY_KEY,
    AlertBook,
    thresholds_from_settings,
)
from omega_serv.domain.admin_web.settings import OPTION_NAME
from omega_serv.domain.config.option import Option
from omega_serv.interfaces.tui.screens._base import OmegaScreen
from omega_serv.interfaces.tui.screens.restart_prompt import notify_reload_required

if TYPE_CHECKING:
    from omega_serv.bootstrap.container import DependencyContainer


def _number_text(value: float | None) -> str:
    return "" if value is None else f"{value:g}"


class AdminAlertsScreen(OmegaScreen):
    def __init__(self, *, container: DependencyContainer) -> None:
        super().__init__()
        self._container = container

    def compose(self) -> ComposeResult:
        yield Header()
        with VerticalScroll(classes="omega-panel"):
            yield Static(_("ALERTES DU PANNEAU WEB"), classes="omega-title")
            yield Static(_("Alertes locales : rien n'est envoyé hors de cette machine. Elles s'affichent dans le "
                           "panneau web (vue Alertes) et dans var/log/alertes.log. Évaluées par l'administration web, "
                           "qui doit être active (en boucle locale suffit) ; disque, mémoire, processeur, température "
                           "et batterie demandent aussi l'Historique."), classes="omega-hint")
            yield Static(_("En cours"), classes="omega-subtitle")
            yield Static("", id="alerts-active")
            yield Static(_("Maintenance"), classes="omega-subtitle")
            yield Static("", id="alerts-maintenance")
            with Horizontal(classes="omega-actions"):
                with Container(classes="omega-btn-frame"):
                    yield Button(_("Maintenance 1 h"), id="maintenance-1h")
                with Container(classes="omega-btn-frame"):
                    yield Button(_("Maintenance 24 h"), id="maintenance-24h")
                with Container(classes="omega-btn-frame"):
                    yield Button(_("Fin de maintenance"), id="maintenance-end")
            yield Static(_("Seuils"), classes="omega-subtitle")
            yield Static(_("Laisser vide pour couper une règle."), classes="omega-hint")
            for rule in RULES:
                yield Static(_("{label} ({low:g} à {high:g}{unit})").format(
                    label=_(rule.label), low=rule.low, high=rule.high, unit=f" {rule.unit}" if rule.unit else ""),
                    classes="omega-subtitle")
                yield Input(id=f"rule-{rule.key}")
            yield Static("", id="alerts-error", classes="omega-hint")
        with Horizontal(classes="omega-actions"):
            with Container(classes="omega-btn-frame"):
                yield Button(_("Enregistrer"), id="save", variant="primary")
            with Container(classes="omega-btn-frame"):
                yield Button(_("Retour"), id="back")
        yield Footer()

    def on_mount(self) -> None:
        config = self._config()
        option = config.options.get(OPTION_NAME) if config is not None else None
        thresholds = thresholds_from_settings(option.settings.get("alerts") if option is not None else None)
        for rule in RULES:
            self.query_one(f"#rule-{rule.key}", Input).value = _number_text(thresholds[rule.key])
        self._show()

    def _config(self):  # type: ignore[no-untyped-def]
        result = load_config(self._container.configuration, self._container.config_file)
        return result.config if result.success else None

    def _show(self) -> None:
        store = self._container.admin_alert_store()
        book = AlertBook.from_dict(store.load())
        lines = []
        for alert in sorted(book.active.values(), key=lambda a: a.opened_at):
            rule = RULES_BY_KEY.get(alert.rule)
            label = _(rule.label) if rule is not None else alert.rule
            since = time.strftime("%Y-%m-%d %H:%M", time.localtime(alert.opened_at))
            lines.append(f"✗ {label}" + (f" - {alert.subject}" if alert.subject else "")
                         + " " + _("(depuis {date})").format(date=since))
        self.query_one("#alerts-active", Static).update("\n".join(lines) or _("Aucune alerte en cours."))
        until = store.maintenance_until()
        text = (_("Maintenance jusqu'à {date} : aucune nouvelle alerte.").format(
            date=time.strftime("%Y-%m-%d %H:%M", time.localtime(until)))
                if until is not None and until > time.time() else _("Pas de maintenance en cours."))
        self.query_one("#alerts-maintenance", Static).update(text)

    def on_button_pressed(self, event: Button.Pressed) -> None:
        button = event.button.id
        store = self._container.admin_alert_store()
        if button == "back":
            self.dismiss()
        elif button in ("maintenance-1h", "maintenance-24h"):
            store.set_maintenance(time.time() + (3600 if button == "maintenance-1h" else 86400))
            self._show()
        elif button == "maintenance-end":
            store.set_maintenance(None)
            self._show()
        elif button == "save":
            self._save()

    def _save(self) -> None:
        error = self.query_one("#alerts-error", Static)
        values: dict[str, float | bool] = {}
        for rule in RULES:
            text = self.query_one(f"#rule-{rule.key}", Input).value.strip().replace(",", ".")
            if not text:
                values[rule.key] = False
                continue
            try:
                number = float(text)
            except ValueError:
                number = None
            if number is None or not rule.low <= number <= rule.high:
                error.update(_("{label} : seuil de {low:g} à {high:g}, ou vide pour couper la règle.").format(
                    label=_(rule.label), low=rule.low, high=rule.high))
                self.query_one(f"#rule-{rule.key}", Input).focus()
                return
            values[rule.key] = int(number) if number.is_integer() else number
        config = self._config()
        if config is None:
            error.update(_("Erreur de configuration - impossible d'enregistrer."))
            return
        existing = config.options.get(OPTION_NAME)
        settings = {**(existing.settings if existing is not None else {}), "alerts": values}
        option = Option(name=OPTION_NAME, enabled=existing.enabled if existing is not None else False,
                        settings=settings)
        self._container.configuration.save(self._container.config_file,
                                           replace(config, options={**config.options, OPTION_NAME: option}))
        error.update("")
        notify_reload_required(self, self._container, _("Alertes mises à jour."))
