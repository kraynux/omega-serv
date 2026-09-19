"""Ecran Simuler - equivalent TUI de `omega-serv active-defense
simulate` (plan_active_defense_omega_serv.md, Phase 4 : "ajouter
simulation, dry-run et explication de la decision dans CLI/TUI").
`preview_playbook_decision` est une lecture seule stricte (aucun
repository.save()/create() appele) - meme patron direct que
`close_incident`/`list_incidents` deja importes tels quels par
incidents_screen.py (l'application ne touche jamais infrastructure/ ici,
donc pas besoin d'un runner injecte comme pour waf_test_runner)."""
from __future__ import annotations

from typing import TYPE_CHECKING, cast

from textual.app import ComposeResult
from textual.containers import Container, Horizontal, Vertical
from textual.widgets import Button, Footer, Header, Input, Static

from omega_serv.application.active_defense.preview_playbook_decision import (
    preview_playbook_decision,
)
from omega_serv.domain.security.active_defense.policies import hash_payload
from omega_serv.domain.security.active_defense.value_objects import (
    KNOWN_ATTACK_CLASSES,
    AttackClass,
)
from omega_serv.interfaces.tui.screens._active_defense_collaborators_cache import (
    ActiveDefenseCollaboratorsCacheMixin,
)
from omega_serv.interfaces.tui.screens._base import OmegaScreen

if TYPE_CHECKING:
    from omega_serv.bootstrap.container import DependencyContainer


class ActiveDefenseSimulateScreen(ActiveDefenseCollaboratorsCacheMixin, OmegaScreen):
    def __init__(self, *, container: DependencyContainer) -> None:
        super().__init__()
        self._container = container
        self._reset_active_defense_cache()

    def compose(self) -> ComposeResult:
        yield Header()
        with Vertical(classes="omega-panel"):
            yield Static("ACTIVE DEFENSE - SIMULER", classes="omega-title")
            yield Static(
                "Observation synthetique : aucune ecriture n'est faite, aucun impact reseau "
                "(dry-run, plan Phase 4).",
                classes="omega-hint",
            )
            yield Input(value="203.0.113.42", id="sim-ip-input")
            yield Input(value="/wp-login.php", id="sim-path-input")
            yield Input(placeholder="user-agent", id="sim-user-agent-input")
            yield Input(value="scan", id="sim-attack-class-input")
            yield Input(value="10", id="sim-score-input")
            with Horizontal(classes="omega-actions"):
                with Container(classes="omega-btn-frame"):
                    yield Button("Simuler", id="simulate", variant="primary")
                with Container(classes="omega-btn-frame"):
                    yield Button("Retour", id="back")
            yield Static("", id="simulate-result", classes="omega-hint")
        yield Footer()

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "back":
            self.dismiss()
            return
        if event.button.id == "simulate":
            self._run_simulation()

    def _run_simulation(self) -> None:
        result_widget = self.query_one("#simulate-result", Static)
        active_defense = self._active_defense_or_none()
        if active_defense is None:
            result_widget.update(self._active_defense_error or "")
            return
        attack_class = self.query_one("#sim-attack-class-input", Input).value.strip() or "scan"
        if attack_class not in KNOWN_ATTACK_CLASSES:
            result_widget.update(
                f"Classe d'attaque inconnue : {attack_class!r} "
                f"(valeurs possibles : {', '.join(sorted(KNOWN_ATTACK_CLASSES))})."
            )
            return
        try:
            score_delta = int(self.query_one("#sim-score-input", Input).value.strip() or "0")
        except ValueError:
            result_widget.update("Score invalide (entier attendu).")
            return
        ip = self.query_one("#sim-ip-input", Input).value.strip() or "203.0.113.42"
        user_agent = self.query_one("#sim-user-agent-input", Input).value.strip()
        subject_id = f"{ip}:{hash_payload(user_agent.encode('utf-8'))}"

        preview = preview_playbook_decision(
            active_defense.threat_state_repository, active_defense.incident_repository,
            active_defense.deception_assignment_repository, self._container.clock, active_defense.config,
            subject_id=subject_id, attack_class=cast("AttackClass", attack_class), score_delta=score_delta,
        )
        lines = [
            f"Source (simulee) : {preview.subject_id}",
            f"Score : {preview.previous_score} -> {preview.projected_score}",
            f"Niveau : {preview.previous_level} -> {preview.projected_level}",
            *(f"  - {line}" for line in preview.explanation),
        ]
        result_widget.update("\n".join(lines))
