"""Sous-ecran Authentification (plan interface §7.1) - liste/ajout/
suppression d'utilisateurs et de zones protegees, verification des
permissions. Le mot de passe est toujours saisi en double masque
(DynamicFormScreen.password_fields), jamais visible a l'ecran ni passe
en argument (meme regle que la CLI, `_resolve_password`)."""
from __future__ import annotations

from dataclasses import replace
from typing import TYPE_CHECKING

from textual.app import ComposeResult
from textual.containers import Container, Horizontal, VerticalScroll
from textual.widgets import Button, DataTable, Footer, Header, Static

from omega_serv.application.auth.manage_users import (
    ManageUsersResult,
    add_user,
    change_password,
    remove_user,
)
from omega_serv.application.auth.manage_zones import (
    ManageZonesResult,
    add_zone,
    remove_zone,
    update_zone,
)
from omega_serv.application.auth.password_protection import (
    protection_error_messages,
    protection_labels,
    protection_to_settings,
)
from omega_serv.application.config.load_config import load_config
from omega_serv.core.i18n import _
from omega_serv.domain.config.option import Option
from omega_serv.domain.security.auth.entities import AuthZone
from omega_serv.domain.security.auth.password_protection import (
    SETTINGS_KEY,
    PasswordProtection,
    parse_protection,
    protection_from_settings,
)
from omega_serv.domain.security.auth.zones import validate_auth_zone
from omega_serv.interfaces.tui.screens._base import OmegaScreen
from omega_serv.interfaces.tui.screens.confirm import ConfirmScreen
from omega_serv.interfaces.tui.screens.dynamic_form_screen import DynamicFormScreen
from omega_serv.interfaces.tui.screens.restart_prompt import notify_reload_required

if TYPE_CHECKING:
    from omega_serv.bootstrap.container import DependencyContainer
    from omega_serv.domain.config.entities import OmegaServConfig
    from omega_serv.ports.auth_zones_repository_port import AuthZonesRepositoryPort
    from omega_serv.ports.users_repository_port import UsersRepositoryPort


class AuthMenuScreen(OmegaScreen):
    def __init__(self, *, container: DependencyContainer) -> None:
        super().__init__()
        self._container = container
        self._selected_username: str | None = None
        self._selected_zone_prefix: str | None = None

    def compose(self) -> ComposeResult:
        yield Header()
        with VerticalScroll(classes="omega-panel"):
            yield Static(_("AUTHENTIFICATION"), classes="omega-title")
            yield Static("", id="form-error", classes="omega-hint")

            yield Static(_("UTILISATEURS"), classes="omega-subtitle")
            yield DataTable(id="users-table")
            with Horizontal(classes="omega-actions"):
                with Container(classes="omega-btn-frame"):
                    yield Button(_("Ajouter"), id="add-user", variant="primary")
                with Container(classes="omega-btn-frame"):
                    yield Button(_("Changer le mot de passe"), id="change-password", disabled=True)
                with Container(classes="omega-btn-frame"):
                    yield Button(_("Supprimer"), id="remove-user", variant="error", disabled=True)

            yield Static(_("ZONES PROTÉGÉES"), classes="omega-subtitle")
            yield DataTable(id="zones-table")
            with Horizontal(classes="omega-actions"):
                with Container(classes="omega-btn-frame"):
                    yield Button(_("Créer une zone"), id="create-zone", variant="primary")
                with Container(classes="omega-btn-frame"):
                    yield Button(_("Modifier"), id="edit-zone", disabled=True)
                with Container(classes="omega-btn-frame"):
                    yield Button(_("Supprimer"), id="remove-zone", variant="error", disabled=True)

            # Retour utilisateur 2026-11-21 : cache des succes et limite des echecs reglables ici.
            yield Static(_("PROTECTION DES MOTS DE PASSE"), classes="omega-subtitle")
            yield Static(
                _("Une vérification coûte 0,3 à 0,5 s de calcul : un succès est retenu, les mauvais mots de passe "
                  "répétés reçoivent 429 sans calcul, et au-delà des vérifications en attente, 503."),
                classes="omega-hint",
            )
            yield DataTable(id="protection-table")
            with Horizontal(classes="omega-actions"), Container(classes="omega-btn-frame"):
                yield Button(_("Modifier les réglages"), id="edit-protection", variant="primary")

        # Barre d'actions HORS de la zone qui defile, toujours visible (demande de l'auteur du 2026-11-15, modele RIPOSTE) :
        # la liste peut grandir, Retour et la derniere rangee restent a portee sans derouler.
        with Horizontal(classes="omega-actions omega-riposte-actions"):
            with Container(classes="omega-btn-frame"):
                yield Button(_("Vérifier les permissions"), id="check-permissions")
            with Container(classes="omega-btn-frame"):
                yield Button(_("Retour"), id="back")
        yield Footer()

    def on_mount(self) -> None:
        users_table = self.query_one("#users-table", DataTable)
        users_table.cursor_type = "row"
        users_table.add_columns(_("Nom d'utilisateur"))

        zones_table = self.query_one("#zones-table", DataTable)
        zones_table.cursor_type = "row"
        zones_table.add_columns(_("Préfixe URL"), _("Realm"), _("Utilisateurs autorisés"), _("Méthodes"))
        self.query_one("#protection-table", DataTable).add_columns(_("Réglage"), _("Valeur"))

        self._refresh_lists()

    def _config(self) -> OmegaServConfig | None:
        result = load_config(self._container.configuration, self._container.config_file)
        return result.config if result.success else None

    def _refresh_lists(self) -> None:
        config = self._config()
        users_table = self.query_one("#users-table", DataTable)
        zones_table = self.query_one("#zones-table", DataTable)
        users_table.clear()
        zones_table.clear()
        self._selected_username = None
        self._selected_zone_prefix = None
        self.query_one("#change-password", Button).disabled = True
        self.query_one("#remove-user", Button).disabled = True
        self.query_one("#remove-zone", Button).disabled = True
        self.query_one("#edit-zone", Button).disabled = True

        if config is None:
            self.query_one("#form-error", Static).update(_("Erreur de configuration."))
            return

        users_repo = self._container.build_users_repository(self._container.project_root / config.paths.auth_file)
        zones_repo = self._container.build_auth_zones_repository(self._container.project_root / config.paths.auth_zones)

        for user in users_repo.load():
            users_table.add_row(user.username, key=user.username)
        protection_table = self.query_one("#protection-table", DataTable)
        protection_table.clear()
        values = protection_to_settings(self._protection(config))
        for name, label in protection_labels().items():
            protection_table.add_row(label, str(values[name]), key=name)

        for zone in zones_repo.load():
            methods = ", ".join(zone.allow_methods) or _("toutes")
            zones_table.add_row(
                zone.path_prefix, zone.realm, ", ".join(zone.allowed_users) or "(aucun)", methods,
                key=zone.path_prefix,
            )

    def on_data_table_row_selected(self, event: DataTable.RowSelected) -> None:
        if event.data_table.id == "users-table":
            self._selected_username = str(event.row_key.value)
            self.query_one("#change-password", Button).disabled = False
            self.query_one("#remove-user", Button).disabled = False
        elif event.data_table.id == "zones-table":
            self._selected_zone_prefix = str(event.row_key.value)
            self.query_one("#remove-zone", Button).disabled = False
            self.query_one("#edit-zone", Button).disabled = False

    def on_button_pressed(self, event: Button.Pressed) -> None:
        button_id = event.button.id
        if button_id == "back":
            self.dismiss()
            return
        if button_id == "add-user":
            self.app.push_screen(
                DynamicFormScreen(
                    title=_("AJOUTER UN UTILISATEUR"),
                    fields=[
                        ("username", _("Nom d'utilisateur"), ""),
                        ("password", _("Mot de passe"), ""),
                        ("password_confirm", _("Confirmer le mot de passe"), ""),
                    ],
                    password_fields=frozenset({"password", "password_confirm"}),
                ),
                self._add_user,
            )
            return
        if button_id == "remove-user" and self._selected_username is not None:
            username = self._selected_username
            self.app.push_screen(
                ConfirmScreen(title=_("SUPPRIMER L'UTILISATEUR"), message=_("Confirmer la suppression de {username!r} ?").format(username=username)),
                lambda confirmed: self._do_remove_user(username, confirmed),
            )
            return
        if button_id == "change-password" and self._selected_username is not None:
            username = self._selected_username
            self.app.push_screen(
                DynamicFormScreen(
                    title=_("CHANGER LE MOT DE PASSE DE {username!r}").format(username=username),
                    fields=[
                        ("password", _("Nouveau mot de passe"), ""),
                        ("password_confirm", _("Confirmer le mot de passe"), ""),
                    ],
                    password_fields=frozenset({"password", "password_confirm"}),
                ),
                lambda values: self._change_password(username, values),
            )
            return
        if button_id == "create-zone":
            self.app.push_screen(
                DynamicFormScreen(title=_("CRÉER UNE ZONE PROTÉGÉE"), fields=self._zone_fields(None),
                                  validate=self._zone_form_error),
                self._create_zone,
            )
            return
        if button_id == "edit-zone" and self._selected_zone_prefix is not None:
            original = self._find_zone(self._selected_zone_prefix)
            if original is None:
                self._refresh_lists()
                return
            self.app.push_screen(
                DynamicFormScreen(title=_("MODIFIER LA ZONE PROTÉGÉE"), fields=self._zone_fields(original),
                                  validate=self._zone_form_error),
                lambda values: self._update_zone(original.path_prefix, values),
            )
            return
        if button_id == "remove-zone" and self._selected_zone_prefix is not None:
            path_prefix = self._selected_zone_prefix
            self.app.push_screen(
                ConfirmScreen(title=_("SUPPRIMER LA ZONE"), message=_("Confirmer la suppression de {path_prefix!r} ?").format(path_prefix=path_prefix)),
                lambda confirmed: self._do_remove_zone(path_prefix, confirmed),
            )
            return
        if button_id == "check-permissions":
            self._check_permissions()
        if button_id == "edit-protection":
            config = self._config()
            if config is None:
                return
            values = protection_to_settings(self._protection(config))
            self.push_form(
                DynamicFormScreen(title=_("PROTECTION DES MOTS DE PASSE"),
                                  fields=[(name, label, str(values[name])) for name, label in protection_labels().items()]),
                self._save_protection,
            )

    @staticmethod
    def _protection(config: OmegaServConfig) -> PasswordProtection:
        option = config.options.get("auth")
        return protection_from_settings(option.settings if option is not None else None)

    def _save_protection(self, values: dict[str, str] | None) -> None:
        if values is None:
            return
        raw: dict[str, object] = {}
        for name, text in values.items():
            try:
                raw[name] = int(text.strip())
            except ValueError:
                raw[name] = text
        errors = protection_error_messages(raw)
        if errors:
            self.report_form_error("\n".join(errors))
            return
        load_result = load_config(self._container.configuration, self._container.config_file)
        if not load_result.success or load_result.config is None:
            self.report_form_error(_("Erreur de configuration - impossible d'enregistrer."))
            return
        existing = load_result.config.options.get("auth")
        settings = dict(existing.settings) if existing is not None else {}
        settings[SETTINGS_KEY] = protection_to_settings(parse_protection(raw))
        options = dict(load_result.config.options)
        options["auth"] = Option(name="auth", enabled=existing.enabled if existing is not None else False,
                                 settings=settings)
        self._container.configuration.save(self._container.config_file, replace(load_result.config, options=options))
        self._refresh_lists()
        notify_reload_required(self, self._container, _("Protection des mots de passe mise à jour."))

    def _repos(self) -> tuple[UsersRepositoryPort, AuthZonesRepositoryPort] | None:
        config = self._config()
        if config is None:
            return None
        return (
            self._container.build_users_repository(self._container.project_root / config.paths.auth_file),
            self._container.build_auth_zones_repository(self._container.project_root / config.paths.auth_zones),
        )

    def _report(self, result: ManageUsersResult | ManageZonesResult) -> None:
        error_widget = self.query_one("#form-error", Static)
        error_widget.update("" if result.success else _("Erreur : {message}").format(message=result.message))
        if result.success:
            notify_reload_required(self, self._container, result.message)
        else:
            self.app.notify(result.message, severity="error")
        self._refresh_lists()

    def _add_user(self, values: dict[str, str] | None) -> None:
        if values is None:
            return
        if values["password"] != values["password_confirm"]:
            self.query_one("#form-error", Static).update(_("Les deux mots de passe ne correspondent pas."))
            return
        repos = self._repos()
        if repos is None:
            return
        self._report(add_user(repos[0], values["username"], values["password"]))

    def _do_remove_user(self, username: str, confirmed: bool | None) -> None:
        if not confirmed:
            return
        repos = self._repos()
        if repos is None:
            return
        self._report(remove_user(repos[0], username))

    def _change_password(self, username: str, values: dict[str, str] | None) -> None:
        if values is None:
            return
        if values["password"] != values["password_confirm"]:
            self.query_one("#form-error", Static).update(_("Les deux mots de passe ne correspondent pas."))
            return
        repos = self._repos()
        if repos is None:
            return
        self._report(change_password(repos[0], username, values["password"]))

    @staticmethod
    def _zone_fields(zone: AuthZone | None) -> list[tuple[str, str, str]]:
        """Memes champs pour Creer et Modifier ; Modifier les pre-remplit avec la zone choisie."""
        return [
            ("path_prefix", _("Préfixe URL (ex: /admin/)"), zone.path_prefix if zone else ""),
            ("realm", _("Realm"), zone.realm if zone else ""),
            ("allowed_users", _("Utilisateurs autorisés (séparés par des virgules)"),
             ", ".join(zone.allowed_users) if zone else ""),
            ("allow_methods", _("Méthodes autorisées (vide = toutes)"), ", ".join(zone.allow_methods) if zone else ""),
        ]

    @staticmethod
    def _zone_from_values(values: dict[str, str]) -> AuthZone:
        return AuthZone(
            path_prefix=values["path_prefix"],
            realm=values["realm"],
            allowed_users=tuple(item.strip() for item in values["allowed_users"].split(",") if item.strip()),
            allow_methods=tuple(item.strip().upper() for item in values["allow_methods"].split(",") if item.strip()),
        )

    def _zone_form_error(self, values: dict[str, str]) -> str | None:
        """Erreur affichee DANS le formulaire, saisie gardee (une faute de frappe ne fait plus tout recommencer)."""
        return validate_auth_zone(self._zone_from_values(values))

    def _find_zone(self, path_prefix: str) -> AuthZone | None:
        repos = self._repos()
        if repos is None:
            return None
        return next((zone for zone in repos[1].load() if zone.path_prefix == path_prefix), None)

    def _create_zone(self, values: dict[str, str] | None) -> None:
        if values is None:
            return
        repos = self._repos()
        if repos is None:
            return
        self._report(add_zone(repos[1], self._zone_from_values(values)))

    def _update_zone(self, original_prefix: str, values: dict[str, str] | None) -> None:
        if values is None:
            return
        repos = self._repos()
        if repos is None:
            return
        self._report(update_zone(repos[1], original_prefix, self._zone_from_values(values)))

    def _do_remove_zone(self, path_prefix: str, confirmed: bool | None) -> None:
        if not confirmed:
            return
        repos = self._repos()
        if repos is None:
            return
        self._report(remove_zone(repos[1], path_prefix))

    def _check_permissions(self) -> None:
        config = self._config()
        error_widget = self.query_one("#form-error", Static)
        if config is None:
            error_widget.update(_("Erreur de configuration."))
            return
        lines = []
        ok = True
        for label, relative_path in (("users.json", config.paths.auth_file), ("zones.json", config.paths.auth_zones)):
            path = self._container.project_root / relative_path
            if not self._container.filesystem.exists(path):
                lines.append(_("[INFO] {label} absent ({path})").format(label=label, path=path))
                continue
            mode = self._container.filesystem.file_mode(path)
            # Masque 0o007 ("other" uniquement), pas 0o077 (2026-09-29,
            # meme incident que le mode 0640 lui-meme - voir
            # infrastructure/auth/users_repository.py) : le GROUPE dedie
            # doit desormais pouvoir lire ce fichier (le service tourne
            # sous ce groupe, jamais sous le compte interactif qui
            # l'ecrit) - seul un acces "other" reste une vraie fuite.
            strict = not (mode & 0o007)
            lines.append(_("[{value}] {label} permissions : {value2}").format(value=_('OK') if strict else _('AVERTISSEMENT'), label=label, value2=oct(mode)))
            if not strict:
                ok = False
        error_widget.update("\n".join(lines))
        self.app.notify(_("Permissions vérifiées.") if ok else _("Permissions trop permissives détectées."), severity="information" if ok else "error")

# <-- INFO DEV ---------------------------------------------------------
# Role :
# - CRUD utilisateurs/zones protegees + verification des permissions
#   fichier (users.json/zones.json).
# Pourquoi dans interfaces/tui/screens/ (charte) :
# - Traduit les actions de l'ecran en appels a application/auth/
#   manage_users.py et manage_zones.py, comme tout autre ecran de menu.
# Points cles :
# - Deux DataTable distinctes (2026-09-29, retour utilisateur : "il
#   faudrait que la zone utilisateur et la zone 'zone' soit bien
#   distincte... l'ergonomie veut que le champ soit deroulant et propose
#   une selection de ce qu'on supprime") - avant ce correctif, un seul
#   Static texte listait tout en vrac et "Supprimer un utilisateur"/
#   "Supprimer une zone"/"Changer un mot de passe" ouvraient un
#   formulaire avec un champ VIDE a retaper de memoire (nom
#   d'utilisateur exact, prefixe exact) - ingerable des que la liste
#   grandit. Meme patron DataTable+selection que TOUS les autres ecrans
#   CRUD de l'application (aliases_screen.py, redirects_screen.py,
#   rewrites_screen.py, dirlisting_screen.py, cache_screen.py,
#   access_control_screen.py) : ce fichier etait le seul a ne pas le
#   suivre. Suppression desormais DIRECTE depuis la selection (plus
#   AUCUN formulaire intermediaire a remplir, juste ConfirmScreen) ;
#   "Changer le mot de passe" ne demande plus que le nouveau mot de
#   passe (deux fois), le nom d'utilisateur vient de la ligne
#   selectionnee, jamais retape.
# - _selected_username/_selected_zone_prefix memorisent la selection de
#   CHAQUE table separement (deux DataTable sur le meme ecran, jamais
#   vu ailleurs dans l'appli jusqu'ici) : on_data_table_row_selected()
#   distingue la table d'origine via event.data_table.id, seule la
#   selection concernee active ses propres boutons.
# - _refresh_lists() (remplace l'ancien _refresh_list() singulier)
#   reinitialise TOUJOURS les deux selections et desactive les boutons
#   Modifier/Supprimer/Changer le mot de passe apres tout ajout ou
#   suppression : une ligne supprimee ne doit jamais rester
#   "selectionnee" sur une DataTable qui vient d'etre reconstruite,
#   meme motif que _refresh_table() dans aliases_screen.py.
# - Modifier une zone existante reste hors-scope ici (retour utilisateur
#   ne le demandait pas) : application/auth/manage_zones.py n'expose
#   qu'add_zone/remove_zone, aucune fonction de mise a jour en place
#   (add_zone refuse explicitement un path_prefix deja existant) -
#   ajouter cette capacite plus tard exigerait d'abord une nouvelle
#   fonction application/, pas seulement un bouton ici.
# Comment il sera utilise :
# - server_config_menu_screen.py (bouton "Authentification").
#---------------------------------------------------------------------->
