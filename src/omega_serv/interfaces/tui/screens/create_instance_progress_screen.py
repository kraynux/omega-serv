# Copyright (c) 2026 kraynux - kraynux@proton.me - Licence MIT (voir fichier LICENSE)
"""Ecran de progression de la creation d'instance (OMEGA-SERV_PLAN-
DETAILLE_MULTI_INSTANCE.md §5/§9 Phase C) - retour utilisateur : jamais
un simple spinner generique pendant que `create_instance()` tourne
(jusqu'a ~1 minute, venv+pip reels), 6 etapes NOMMEES et visibles au
fur et a mesure.

`create_instance_runner` (application/instances/create_instance.py,
synchrone - venv/pip sont des appels bloquants reels) tourne dans un
thread de travail Textual (`run_worker(thread=True)`) pour ne jamais
geler la boucle asyncio principale pendant l'operation ; chaque mise a
jour de progression est relayee vers l'UI via `App.call_from_thread`
(premiere utilisation de ce patron dans ce projet - aucun besoin
similaire avant celui-ci, jamais introduit par anticipation)."""
from __future__ import annotations

from typing import TYPE_CHECKING, ClassVar

from textual.app import ComposeResult
from textual.binding import Binding, BindingType
from textual.containers import Container, Horizontal, Vertical
from textual.widgets import Button, Footer, Header, Static

from omega_serv.interfaces.tui.screens._base import OmegaScreen

if TYPE_CHECKING:
    from pathlib import Path

    from omega_serv.bootstrap.container import DependencyContainer


class CreateInstanceProgressScreen(OmegaScreen):
    BINDINGS: ClassVar[list[BindingType]] = [Binding("escape", "back", "Retour", show=True)]

    def __init__(
        self, *, container: DependencyContainer, source_root: Path, name: str,
        target_parent_dir: Path, bind: str, port: int, service_name: str,
    ) -> None:
        super().__init__()
        self._container = container
        self._source_root = source_root
        self._instance_name = name
        self._target_parent_dir = target_parent_dir
        self._bind = bind
        self._port = port
        self._service_name = service_name
        self._finished = False
        self._success = False

    def compose(self) -> ComposeResult:
        yield Header()
        with Vertical(classes="omega-panel"):
            yield Static("CREATION D'INSTANCE", classes="omega-title")
            target_root = self._target_parent_dir / self._instance_name
            yield Static(f"Nom : {self._instance_name}  -  Repertoire : {target_root}", classes="omega-hint")
            yield Static("En attente...", id="progress-label", classes="omega-hint")
            yield Static("", id="progress-result", classes="omega-hint")
            with Horizontal(classes="omega-actions"), Container(classes="omega-btn-frame"):
                yield Button("Fermer", id="close", disabled=True)
        yield Footer()

    def on_mount(self) -> None:
        self.run_worker(self._run_creation, thread=True, exclusive=True)

    def _run_creation(self) -> None:
        runner = self._container.create_instance_runner
        if runner is None:
            self.app.call_from_thread(self._finish, "Fonction de creation d'instance indisponible dans cet environnement.")
            return
        error = runner(
            self._source_root, self._instance_name, self._target_parent_dir, self._bind, self._port, self._service_name,
            self._container.filesystem, self._container.instance_registry, self._container.clock,
            self._report_step,
        )
        self.app.call_from_thread(self._finish, error)

    def _report_step(self, index: int, total: int, label: str) -> None:
        self.app.call_from_thread(self._update_progress, index, total, label)

    def _update_progress(self, index: int, total: int, label: str) -> None:
        self.query_one("#progress-label", Static).update(f"Etape {index}/{total} : {label}...")

    def _finish(self, error: str | None) -> None:
        self._finished = True
        self._success = error is None
        if error is None:
            self.query_one("#progress-label", Static).update("Etape 6/6 : Enregistrement dans le registre...")
            self.query_one("#progress-result", Static).update("Instance creee avec succes.")
        else:
            self.query_one("#progress-result", Static).update(f"Echec : {error}")
        self.query_one("#close", Button).disabled = False

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "close" and self._finished:
            self.dismiss()

    def action_back(self) -> None:
        if self._finished:
            self.dismiss()
        # Sinon ignore - jamais d'annulation en cours d'operation (V1),
        # le worker continuerait de tourner en arriere-plan meme si
        # l'ecran etait ferme, laissant l'utilisateur sans retour.
