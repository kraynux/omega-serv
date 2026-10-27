"""Sous-ecran Resistance et limites (plan interface §7) - les 10 champs
entiers de ServerConfig lies aux limites/delais anti-abus (spec §9.2), plus
le nombre de workers du mode « boost » (OMEGA-SERV_ETUDE_MODE_BOOST.md) : sous
le champ, les chiffres REELS de la machine (decision utilisateur 2026-10-26 :
un nombre de workers doit correspondre a la machine ou omega-serv est installe)."""
from __future__ import annotations

from dataclasses import replace
from typing import TYPE_CHECKING

from textual.app import ComposeResult
from textual.containers import Container, Horizontal, Vertical
from textual.widgets import Button, Footer, Header, Input, Static

from omega_serv.application.config.load_config import load_config
from omega_serv.core.i18n import _
from omega_serv.core.platform_info import cpu_info
from omega_serv.domain.config.validation import validate_config
from omega_serv.domain.security.waf.shared_counters import boost_errors
from omega_serv.interfaces.tui.screens._base import OmegaScreen
from omega_serv.interfaces.tui.screens.restart_prompt import (
    notify_reload_required,
    notify_restart_required,
)

if TYPE_CHECKING:
    from omega_serv.bootstrap.container import DependencyContainer

_FIELDS: tuple[tuple[str, str], ...] = (
    ("max_connections", _("Connexions simultanées max (max_connections)")),
    ("max_request_size", _("Taille maximale de requête en octets (max_request_size)")),
    ("max_header_size", _("Taille maximale des en-têtes en octets (max_header_size)")),
    ("max_request_line_size", _("Taille maximale de la ligne de requête (max_request_line_size)")),
    ("read_timeout_seconds", _("Délai de lecture en secondes (read_timeout_seconds)")),
    ("write_timeout_seconds", _("Délai d'écriture en secondes (write_timeout_seconds)")),
    ("keepalive_timeout_seconds", _("Délai keep-alive en secondes (keepalive_timeout_seconds)")),
    ("max_keepalive_requests", _("Requêtes max par connexion keep-alive (max_keepalive_requests)")),
    ("listen_backlog", _("File d'attente d'écoute (listen_backlog)")),
    ("shutdown_grace_period_seconds", _("Délai de grâce à l'arrêt en secondes (shutdown_grace_period_seconds)")),
)


class LimitsScreen(OmegaScreen):
    def __init__(self, *, container: DependencyContainer) -> None:
        super().__init__()
        self._container = container

    def compose(self) -> ComposeResult:
        yield Header()
        with Vertical(classes="omega-form-panel"):
            yield Static(_("RÉSISTANCE ET LIMITES"), classes="omega-title")
            yield Static("", id="form-error", classes="omega-hint")
            for field_name, label in _FIELDS:
                yield Static(label, classes="omega-subtitle")
                yield Input(id=f"field-{field_name}")
            yield Static(_("Nombre de workers - mode boost (workers, 0 = automatique)"), classes="omega-subtitle")
            yield Input(id="field-workers")
            yield Static(self._machine_hint(), id="workers-hint", classes="omega-hint")
            with Horizontal(classes="omega-actions"):
                with Container(classes="omega-btn-frame"):
                    yield Button(_("Enregistrer"), id="save", variant="primary")
                with Container(classes="omega-btn-frame"):
                    yield Button(_("Retour"), id="back")
        yield Footer()

    def on_mount(self) -> None:
        result = load_config(self._container.configuration, self._container.config_file)
        if not result.success:
            self.query_one("#form-error", Static).update(
                _("Erreur de configuration : ") + "; ".join(result.errors)
            )
            self.query_one("#save", Button).disabled = True
            return
        assert result.config is not None
        server = result.config.server
        for field_name, _label in _FIELDS:
            self.query_one(f"#field-{field_name}", Input).value = str(getattr(server, field_name))
        self.query_one("#field-workers", Input).value = str(server.workers)

    @staticmethod
    def _machine_hint() -> str:
        cpu = cpu_info()
        quota = (
            _(" (quota de {quota:g} CPU)").format(quota=cpu.quota) if cpu.quota is not None else ""
        )
        return _(
            "Cette machine : {physical} cœur(s) physique(s), {logical} thread(s), {available} CPU "
            "disponible(s) pour omega-serv{quota}. Automatique (0) : {recommended} worker(s) ; "
            "maximum : {available}. Le nombre de workers doit correspondre à cette machine : au-delà, "
            "les processus se disputent le processeur. 1 = un seul processus (fonctionnement "
            "classique). Les compteurs de sécurité (rate limit, récidive) restent exacts quel que "
            "soit le nombre de workers ; un script magnet garde ses propres compteurs dans chaque "
            "worker. Tout changement exige un redémarrage complet."
        ).format(
            physical=cpu.physical, logical=cpu.logical, available=cpu.available, quota=quota,
            recommended=cpu.recommended_workers,
        )

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "back":
            self.dismiss()
            return
        if event.button.id == "save":
            self._save()

    def _save(self) -> None:
        error_widget = self.query_one("#form-error", Static)
        load_result = load_config(self._container.configuration, self._container.config_file)
        if not load_result.success:
            error_widget.update(_("Erreur de configuration : ") + "; ".join(load_result.errors))
            return
        assert load_result.config is not None

        values: dict[str, int] = {}
        for field_name, label in (*_FIELDS, ("workers", _("Nombre de workers"))):
            text = self.query_one(f"#field-{field_name}", Input).value.strip()
            try:
                values[field_name] = int(text)
            except ValueError:
                error_widget.update(_("Valeur invalide pour {label} (nombre entier attendu) : {text!r}").format(label=label, text=text))
                return

        new_server = replace(
            load_result.config.server,
            max_connections=values["max_connections"],
            max_request_size=values["max_request_size"],
            max_header_size=values["max_header_size"],
            max_request_line_size=values["max_request_line_size"],
            read_timeout_seconds=values["read_timeout_seconds"],
            write_timeout_seconds=values["write_timeout_seconds"],
            keepalive_timeout_seconds=values["keepalive_timeout_seconds"],
            max_keepalive_requests=values["max_keepalive_requests"],
            listen_backlog=values["listen_backlog"],
            shutdown_grace_period_seconds=values["shutdown_grace_period_seconds"],
            workers=values["workers"],
        )
        new_config = replace(load_result.config, server=new_server)

        available = cpu_info().available
        errors = validate_config(new_config) + boost_errors(new_config)
        if new_server.workers > available:
            errors.append(
                _("{workers} workers demandés, mais cette machine n'a que {available} CPU disponible(s) "
                "pour omega-serv").format(workers=new_server.workers, available=available)
            )
        if errors:
            error_widget.update(_("Erreur de validation :\n") + "\n".join(f"  - {e}" for e in errors))
            return

        self._container.configuration.save(self._container.config_file, new_config)
        error_widget.update("")
        if new_server.workers != load_result.config.server.workers:
            notify_restart_required(
                self, self._container,
                _("Enregistré - le nombre de workers ne change qu'au REDÉMARRAGE COMPLET du service."),
            )
        elif new_server.listen_backlog != load_result.config.server.listen_backlog:
            notify_restart_required(
                self, self._container,
                _("Enregistré - mais listen_backlog nécessite un REDÉMARRAGE COMPLET pour prendre "
                "effet (jamais un simple rechargement, le socket d'écoute n'est jamais retouché)."),
            )
        else:
            notify_reload_required(self, self._container, _("Limites enregistrées."))
