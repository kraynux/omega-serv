"""Ecran Sources distantes (SSH) (OMEGA-SERV_ETUDE-FAISABILITE_LOGS_
DISTANTS.md, 2026-10-15) : definit des sources distantes (hote/chemin/
utilisateur-port-cle optionnels) et recupere, a la DEMANDE EXPLICITE de
l'utilisateur, le log correspondant via `scp` (jamais automatique,
jamais de polling). Aucun mot de passe n'est jamais demande ni stocke -
l'authentification reste entierement geree par la configuration SSH
deja existante de l'utilisateur (agent, ~/.ssh/config) ; `identity_file`
n'est qu'un chemin de reference, jamais le contenu d'une cle.

`Recuperer maintenant` tourne dans un worker thread (patron EXACT de
`capabilities_screen.py`/`lets_encrypt_screen.py` - `run_worker(...,
thread=True, exclusive=True)` puis `call_from_thread` pour revenir sur
le thread UI) : un transfert sur un reseau lent ou un hote injoignable
ne doit jamais geler l'interface. Sur succes, le fichier recupere est
ajoute a la Bibliotheque comme un `LogFile` ordinaire (`access="ssh"`
pour tracer la provenance) via `add_to_library` deja existant - a partir
de la, tous les viewers/stats/traitement IP deja construits fonctionnent
sans aucune modification."""
from __future__ import annotations

from collections.abc import Callable
from pathlib import Path
from typing import TYPE_CHECKING

from textual.app import ComposeResult
from textual.containers import Container, Horizontal, Vertical
from textual.widgets import Button, DataTable, Footer, Header, Input, Static

from omega_serv.application.logs.library import add_to_library
from omega_serv.application.logs.remote_fetch import RemoteFetchResult, fetch_remote_log
from omega_serv.application.logs.remote_sources import (
    list_remote_sources,
    remove_remote_source,
    save_remote_source,
)
from omega_serv.core.i18n import _
from omega_serv.domain.logs.library import LogFile
from omega_serv.domain.logs.remote_source import RemoteLogSource, safe_cache_filename
from omega_serv.interfaces.tui.screens._base import OmegaScreen
from omega_serv.interfaces.tui.screens.confirm import ConfirmScreen

if TYPE_CHECKING:
    from omega_serv.bootstrap.container import DependencyContainer
    from omega_serv.ports.process_runner_port import ProcessRunnerPort

_INPUT_IDS = (
    "label-input", "host-input", "remote-path-input", "user-input", "port-input", "identity-input",
)


class RemoteLogSourcesScreen(OmegaScreen):
    def __init__(self, *, container: DependencyContainer) -> None:
        super().__init__()
        self._container = container
        self._selected_label: str | None = None

    def compose(self) -> ComposeResult:
        yield Header()
        with Vertical(classes="omega-panel"):
            yield Static(_("SOURCES DISTANTES (SSH)"), classes="omega-title")
            yield Static(
                _("Récupère, sur demande, UNE COPIE du log d'un serveur du réseau local via scp - "
                "ce n'est jamais une consultation en direct, mais un instantané figé au moment du "
                "clic. Chaque nouvelle 'Récupération maintenant' remplace la copie précédente par "
                "une plus récente (la Bibliothèque affiche la date de cette dernière récupération, "
                "colonne 'Modifié'). Aucun mot de passe n'est jamais demandé ni stocké : une "
                "éventuelle clé privée n'est référencée que par son chemin - l'authentification "
                "reste entièrement gérée par votre propre configuration SSH."),
                classes="omega-hint",
            )
            yield Static("", id="sources-error", classes="omega-hint")
            yield DataTable(id="sources-table")
            with Horizontal(classes="omega-actions"):
                with Container(classes="omega-btn-frame"):
                    yield Button(_("Récupérer maintenant"), id="fetch", variant="primary", disabled=True)
                with Container(classes="omega-btn-frame"):
                    yield Button(_("Supprimer"), id="delete", variant="error", disabled=True)

            yield Static(_("Ajouter une source"), classes="omega-subtitle")
            yield Input(placeholder=_("Label"), id="label-input")
            yield Input(placeholder=_("Hôte (ex: backend1 ou 192.168.1.10)"), id="host-input")
            yield Input(placeholder=_("Chemin distant (ex: /var/log/nginx/access.log)"), id="remote-path-input")
            yield Input(placeholder=_("Utilisateur (optionnel)"), id="user-input")
            yield Input(placeholder=_("Port (optionnel)"), id="port-input")
            yield Input(placeholder=_("Chemin de la clé privée (optionnel)"), id="identity-input")
            with Horizontal(classes="omega-actions"), Container(classes="omega-btn-frame"):
                yield Button(_("Enregistrer"), id="save")

            with Horizontal(classes="omega-actions"), Container(classes="omega-btn-frame"):
                yield Button(_("Retour"), id="back")
        yield Footer()

    def on_mount(self) -> None:
        table = self.query_one("#sources-table", DataTable)
        table.cursor_type = "row"
        table.add_columns(_("Label"), _("Hôte"), _("Chemin distant"), _("Utilisateur"), _("Port"), _("Clé"))
        self._refresh()

    def _refresh(self) -> None:
        table = self.query_one("#sources-table", DataTable)
        table.clear()
        for source in list_remote_sources(self._container.build_remote_log_source_repository()):
            table.add_row(
                source.label, source.host, source.remote_path,
                source.user or "-", str(source.port) if source.port else "-", source.identity_file or "-",
                key=source.label,
            )

    def on_data_table_row_highlighted(self, event: DataTable.RowHighlighted) -> None:
        if event.data_table.id != "sources-table":
            return
        row = event.data_table.get_row_at(event.cursor_row)
        self._selected_label = str(row[0]) if row else None
        self.query_one("#fetch", Button).disabled = self._selected_label is None
        self.query_one("#delete", Button).disabled = self._selected_label is None

    def on_button_pressed(self, event: Button.Pressed) -> None:
        button_id = event.button.id
        if button_id == "back":
            self.dismiss()
        elif button_id == "save":
            self._save()
        elif button_id == "delete":
            self._delete()
        elif button_id == "fetch":
            self._fetch()

    def _save(self) -> None:
        error_widget = self.query_one("#sources-error", Static)
        port_raw = self.query_one("#port-input", Input).value.strip()
        port: int | None = None
        if port_raw:
            if not port_raw.isdigit():
                error_widget.update(_("Port invalide : {port_raw!r}.").format(port_raw=port_raw))
                return
            port = int(port_raw)

        result = save_remote_source(
            self._container.build_remote_log_source_repository(),
            label=self.query_one("#label-input", Input).value,
            host=self.query_one("#host-input", Input).value,
            remote_path=self.query_one("#remote-path-input", Input).value,
            user=self.query_one("#user-input", Input).value,
            port=port,
            identity_file=self.query_one("#identity-input", Input).value,
        )
        if not result.success:
            error_widget.update(result.message)
            return

        error_widget.update("")
        self.app.notify(result.message)
        for input_id in _INPUT_IDS:
            self.query_one(f"#{input_id}", Input).value = ""
        self._refresh()

    def _delete(self) -> None:
        if self._selected_label is None:
            return
        label = self._selected_label
        self.app.push_screen(
            ConfirmScreen(title=_("SUPPRIMER CETTE SOURCE ?"), message=label),
            lambda confirmed: self._delete_if_confirmed(confirmed, label),
        )

    def _delete_if_confirmed(self, confirmed: bool | None, label: str) -> None:
        if not confirmed:
            return
        remove_remote_source(self._container.build_remote_log_source_repository(), label)
        self._selected_label = None
        self.query_one("#fetch", Button).disabled = True
        self.query_one("#delete", Button).disabled = True
        self._refresh()

    def _fetch(self) -> None:
        error_widget = self.query_one("#sources-error", Static)
        if self._selected_label is None:
            return
        runner_factory = self._container.remote_log_fetch_runner_factory
        if runner_factory is None:
            error_widget.update(_("Récupération distante indisponible dans cet environnement."))
            return
        source = next(
            (s for s in list_remote_sources(self._container.build_remote_log_source_repository())
             if s.label == self._selected_label),
            None,
        )
        if source is None:
            return
        local_dest = self._container.project_root / "var" / "log" / "remote" / safe_cache_filename(source.label)

        error_widget.update(_("Récupération en cours..."))
        self.query_one("#fetch", Button).disabled = True
        self.run_worker(
            lambda: self._fetch_in_thread(source, local_dest, runner_factory), thread=True, exclusive=True,
        )

    def _fetch_in_thread(
        self, source: RemoteLogSource, local_dest: Path, runner_factory: Callable[[], ProcessRunnerPort],
    ) -> None:
        result = fetch_remote_log(runner_factory(), source, local_dest)
        if result.success:
            add_to_library(
                self._container.build_log_library_repository(),
                LogFile(path=str(local_dest), access="ssh", service_id=source.label),
            )
        self.app.call_from_thread(self._finish_fetch, result)

    def _finish_fetch(self, result: RemoteFetchResult) -> None:
        self.query_one("#fetch", Button).disabled = self._selected_label is None
        error_widget = self.query_one("#sources-error", Static)
        if result.success:
            error_widget.update("")
            self.app.notify(result.message + _(" Ajouté à la Bibliothèque."))
        else:
            error_widget.update(result.message)
