"""Acces commun des 6 ecrans RIPOSTE (lot 5) a la configuration et a la base.

- La base est ouverte par la fabrique injectee (`container.riposte_store_factory`, jamais un import
  d'infrastructure ici) : jamais creee (elle appartient au processus RIPOSTE), une connexion par
  operation, fermee aussitot - jamais partagee entre le fil de l'interface et un travailleur.
- Les commandes (lever, oublier, relire la configuration...) sont DEPOSEES puis leur resultat est
  attendu hors du fil de l'interface (<= 3 s) ; processus arrete : l'ecran le dit, la commande attend
  son prochain demarrage (plan §3.7)."""
from __future__ import annotations

import time
from collections.abc import Callable, Iterator
from contextlib import contextmanager
from datetime import datetime
from typing import TYPE_CHECKING, Any

from rich.text import Text
from textual.widgets import Static

from omega_serv.application.config.load_config import load_config
from omega_serv.application.riposte.console import (
    Commands,
    database_path,
    finished_commands,
    process_running,
    riposte_enabled,
    submit_commands,
)
from omega_serv.application.services.resolve_current_service_name import (
    resolve_current_service_name,
)
from omega_serv.core.i18n import _
from omega_serv.interfaces.cli.riposte_text import command_result_text

if TYPE_CHECKING:
    from textual.app import App

    from omega_serv.bootstrap.container import DependencyContainer
    from omega_serv.domain.config.entities import OmegaServConfig
    from omega_serv.domain.security.riposte.actions import RiposteCommand
    from omega_serv.ports.riposte_store_port import RiposteStorePort

def show(widget: Static, text: str) -> None:
    """Texte de DONNEES (jamais interprete comme balisage : « [scan] » doit rester visible) ; un message vide
    ne laisse pas de trou dans l'ecran."""
    widget.update(Text(text))
    widget.display = bool(text)


def cell(text: str) -> Text:
    """Cellule de tableau en texte brut (memes raisons que `show`)."""
    return Text(text)


def local_time(moment: datetime, *, short: bool = False) -> str:
    """Heure locale de la machine (les dates sont stockees en UTC)."""
    return moment.astimezone().strftime("%m-%d %H:%M" if short else "%Y-%m-%d %H:%M")


WAIT_SECONDS = 3.0
_POLL_SECONDS = 0.2


class StoreUnavailable(Exception):
    """Base absente ou illisible : le message (traduit) est pret a afficher."""


class RiposteAccessMixin:
    """A melanger avec `OmegaScreen` : suppose `self._container` et `self.app`."""

    _container: DependencyContainer
    app: App[Any]

    def _service_name(self) -> str:
        """Nom du service de CETTE instance : prefixe des jails reseau (`<service>-riposte-<duree>`)."""
        container = self._container
        return resolve_current_service_name(container.instance_registry, container.filesystem,
                                            container.settings_store, container.project_root)

    def _load_riposte_config(self) -> OmegaServConfig | None:
        result = load_config(self._container.configuration, self._container.config_file)
        if not result.success or result.config is None:
            self.app.notify(_("Configuration illisible : ") + "; ".join(result.errors), severity="error")
            return None
        return result.config

    @contextmanager
    def _riposte_store(self, config: OmegaServConfig, *, write: bool = False) -> Iterator[RiposteStorePort]:
        factory = self._container.riposte_store_factory
        if factory is None:
            raise StoreUnavailable(_("RIPOSTE indisponible dans cet environnement."))
        try:
            store = factory(database_path(config, self._container.project_root), write)
        except FileNotFoundError:
            raise StoreUnavailable(_("RIPOSTE n'a encore jamais été lancé sur cette instance.")) from None
        except OSError as error:
            message = _("Base RIPOSTE illisible : {error}").format(error=error)
            if write:
                message += " " + _("Droits d'écriture sur la base requis (groupe du service omega-serv).")
            raise StoreUnavailable(message) from None
        try:
            yield store
        finally:
            store.close()

    def _send_commands(self, config: OmegaServConfig, commands: Commands, *,
                       done: Callable[[], None] | None = None) -> None:
        """Depose les commandes, puis affiche leurs resultats (notifications) et rappelle `done`."""
        try:
            with self._riposte_store(config, write=True) as store:
                now = self._container.clock.now()
                ids = submit_commands(store, commands, now)
                running = process_running(store, now)
        except StoreUnavailable as error:
            self.app.notify(str(error), severity="warning")
            if done is not None:
                done()
            return
        except OSError as error:
            self.app.notify(_("Commande non déposée : {error}").format(error=error), severity="error")
            if done is not None:
                done()
            return
        self._after_deposit(config, ids, running, done)

    def _reload_riposte(self, config: OmegaServConfig, extra: Commands | None = None, *,
                        done: Callable[[], None] | None = None) -> None:
        """Apres une ecriture de la configuration : le processus relit (commande `reload`). RIPOSTE desactive :
        rien a relire (la configuration sera lue a son demarrage)."""
        commands: Commands = [("reload", {})] if riposte_enabled(config) else []
        commands += extra or []
        if not commands:
            if done is not None:
                done()
            return
        self._send_commands(config, commands, done=done)

    def _after_deposit(self, config: OmegaServConfig, ids: list[int], running: bool,
                       done: Callable[[], None] | None) -> None:
        if not ids:
            if done is not None:
                done()
            return
        if not running:
            self.app.notify(_("RIPOSTE est arrêté : la commande sera exécutée à son prochain démarrage."),
                            severity="warning")
            if done is not None:
                done()
            return

        def wait() -> None:
            results: list[RiposteCommand] = []
            deadline = time.monotonic() + WAIT_SECONDS
            try:
                with self._riposte_store(config) as store:  # connexion propre a ce fil
                    while time.monotonic() < deadline:
                        results = finished_commands(store, ids)
                        if len(results) == len(ids):
                            break
                        time.sleep(_POLL_SECONDS)
            except StoreUnavailable:
                results = []
            self.app.call_from_thread(self._commands_finished, results, len(ids), done)

        self.run_worker(wait, thread=True, group="riposte-commands")  # type: ignore[attr-defined]

    def _commands_finished(self, results: list[RiposteCommand], expected: int, done: Callable[[], None] | None) -> None:
        for command in results:
            self.app.notify(command_result_text(command.result, command.result_params),
                            severity="error" if command.state == "failed" else "information")
        if len(results) < expected:
            self.app.notify(_("Commande déposée, pas encore exécutée : rafraîchir dans quelques secondes."),
                            severity="warning")
        if done is not None:
            done()
