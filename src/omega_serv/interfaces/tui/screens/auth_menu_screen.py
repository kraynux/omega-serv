"""Sous-ecran Authentification (plan interface §7.1) - liste/ajout/
suppression d'utilisateurs et de zones protegees, verification des
permissions. Le mot de passe est toujours saisi en double masque
(DynamicFormScreen.password_fields), jamais visible a l'ecran ni passe
en argument (meme regle que la CLI, `_resolve_password`)."""
from __future__ import annotations

from typing import TYPE_CHECKING

from textual.app import ComposeResult
from textual.containers import Container, Horizontal, VerticalScroll
from textual.widgets import Button, Footer, Header, Static

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

    def compose(self) -> ComposeResult:
        yield Header()
        with VerticalScroll(classes="omega-panel"):
            yield Static("AUTHENTIFICATION", classes="omega-title")
            yield Static("", id="form-error", classes="omega-hint")
            yield Static("", id="auth-list")
            with Horizontal(classes="omega-actions"):
                with Container(classes="omega-btn-frame"):
                    yield Button("Ajouter un utilisateur", id="add-user", variant="primary")
                with Container(classes="omega-btn-frame"):
                    yield Button("Supprimer un utilisateur", id="remove-user", variant="error")
            with Horizontal(classes="omega-actions"), Container(classes="omega-btn-frame"):
                yield Button("Changer un mot de passe", id="change-password", variant="primary")
            with Horizontal(classes="omega-actions"):
                with Container(classes="omega-btn-frame"):
                    yield Button("Creer une zone", id="create-zone", variant="primary")
                with Container(classes="omega-btn-frame"):
                    yield Button("Supprimer une zone", id="remove-zone", variant="error")
            with Horizontal(classes="omega-actions"):
                with Container(classes="omega-btn-frame"):
                    yield Button("Verifier les permissions", id="check-permissions")
                with Container(classes="omega-btn-frame"):
                    yield Button("Retour", id="back")
        yield Footer()

    def on_mount(self) -> None:
        self._refresh_list()

    def _config(self) -> OmegaServConfig | None:
        result = load_config(self._container.configuration, self._container.config_file)
        return result.config if result.success else None

    def _refresh_list(self) -> None:
        config = self._config()
        widget = self.query_one("#auth-list", Static)
        if config is None:
            widget.update("Erreur de configuration.")
            return
        users_repo = self._container.build_users_repository(self._container.project_root / config.paths.auth_file)
        zones_repo = self._container.build_auth_zones_repository(self._container.project_root / config.paths.auth_zones)
        users = users_repo.load()
        zones = zones_repo.load()

        lines = ["Utilisateurs :"]
        if users:
            lines.extend(f"  - {u.username}" for u in users)
        else:
            lines.append("  (aucun)")
        lines.append("Zones protegees :")
        if not zones:
            lines.append("  (aucune)")
        for zone in zones:
            methods = ", ".join(zone.allow_methods) or "toutes"
            lines.append(f"  - {zone.path_prefix} (realm={zone.realm!r}, utilisateurs={list(zone.allowed_users)}, methodes={methods})")
        widget.update("\n".join(lines))

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
        if button_id == "remove-user":
            self.app.push_screen(
                DynamicFormScreen(title="SUPPRIMER UN UTILISATEUR", fields=[("username", "Nom d'utilisateur", "")]),
                self._remove_user,
            )
            return
        if button_id == "change-password":
            self.app.push_screen(
                DynamicFormScreen(
                    title="CHANGER UN MOT DE PASSE",
                    fields=[
                        ("username", "Nom d'utilisateur", ""),
                        ("password", "Nouveau mot de passe", ""),
                        ("password_confirm", "Confirmer le mot de passe", ""),
                    ],
                    password_fields=frozenset({"password", "password_confirm"}),
                ),
                self._change_password,
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
        if button_id == "remove-zone":
            self.app.push_screen(
                DynamicFormScreen(title="SUPPRIMER UNE ZONE", fields=[("path_prefix", "Prefixe URL", "")]),
                self._remove_zone,
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
        self._refresh_list()

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

    def _remove_user(self, values: dict[str, str] | None) -> None:
        if values is None:
            return
        self.app.push_screen(
            ConfirmScreen(title="SUPPRIMER L'UTILISATEUR", message=f"Confirmer la suppression de {values['username']!r} ?"),
            lambda confirmed: self._do_remove_user(values["username"], confirmed),
        )

    def _do_remove_user(self, username: str, confirmed: bool | None) -> None:
        if not confirmed:
            return
        repos = self._repos()
        if repos is None:
            return
        self._report(remove_user(repos[0], username))

    def _change_password(self, values: dict[str, str] | None) -> None:
        if values is None:
            return
        if values["password"] != values["password_confirm"]:
            self.query_one("#form-error", Static).update("Les deux mots de passe ne correspondent pas.")
            return
        repos = self._repos()
        if repos is None:
            return
        self._report(change_password(repos[0], values["username"], values["password"]))

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

    def _remove_zone(self, values: dict[str, str] | None) -> None:
        if values is None:
            return
        self.app.push_screen(
            ConfirmScreen(title="SUPPRIMER LA ZONE", message=f"Confirmer la suppression de {values['path_prefix']!r} ?"),
            lambda confirmed: self._do_remove_zone(values["path_prefix"], confirmed),
        )

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
            strict = not (mode & 0o077)
            lines.append(f"[{'OK' if strict else 'AVERTISSEMENT'}] {label} permissions : {oct(mode)}")
            if not strict:
                ok = False
        error_widget.update("\n".join(lines))
        self.app.notify("Permissions verifiees." if ok else "Permissions trop permissives detectees.", severity="information" if ok else "error")
