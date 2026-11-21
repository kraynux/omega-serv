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

from pathlib import Path
from typing import TYPE_CHECKING

from textual.app import ComposeResult
from textual.containers import Container, Horizontal, VerticalScroll
from textual.widgets import Button, Checkbox, DataTable, Footer, Header, Input, Static

from omega_serv.application.config.load_config import load_config
from omega_serv.core.i18n import _
from omega_serv.domain.persistence.backup import BackupRequest
from omega_serv.interfaces.tui.screens._base import OmegaScreen, main_menu_title
from omega_serv.interfaces.tui.screens.confirm import ConfirmScreen
from omega_serv.interfaces.tui.screens.dynamic_form_screen import DynamicFormScreen
from omega_serv.interfaces.tui.screens.restart_prompt import notify_restart_required

if TYPE_CHECKING:
    from collections.abc import Callable

    from omega_serv.application.persistence.backup_transfer import TransferResult
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
        with VerticalScroll(classes="omega-panel omega-main-panel"):
            yield main_menu_title(_("SAUVEGARDE / RESTAURATION DE LA CONFIGURATION"))
            yield Static("", id="backup-error", classes="omega-hint")
            yield Static(
                _("Le fichier de configuration est toujours inclus : réglages du serveur et de toutes les zones "
                  "(alias, rewrites, listing, cache, redirections, FastCGI, reverse proxy), profils "
                  "personnalisés compris. Une sauvegarde n'est jamais chiffrée par défaut."),
                classes="omega-hint",
            )
            yield Checkbox(_("Tout sauvegarder (configuration complète)"), id="include-all")
            yield Checkbox(_("Inclure les règles WAF (règles + liste de blocage)"), id="include-waf")
            yield Static(_("Règles WAF : packs, listes de mots-clés, scripts Magnet et listes de blocage."),
                         classes="omega-hint")
            yield Checkbox(_("Inclure les zones d'authentification (secrets réels)"), id="include-auth")
            yield Checkbox(_("Inclure les certificats (clés privées TLS incluses)"), id="include-certificates")
            yield Checkbox(_("Inclure Active Defense (base de menaces/incidents)"), id="include-active-defense")
            yield Checkbox(_("Inclure RIPOSTE (mémoire de récidive, décisions, actions)"), id="include-riposte")
            yield Checkbox(_("Inclure les pages d'erreur personnalisées"), id="include-error-pages")
            yield Checkbox(_("Inclure les préférences (thème, langues, nom du service)"), id="include-preferences")
            yield Checkbox(_("Inclure la bibliothèque des journaux (favoris, sources, rotations)"), id="include-logs-library")
            # Hors « Tout sauvegarder » (decision de l'auteur du 2026-11-15) : contenu, pas configuration.
            yield Checkbox(_("Inclure le contenu du site (webroot) - peut être long"), id="include-site-content")
            # Demandes de l'auteur du 2026-11-15, hors « Tout sauvegarder » elles aussi : fichiers, pas reglages.
            yield Checkbox(_("Inclure les données des zones personnalisées"), id="include-zone-data")
            yield Static(_("Dossiers vers lesquels pointent les zones : cible des alias, dossiers du listing, "
                           "scripts FastCGI. Rewrites, redirections et cache n'ont que des réglages, déjà dans "
                           "la configuration. Un dossier hors du dossier omega-serv est signalé, pas sauvegardé."),
                         classes="omega-hint")
            yield Checkbox(_("Inclure les rapports d'export"), id="include-exports")
            yield Static(_("Description"), classes="omega-subtitle")
            yield Input(id="description-input")
            with Horizontal(classes="omega-actions"):
                with Container(classes="omega-btn-frame"):
                    yield Button(_("Créer une sauvegarde"), id="create", variant="primary")
                with Container(classes="omega-btn-frame"):
                    yield Button(_("Importer une sauvegarde"), id="import")
            yield DataTable(id="backups-table")
            with Horizontal(classes="omega-actions"):
                with Container(classes="omega-btn-frame"):
                    yield Button(_("Restaurer"), id="restore", variant="error", disabled=True)
                with Container(classes="omega-btn-frame"):
                    yield Button(_("Exporter"), id="export", disabled=True)
                with Container(classes="omega-btn-frame"):
                    yield Button(_("Supprimer"), id="delete", variant="error", disabled=True)
        with Horizontal(classes="omega-actions omega-riposte-actions omega-service-back"), \
                Container(classes="omega-btn-frame"):
            yield Button(_("Retour"), id="back")
        yield Footer()

    def on_mount(self) -> None:
        table = self.query_one("#backups-table", DataTable)
        table.cursor_type = "row"
        table.add_columns(_("ID"), _("Date"), _("Contenu"), _("Taille (octets)"), _("Description"))
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
        for button_id in ("#restore", "#delete", "#export"):
            self.query_one(button_id, Button).disabled = True

    def on_data_table_row_selected(self, event: DataTable.RowSelected) -> None:
        self._selected_snapshot_id = str(event.row_key.value)
        for button_id in ("#restore", "#delete", "#export"):
            self.query_one(button_id, Button).disabled = False

    def on_button_pressed(self, event: Button.Pressed) -> None:
        button_id = event.button.id
        if button_id == "back":
            self.dismiss()
            return
        if button_id == "create":
            self._create()
            return
        if button_id == "restore" and self._selected_snapshot_id is not None:
            self._ask_restore(self._selected_snapshot_id)
            return
        if button_id == "export" and self._selected_snapshot_id is not None:
            snapshot_id = self._selected_snapshot_id
            self.push_form(
                DynamicFormScreen(title=_("EXPORTER LA SAUVEGARDE"),
                                  fields=[("dest_dir", _("Dossier de destination (hors du dossier omega-serv, pour "
                                                         "survivre à une désinstallation)"), str(Path.home()))]),
                lambda values: self._export(snapshot_id, values),
            )
            return
        if button_id == "import":
            self.push_form(
                DynamicFormScreen(title=_("IMPORTER UNE SAUVEGARDE"),
                                  fields=[("archive", _("Archive exportée (.tar.gz, son fichier .sha256 à côté)"), "")]),
                self._import,
            )
            return
        if button_id == "delete" and self._selected_snapshot_id is not None:
            self.app.push_screen(
                ConfirmScreen(
                    title=_("SUPPRIMER LA SAUVEGARDE"),
                    message=_("Supprimer définitivement {selected_snapshot_id} ?").format(selected_snapshot_id=self._selected_snapshot_id),
                ),
                self._delete_if_confirmed,
            )

    def _create(self) -> None:
        error_widget = self.query_one("#backup-error", Static)
        load_result = load_config(self._container.configuration, self._container.config_file)
        if not load_result.success or load_result.config is None:
            error_widget.update(_("Erreur de configuration : ") + "; ".join(load_result.errors))
            return

        include_auth = self.query_one("#include-auth", Checkbox).value
        include_certificates = self.query_one("#include-certificates", Checkbox).value
        if include_auth or include_certificates:
            self.app.push_screen(
                ConfirmScreen(
                    title=_("INCLURE DES SECRETS RÉELS"),
                    message=(
                        _("Cette sauvegarde inclura des secrets réels (hash de mot de passe "
                        "et/ou clé privée TLS), jamais chiffres par défaut. Continuer ?")
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
            error_widget.update(_("Erreur de configuration : ") + "; ".join(load_result.errors))
            return

        request = BackupRequest(
            include_waf_rules=self.query_one("#include-waf", Checkbox).value,
            include_auth_zones=self.query_one("#include-auth", Checkbox).value,
            include_certificates=self.query_one("#include-certificates", Checkbox).value,
            include_active_defense=self.query_one("#include-active-defense", Checkbox).value,
            include_riposte=self.query_one("#include-riposte", Checkbox).value,
            include_error_pages=self.query_one("#include-error-pages", Checkbox).value,
            include_preferences=self.query_one("#include-preferences", Checkbox).value,
            include_logs_library=self.query_one("#include-logs-library", Checkbox).value,
            include_site_content=self.query_one("#include-site-content", Checkbox).value,
            include_zone_data=self.query_one("#include-zone-data", Checkbox).value,
            include_exports=self.query_one("#include-exports", Checkbox).value,
            description=self.query_one("#description-input", Input).value,
        )
        error_widget.update(
            _("Création de la sauvegarde en cours (contenu du site compris : cela peut être long)...")
            if request.include_site_content else _("Création de la sauvegarde en cours..."))
        self._busy(True)
        config = load_result.config
        self.run_worker(lambda: self._create_in_thread(request, config), thread=True, exclusive=True)

    def _create_in_thread(self, request: BackupRequest, config: OmegaServConfig) -> None:
        result = self._container.create_backup(request, config, self._container.config_file)
        self.app.call_from_thread(self._finish_create, result)

    def _finish_create(self, result: BackupResult) -> None:
        self._busy(False)
        error_widget = self.query_one("#backup-error", Static)
        if not result.success:
            error_widget.update(result.message)
            return
        # Elements demandes mais non archives (hors du dossier omega-serv) : toujours dits, jamais tus.
        error_widget.update("\n".join(result.skipped))
        self.app.notify(result.message)
        self._refresh()

    def _busy(self, busy: bool) -> None:
        """Indicateur d'attente sur la liste pendant une operation longue (decision de l'auteur du 2026-11-15)."""
        self.query_one("#backups-table", DataTable).loading = busy
        for button_id in ("#create", "#import"):
            self.query_one(button_id, Button).disabled = busy

    # --- export / import (projets 3.0.0 §7.4) ---

    def _export(self, snapshot_id: str, values: dict[str, str] | None) -> None:
        if values is None:
            return
        dest_dir = Path(values["dest_dir"].strip()).expanduser()
        if not dest_dir.is_dir():
            self.report_form_error(_("Dossier de destination introuvable : {path}").format(path=dest_dir))
            return
        self.query_one("#backup-error", Static).update(_("Export en cours..."))
        self._busy(True)
        self.run_worker(lambda: self.app.call_from_thread(
            self._finish_transfer, self._container.export_backup(snapshot_id, dest_dir)), thread=True, exclusive=True)

    def _import(self, values: dict[str, str] | None) -> None:
        if values is None:
            return
        archive = Path(values["archive"].strip()).expanduser()
        if not archive.is_file():
            self.report_form_error(_("Fichier introuvable : {path}").format(path=archive))
            return
        config = self._config_or_none()
        webroot = config.paths.webroot if config is not None else "webroot"
        self.query_one("#backup-error", Static).update(_("Vérification et import en cours..."))
        self._busy(True)
        self.run_worker(lambda: self.app.call_from_thread(
            self._finish_transfer, self._container.import_backup(archive, webroot)), thread=True, exclusive=True)

    def _finish_transfer(self, result: TransferResult) -> None:
        self._busy(False)
        self.query_one("#backup-error", Static).update("" if result.success else result.message)
        self.app.notify(result.message, severity="information" if result.success else "error", timeout=12)
        self._refresh()

    def _config_or_none(self) -> OmegaServConfig | None:
        load_result = load_config(self._container.configuration, self._container.config_file)
        return load_result.config if load_result.success else None

    # --- restauration : version et conflit de port annonces AVANT (2026-11-15) ---

    def _ask_restore(self, snapshot_id: str) -> None:
        identity = self._container.backup_identity(snapshot_id)
        lines = [_("Restaurer {selected_snapshot_id} écrasera les fichiers actuels aux mêmes emplacements.").format(
            selected_snapshot_id=snapshot_id)]
        current_version = self._container.app_version
        if identity is not None and identity.app_version and identity.app_version != current_version:
            lines.append(_("Sauvegarde faite avec omega-serv {old}, celui-ci est en {new} : les réglages qu'il ne "
                           "connaît pas sont ignorés, les nouveaux prennent leur valeur par défaut.").format(
                old=identity.app_version, new=current_version))
        conflict = self._container.backup_port_conflict(snapshot_id)
        if conflict is not None:
            archived, other = conflict
            config = self._config_or_none()
            here = f"{config.server.bind}:{config.server.port}" if config is not None else "?"
            lines.append(_("Conflit : l'archive écoute sur {address}, déjà utilisé par l'instance {name!r}. "
                           "Confirmer restaure en GARDANT l'adresse et le port de cette instance ({here}) et son nom "
                           "de service actuel ; Annuler ne restaure rien.").format(
                address=f"{archived.bind}:{archived.port}", name=other.name, here=here))
        lines.append(_("Continuer ?"))
        self.app.push_screen(
            ConfirmScreen(title=_("RESTAURER LA SAUVEGARDE"), message="\n".join(lines)),
            lambda confirmed: self._restore_if_confirmed(confirmed, keep_identity=conflict is not None),
        )

    def _current_identity(self) -> tuple[str, int, str | None] | None:
        config = self._config_or_none()
        if config is None:
            return None
        service_name = self._container.settings_store.get("service_name", "")
        return config.server.bind, config.server.port, service_name

    def _reapply_identity(self, identity: tuple[str, int, str | None] | None) -> None:
        """Apres une restauration en conflit de port : adresse, port et nom de service de CETTE instance remis."""
        if identity is None:
            return
        from dataclasses import replace

        config = self._config_or_none()
        if config is not None:
            server = replace(config.server, bind=identity[0], port=identity[1])
            self._container.configuration.save(self._container.config_file, replace(config, server=server))
        if identity[2]:
            self._container.settings_store.set("service_name", identity[2])

    _keep_identity: tuple[str, int, str | None] | None = None

    def _identity_fixer(self) -> Callable[[], None] | None:
        identity = self._keep_identity
        return (lambda: self._reapply_identity(identity)) if identity is not None else None

    def _keep_identity_done(self) -> None:
        self._keep_identity = None

    def _restore_if_confirmed(self, confirmed: bool | None, keep_identity: bool = False) -> None:
        if not confirmed or self._selected_snapshot_id is None:
            return
        snapshot_id = self._selected_snapshot_id
        self._keep_identity = self._current_identity() if keep_identity else None
        for button_id in ("#restore", "#delete", "#export"):
            self.query_one(button_id, Button).disabled = True
        self._busy(True)
        self.run_worker(lambda: self._restore_in_thread(snapshot_id), thread=True, exclusive=True)

    def _restore_in_thread(self, snapshot_id: str) -> None:
        result = self._container.restore_backup(snapshot_id, after_restore=self._identity_fixer())
        self.app.call_from_thread(self._finish_restore, result, snapshot_id)

    def _finish_restore(self, result: RestoreResult, snapshot_id: str | None = None) -> None:
        self._busy(False)
        if result.success or not result.needs_service_stop:
            self._keep_identity_done()
        error_widget = self.query_one("#backup-error", Static)
        if result.needs_service_stop and snapshot_id is not None:
            # Base dans la sauvegarde + serveur actif (decision utilisateur 2026-11-01) : jamais restauree
            # sous le serveur ; on propose « Arreter, restaurer, redemarrer ».
            error_widget.update(result.message)
            self.app.push_screen(
                ConfirmScreen(
                    title=_("ARRÊTER, RESTAURER, REDÉMARRER"),
                    message=_("Cette sauvegarde contient une base ({databases}) et le serveur tourne. Arrêter le "
                              "service, restaurer, puis le redémarrer ? Les bases actuelles sont mises de côté "
                              "avant d'être remplacées. Une authentification (sudo) peut être demandée.").format(
                        databases=", ".join(result.databases)),
                ),
                lambda confirmed: self._restore_stopping_service(snapshot_id, confirmed),
            )
            self._refresh()
            return
        if not result.success:
            error_widget.update(result.message)
            self._refresh()
            return
        # Projets 3.0.0 §8.2, P1 : dossiers de zones actives absents apres la restauration, annonces ici (restent
        # affiches) en plus de la notification.
        error_widget.update(
            _("Dossiers de zones absents après la restauration :\n") + "\n".join(f"  - {m}" for m in result.missing_zone_folders)
            if result.missing_zone_folders else ""
        )
        notify_restart_required(self, self._container, result.message)
        self._refresh()

    def _restore_stopping_service(self, snapshot_id: str, confirmed: bool | None) -> None:
        if not confirmed:
            self._refresh()
            return
        with self._maybe_suspend():  # sudo eventuel : terminal rendu le temps de l'arret/redemarrage
            result = self._container.restore_backup(snapshot_id, stop_and_restart=True,
                                                    after_restore=self._identity_fixer())
        self._keep_identity_done()
        self.app.notify(result.message, severity="information" if result.success else "error")
        self.query_one("#backup-error", Static).update("" if result.success else result.message)
        self._refresh()

    _COMPONENT_CHECKBOXES = (
        "#include-waf", "#include-auth", "#include-certificates", "#include-active-defense",
        "#include-riposte", "#include-error-pages", "#include-preferences", "#include-logs-library",
    )

    def on_checkbox_changed(self, event: Checkbox.Changed) -> None:
        """« Tout sauvegarder » coche OU decoche toutes les cases (retour utilisateur 2026-11-01 : decocher
        laissait tout coche). Decocher une seule case quand tout etait coche decoche seulement « Tout
        sauvegarder ». Les secrets restent confirmes a la creation."""
        all_box = self.query_one("#include-all", Checkbox)
        if event.checkbox.id == "include-all":
            if getattr(self, "_skip_next_all_event", False):
                self._skip_next_all_event = False  # decochee par le programme (ci-dessous) : ne rien propager
                return
            for checkbox_id in self._COMPONENT_CHECKBOXES:
                self.query_one(checkbox_id, Checkbox).value = event.value
        elif f"#{event.checkbox.id}" in self._COMPONENT_CHECKBOXES and not event.value and all_box.value:
            # Seules les cases de « Tout sauvegarder » le decochent (contenu du site, donnees des zones et
            # rapports d'export n'en font pas partie).
            self._skip_next_all_event = True
            all_box.value = False

    def _delete_if_confirmed(self, confirmed: bool | None) -> None:
        if not confirmed or self._selected_snapshot_id is None:
            return
        deleted = self._container.delete_backup(self._selected_snapshot_id)
        error_widget = self.query_one("#backup-error", Static)
        if not deleted:
            error_widget.update(_("Sauvegarde introuvable : {selected_snapshot_id}").format(selected_snapshot_id=self._selected_snapshot_id))
        else:
            error_widget.update("")
            self.app.notify(_("Sauvegarde supprimée : {selected_snapshot_id}").format(selected_snapshot_id=self._selected_snapshot_id))
        self._refresh()
