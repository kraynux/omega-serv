"""Sous-ecran Authentification (plan interface §7.1) - liste/ajout/
suppression d'utilisateurs et de zones protegees, verification des
permissions. Le mot de passe est toujours saisi en double masque
(DynamicFormScreen.password_fields), jamais visible a l'ecran ni passe
en argument (meme regle que la CLI, `_resolve_password`)."""
from __future__ import annotations

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
from omega_serv.application.auth.manage_zones import ManageZonesResult, add_zone, remove_zone
from omega_serv.application.config.load_config import load_config
from omega_serv.domain.security.auth.entities import AuthZone
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
            yield Static("AUTHENTIFICATION", classes="omega-title")
            yield Static("", id="form-error", classes="omega-hint")

            yield Static("UTILISATEURS", classes="omega-subtitle")
            yield DataTable(id="users-table")
            with Horizontal(classes="omega-actions"):
                with Container(classes="omega-btn-frame"):
                    yield Button("Ajouter", id="add-user", variant="primary")
                with Container(classes="omega-btn-frame"):
                    yield Button("Changer le mot de passe", id="change-password", disabled=True)
                with Container(classes="omega-btn-frame"):
                    yield Button("Supprimer", id="remove-user", variant="error", disabled=True)

            yield Static("ZONES PROTEGEES", classes="omega-subtitle")
            yield DataTable(id="zones-table")
            with Horizontal(classes="omega-actions"):
                with Container(classes="omega-btn-frame"):
                    yield Button("Creer une zone", id="create-zone", variant="primary")
                with Container(classes="omega-btn-frame"):
                    yield Button("Supprimer", id="remove-zone", variant="error", disabled=True)

            with Horizontal(classes="omega-actions"):
                with Container(classes="omega-btn-frame"):
                    yield Button("Verifier les permissions", id="check-permissions")
                with Container(classes="omega-btn-frame"):
                    yield Button("Retour", id="back")
        yield Footer()

    def on_mount(self) -> None:
        users_table = self.query_one("#users-table", DataTable)
        users_table.cursor_type = "row"
        users_table.add_columns("Nom d'utilisateur")

        zones_table = self.query_one("#zones-table", DataTable)
        zones_table.cursor_type = "row"
        zones_table.add_columns("Prefixe URL", "Realm", "Utilisateurs autorises", "Methodes")

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

        if config is None:
            self.query_one("#form-error", Static).update("Erreur de configuration.")
            return

        users_repo = self._container.build_users_repository(self._container.project_root / config.paths.auth_file)
        zones_repo = self._container.build_auth_zones_repository(self._container.project_root / config.paths.auth_zones)

        for user in users_repo.load():
            users_table.add_row(user.username, key=user.username)

        for zone in zones_repo.load():
            methods = ", ".join(zone.allow_methods) or "toutes"
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

    def on_button_pressed(self, event: Button.Pressed) -> None:
        button_id = event.button.id
        if button_id == "back":
            self.dismiss()
            return
        if button_id == "add-user":
            self.app.push_screen(
                DynamicFormScreen(
                    title="AJOUTER UN UTILISATEUR",
                    fields=[
                        ("username", "Nom d'utilisateur", ""),
                        ("password", "Mot de passe", ""),
                        ("password_confirm", "Confirmer le mot de passe", ""),
                    ],
                    password_fields=frozenset({"password", "password_confirm"}),
                ),
                self._add_user,
            )
            return
        if button_id == "remove-user" and self._selected_username is not None:
            username = self._selected_username
            self.app.push_screen(
                ConfirmScreen(title="SUPPRIMER L'UTILISATEUR", message=f"Confirmer la suppression de {username!r} ?"),
                lambda confirmed: self._do_remove_user(username, confirmed),
            )
            return
        if button_id == "change-password" and self._selected_username is not None:
            username = self._selected_username
            self.app.push_screen(
                DynamicFormScreen(
                    title=f"CHANGER LE MOT DE PASSE DE {username!r}",
                    fields=[
                        ("password", "Nouveau mot de passe", ""),
                        ("password_confirm", "Confirmer le mot de passe", ""),
                    ],
                    password_fields=frozenset({"password", "password_confirm"}),
                ),
                lambda values: self._change_password(username, values),
            )
            return
        if button_id == "create-zone":
            self.app.push_screen(
                DynamicFormScreen(
                    title="CREER UNE ZONE PROTEGEE",
                    fields=[
                        ("path_prefix", "Prefixe URL (ex: /admin/)", ""),
                        ("realm", "Realm", ""),
                        ("allowed_users", "Utilisateurs autorises (separes par des virgules)", ""),
                        ("allow_methods", "Methodes autorisees (vide = toutes)", ""),
                    ],
                ),
                self._create_zone,
            )
            return
        if button_id == "remove-zone" and self._selected_zone_prefix is not None:
            path_prefix = self._selected_zone_prefix
            self.app.push_screen(
                ConfirmScreen(title="SUPPRIMER LA ZONE", message=f"Confirmer la suppression de {path_prefix!r} ?"),
                lambda confirmed: self._do_remove_zone(path_prefix, confirmed),
            )
            return
        if button_id == "check-permissions":
            self._check_permissions()

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
        error_widget.update("" if result.success else f"Erreur : {result.message}")
        if result.success:
            notify_reload_required(self, self._container, result.message)
        else:
            self.app.notify(result.message, severity="error")
        self._refresh_lists()

    def _add_user(self, values: dict[str, str] | None) -> None:
        if values is None:
            return
        if values["password"] != values["password_confirm"]:
            self.query_one("#form-error", Static).update("Les deux mots de passe ne correspondent pas.")
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
            self.query_one("#form-error", Static).update("Les deux mots de passe ne correspondent pas.")
            return
        repos = self._repos()
        if repos is None:
            return
        self._report(change_password(repos[0], username, values["password"]))

    def _create_zone(self, values: dict[str, str] | None) -> None:
        if values is None:
            return
        zone = AuthZone(
            path_prefix=values["path_prefix"],
            realm=values["realm"],
            allowed_users=tuple(item.strip() for item in values["allowed_users"].split(",") if item.strip()),
            allow_methods=tuple(item.strip().upper() for item in values["allow_methods"].split(",") if item.strip()),
        )
        repos = self._repos()
        if repos is None:
            return
        self._report(add_zone(repos[1], zone))

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
            error_widget.update("Erreur de configuration.")
            return
        lines = []
        ok = True
        for label, relative_path in (("users.json", config.paths.auth_file), ("zones.json", config.paths.auth_zones)):
            path = self._container.project_root / relative_path
            if not self._container.filesystem.exists(path):
                lines.append(f"[INFO] {label} absent ({path})")
                continue
            mode = self._container.filesystem.file_mode(path)
            # Masque 0o007 ("other" uniquement), pas 0o077 (2026-09-29,
            # meme incident que le mode 0640 lui-meme - voir
            # infrastructure/auth/users_repository.py) : le GROUPE dedie
            # doit desormais pouvoir lire ce fichier (le service tourne
            # sous ce groupe, jamais sous le compte interactif qui
            # l'ecrit) - seul un acces "other" reste une vraie fuite.
            strict = not (mode & 0o007)
            lines.append(f"[{'OK' if strict else 'AVERTISSEMENT'}] {label} permissions : {oct(mode)}")
            if not strict:
                ok = False
        error_widget.update("\n".join(lines))
        self.app.notify("Permissions verifiees." if ok else "Permissions trop permissives detectees.", severity="information" if ok else "error")

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
