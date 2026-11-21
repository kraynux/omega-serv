"""Ecran « Configuration distante » : reglages de l'administration web de l'instance pilotee (tableau de bord web,
lot 2, OMEGA-SERV_PLAN-DETAILLE_TABLEAU_DE_BORD_WEB.md ; place decidee par l'auteur les 2026-11-15 et 16 : ecran
Instances, bouton « Configuration distante »).

L'option `admin_web` s'active toujours dans « Voir options actives » (redemarrage complet) ; cet ecran regle
l'acces : adresse, port, TLS (obligatoire hors de cette machine), certificat, reseaux permis. Enregistrer valide
d'abord (aucune ecriture si un reglage est refuse, saisie gardee), puis demande un rechargement : le processus
d'administration relit ses reglages sans couper le site. Les avertissements (certificat absent, port deja pris par
une autre instance) disent pourquoi l'administration ne demarrerait pas - le site, lui, demarre toujours.

Lot 8 (2026-11-17, essai reel depuis un portable : « le but c'est pas qu'il aille taper des commandes dans un autre
terminal ») : bilan « prêt / ce qui manque » en haut de l'ecran, une ligne par point avec le bouton qui le regle
(Activer, Générer le certificat, Comptes, Redémarrer, Recharger) ; a l'enregistrement, TLS « Certificat dédié »
choisi tout seul hors boucle locale, et essai d'ecoute reel (port pris par un autre programme, adresse absente)."""
from __future__ import annotations

from dataclasses import replace
from typing import TYPE_CHECKING

from textual.app import ComposeResult
from textual.containers import Container, Horizontal, Vertical, VerticalScroll
from textual.widgets import Button, Footer, Header, Input, Select, Static

from omega_serv.application.admin_web import certificate_setup
from omega_serv.application.admin_web.firewall_setup import (
    FirewallRecord,
    firewall_label,
    firewall_sources,
)
from omega_serv.application.admin_web.readiness import (
    ACTION_ACCOUNTS,
    ACTION_CERTIFICATE,
    ACTION_ENABLE,
    ACTION_FIREWALL,
    ACTION_RELOAD,
    ACTION_RESTART,
)
from omega_serv.application.admin_web.web_theme import FOLLOW_TUI, WEB_THEMES
from omega_serv.application.config.load_config import load_config
from omega_serv.application.config.manage_option import set_option_enabled, waf_rule_packs_present
from omega_serv.core.i18n import _
from omega_serv.domain.admin_web.settings import (
    DEFAULT_PORT,
    OPTION_NAME,
    AdminWebSettings,
    binds_overlap,
    is_loopback_bind,
    validate_admin_web,
)
from omega_serv.domain.config.option import Option
from omega_serv.domain.services.systemd_unit import DEFAULT_SYSTEM_GROUP
from omega_serv.interfaces.tui.screens._base import OmegaScreen
from omega_serv.interfaces.tui.screens.engine_guard import save_guarded
from omega_serv.interfaces.tui.screens.restart_prompt import (
    notify_reload_required,
    notify_restart_required,
)
from omega_serv.ports.admin_web_setup_port import LISTEN_IN_USE, LISTEN_NO_ADDRESS

if TYPE_CHECKING:
    from textual.widget import Widget

    from omega_serv.bootstrap.container import DependencyContainer
    from omega_serv.domain.config.entities import OmegaServConfig

_TLS_CHOICES: tuple[tuple[str, str], ...] = (
    (_("Aucun - cette machine seulement (127.0.0.1)"), "none"),
    (_("Certificat du site (écran TLS)"), "site"),
    (_("Certificat dédié (chemins ci-dessous)"), "own"),
)


def _int_or_text(text: str) -> int | str:
    stripped = text.strip()
    return int(stripped) if stripped.isascii() and stripped.isdigit() else stripped


def _history_choices() -> tuple[tuple[str, str], ...]:
    return ((_("Activé"), "on"), (_("Désactivé"), "off"))


def _theme_choices() -> tuple[tuple[str, str], ...]:
    """Plan §9.7 (decision de l'auteur du 2026-11-17) : « comme la TUI » par defaut, ou l'un des 10 themes omega."""
    return ((_("Comme la TUI"), FOLLOW_TUI), *((name, name) for name in WEB_THEMES))


def _action_label(action: str) -> str:
    return {
        ACTION_ENABLE: _("Activer"),
        ACTION_CERTIFICATE: _("Générer le certificat"),
        ACTION_ACCOUNTS: _("Comptes"),
        ACTION_RESTART: _("Redémarrer"),
        ACTION_RELOAD: _("Recharger"),
        ACTION_FIREWALL: _("Ouvrir le port"),
    }.get(action, action)


class AdminWebScreen(OmegaScreen):
    def __init__(self, *, container: DependencyContainer) -> None:
        super().__init__()
        self._container = container

    def compose(self) -> ComposeResult:
        yield Header()
        with VerticalScroll(classes="omega-panel"):
            yield Static(_("ADMINISTRATION WEB - CONFIGURATION DISTANTE"), classes="omega-title")
            yield Static(_("État"), classes="omega-subtitle")
            yield Vertical(id="admin-web-state", classes="omega-readiness")
            yield Static("", id="admin-web-error", classes="omega-hint")
            yield Static(_("Adresse d'écoute"), classes="omega-subtitle")
            yield Static(_("127.0.0.1 : depuis cette machine seulement. Adresse Tailscale ou du réseau local pour y "
                           "accéder depuis un autre appareil (TLS obligatoire alors). 0.0.0.0 : toutes les adresses."),
                         classes="omega-hint")
            yield Input(id="bind-input")
            yield Static(_("Port"), classes="omega-subtitle")
            yield Static(_("Toujours différent du port du site et de ceux des autres instances."), classes="omega-hint")
            yield Input(id="port-input")
            yield Static(_("Chiffrement (TLS)"), classes="omega-subtitle")
            yield Select(_TLS_CHOICES, allow_blank=False, value="none", id="tls-select")
            yield Static(_("Certificat dédié"), classes="omega-subtitle")
            yield Static(_("Chemins relatifs au dossier de l'instance, utilisés seulement avec « Certificat dédié »."),
                         classes="omega-hint")
            yield Input(id="certificate-input")
            yield Input(id="key-input")
            yield Static(_("Réseaux permis"), classes="omega-subtitle")
            yield Static(_("Séparés par des virgules. Une adresse hors de ces réseaux est refusée avant même la page de "
                           "connexion ; la connexion reste toujours exigée. Par défaut : cette machine, Tailscale et "
                           "le réseau local."), classes="omega-hint")
            yield Input(id="networks-input")
            yield Static(_("Historique"), classes="omega-subtitle")
            yield Static(_("Graphes de la machine et de cette instance, de 1 heure à 30 jours, dans la vue Historique "
                           "du tableau de bord.") + " " + _("Un relevé toutes les 10 s, gardé dans var/run/admin/."),
                         classes="omega-hint")
            yield Select(_history_choices(), allow_blank=False, value="on", id="history-select")
            yield Static(_("Thème du panneau web"), classes="omega-subtitle")
            yield Static(_("« Comme la TUI » suit le thème de cette instance (touche t). Chaque navigateur peut aussi "
                           "choisir le sien dans la barre du haut du panneau, gardé dans ce navigateur seulement."),
                         classes="omega-hint")
            yield Select(_theme_choices(), allow_blank=False, value=FOLLOW_TUI, id="theme-select")
            yield Static(_("Adresses IP dans la vue Trafic"), classes="omega-subtitle")
            yield Static(_("Masquées : dernier nombre à 0 en IPv4 (192.168.1.0), 48 premiers bits seulement en IPv6. "
                           "Le journal d'accès, lui, garde les adresses entières."), classes="omega-hint")
            yield Select(((_("Entières"), "full"), (_("Masquées"), "masked")), allow_blank=False, value="full",
                         id="mask-select")
        with Horizontal(classes="omega-actions omega-riposte-actions"):
            with Container(classes="omega-btn-frame"):
                yield Button(_("Enregistrer"), id="save", variant="primary")
            with Container(classes="omega-btn-frame"):
                yield Button(_("Comptes"), id="accounts")
            with Container(classes="omega-btn-frame"):
                yield Button(_("Maître"), id="master")
            with Container(classes="omega-btn-frame"):
                yield Button(_("Alertes"), id="alerts")
        with Horizontal(classes="omega-actions omega-riposte-actions omega-service-back"), \
                Container(classes="omega-btn-frame"):
            yield Button(_("Retour"), id="back")
        yield Footer()

    def on_mount(self) -> None:
        config = self._config()
        option = config.options.get(OPTION_NAME) if config is not None else None
        settings = AdminWebSettings.from_settings(option.settings if option is not None else {})
        self.query_one("#bind-input", Input).value = str(settings.bind)
        self.query_one("#port-input", Input).value = str(settings.port)
        if settings.tls in ("none", "site", "own"):
            self.query_one("#tls-select", Select).value = settings.tls
        self.query_one("#certificate-input", Input).value = str(settings.certificate_path)
        self.query_one("#key-input", Input).value = str(settings.private_key_path)
        self.query_one("#networks-input", Input).value = ", ".join(str(n) for n in settings.allowed_networks)
        self.query_one("#history-select", Select).value = "off" if settings.history is False else "on"
        self.query_one("#theme-select", Select).value = settings.theme if settings.theme in WEB_THEMES else FOLLOW_TUI
        self.query_one("#mask-select", Select).value = "masked" if settings.stats_mask_ip is True else "full"
        self._show_state(config)

    def _config(self) -> OmegaServConfig | None:
        result = load_config(self._container.configuration, self._container.config_file)
        return result.config if result.success else None

    def _show_state(self, config: OmegaServConfig | None) -> None:
        """Bilan « prêt / ce qui manque » (lot 8) : une ligne par point, son bouton s'il y a quelque chose a faire."""
        box = self.query_one("#admin-web-state", Vertical)
        box.remove_children()
        if config is None:
            box.mount(Static(_("Configuration illisible."), classes="omega-hint"))
            return
        rows: list[Widget] = []
        for item in self._container.admin_web_readiness(config):
            mark = {True: "✓", False: "✗", None: "•"}[item.ok]
            text = Static(f"{mark} {item.text}", classes="omega-readiness-text")
            if not item.action:
                rows.append(Horizontal(text, classes="omega-readiness-row"))
                continue
            # Pas d'id : le bilan est remonte a chaque rafraichissement (ids en double avant la fin du retrait).
            button = Button(_action_label(item.action), name=item.action, classes=f"omega-readiness-fix fix-{item.action}")
            # Essai de l'auteur du 2026-11-17 : bouton au style des autres (.omega-actions), sous le texte, a gauche.
            rows.append(Vertical(text, Horizontal(Container(button, classes="omega-btn-frame"),
                                                  classes="omega-actions omega-readiness-actions"),
                                 classes="omega-readiness-row"))
        box.mount(*rows)

    def _form_settings(self) -> AdminWebSettings:
        networks = [item.strip() for item in self.query_one("#networks-input", Input).value.split(",") if item.strip()]
        return AdminWebSettings(
            bind=self.query_one("#bind-input", Input).value.strip(),
            port=_int_or_text(self.query_one("#port-input", Input).value),  # type: ignore[arg-type]
            tls=str(self.query_one("#tls-select", Select).value),
            certificate_path=self.query_one("#certificate-input", Input).value.strip(),
            private_key_path=self.query_one("#key-input", Input).value.strip(),
            allowed_networks=tuple(networks),
            history=self.query_one("#history-select", Select).value != "off",
            theme=str(self.query_one("#theme-select", Select).value),
            stats_mask_ip=self.query_one("#mask-select", Select).value == "masked",
        )

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.has_class("omega-readiness-fix"):
            self._fix(event.button.name or "")
        elif event.button.id == "back":
            self.dismiss()
        elif event.button.id == "save":
            self._save()
        elif event.button.id == "accounts":
            self._open_accounts()
        elif event.button.id == "alerts":
            from omega_serv.interfaces.tui.screens.admin_alerts_screen import AdminAlertsScreen

            self.app.push_screen(AdminAlertsScreen(container=self._container))
        elif event.button.id == "master":
            from omega_serv.interfaces.tui.screens.admin_master_screen import AdminMasterScreen

            self.app.push_screen(AdminMasterScreen(container=self._container))

    def _open_accounts(self) -> None:
        from omega_serv.interfaces.tui.screens.admin_accounts_screen import AdminAccountsScreen

        self.app.push_screen(AdminAccountsScreen(container=self._container),
                             lambda _result: self._show_state(self._config()))

    # ------------------------------------------------------------------ boutons du bilan (lot 8)
    def _fix(self, action: str) -> None:
        if action == ACTION_ACCOUNTS:
            self._open_accounts()
        elif action == ACTION_ENABLE:
            self._enable()
        elif action == ACTION_CERTIFICATE:
            self._make_certificate()
        elif action == ACTION_FIREWALL:
            self._open_firewall()
        elif action == ACTION_RESTART:
            notify_restart_required(self, self._container, _(
                "L'administration web est lancée au démarrage du serveur."))
        elif action == ACTION_RELOAD:
            notify_reload_required(self, self._container, _("Administration web : rechargement demandé."))
            self._show_state(self._config())

    def _enable(self) -> None:
        config = self._config()
        if config is None:
            self.app.notify(_("Configuration introuvable ou invalide."), severity="error")
            return
        container = self._container
        result = set_option_enabled(config, OPTION_NAME, True,
                                    waf_rule_packs_present(container.filesystem, container.project_root))
        if not result.success or result.new_config is None:
            self.app.notify(result.message, severity="error")
            return
        new_config = result.new_config

        def after_save() -> None:
            self._show_state(new_config)
            notify_restart_required(self, container, _(
                "{message} Nécessite un REDÉMARRAGE COMPLET pour prendre effet (le processus d'administration web "
                "est lancé ou arrêté au démarrage du serveur).").format(message=result.message))

        save_guarded(self, container, config, new_config, after_save)

    def _make_certificate(self) -> None:
        config = self._config()
        container = self._container
        factory = container.certificate_tool_factory
        setup = container.admin_web_setup
        if config is None or factory is None or setup is None:
            self.app.notify(_("Génération du certificat indisponible ici."), severity="error")
            return
        option = config.options.get(OPTION_NAME)
        settings = AdminWebSettings.from_settings(option.settings if option is not None else {})
        made = certificate_setup.generate(factory(), setup, container.filesystem, container.project_root, settings)
        if not made.ok:
            self.app.notify(made.message, severity="error", timeout=10)
            return
        shared = certificate_setup.share(setup, container.project_root, settings, DEFAULT_SYSTEM_GROUP,
                                         privileged=False)
        if shared.needs_privilege:  # session sans le groupe du service : sudo, invite par-dessus la TUI
            with self._maybe_suspend():
                shared = certificate_setup.share(setup, container.project_root, settings, DEFAULT_SYSTEM_GROUP,
                                                 privileged=True)
        self.app.notify(f"{made.message} {shared.message}", severity="information" if shared.ok else "warning",
                        timeout=10)
        if option is not None and option.enabled:
            notify_reload_required(self, container, _("Administration web : nouveau certificat."))
        self._show_state(self._config())

    def _open_firewall(self) -> None:
        """Sous-lot 8b : `omega-fire.sh port ouvrir` sous sudo (invite par-dessus la TUI), seulement si omega-fire et
        cette instance sont toujours inscrits dans la zone omega-connect."""
        config = self._config()
        container = self._container
        setup = container.admin_web_setup
        if config is None or setup is None:
            self.app.notify(_("Ouverture du port indisponible ici."), severity="error")
            return
        option = config.options.get(OPTION_NAME)
        settings = AdminWebSettings.from_settings(option.settings if option is not None else {})
        sources = firewall_sources(settings)
        launcher = setup.linked_firewall(container.project_root)
        if not launcher or not sources or not isinstance(settings.port, int):
            self.app.notify(_("omega-fire n'est plus relié à cette instance par omega-connect : rien n'est ouvert."),
                            severity="warning", timeout=10)
            self._show_state(config)
            return
        with self._maybe_suspend():
            opening = setup.open_firewall_port(launcher, settings.port, sources,
                                               firewall_label(container.project_root.name))
        if opening.ok:
            container.save_admin_firewall_record(FirewallRecord(
                settings.port, sources, container.clock.now().isoformat(timespec="seconds")))
            added = sum(1 for _target, _source, state in opening.lines if state == "ajoutee")
            present = sum(1 for _target, _source, state in opening.lines if state == "deja")
            self.app.notify(_("Port {port}/tcp ouvert par omega-fire : {added} règle(s) ajoutée(s), {present} déjà "
                              "en place.").format(port=settings.port, added=added, present=present),
                            severity="information", timeout=10)
        else:
            failed = "; ".join(f"{target} {source}" for target, source, state in opening.lines if state == "echec")
            self.app.notify(_("omega-fire n'a pas ouvert le port {port}/tcp : {detail}").format(
                port=settings.port, detail=opening.error or failed or "?"), severity="error", timeout=15)
        self._show_state(self._config())

    def _listen_problem(self, settings: AdminWebSettings) -> str:
        """Essai d'ecoute reel si l'adresse ou le port changent ; jamais contre notre propre ecoute."""
        setup = self._container.admin_web_setup
        if setup is None or not isinstance(settings.port, int):
            return ""
        state = self._container.admin_run_state()
        if state is not None and state.listening and state.port == settings.port \
                and binds_overlap(state.bind, str(settings.bind)):
            return ""
        result = setup.can_listen(str(settings.bind), settings.port)
        if result == LISTEN_IN_USE:
            return _("Port {port} déjà utilisé sur cette machine par un autre programme : choisissez-en un autre "
                     "({default} par défaut).").format(port=settings.port, default=DEFAULT_PORT)
        if result == LISTEN_NO_ADDRESS:
            return _("Adresse {bind} absente de cette machine (réseau ou Tailscale arrêté ?).").format(
                bind=settings.bind)
        return ""

    def _save(self) -> None:
        config = self._config()
        error_widget = self.query_one("#admin-web-error", Static)
        if config is None:
            error_widget.update(_("Erreur de configuration - impossible d'enregistrer."))
            return
        settings = self._form_settings()
        notes = []
        if settings.tls == "none" and isinstance(settings.bind, str) and settings.bind \
                and not is_loopback_bind(settings.bind):
            settings = replace(settings, tls="own")  # TLS obligatoire hors de cette machine : choisi tout seul
            self.query_one("#tls-select", Select).value = "own"
            notes.append(_("Chiffrement : « Certificat dédié » (obligatoire hors de cette machine)."))
        errors = validate_admin_web(settings, server_bind=config.server.bind, server_port=config.server.port)
        if not errors:
            problem = self._listen_problem(settings)
            errors = [problem] if problem else []
        if errors:
            error_widget.update("\n".join(errors))  # saisie gardee : rien n'est ecrit
            return
        existing = config.options.get(OPTION_NAME)
        enabled = existing.enabled if existing is not None else False
        merged = {**(existing.settings if existing is not None else {}), **settings.to_settings()}
        options = {**config.options, OPTION_NAME: Option(name=OPTION_NAME, enabled=enabled, settings=merged)}
        new_config = replace(config, options=options)
        self._container.configuration.save(self._container.config_file, new_config)
        error_widget.update("\n".join(notes))
        self._show_state(new_config)
        notify_reload_required(self, self._container, _("Administration web mise à jour."))
