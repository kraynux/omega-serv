"""Sous-ecran Resistance et limites (plan interface §7) - les 10 champs
entiers de ServerConfig lies aux limites/delais anti-abus (spec §9.2), plus
le nombre de processus (`server.workers`, OMEGA-SERV_ETUDE_MODE_BOOST.md) : sous
le champ, les chiffres REELS de la machine (decision utilisateur 2026-10-26 :
un nombre de workers doit correspondre a la machine ou omega-serv est installe).

Plan moteur C++ §25 (decision utilisateur 2026-11-04) : plus de noms de niveaux. Le maximum depend du moteur choisi
dans « Configuration de base » et du processeur detecte (engine_levels.max_workers) ; l'ecran dit ce qui est
compatible, si augmenter apporte quelque chose sur CETTE machine, et refuse une valeur au-dela du maximum : on ne
laisse jamais croire a un reglage qui ne serait pas applique."""
from __future__ import annotations

from dataclasses import replace
from typing import TYPE_CHECKING

from textual.app import ComposeResult
from textual.containers import Container, Horizontal, Vertical
from textual.widgets import Button, Footer, Header, Input, Static

from omega_serv.application.config.load_config import load_config
from omega_serv.application.server.engine_levels import describe_run, max_workers
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
            yield Static(_("Nombre de processus (workers)"), classes="omega-subtitle")
            yield Input(id="field-workers")
            yield Static(self._machine_hint(), id="workers-hint", classes="omega-hint")
            yield Static("", id="workers-engine-hint", classes="omega-hint")
            yield Static("", id="workers-result", classes="omega-hint")
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
        # Moteur EFFECTIF prevu (un natif demande mais impossible tourne en Python : son maximum s'applique)
        self._engine = self._container.engine_status(result.config).forecast.effective
        self._security_active = any(result.config.option_enabled(name) for name in ("waf", "active_defense", "auth"))
        self._maximum = max_workers(self._engine, cpu_info().usable_cores)
        # Une valeur de fichier hors bornes (0 = ancien « automatique », config copiee) est montree telle quelle :
        # la ligne de resultat dit ce qui sera applique, l'enregistrement demande une valeur correcte.
        self.query_one("#field-workers", Input).value = str(server.workers)
        self.query_one("#workers-engine-hint", Static).update(self._engine_hint())
        self._refresh_result()

    def on_input_changed(self, event: Input.Changed) -> None:
        if event.input.id == "field-workers" and hasattr(self, "_engine"):
            self._refresh_result()

    def _workers_error(self, workers: int) -> str | None:
        if workers < 1:
            return _("Au moins 1 processus.")
        if workers > self._maximum:
            engine = _("moteur natif") if self._engine == "native" else _("moteur Python")
            return _("Trop élevé : {maximum} processus au maximum sur cette machine avec le {engine}.").format(
                maximum=self._maximum, engine=engine)
        return None

    def _refresh_result(self) -> None:
        result = self.query_one("#workers-result", Static)
        try:
            workers = int(self.query_one("#field-workers", Input).value.strip())
        except ValueError:
            result.update("")
            return
        error = self._workers_error(workers)
        if error:
            result.update(error)
            return
        lines = [_("Au prochain démarrage : {run}.").format(run=describe_run(self._engine, workers))]
        if self._engine == "native" and workers > 1 and not self._security_active:
            lines.append(_("Le 2e reste sans effet tant qu'aucun contrôle de sécurité (WAF, Active Defense, "
                           "authentification) n'est actif."))
        result.update(" ".join(lines))

    def _engine_hint(self) -> str:
        cores = cpu_info().usable_cores
        if self._engine != "native":
            return _(
                "Moteur Python (écran « Configuration de base ») : de 1 à {maximum} processus sur cette machine, un "
                "par cœur physique. Chaque processus sert les requêtes : en ajouter augmente le débit, jusqu'à ce "
                "nombre. Au-delà, les processus se disputeraient le processeur."
            ).format(maximum=self._maximum)
        if self._maximum > 1:
            return _(
                "Moteur natif (écran « Configuration de base ») : il utilise déjà tous les cœurs à lui seul. Les "
                "processus réglés ici font les contrôles de sécurité (WAF, Active Defense, authentification) : 1 ou "
                "2 sur cette machine. Ils ne reçoivent que les requêtes à vérifier : un 2e augmente le débit "
                "seulement quand beaucoup de requêtes passent par eux (magnet actif, attaque "
                "en cours)."
            )
        return _(
            "Moteur natif (écran « Configuration de base ») : il utilise déjà tous les cœurs à lui seul. Les "
            "processus réglés ici font les contrôles de sécurité : 1 seul sur cette machine ({cores} cœur(s) "
            "physique(s)). Un 2e n'apporterait rien, le processeur étant déjà occupé ; il faut au moins 4 cœurs "
            "physiques."
        ).format(cores=cores)

    @staticmethod
    def _machine_hint() -> str:
        cpu = cpu_info()
        quota = (
            _(" (quota de {quota:g} CPU)").format(quota=cpu.quota) if cpu.quota is not None else ""
        )
        return _(
            "Cette machine : {physical} cœur(s) physique(s), {logical} thread(s), {available} CPU "
            "disponible(s) pour omega-serv{quota}. Les compteurs de sécurité (rate limit, récidive) restent "
            "exacts quel que soit le nombre de processus ; un script magnet garde ses propres compteurs dans "
            "chaque processus. Tout changement exige un redémarrage complet."
        ).format(physical=cpu.physical, logical=cpu.logical, available=cpu.available, quota=quota)

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
        for field_name, label in (*_FIELDS, ("workers", _("Nombre de processus (workers)"))):
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

        errors = validate_config(new_config) + boost_errors(new_config)
        workers_error = self._workers_error(new_server.workers)
        if workers_error:
            errors.append(workers_error)
        if errors:
            error_widget.update(_("Erreur de validation :\n") + "\n".join(f"  - {e}" for e in errors))
            return

        self._container.configuration.save(self._container.config_file, new_config)
        error_widget.update("")
        if new_server.workers != load_result.config.server.workers:
            notify_restart_required(
                self, self._container,
                _("Enregistré - le nombre de processus ne change qu'au REDÉMARRAGE COMPLET du service."),
            )
        elif new_server.listen_backlog != load_result.config.server.listen_backlog:
            notify_restart_required(
                self, self._container,
                _("Enregistré - mais listen_backlog nécessite un REDÉMARRAGE COMPLET pour prendre "
                "effet (jamais un simple rechargement, le socket d'écoute n'est jamais retouché)."),
            )
        else:
            notify_reload_required(self, self._container, _("Limites enregistrées."))
