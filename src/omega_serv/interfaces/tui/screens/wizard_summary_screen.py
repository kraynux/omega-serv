"""Assistant premier lancement, etape 7/8 - resume final (meme diff que
spec §9.2, entre les valeurs par defaut et la configuration composee par
l'assistant) + confirmation d'ecriture (plan interface §11). L'ecriture
elle-meme passe par `container.configuration.save()`, qui sauvegarde deja
tout fichier existant avant ecrasement (JsonConfigRepository, comportement
etabli depuis la Phase 0) - aucune logique de sauvegarde supplementaire
necessaire ici meme si un `config/omega-serve.json` preexistait."""
from __future__ import annotations

from typing import TYPE_CHECKING

from textual.app import ComposeResult
from textual.containers import Container, Horizontal, VerticalScroll
from textual.widgets import Button, Footer, Header, Static

from omega_serv.core.i18n import _
from omega_serv.domain.config.defaults import builtin_safe_defaults
from omega_serv.domain.config.diff import diff_configs
from omega_serv.interfaces.tui.screens._base import OmegaScreen
from omega_serv.interfaces.tui.screens.wizard_service_screen import WizardServiceScreen

if TYPE_CHECKING:
    from omega_serv.bootstrap.container import DependencyContainer
    from omega_serv.interfaces.tui.screens.wizard_state import WizardState


class WizardSummaryScreen(OmegaScreen):
    def __init__(self, *, container: DependencyContainer, state: WizardState) -> None:
        super().__init__()
        self._container = container
        self._state = state

    def compose(self) -> ComposeResult:
        yield Header()
        with VerticalScroll(classes="omega-panel"):
            yield Static(_("ÉTAPE 7/8 : RÉSUMÉ"), classes="omega-title")
            yield Static("", id="summary-diff")
            with Horizontal(classes="omega-actions"):
                with Container(classes="omega-btn-frame"):
                    yield Button(_("Écrire la configuration"), id="write", variant="primary")
                with Container(classes="omega-btn-frame"):
                    yield Button(_("Précédent"), id="back")
        yield Footer()

    def on_mount(self) -> None:
        changes = diff_configs(builtin_safe_defaults().to_dict(), self._state.config.to_dict())
        if not changes:
            self.query_one("#summary-diff", Static).update(_("Aucune différence avec les valeurs par défaut."))
            return
        self.query_one("#summary-diff", Static).update(
            _("Profil : {value}\n\nModifications :\n").format(value=self._state.profile_name or _('(aucun)'))
            + "\n".join(str(change) for change in changes)
        )

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "back":
            self.dismiss()
            return
        if event.button.id == "write":
            self._write()

    def _write(self) -> None:
        self._container.configuration.save(self._container.config_file, self._state.config)
        self.app.notify(_("Configuration écrite dans {config_file}.").format(config_file=self._container.config_file))
        self.app.push_screen(WizardServiceScreen(container=self._container))
