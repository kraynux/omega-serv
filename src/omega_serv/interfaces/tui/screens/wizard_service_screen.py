"""Assistant premier lancement, etape 8/8 - propose d'installer le
service systeme maintenant (plan interface §11, §9), de lancer le
serveur reellement au premier plan tout de suite, ou de le rappeler pour
plus tard (`omega-serv.sh serve`). Reutilise `ServiceScreen` telle quelle
pour l'installation (aucune nouvelle logique d'installation ici).

"Lancer maintenant" (retour utilisateur 2026-09-09) : le seul rappel
existant ("Terminer" + toast ephemere "lancez `omega-serv.sh serve`
quand vous etes pret") s'est revele trop discret en pratique - un
utilisateur reel a fini l'assistant, cru le serveur deja actif, et
constate que rien n'ecoutait sur le port configure. Ce bouton attend
reellement `container.serve_foreground_runner` (bloquant jusqu'a
Ctrl+C/SIGTERM, meme coroutine partagee que la CLI `cmd_serve` via
`run_server_until_stopped` - jamais dupliquee) sous `_maybe_suspend()`
(meme mecanisme que sudo/lnav : rend la main au vrai terminal).
**Doit rester `await`, jamais un appel synchrone enveloppe dans
`asyncio.run()`** : `App.suspend()` ne suspend jamais la boucle asyncio
de Textual elle-meme (seulement le pilote du terminal), donc imbriquer
un second `asyncio.run()` a l'interieur de ce gestionnaire leve
`RuntimeError: asyncio.run() cannot be called from a running event
loop` - verifie empiriquement avant d'ecrire ce commentaire, premiere
version de ce bouton reellement cassee de cette maniere. "Terminer"
depile tout l'assistant d'un coup (pas ecran par ecran) pour revenir
directement a l'accueil."""
from __future__ import annotations

from typing import TYPE_CHECKING

from textual.app import ComposeResult
from textual.containers import Container, Horizontal, Vertical
from textual.widgets import Button, Footer, Header, Static

from omega_serv.interfaces.tui.screens._base import OmegaScreen
from omega_serv.interfaces.tui.screens.service_screen import ServiceScreen

if TYPE_CHECKING:
    from omega_serv.bootstrap.container import DependencyContainer


class WizardServiceScreen(OmegaScreen):
    def __init__(self, *, container: DependencyContainer) -> None:
        super().__init__()
        self._container = container

    def compose(self) -> ComposeResult:
        yield Header()
        with Vertical(classes="omega-panel"):
            yield Static("ETAPE 8/8 : SERVICE SYSTEME", classes="omega-title")
            yield Static(
                "La configuration a ete ecrite. Trois choix : lancer le serveur "
                "maintenant au premier plan (bloquant jusqu'a Ctrl+C), l'installer "
                "comme service systeme (demarrage automatique), ou terminer sans rien "
                "lancer (pensez alors a `omega-serv.sh serve` quand vous serez pret).",
                classes="omega-hint",
            )
            with Horizontal(classes="omega-actions"):
                with Container(classes="omega-btn-frame"):
                    yield Button("Lancer maintenant", id="launch-now", variant="primary")
                with Container(classes="omega-btn-frame"):
                    yield Button("Installer le service", id="install")
                with Container(classes="omega-btn-frame"):
                    yield Button("Terminer", id="finish")
        yield Footer()

    async def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "launch-now":
            await self._launch_now()
            return
        if event.button.id == "install":
            self.app.push_screen(ServiceScreen(container=self._container))
            return
        if event.button.id == "finish":
            self._pop_to_home()
            self.app.notify("Assistant termine. Lancez `omega-serv.sh serve` quand vous etes pret.")

    async def _launch_now(self) -> None:
        runner = self._container.serve_foreground_runner
        if runner is None:
            self.app.notify("Lancement direct indisponible dans cet environnement.", severity="error")
            return
        with self._maybe_suspend():
            try:
                result = await runner(self._container.config_file, self._container)
            except KeyboardInterrupt:
                result = 0
        self._pop_to_home()
        if result != 0:
            self.app.notify("Le serveur s'est arrete avec une erreur (voir le terminal).", severity="error")
        else:
            self.app.notify("Serveur arrete.")

    def _pop_to_home(self) -> None:
        while len(self.app.screen_stack) > 1 and type(self.app.screen).__name__ != "HomeScreen":
            self.app.pop_screen()
