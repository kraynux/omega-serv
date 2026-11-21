# Copyright (c) 2026 kraynux - kraynux@proton.me - Licence MIT (voir fichier LICENSE)
"""Assistant de profil personnalise (projets 3.0.0 §1, §B, §7.1 ; decisions de l'auteur des 2026-11-07 et
2026-11-15). Choix par listes (jamais de texte libre a deviner), verification en direct : erreurs d'identification
sous chaque champ, trous bloquants, trous a accepter un par un. « Enregistrer » n'est actif que si tout est bon ; une
saisie fautive ne ferme jamais l'ecran et ne remet rien a zero."""
from __future__ import annotations

from typing import TYPE_CHECKING

from textual.app import ComposeResult
from textual.containers import Container, Horizontal, Vertical, VerticalScroll
from textual.widgets import Button, Checkbox, Footer, Header, Input, Select, Static

from omega_serv.application.config.create_custom_profile import (
    CustomProfileCheck,
    build_custom_profile,
    check_custom_profile,
)
from omega_serv.application.config.load_config import load_config
from omega_serv.core.i18n import _
from omega_serv.domain.config.custom_profile import (
    DESCRIPTION_MAX,
    LABEL_MAX,
    choices,
    minimal_selection,
)
from omega_serv.interfaces.tui.screens._base import OmegaScreen

if TYPE_CHECKING:
    from omega_serv.bootstrap.container import DependencyContainer
    from omega_serv.domain.config.entities import OmegaServConfig


class CustomProfileScreen(OmegaScreen):
    def __init__(self, *, container: DependencyContainer, base_selection: dict[str, str] | None = None) -> None:
        super().__init__()
        self._container = container
        self._selection = {**minimal_selection(), **(base_selection or {})}
        self._accepted: set[str] = set()
        self._accept_codes: tuple[str, ...] = ()
        self._check: CustomProfileCheck | None = None

    def compose(self) -> ComposeResult:
        yield Header()
        with VerticalScroll(classes="omega-panel omega-form-panel"):
            yield Static(_("CRÉER UN PROFIL PERSONNALISÉ"), classes="omega-title")
            yield Static(_("Point de départ : un serveur web minimal, sans protection. Ce que le cœur HTTP impose "
                           "(analyse stricte, confinement au webroot, rejet de la traversée) reste toujours actif. "
                           "Le profil fixe la sécurité et les options ; adresse, port, TLS, chemins et journaux "
                           "restent ceux de l'instance."), classes="omega-hint")
            yield Static(_("Nom (fichier, 3 à 32 : a-z 0-9 - _)"), classes="omega-subtitle")
            yield Input(id="name-input", max_length=32)
            yield Static("", id="name-error", classes="omega-hint")
            yield Static(_("Libellé affiché (tableau de bord, {maximum} caractères au plus)").format(maximum=LABEL_MAX),
                         classes="omega-subtitle")
            yield Input(id="label-input", max_length=LABEL_MAX)
            yield Static("", id="label-error", classes="omega-hint")
            yield Static(_("Description (facultative, {maximum} caractères au plus)").format(maximum=DESCRIPTION_MAX),
                         classes="omega-subtitle")
            yield Input(id="description-input", max_length=DESCRIPTION_MAX)
            yield Static("", id="description-error", classes="omega-hint")
            for choice in choices():
                yield Static(choice.label, classes="omega-subtitle")
                yield Select([(label, value) for value, label in choice.values], id=f"choice-{choice.key}",
                             value=self._selection[choice.key], allow_blank=False)
            yield Static(_("VÉRIFICATION"), classes="omega-subtitle")
            yield Static("", id="blocking", classes="omega-hint")
            yield Vertical(id="accept-box")
        with Vertical(classes="omega-proxy-actions"):
            with Horizontal(classes="omega-actions omega-riposte-actions"), Container(classes="omega-btn-frame"):
                yield Button(_("Enregistrer le profil"), id="save", variant="primary", disabled=True)
            with Horizontal(classes="omega-actions omega-riposte-actions omega-service-back"), \
                    Container(classes="omega-btn-frame"):
                yield Button(_("Retour"), id="back")
        yield Footer()

    def on_mount(self) -> None:
        self._recheck()

    def _config(self) -> OmegaServConfig | None:
        result = load_config(self._container.configuration, self._container.config_file)
        return result.config if result.success else None

    def _values(self) -> tuple[str, str, str]:
        return (self.query_one("#name-input", Input).value.strip(), self.query_one("#label-input", Input).value,
                self.query_one("#description-input", Input).value)

    def _recheck(self) -> None:
        config = self._config()
        if config is None:
            self.query_one("#blocking", Static).update(_("Configuration actuelle illisible : corrigez-la d'abord."))
            self.query_one("#save", Button).disabled = True
            return
        name, label, description = self._values()
        check = check_custom_profile(name, label, description, self._selection, self._accepted,
                                     set(self._container.profiles.list_profile_names()), config)
        self._check = check
        for field in ("name", "label", "description"):
            self.query_one(f"#{field}-error", Static).update(
                f"[$error]{check.field_errors[field]}[/]" if field in check.field_errors else "")
        self.query_one("#blocking", Static).update(
            "\n".join(f"[$error]{_('Bloquant')} : {message}[/]" for message in check.blocking)
            or _("Aucun point bloquant."))
        codes = tuple(code for code, _message in check.to_accept)
        if codes != self._accept_codes:
            self._accept_codes = codes
            box = self.query_one("#accept-box", Vertical)
            box.remove_children()
            # Sans id : la liste est reconstruite (retrait asynchrone) ; le code du trou est porte par `name`.
            # Le point est un paragraphe a part (il revient a la ligne) : en libelle de case il debordait de
            # 60 colonnes et la boite, a hauteur fixe, coupait la fin du formulaire (constat de l'auteur 2026-11-15).
            box.mount_all([Vertical(Static(message, classes="omega-hint omega-accept-message"),
                                    Checkbox(_("J'accepte ce point"), code in self._accepted, name=code,
                                             classes="omega-accept-hole"),
                                    classes="omega-accept-item")
                           for code, message in check.to_accept])
        self.query_one("#save", Button).disabled = not check.can_save

    def on_input_changed(self, _event: Input.Changed) -> None:
        self._recheck()

    def on_select_changed(self, event: Select.Changed) -> None:
        if event.select.id and event.select.id.startswith("choice-") and isinstance(event.value, str):
            self._selection[event.select.id.removeprefix("choice-")] = event.value
            self._recheck()

    def on_checkbox_changed(self, event: Checkbox.Changed) -> None:
        if event.checkbox.has_class("omega-accept-hole") and event.checkbox.name:
            code = event.checkbox.name
            (self._accepted.add if event.value else self._accepted.discard)(code)
            self._recheck()

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "back":
            self.dismiss()
            return
        if event.button.id == "save":
            self._recheck()
            if self._check is None or not self._check.can_save:
                return
            name, label, description = self._values()
            profile = build_custom_profile(name, label, description, self._selection,
                                           self._container.clock.now().isoformat())
            try:
                self._container.profiles.save_custom_profile(profile)
            except OSError as exc:
                self.query_one("#blocking", Static).update(_("Enregistrement impossible : {exc}").format(exc=exc))
                return
            self.app.notify(_("Profil personnalisé enregistré : {name}. Appliquez-le depuis l'écran Profils.").format(
                name=name))
            self.dismiss()
