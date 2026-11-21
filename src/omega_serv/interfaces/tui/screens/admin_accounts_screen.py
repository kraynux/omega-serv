"""Comptes de l'administration web (tableau de bord web, lot 3 ; decisions de l'auteur du 2026-11-16).

Ouvert depuis Instances -> Configuration distante -> Comptes. Les comptes se creent, se modifient et se suppriment
seulement ici ou par la CLI (`omega-serv admin-web account`), jamais depuis le web. Role `lecture` (Tableau de bord
seulement) ou `administration` (Tableau de bord et Administration). TOTP : deux methodes toujours proposees, QR code
pour scanner avec un autre appareil, et sans scan (secret par groupes de 4, lien otpauth) quand ce terminal est sur
le telephone meme qui porte l'application. Tout changement de compte ferme ses sessions web ouvertes."""
from __future__ import annotations

from typing import TYPE_CHECKING

from rich.text import Text
from textual.app import ComposeResult
from textual.containers import Container, Horizontal, Vertical, VerticalScroll
from textual.widgets import Button, DataTable, Footer, Header, Input, Static

from omega_serv.application.admin_web.manage_accounts import (
    LOW_BACKUP_CODES,
    AccountResult,
    add_account,
    confirm_totp,
    disable_totp,
    new_totp_secret,
    regenerate_backup_codes,
    remaining_backup_codes,
    remove_account,
    set_password,
    set_role,
)
from omega_serv.core.i18n import _
from omega_serv.domain.admin_web import qr, totp
from omega_serv.domain.admin_web.accounts import ROLES
from omega_serv.interfaces.tui.screens._base import OmegaScreen
from omega_serv.interfaces.tui.screens.confirm import ConfirmScreen
from omega_serv.interfaces.tui.screens.dynamic_form_screen import DynamicFormScreen

if TYPE_CHECKING:
    from omega_serv.bootstrap.container import DependencyContainer


def _role_choices() -> dict[str, list[tuple[str, str]]]:
    """Essai de l'auteur du 2026-11-17 : le role se choisit dans un menu deroulant, pas en le tapant."""
    return {"role": [(_("lecture - Tableau de bord seulement"), "lecture"),
                     (_("administration - Tableau de bord et Administration (actions)"), "administration")]}


def _role_error(values: dict[str, str]) -> str | None:
    if "role" in values and values["role"] not in ROLES:
        return _("Rôle : lecture ou administration.")
    if "password" in values and values["password"] != values.get("password2", values["password"]):
        return _("Les deux saisies du mot de passe diffèrent.")
    return None


class AdminAccountsScreen(OmegaScreen):
    def __init__(self, *, container: DependencyContainer) -> None:
        super().__init__()
        self._container = container
        self._selected: str | None = None

    def compose(self) -> ComposeResult:
        yield Header()
        with Vertical(classes="omega-panel omega-main-panel"):
            yield Static(_("ADMINISTRATION WEB - COMPTES"), classes="omega-title")
            yield Static(_("Lecture : Tableau de bord seulement. Administration : Tableau de bord et Administration ; "
                           "TOTP obligatoire pour ce rôle dès que l'administration web sort de cette machine. Tout "
                           "changement ferme les sessions web du compte."), classes="omega-hint")
            yield Static("", id="accounts-message", classes="omega-hint")
            yield DataTable(id="accounts-table")
        with Vertical(classes="omega-proxy-actions"):
            with Horizontal(classes="omega-actions omega-riposte-actions"):
                with Container(classes="omega-btn-frame"):
                    yield Button(_("Ajouter un compte"), id="add", variant="primary")
                with Container(classes="omega-btn-frame"):
                    yield Button(_("Mot de passe"), id="password", disabled=True)
                with Container(classes="omega-btn-frame"):
                    yield Button(_("Rôle"), id="role", disabled=True)
                with Container(classes="omega-btn-frame"):
                    yield Button(_("Sessions"), id="sessions")
            with Horizontal(classes="omega-actions omega-riposte-actions"):
                with Container(classes="omega-btn-frame"):
                    yield Button(_("Activer TOTP"), id="totp-enable", disabled=True)
                with Container(classes="omega-btn-frame"):
                    yield Button(_("Désactiver TOTP"), id="totp-disable", disabled=True)
                with Container(classes="omega-btn-frame"):
                    yield Button(_("Nouveaux codes de secours"), id="backup-codes", disabled=True)
            # Action destructrice a part (meme regle que l'ecran Instances, decision de l'auteur du 2026-11-15).
            with Horizontal(classes="omega-actions omega-riposte-actions"), Container(classes="omega-btn-frame"):
                yield Button(_("Supprimer"), id="remove", variant="error", disabled=True)
            with Horizontal(classes="omega-actions omega-riposte-actions omega-service-back"), \
                    Container(classes="omega-btn-frame"):
                yield Button(_("Retour"), id="back")
        yield Footer()

    def on_mount(self) -> None:
        table = self.query_one("#accounts-table", DataTable)
        table.cursor_type = "row"
        table.add_columns(_("Identifiant"), _("Rôle"), _("TOTP"), _("Codes de secours"))
        self._refresh()

    def _refresh(self) -> None:
        table = self.query_one("#accounts-table", DataTable)
        table.clear()
        try:
            accounts = self._container.admin_accounts.load()
        except Exception as error:  # noqa: BLE001 - fichier abime : message clair dans l'ecran, jamais un plantage
            self.query_one("#accounts-message", Static).update(str(error))
            return
        used = self._container.admin_used_backup_codes()
        low = []
        for account in accounts:
            left = remaining_backup_codes(account, used)
            codes = (_("{left} sur {total}").format(left=left, total=len(account.backup_code_hashes))
                     if account.totp_enabled else "-")
            if account.totp_enabled and left <= LOW_BACKUP_CODES:
                low.append(account.username)
            table.add_row(account.username, account.role, _("activé") if account.totp_enabled else _("non"), codes,
                          key=account.username)
        message = self.query_one("#accounts-message", Static)
        if not accounts:
            message.update(_("Aucun compte : « Ajouter un compte »."))
        elif low:
            message.update(_("Peu de codes de secours restants pour {names} : « Nouveaux codes de secours ».").format(
                names=", ".join(low)))
        self._select(self._selected if any(a.username == self._selected for a in accounts) else None)

    def _select(self, username: str | None) -> None:
        self._selected = username
        for button_id in ("password", "role", "totp-enable", "totp-disable", "backup-codes", "remove"):
            self.query_one(f"#{button_id}", Button).disabled = username is None

    def on_data_table_row_highlighted(self, event: DataTable.RowHighlighted) -> None:
        if event.row_key is not None and event.row_key.value is not None:
            self._select(str(event.row_key.value))

    def on_data_table_row_selected(self, event: DataTable.RowSelected) -> None:
        self._select(str(event.row_key.value))

    def _role_of(self, username: str) -> str:
        try:
            return next((a.role for a in self._container.admin_accounts.load() if a.username == username), "lecture")
        except Exception:  # noqa: BLE001 - fichier abime : le menu part de « lecture »
            return "lecture"

    def _show(self, result: AccountResult) -> None:
        self.query_one("#accounts-message", Static).update(result.message)
        self.app.notify(result.message, severity="information" if result.success else "error")
        self._refresh()

    def on_button_pressed(self, event: Button.Pressed) -> None:
        button, name = event.button.id, self._selected
        if button == "back":
            self.dismiss()
        elif button == "sessions":
            from omega_serv.interfaces.tui.screens.admin_sessions_screen import AdminSessionsScreen

            self.app.push_screen(AdminSessionsScreen(container=self._container))
        elif button == "add":
            self.push_form(DynamicFormScreen(
                title=_("AJOUTER UN COMPTE"),
                fields=[("username", _("Identifiant"), ""), ("password", _("Mot de passe (12 caractères au moins)"), ""),
                        ("password2", _("Mot de passe (à nouveau)"), ""),
                        ("role", _("Rôle"), "lecture")],
                password_fields=frozenset({"password", "password2"}), validate=_role_error, choices=_role_choices()),
                self._added)
        elif name is None:
            return
        elif button == "password":
            self.push_form(DynamicFormScreen(
                title=_("MOT DE PASSE DE {name}").format(name=name),
                fields=[("password", _("Nouveau mot de passe (12 caractères au moins)"), ""),
                        ("password2", _("Mot de passe (à nouveau)"), "")],
                password_fields=frozenset({"password", "password2"}), validate=_role_error),
                lambda values: self._show(set_password(self._container.admin_accounts, name, values["password"]))
                if values else None)
        elif button == "role":
            self.push_form(DynamicFormScreen(
                title=_("RÔLE DE {name}").format(name=name),
                fields=[("role", _("Rôle"), self._role_of(name))], validate=_role_error, choices=_role_choices()),
                lambda values: self._show(set_role(self._container.admin_accounts, name, values["role"]))
                if values else None)
        elif button == "totp-enable":
            self.app.push_screen(TotpEnrolScreen(container=self._container, username=name),
                                 lambda _result: self._refresh())
        elif button == "totp-disable":
            self.app.push_screen(ConfirmScreen(title=_("DÉSACTIVER TOTP"), message=_(
                "Désactiver TOTP pour {name!r} ? Ses codes de secours sont effacés.").format(name=name)),
                lambda ok: self._show(disable_totp(self._container.admin_accounts, name)) if ok else None)
        elif button == "backup-codes":
            self.app.push_screen(ConfirmScreen(title=_("NOUVEAUX CODES DE SECOURS"), message=_(
                "Générer 10 nouveaux codes de secours pour {name!r} ? Les anciens ne marcheront plus ; le TOTP du "
                "téléphone ne change pas.").format(name=name)),
                lambda ok: self._regenerate(name) if ok else None)
        elif button == "remove":
            self.app.push_screen(ConfirmScreen(title=_("SUPPRIMER LE COMPTE"), message=_(
                "Supprimer le compte {name!r} ? Ses sessions web ouvertes sont fermées.").format(name=name)),
                lambda ok: self._show(remove_account(self._container.admin_accounts, name)) if ok else None)

    def _regenerate(self, name: str) -> None:
        result = regenerate_backup_codes(self._container.admin_accounts, name)
        self._show(result)
        if result.backup_codes:
            self.app.push_screen(BackupCodesScreen(username=name, codes=result.backup_codes))

    def _added(self, values: dict[str, str] | None) -> None:
        if values is None:
            return
        result = add_account(self._container.admin_accounts, values["username"], values["password"], values["role"])
        if not result.success:
            self.report_form_error(result.message)
            return
        self._show(result)


class BackupCodesScreen(OmegaScreen):
    """Les 10 nouveaux codes de secours, affiches une seule fois (omega-serv n'en garde que l'empreinte)."""

    def __init__(self, *, username: str, codes: tuple[str, ...]) -> None:
        super().__init__()
        self._username = username
        self._codes = codes

    def compose(self) -> ComposeResult:
        yield Header()
        with VerticalScroll(classes="omega-panel"):
            yield Static(_("CODES DE SECOURS - {name}").format(name=self._username), classes="omega-title")
            yield Static(_("Un seul usage chacun ; notez-les maintenant (papier, ou gestionnaire de mots de passe sur un "
                           "autre appareil) : ils ne seront plus affichés."), classes="omega-hint")
            yield Static(Text("\n".join(self._codes), style="bold"), id="backup-codes-list")
        with Horizontal(classes="omega-actions omega-riposte-actions omega-service-back"), \
                Container(classes="omega-btn-frame"):
            yield Button(_("Retour"), id="back")
        yield Footer()

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "back":
            self.dismiss()


class TotpEnrolScreen(OmegaScreen):
    """Activation TOTP : QR code (blanc sur noir, lisible quel que soit le theme), secret par groupes de 4 et lien
    otpauth, puis le code affiche par l'application ; les codes de secours apres un code juste seulement."""

    def __init__(self, *, container: DependencyContainer, username: str) -> None:
        super().__init__()
        self._container = container
        self._username = username
        self._secret = new_totp_secret()

    def compose(self) -> ComposeResult:
        uri = totp.otpauth_uri(self._secret, self._username, f"omega-serv {self._container.project_root.name}")
        yield Header()
        with VerticalScroll(classes="omega-panel"):
            yield Static(_("ACTIVER TOTP - {name}").format(name=self._username), classes="omega-title")
            yield Static(_("1. Scannez ce QR code avec l'application d'authentification (Aegis, FreeOTP, 2FAS...) "
                           "depuis un autre appareil :"), classes="omega-hint")
            yield Static(Text("\n".join(qr.to_text(qr.encode(uri))), style="bright_white on black"), id="totp-qr")
            yield Static(_("Sans scan : « Copier le secret » puis collez-le dans l'application (saisie manuelle, type "
                           "« basé sur le temps »), ou « Copier le lien » puis ouvrez-le sur l'appareil qui a "
                           "l'application."), classes="omega-hint")
            yield Static(Text(totp.grouped(self._secret), style="bold"), id="totp-secret")
            yield Static(Text(uri), id="totp-uri")
            yield Static(_("2. Code à 6 chiffres affiché par l'application :"), classes="omega-subtitle")
            yield Input(id="totp-code")
            yield Static("", id="totp-result", classes="omega-hint")
        with Horizontal(classes="omega-actions omega-riposte-actions"):
            with Container(classes="omega-btn-frame"):
                yield Button(_("Valider le code"), id="confirm-code", variant="primary")
            with Container(classes="omega-btn-frame"):
                yield Button(_("Copier le secret"), id="copy-secret")
            with Container(classes="omega-btn-frame"):
                yield Button(_("Copier le lien"), id="copy-uri")
        with Horizontal(classes="omega-actions omega-riposte-actions omega-service-back"), \
                Container(classes="omega-btn-frame"):
            yield Button(_("Retour"), id="back")
        yield Footer()

    def _copy(self, text: str, what: str) -> None:
        """Presse-papiers du systeme (xclip, wl-copy...) et, en plus, copie par le terminal (OSC 52) : utile par SSH,
        ou le presse-papiers de cette machine n'est pas celui de la personne."""
        clipboard = self._container.clipboard
        tool = clipboard.copy(text) if clipboard is not None else ""
        self.app.copy_to_clipboard(text)
        self.app.notify(_("{what} copié dans le presse-papiers ({tool}).").format(what=what, tool=tool) if tool else _(
            "{what} envoyé au presse-papiers du terminal (copie acceptée selon le terminal ; sinon, recopiez le texte "
            "affiché).").format(what=what), timeout=8)

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "back":
            self.dismiss()
            return
        if event.button.id == "copy-secret":
            self._copy(self._secret, _("Secret"))
            return
        if event.button.id == "copy-uri":
            self._copy(totp.otpauth_uri(self._secret, self._username, f"omega-serv {self._container.project_root.name}"),
                       _("Lien"))
            return
        if event.button.id != "confirm-code":
            return
        result = confirm_totp(self._container.admin_accounts, self._username, self._secret,
                              self.query_one("#totp-code", Input).value)
        output = self.query_one("#totp-result", Static)
        if not result.success:
            output.update(result.message)
            return
        codes = "\n".join(f"   {code}" for code in result.backup_codes)
        output.update(result.message + "\n" + _("Codes de secours (un seul usage chacun ; notez-les maintenant, ils ne "
                                                "seront plus affichés) :") + "\n" + codes)
        self.query_one("#confirm-code", Button).disabled = True
