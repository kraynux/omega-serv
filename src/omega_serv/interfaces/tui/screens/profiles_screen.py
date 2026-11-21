"""Ecran Profils (plan interface §6, menu 2.1-2.3) : liste + detail +
lancement de l'application (le diff/la confirmation eux-memes vivent
dans apply_profile_screen.py, jamais melanges ici - meme separation que
la CLI `profile show` / `profile apply`)."""
from __future__ import annotations

from typing import TYPE_CHECKING

from textual.app import ComposeResult
from textual.containers import Container, Horizontal, Vertical, VerticalScroll
from textual.widgets import Button, DataTable, Footer, Header, Static

from omega_serv.core.i18n import _
from omega_serv.domain.config.exceptions import ProfileLoadError, ProfileNotFoundError
from omega_serv.interfaces.tui.screens._base import OmegaScreen, main_menu_title
from omega_serv.interfaces.tui.screens.apply_profile_screen import ApplyProfileScreen
from omega_serv.interfaces.tui.screens.confirm import ConfirmScreen
from omega_serv.interfaces.tui.screens.custom_profile_screen import CustomProfileScreen

if TYPE_CHECKING:
    from omega_serv.bootstrap.container import DependencyContainer


class ProfilesScreen(OmegaScreen):
    """Liste des profils (`profile list`), detail au clic (`profile
    show`), bouton "Appliquer" vers ApplyProfileScreen (`profile apply`)."""

    def __init__(self, *, container: DependencyContainer) -> None:
        super().__init__()
        self._container = container
        self._selected_name: str | None = None

    def compose(self) -> ComposeResult:
        yield Header()
        with VerticalScroll(classes="omega-panel omega-main-panel"):
            yield main_menu_title(_("PROFILS"))
            yield DataTable(id="profiles-table")
            yield Static(_("Sélectionnez un profil pour voir son détail."), id="profile-detail", classes="omega-hint")
        with Vertical(classes="omega-proxy-actions"):
            with Horizontal(classes="omega-actions omega-riposte-actions"):
                with Container(classes="omega-btn-frame"):
                    yield Button(_("Appliquer"), id="apply", variant="primary", disabled=True)
                with Container(classes="omega-btn-frame"):
                    yield Button(_("Créer un profil personnalisé"), id="create-custom")
                with Container(classes="omega-btn-frame"):
                    yield Button(_("Supprimer"), id="delete-custom", variant="error", disabled=True)
            with Horizontal(classes="omega-actions omega-riposte-actions omega-service-back"), \
                    Container(classes="omega-btn-frame"):
                yield Button(_("Retour"), id="back")
        yield Footer()

    def on_mount(self) -> None:
        table = self.query_one("#profiles-table", DataTable)
        table.cursor_type = "row"
        table.add_columns(_("Nom"), _("Type"), _("Libellé"))
        self._refresh_table()

    def _refresh_table(self) -> None:
        table = self.query_one("#profiles-table", DataTable)
        table.clear()
        provided = set(self._container.profiles.provided_profile_names())
        for name in sorted(self._container.profiles.list_profile_names(), key=lambda n: (n not in provided, n)):
            try:
                label = self._container.profiles.load_profile(name).label
            except (ProfileNotFoundError, ProfileLoadError):
                label = ""
            table.add_row(name, _("fourni") if name in provided else _("personnalisé"), label, key=name)
        self._selected_name = None
        self.query_one("#apply", Button).disabled = True
        self.query_one("#delete-custom", Button).disabled = True

    def on_data_table_row_selected(self, event: DataTable.RowSelected) -> None:
        name = str(event.row_key.value)
        self._selected_name = name
        try:
            profile = self._container.profiles.load_profile(name)
        except (ProfileNotFoundError, ProfileLoadError) as exc:
            self.query_one("#profile-detail", Static).update(_("Erreur : {exc}").format(exc=exc))
            self.query_one("#apply", Button).disabled = True
            return
        description = profile.description if profile.custom else _(profile.description)
        title = " - ".join((profile.name, profile.label)) if profile.label else profile.name  # noqa: FLY002 - inventaire i18n
        self.query_one("#profile-detail", Static).update(_("[b]{name}[/b]\n{description}").format(name=title, description=description))
        self.query_one("#apply", Button).disabled = False
        self.query_one("#delete-custom", Button).disabled = not profile.custom

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "back":
            self.dismiss()
            return
        if event.button.id == "apply" and self._selected_name is not None:
            self.app.push_screen(ApplyProfileScreen(container=self._container, profile_name=self._selected_name))
            return
        if event.button.id == "create-custom":
            # Non modifiable apres coup (decision 2026-11-07) : on en recree un, en repartant au besoin des choix
            # du profil personnalise selectionne.
            base = None
            if self._selected_name is not None:
                try:
                    selected = self._container.profiles.load_profile(self._selected_name)
                    base = selected.selection if selected.custom else None
                except (ProfileNotFoundError, ProfileLoadError):
                    base = None
            self.app.push_screen(CustomProfileScreen(container=self._container, base_selection=base),
                                 lambda _result: self._refresh_table())
            return
        if event.button.id == "delete-custom" and self._selected_name is not None:
            name = self._selected_name
            self.app.push_screen(
                ConfirmScreen(title=_("SUPPRIMER LE PROFIL PERSONNALISÉ"),
                              message=_("Supprimer définitivement le profil {name!r} ? La configuration actuelle "
                                        "n'est pas modifiée.").format(name=name)),
                lambda confirmed: self._delete_custom(name, confirmed),
            )

    def _delete_custom(self, name: str, confirmed: bool | None) -> None:
        if not confirmed:
            return
        if self._container.profiles.delete_custom_profile(name):
            self.app.notify(_("Profil supprimé : {name}").format(name=name))
        self._refresh_table()
