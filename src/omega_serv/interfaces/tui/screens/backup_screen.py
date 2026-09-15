# Copyright (c) 2026 kraynux - kraynux@proton.me - Licence MIT (voir fichier LICENSE)
"""Ecran Sauvegarde/restauration de configuration (plan interface §3.5/§10,
menu 6) - un seul ecran couvre creation/liste/restauration/suppression,
meme regroupement que le tableau du plan ("Sauvegarder/restaurer/gerer la
configuration" est une seule ligne). Inclure les zones d'authentification
ou les certificats necessite une confirmation explicite (secrets reels,
jamais chiffres par defaut - meme discipline que --confirm-permanent du
blocklist) ; restaurer ecrase directement les fichiers vises, toujours
confirme (action destructive, meme patron que purge_log_archives_screen.py/
revoke_certificate_screen.py). La suppression d'une sauvegarde n'a pas
d'equivalent CLI (contrairement a creer/lister/restaurer, §3.5 du plan) -
convenance TUI uniquement, meme situation que la purge d'archives de logs
en Phase VI qui n'a elle non plus aucune commande CLI."""
from __future__ import annotations

from typing import TYPE_CHECKING

from textual.app import ComposeResult
from textual.containers import Container, Horizontal, Vertical
from textual.widgets import Button, Checkbox, DataTable, Footer, Header, Input, Static

from omega_serv.application.config.load_config import load_config
from omega_serv.domain.persistence.backup import BackupRequest
from omega_serv.interfaces.tui.screens._base import OmegaScreen
from omega_serv.interfaces.tui.screens.confirm import ConfirmScreen
from omega_serv.interfaces.tui.screens.restart_prompt import notify_restart_required

if TYPE_CHECKING:
    from omega_serv.application.persistence.create_backup import BackupResult
    from omega_serv.application.persistence.restore_backup import RestoreResult
    from omega_serv.bootstrap.container import DependencyContainer
    from omega_serv.domain.config.entities import OmegaServConfig


class BackupScreen(OmegaScreen):
    def __init__(self, *, container: DependencyContainer) -> None:
        super().__init__()
        self._container = container
        self._selected_snapshot_id: str | None = None

    def compose(self) -> ComposeResult:
        yield Header()
        with Vertical(classes="omega-panel"):
            yield Static("SAUVEGARDE / RESTAURATION DE LA CONFIGURATION", classes="omega-title")
            yield Static("", id="backup-error", classes="omega-hint")
            yield Static(
                "Le fichier de configuration est toujours inclus. Une sauvegarde "
                "n'est jamais chiffree par defaut.",
                classes="omega-hint",
            )
            yield Checkbox("Inclure les regles WAF (regles + liste de blocage)", id="include-waf")
            yield Checkbox("Inclure les zones d'authentification (secrets reels)", id="include-auth")
            yield Checkbox("Inclure les certificats (cles privees TLS incluses)", id="include-certificates")
            yield Checkbox("Inclure Active Defense (base de menaces/incidents)", id="include-active-defense")
            yield Static("Description", classes="omega-subtitle")
            yield Input(id="description-input")
            with Horizontal(classes="omega-actions"):
                with Container(classes="omega-btn-frame"):
                    yield Button("Creer une sauvegarde", id="create", variant="primary")
                with Container(classes="omega-btn-frame"):
                    yield Button("Retour", id="back")
            yield DataTable(id="backups-table")
            with Horizontal(classes="omega-actions"):
                with Container(classes="omega-btn-frame"):
                    yield Button("Restaurer", id="restore", variant="error", disabled=True)
                with Container(classes="omega-btn-frame"):
                    yield Button("Supprimer", id="delete", variant="error", disabled=True)
        yield Footer()

    def on_mount(self) -> None:
        table = self.query_one("#backups-table", DataTable)
        table.cursor_type = "row"
        table.add_columns("ID", "Date", "Contenu", "Taille (octets)", "Description")
        self._refresh()

    def _refresh(self) -> None:
        table = self.query_one("#backups-table", DataTable)
        table.clear()
        for metadata in self._container.list_backups():
            table.add_row(
                metadata.snapshot_id,
                metadata.created_at.isoformat(),
                metadata.scope,
                str(metadata.file_size_bytes or 0),
                metadata.description,
                key=metadata.snapshot_id,
            )
        self._selected_snapshot_id = None
        self.query_one("#restore", Button).disabled = True
        self.query_one("#delete", Button).disabled = True

    def on_data_table_row_selected(self, event: DataTable.RowSelected) -> None:
        self._selected_snapshot_id = str(event.row_key.value)
        self.query_one("#restore", Button).disabled = False
        self.query_one("#delete", Button).disabled = False

    def on_button_pressed(self, event: Button.Pressed) -> None:
        button_id = event.button.id
        if button_id == "back":
            self.dismiss()
            return
        if button_id == "create":
            self._create()
            return
        if button_id == "restore" and self._selected_snapshot_id is not None:
            self.app.push_screen(
                ConfirmScreen(
                    title="RESTAURER LA SAUVEGARDE",
                    message=(
                        f"Restaurer {self._selected_snapshot_id} ecrasera les fichiers actuels "
                        "aux memes emplacements. Continuer ?"
                    ),
                ),
                self._restore_if_confirmed,
            )
            return
        if button_id == "delete" and self._selected_snapshot_id is not None:
            self.app.push_screen(
                ConfirmScreen(
                    title="SUPPRIMER LA SAUVEGARDE",
                    message=f"Supprimer definitivement {self._selected_snapshot_id} ?",
                ),
                self._delete_if_confirmed,
            )

    def _create(self) -> None:
        error_widget = self.query_one("#backup-error", Static)
        load_result = load_config(self._container.configuration, self._container.config_file)
        if not load_result.success or load_result.config is None:
            error_widget.update("Erreur de configuration : " + "; ".join(load_result.errors))
            return

        include_auth = self.query_one("#include-auth", Checkbox).value
        include_certificates = self.query_one("#include-certificates", Checkbox).value
        if include_auth or include_certificates:
            self.app.push_screen(
                ConfirmScreen(
                    title="INCLURE DES SECRETS REELS",
                    message=(
                        "Cette sauvegarde inclura des secrets reels (hash de mot de passe "
                        "et/ou cle privee TLS), jamais chiffres par defaut. Continuer ?"
                    ),
                ),
                self._create_if_confirmed,
            )
            return
        self._do_create()

    def _create_if_confirmed(self, confirmed: bool | None) -> None:
        if confirmed:
            self._do_create()

    def _do_create(self) -> None:
        error_widget = self.query_one("#backup-error", Static)
        load_result = load_config(self._container.configuration, self._container.config_file)
        if not load_result.success or load_result.config is None:
            error_widget.update("Erreur de configuration : " + "; ".join(load_result.errors))
            return

        request = BackupRequest(
            include_waf_rules=self.query_one("#include-waf", Checkbox).value,
            include_auth_zones=self.query_one("#include-auth", Checkbox).value,
            include_certificates=self.query_one("#include-certificates", Checkbox).value,
            include_active_defense=self.query_one("#include-active-defense", Checkbox).value,
            description=self.query_one("#description-input", Input).value,
        )
        # Retour utilisateur (audit "gel d'ecran") : `tarfile` (creation/
        # extraction) tourne en synchrone sur la boucle asyncio - gele
        # l'interface le temps de l'operation, significatif des que la
        # base Active Defense ou les certificats sont inclus. Meme
        # patron que generate_self_signed_screen.py : deporte dans un
        # thread de travail.
        error_widget.update("Creation de la sauvegarde en cours...")
        self.query_one("#create", Button).disabled = True
        config = load_result.config
        self.run_worker(lambda: self._create_in_thread(request, config), thread=True, exclusive=True)

    def _create_in_thread(self, request: BackupRequest, config: OmegaServConfig) -> None:
        result = self._container.create_backup(request, config, self._container.config_file)
        self.app.call_from_thread(self._finish_create, result)

    def _finish_create(self, result: BackupResult) -> None:
        self.query_one("#create", Button).disabled = False
        error_widget = self.query_one("#backup-error", Static)
        if not result.success:
            error_widget.update(result.message)
            return
        error_widget.update("")
        self.app.notify(result.message)
        self._refresh()

    def _restore_if_confirmed(self, confirmed: bool | None) -> None:
        if not confirmed or self._selected_snapshot_id is None:
            return
        # Retour utilisateur (audit "gel d'ecran") : extraction tarfile
        # synchrone sur la boucle asyncio - meme correctif que
        # _do_create ci-dessus.
        snapshot_id = self._selected_snapshot_id
        self.query_one("#restore", Button).disabled = True
        self.query_one("#delete", Button).disabled = True
        self.run_worker(lambda: self._restore_in_thread(snapshot_id), thread=True, exclusive=True)

    def _restore_in_thread(self, snapshot_id: str) -> None:
        result = self._container.restore_backup(snapshot_id)
        self.app.call_from_thread(self._finish_restore, result)

    def _finish_restore(self, result: RestoreResult) -> None:
        error_widget = self.query_one("#backup-error", Static)
        if not result.success:
            error_widget.update(result.message)
            self._refresh()
            return
        error_widget.update("")
        # Retour utilisateur (guide d'aide, point 4) : une restauration
        # peut ecraser N'IMPORTE QUEL fichier (configuration, certificats,
        # zones d'auth...) - toujours un REDEMARRAGE COMPLET par prudence
        # (un simple rechargement ne suffit jamais pour des certificats
        # TLS deja en memoire, meme sujet que generate_self_signed_screen.py).
        notify_restart_required(self, self._container, result.message)
        self._refresh()

    def _delete_if_confirmed(self, confirmed: bool | None) -> None:
        if not confirmed or self._selected_snapshot_id is None:
            return
        deleted = self._container.delete_backup(self._selected_snapshot_id)
        error_widget = self.query_one("#backup-error", Static)
        if not deleted:
            error_widget.update(f"Sauvegarde introuvable : {self._selected_snapshot_id}")
        else:
            error_widget.update("")
            self.app.notify(f"Sauvegarde supprimee : {self._selected_snapshot_id}")
        self._refresh()
