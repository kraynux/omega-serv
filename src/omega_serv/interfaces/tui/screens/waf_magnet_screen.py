"""Sous-ecran WAF - Magnet (import d'un WAF externe), ajoute au menu
WAF (apres "Custom") - retour utilisateur 2026-10-10. Le but n'est PAS
d'ecrire un script WAF de plus : c'est d'importer, SANS le reecrire, un
script `mod_magnet` Lighttpd existant, ecrit pour un autre site (voir
OMEGA-SERV_WAF_LUA_DEPERSONNALISATION.md, OMEGA-SERV_ETUDE_INCLUDE_ET_
MAGNET_LUA.md §5.2 revise). Le natif reste toujours actif ; ce script
n'est jamais qu'un renfort additif (`domain/security/waf/
combine_decisions.py` : le plus restrictif des deux gagne toujours).

"Verifier la compatibilite" execute REELLEMENT le pont `lighty.*`
(via `container.magnet_compat_check_runner`, injecte depuis __main__.py
car le cas d'usage touche `lupa`/infrastructure/ transitivement - meme
raison que les autres usines de ce module) avec les valeurs du
formulaire EN COURS DE SAISIE, pas seulement celles deja enregistrees -
permet de tester un script avant de l'activer en production, exactement
le moment ou l'utilisateur doit "voir ce qui est compatible ou pas"
(besoin exprime a l'origine de cette fonctionnalite)."""
from __future__ import annotations

from dataclasses import replace
from typing import TYPE_CHECKING

from textual.app import ComposeResult
from textual.containers import Container, Horizontal, VerticalScroll
from textual.widgets import Button, Footer, Header, Input, Static

from omega_serv.application.config.load_config import load_config
from omega_serv.core.i18n import _
from omega_serv.domain.config.option import Option
from omega_serv.domain.security.waf.config import (
    MagnetConfig,
    MagnetPathsConfig,
    parse_waf_config,
)
from omega_serv.interfaces.tui.screens._base import OmegaScreen
from omega_serv.interfaces.tui.screens._service_reload import reload_service_after_waf_change
from omega_serv.interfaces.tui.yes_no import is_yes, to_text

if TYPE_CHECKING:
    from omega_serv.bootstrap.container import DependencyContainer
    from omega_serv.domain.config.entities import OmegaServConfig

_SCRIPTS_SUBDIR = ("secure", "waf", "scripts")


class WafMagnetScreen(OmegaScreen):
    def __init__(self, *, container: DependencyContainer) -> None:
        super().__init__()
        self._container = container

    def compose(self) -> ComposeResult:
        yield Header()
        with VerticalScroll(classes="omega-panel"):
            yield Static(_("WAF - MAGNET (IMPORT D'UN WAF EXTERNE)"), classes="omega-title")
            yield Static(
                _("Importe un script WAF mod_magnet Lighttpd EXISTANT (écrit pour un autre site), "
                "sans le réécrire. Reste toujours un renfort additif : il ne peut jamais lever un "
                "blocage déjà décidé par le WAF natif. Seuls les chemins personnels du script (fichiers "
                "de log/blocage) se dissocient via les champs ci-dessous - toute la logique du script "
                "reste inchangée."),
                classes="omega-hint",
            )
            yield Static("", id="form-error", classes="omega-hint")

            yield Static(_("Actif (oui/non)"), classes="omega-subtitle")
            yield Input(value=to_text(False), id="enabled-input")
            yield Static(_("Script (chemin relatif au projet)"), classes="omega-subtitle")
            yield Static(self._available_scripts_hint(), id="available-scripts-hint", classes="omega-hint")
            yield Input(placeholder="secure/waf/scripts/waf.lua", id="script-input")
            yield Static(_("Délai maximum par appel (ms)"), classes="omega-subtitle")
            yield Input(value="50", id="timeout-input")
            yield Static(_("Comportement en cas d'erreur du script (ignore/fail-closed)"), classes="omega-subtitle")
            yield Input(value="ignore", id="on-error-input")

            yield Static(
                _("Chemins personnels dissociés (vide = le script garde son propre chemin en dur)"),
                classes="omega-subtitle",
            )
            yield Input(placeholder="blocklist_file", id="path-blocklist-file-input")
            yield Input(placeholder="rules_dir", id="path-rules-dir-input")
            yield Input(placeholder="alerts_log", id="path-alerts-log-input")
            yield Input(placeholder="blocklist_log", id="path-blocklist-log-input")
            yield Input(placeholder="rate_store_file", id="path-rate-store-file-input")

            with Horizontal(classes="omega-actions"):
                with Container(classes="omega-btn-frame"):
                    yield Button(_("Vérifier la compatibilité"), id="check-compat")
                with Container(classes="omega-btn-frame"):
                    yield Button(_("Enregistrer"), id="save", variant="primary")
                with Container(classes="omega-btn-frame"):
                    yield Button(_("Retour"), id="back")
            yield Static("", id="compat-result", classes="omega-hint")
        yield Footer()

    def on_mount(self) -> None:
        self._refresh()

    def _config(self) -> OmegaServConfig | None:
        result = load_config(self._container.configuration, self._container.config_file)
        return result.config if result.success else None

    def _available_scripts_hint(self) -> str:
        scripts_dir = self._container.project_root.joinpath(*_SCRIPTS_SUBDIR)
        if not self._container.filesystem.is_dir(scripts_dir):
            return _("Aucun script trouvé sous secure/waf/scripts/.")
        scripts = sorted(name for name in self._container.filesystem.list_directory_entries(scripts_dir) if name.endswith(".lua"))
        if not scripts:
            return _("Aucun script .lua trouvé sous secure/waf/scripts/.")
        listed = ", ".join(f"secure/waf/scripts/{name}" for name in scripts)
        return _("Scripts disponibles sur disque : {listed}").format(listed=listed)

    def _refresh(self) -> None:
        config = self._config()
        if config is None:
            self.query_one("#form-error", Static).update(_("Erreur de configuration."))
            return
        settings = config.options["waf"].settings if "waf" in config.options else {}
        magnet = parse_waf_config(settings).magnet
        self.query_one("#enabled-input", Input).value = to_text(magnet.enabled)
        self.query_one("#script-input", Input).value = magnet.script
        self.query_one("#timeout-input", Input).value = str(magnet.timeout_ms)
        self.query_one("#on-error-input", Input).value = magnet.on_error
        self.query_one("#path-blocklist-file-input", Input).value = magnet.paths.blocklist_file
        self.query_one("#path-rules-dir-input", Input).value = magnet.paths.rules_dir
        self.query_one("#path-alerts-log-input", Input).value = magnet.paths.alerts_log
        self.query_one("#path-blocklist-log-input", Input).value = magnet.paths.blocklist_log
        self.query_one("#path-rate-store-file-input", Input).value = magnet.paths.rate_store_file

    async def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "back":
            self.dismiss()
            return
        if event.button.id == "save":
            self._save()
            return
        if event.button.id == "check-compat":
            await self._check_compatibility()

    def _magnet_config_from_form(self) -> MagnetConfig:
        return MagnetConfig(
            enabled=is_yes(self.query_one("#enabled-input", Input).value),
            script=self.query_one("#script-input", Input).value.strip(),
            timeout_ms=int(self.query_one("#timeout-input", Input).value.strip() or "50"),
            on_error=self.query_one("#on-error-input", Input).value.strip(),  # type: ignore[arg-type]
            paths=MagnetPathsConfig(
                blocklist_file=self.query_one("#path-blocklist-file-input", Input).value.strip() or MagnetPathsConfig().blocklist_file,
                rules_dir=self.query_one("#path-rules-dir-input", Input).value.strip() or MagnetPathsConfig().rules_dir,
                alerts_log=self.query_one("#path-alerts-log-input", Input).value.strip() or MagnetPathsConfig().alerts_log,
                blocklist_log=self.query_one("#path-blocklist-log-input", Input).value.strip() or MagnetPathsConfig().blocklist_log,
                rate_store_file=self.query_one("#path-rate-store-file-input", Input).value.strip() or MagnetPathsConfig().rate_store_file,
            ),
        )

    def _save(self) -> None:
        error_widget = self.query_one("#form-error", Static)
        load_result = load_config(self._container.configuration, self._container.config_file)
        if not load_result.success or load_result.config is None:
            error_widget.update(_("Erreur de configuration - impossible d'enregistrer."))
            return

        try:
            magnet = self._magnet_config_from_form()
        except ValueError:
            error_widget.update(_("Délai (ms) invalide : un nombre entier est attendu."))
            return
        if magnet.on_error not in ("ignore", "fail-closed"):
            error_widget.update(_("Valeur invalide : {on_error!r} (attendu : ignore, fail-closed)").format(on_error=magnet.on_error))
            return
        if magnet.timeout_ms <= 0:
            error_widget.update(_("Le délai (ms) doit être strictement positif."))
            return
        if magnet.enabled and not magnet.script:
            error_widget.update(_("Un chemin de script est requis pour activer le magnet."))
            return

        existing = load_result.config.options.get("waf")
        enabled = existing.enabled if existing is not None else False
        new_settings = dict(existing.settings) if existing is not None else {}
        new_settings["magnet"] = {
            "enabled": magnet.enabled,
            "script": magnet.script,
            "timeout_ms": magnet.timeout_ms,
            "on_error": magnet.on_error,
            "paths": {
                "blocklist_file": magnet.paths.blocklist_file,
                "rules_dir": magnet.paths.rules_dir,
                "alerts_log": magnet.paths.alerts_log,
                "blocklist_log": magnet.paths.blocklist_log,
                "rate_store_file": magnet.paths.rate_store_file,
            },
        }
        new_options = dict(load_result.config.options)
        new_options["waf"] = Option(name="waf", enabled=enabled, settings=new_settings)
        new_config = replace(load_result.config, options=new_options)
        self._container.configuration.save(self._container.config_file, new_config)
        error_widget.update("")
        self.app.notify(_("Réglages magnet enregistrés."))
        reload_message = reload_service_after_waf_change(self, self._container)
        if reload_message is not None:
            self.app.notify(reload_message)

    async def _check_compatibility(self) -> None:
        result_widget = self.query_one("#compat-result", Static)
        error_widget = self.query_one("#form-error", Static)
        error_widget.update("")

        try:
            magnet = self._magnet_config_from_form()
        except ValueError:
            result_widget.update(_("Délai (ms) invalide : un nombre entier est attendu."))
            return
        if not magnet.script:
            result_widget.update(_("Renseignez d'abord un chemin de script."))
            return

        runner = self._container.magnet_compat_check_runner
        if runner is None:
            result_widget.update(_("Vérification indisponible dans cet environnement."))
            return
        result_widget.update(_("Vérification en cours..."))
        check = await runner(magnet, self._container.project_root, self._container.filesystem)

        if check.dependency_missing:
            result_widget.update(
                _("Dépendance 'lupa' absente - installer l'extra optionnel avec "
                "`pip install -e \".[magnet]\"`.")
            )
            return
        if check.construction_error:
            result_widget.update(_("ERREUR : {construction_error}").format(construction_error=check.construction_error))
            return

        lines: list[str] = []
        if check.unsupported_members:
            lines.append(
                _("ℹ️ INFORMATION (n'empêche jamais l'enregistrement/l'activation) - ce script référence lighty.{{{value}}}, que ce pont ne branche pas (restera toujours `nil` ici, jamais une erreur en soi). Si le script vérifie déjà la présence de ce membre avant de l'utiliser (ex. `type(lighty.X) == \"function\"`, un repli vers une ancienne API), ce code ne s'exécute tout simplement jamais sous omega-serv et n'a aucun effet réel - regardez le code autour de cette référence pour en juger. Le résultat de la requête de test ci-dessous reste le signal le plus fiable : une incompatibilité réelle s'y traduit par une erreur, pas seulement par cet avertissement.").format(value=', '.join(sorted(check.unsupported_members)))
            )
        if check.dry_run_error:
            lines.append(
                _("⚠️ PROBLÈME RÉEL DÉTECTÉ - le script a levé une erreur sur une requête de test bénigne : {dry_run_error}").format(dry_run_error=check.dry_run_error)
            )
        if magnet.on_error == "fail-closed" and (check.unsupported_members or check.dry_run_error):
            lines.append(
                _("⚠️ ATTENTION - on_error='fail-closed' combiné à une incompatibilité détectée : toute "
                "requête future qui déclenche la même erreur sera BLOQUÉE (y compris du trafic légitime).")
            )
        if not lines:
            lines.append(_("Compatibilité OK : scan statique propre, requête de test sans erreur."))
        result_widget.update("\n".join(lines))
