# Copyright (c) 2026 kraynux - kraynux@proton.me - Licence MIT (voir fichier LICENSE)
"""Ecran Active Defense - Reglages (retour utilisateur 2026-09-14 :
"but du projet aucune edition manuelle, donc on va sur une interface
pour custom les modes, les activer etc.") - jusqu'ici, `mode`/`war_mode`/
`deception`/`ioc`/`storage`/`logging` (domain/security/active_defense/
config.py::ActiveDefenseConfig) n'etaient editables qu'a la main dans
config/omega-serve.json, aucun ecran ni commande CLI ne les exposait
(ActiveDefenseStatusScreen etait deja explicitement documente comme
lecture seule, "reglages fins... D-008" - le besoin est maintenant
confirme, ce chantier le construit).

Meme patron que waf_modules_screen.py (VerticalScroll, settings-dict
manipule directement, pas de dataclass to_dict() - aucune des classes
de domain/config/ ou active_defense/config.py n'en a, convention deja
etablie de reconstruire le dict a la main cote ecran) : reutilise
`validate_active_defense_config` (domain, pure) AVANT toute ecriture,
jamais une seconde logique de validation.

active_defense n'est JAMAIS recharge a chaud (reload_scoped() ne
retouche jamais _active_defense_config, meme regle que documentee dans
options_screen.py) - un REDEMARRAGE COMPLET est donc systematiquement
requis apres tout enregistrement ici, sans exception."""
from __future__ import annotations

from dataclasses import replace
from typing import TYPE_CHECKING

from textual.app import ComposeResult
from textual.containers import Container, Horizontal, VerticalScroll
from textual.widgets import Button, DataTable, Footer, Header, Input, Static

from omega_serv.application.config.load_config import load_config
from omega_serv.domain.config.option import Option
from omega_serv.domain.security.active_defense.config import (
    parse_active_defense_config,
    validate_active_defense_config,
)
from omega_serv.interfaces.tui.screens._base import OmegaScreen
from omega_serv.interfaces.tui.screens.confirm import ConfirmScreen
from omega_serv.interfaces.tui.screens.dynamic_form_screen import DynamicFormScreen
from omega_serv.interfaces.tui.screens.restart_prompt import notify_restart_required

if TYPE_CHECKING:
    from omega_serv.bootstrap.container import DependencyContainer
    from omega_serv.domain.config.entities import OmegaServConfig

_TRUE_VALUES = frozenset({"oui", "true", "1", "o", "y"})


def _bool_to_text(value: bool) -> str:
    return "oui" if value else "non"


def _text_to_bool(value: str) -> bool:
    return value.strip().lower() in _TRUE_VALUES


def _csv(values: tuple[str, ...] | list[str]) -> str:
    return ", ".join(values)


def _parse_csv(text: str) -> list[str]:
    return [item.strip() for item in text.split(",") if item.strip()]


class ActiveDefenseSettingsScreen(OmegaScreen):
    def __init__(self, *, container: DependencyContainer) -> None:
        super().__init__()
        self._container = container
        self._selected_profile_name: str | None = None
        self._selected_decoy_zone_name: str | None = None

    def compose(self) -> ComposeResult:
        yield Header()
        with VerticalScroll(classes="omega-panel"):
            yield Static("ACTIVE DEFENSE - REGLAGES", classes="omega-title")
            yield Static(
                "L'activation de l'option 'active_defense' se fait dans le menu Options. "
                "TOUT changement ici exige un REDEMARRAGE COMPLET (jamais un simple "
                "rechargement) - active_defense n'est jamais recharge a chaud.",
                classes="omega-hint",
            )
            yield Static("", id="form-error", classes="omega-hint")

            yield Static("GENERAL", classes="omega-subtitle")
            yield Static("Mode (monitor/enforce)")
            yield Input(id="mode-input")
            yield Static("Duree de vie d'un etat de menace sans nouvel evenement (state_ttl_seconds)")
            yield Input(id="state-ttl-input")

            yield Static("MODE GUERRE (war_mode)", classes="omega-subtitle")
            yield Static("Mode guerre actif (oui/non) - LE VRAI INTERRUPTEUR qui declenche tout")
            yield Input(id="war-enabled-input")
            yield Static("Portee (source/instance)")
            yield Input(id="war-scope-input")
            yield Static("Actions autorisees (separees par des virgules)")
            yield Input(id="war-actions-input")
            yield Static("Seuil suspect / hostile / incident / confine (suspicious_score, hostile_score, incident_score, contained_score)")
            yield Input(id="war-suspicious-input")
            yield Input(id="war-hostile-input")
            yield Input(id="war-incident-input")
            yield Input(id="war-contained-input")
            yield Static("Ralentissement actif (oui/non) + delai min/max/jitter en millisecondes")
            yield Input(id="slowdown-enabled-input")
            yield Input(id="slowdown-min-input")
            yield Input(id="slowdown-max-input")
            yield Input(id="slowdown-jitter-input")
            yield Static("Limite de requetes : nombre + fenetre en secondes")
            yield Input(id="rate-limit-requests-input")
            yield Input(id="rate-limit-window-input")

            yield Static("DECEPTION", classes="omega-subtitle")
            yield Static("Deception active (oui/non)")
            yield Input(id="deception-enabled-input")
            yield Static("Comportement si aucun profil ne correspond (pass_through/reject)")
            yield Input(id="deception-fallback-input")
            yield Static("Duree de vie d'une affectation vers un leurre (assignments_ttl_seconds)")
            yield Input(id="deception-ttl-input")

            yield Static("Profils de leurre", classes="omega-subtitle")
            yield DataTable(id="profiles-table")
            with Horizontal(classes="omega-actions"):
                with Container(classes="omega-btn-frame"):
                    yield Button("Ajouter un profil", id="add-profile", variant="primary")
                with Container(classes="omega-btn-frame"):
                    yield Button("Supprimer le profil", id="delete-profile", variant="error", disabled=True)

            yield Static("Zones de leurre (Niveau 2, cibles reellement isolees)", classes="omega-subtitle")
            yield DataTable(id="decoy-zones-table")
            with Horizontal(classes="omega-actions"):
                with Container(classes="omega-btn-frame"):
                    yield Button("Ajouter une zone", id="add-decoy-zone", variant="primary")
                with Container(classes="omega-btn-frame"):
                    yield Button("Supprimer la zone", id="delete-decoy-zone", variant="error", disabled=True)

            yield Static("IOC (INDICATEURS DE COMPROMISSION)", classes="omega-subtitle")
            yield Static("Export IoC actif (oui/non)")
            yield Input(id="ioc-enabled-input")
            yield Static("Export automatique a la fermeture d'un incident (oui/non)")
            yield Input(id="ioc-auto-export-input")
            yield Static("Formats d'export (separes par des virgules : json, csv, markdown)")
            yield Input(id="ioc-formats-input")
            yield Static("Politique de partage (local_only/manual_export)")
            yield Input(id="ioc-share-policy-input")
            yield Static("Confiance minimale requise (0-100)")
            yield Input(id="ioc-min-confidence-input")

            yield Static("STOCKAGE ET JOURNALISATION", classes="omega-subtitle")
            yield Static("Base de donnees (storage.database)")
            yield Input(id="storage-database-input")
            yield Static("Repertoire d'export (storage.export_dir)")
            yield Input(id="storage-export-dir-input")
            yield Static("Capture enrichie active (oui/non)")
            yield Input(id="logging-enhanced-input")
            yield Static("Capturer le corps de la requete (oui/non)")
            yield Input(id="logging-capture-body-input")
            yield Static("Taille max du corps capture, en octets (max_body_bytes)")
            yield Input(id="logging-max-body-input")
            yield Static("Champs a masquer (separes par des virgules)")
            yield Input(id="logging-redact-input")
            yield Static("Fichier de journal enrichi (log_path)")
            yield Input(id="logging-log-path-input")

            with Horizontal(classes="omega-actions"):
                with Container(classes="omega-btn-frame"):
                    yield Button("Enregistrer", id="save", variant="primary")
                with Container(classes="omega-btn-frame"):
                    yield Button("Retour", id="back")
        yield Footer()

    # ------------------------------------------------------------------
    # Chargement
    # ------------------------------------------------------------------
    def on_mount(self) -> None:
        table = self.query_one("#profiles-table", DataTable)
        table.cursor_type = "row"
        table.add_columns("Nom", "Actif", "Classes d'attaque", "Isolation", "Zone leurre")
        decoy_table = self.query_one("#decoy-zones-table", DataTable)
        decoy_table.cursor_type = "row"
        decoy_table.add_columns("Nom", "Upstreams", "Verifie TLS")
        self._refresh()

    def _config(self) -> OmegaServConfig | None:
        result = load_config(self._container.configuration, self._container.config_file)
        return result.config if result.success else None

    def _settings(self) -> dict:
        config = self._config()
        if config is None:
            return {}
        option = config.options.get("active_defense")
        return dict(option.settings) if option is not None else {}

    def _refresh(self) -> None:
        settings = self._settings()
        active_defense = parse_active_defense_config(settings)

        self.query_one("#mode-input", Input).value = active_defense.mode
        self.query_one("#state-ttl-input", Input).value = str(active_defense.state_ttl_seconds)

        war = active_defense.war_mode
        self.query_one("#war-enabled-input", Input).value = _bool_to_text(war.enabled)
        self.query_one("#war-scope-input", Input).value = war.scope
        self.query_one("#war-actions-input", Input).value = _csv(war.actions)
        self.query_one("#war-suspicious-input", Input).value = str(war.thresholds.suspicious_score)
        self.query_one("#war-hostile-input", Input).value = str(war.thresholds.hostile_score)
        self.query_one("#war-incident-input", Input).value = str(war.thresholds.incident_score)
        self.query_one("#war-contained-input", Input).value = str(war.thresholds.contained_score)
        self.query_one("#slowdown-enabled-input", Input).value = _bool_to_text(war.slowdown.enabled)
        self.query_one("#slowdown-min-input", Input).value = str(war.slowdown.minimum_ms)
        self.query_one("#slowdown-max-input", Input).value = str(war.slowdown.maximum_ms)
        self.query_one("#slowdown-jitter-input", Input).value = str(war.slowdown.jitter_ms)
        self.query_one("#rate-limit-requests-input", Input).value = str(war.rate_limit.requests)
        self.query_one("#rate-limit-window-input", Input).value = str(war.rate_limit.window_seconds)

        deception = active_defense.deception
        self.query_one("#deception-enabled-input", Input).value = _bool_to_text(deception.enabled)
        self.query_one("#deception-fallback-input", Input).value = deception.fallback
        self.query_one("#deception-ttl-input", Input).value = str(deception.assignments_ttl_seconds)

        profiles_table = self.query_one("#profiles-table", DataTable)
        profiles_table.clear()
        self._selected_profile_name = None
        self.query_one("#delete-profile", Button).disabled = True
        for name, profile in sorted(deception.profiles.items()):
            profiles_table.add_row(
                name, _bool_to_text(profile.enabled), _csv(profile.match_attack_classes),
                profile.isolation_level, profile.reverse_proxy_zone_name or "-", key=name,
            )

        decoy_table = self.query_one("#decoy-zones-table", DataTable)
        decoy_table.clear()
        self._selected_decoy_zone_name = None
        self.query_one("#delete-decoy-zone", Button).disabled = True
        for name, zone in sorted(deception.decoy_zones.items()):
            upstreams = ", ".join(f"{'https://' if u.use_tls else ''}{u.host}:{u.port}" for u in zone.upstreams)
            decoy_table.add_row(name, upstreams, _bool_to_text(zone.verify_upstream_tls), key=name)

        ioc = active_defense.ioc
        self.query_one("#ioc-enabled-input", Input).value = _bool_to_text(ioc.enabled)
        self.query_one("#ioc-auto-export-input", Input).value = _bool_to_text(ioc.auto_export_on_close)
        self.query_one("#ioc-formats-input", Input).value = _csv(ioc.formats)
        self.query_one("#ioc-share-policy-input", Input).value = ioc.share_policy
        self.query_one("#ioc-min-confidence-input", Input).value = str(ioc.minimum_confidence)

        self.query_one("#storage-database-input", Input).value = active_defense.storage.database
        self.query_one("#storage-export-dir-input", Input).value = active_defense.storage.export_dir
        self.query_one("#logging-enhanced-input", Input).value = _bool_to_text(active_defense.logging.enhanced_capture)
        self.query_one("#logging-capture-body-input", Input).value = _bool_to_text(active_defense.logging.capture_request_body)
        self.query_one("#logging-max-body-input", Input).value = str(active_defense.logging.max_body_bytes)
        self.query_one("#logging-redact-input", Input).value = _csv(active_defense.logging.redact_fields)
        self.query_one("#logging-log-path-input", Input).value = active_defense.logging.log_path

    def on_data_table_row_selected(self, event: DataTable.RowSelected) -> None:
        if event.data_table.id == "profiles-table":
            self._selected_profile_name = str(event.row_key.value)
            self.query_one("#delete-profile", Button).disabled = False
            return
        self._selected_decoy_zone_name = str(event.row_key.value)
        self.query_one("#delete-decoy-zone", Button).disabled = False

    # ------------------------------------------------------------------
    # Boutons
    # ------------------------------------------------------------------
    def on_button_pressed(self, event: Button.Pressed) -> None:
        button_id = event.button.id
        if button_id == "back":
            self.dismiss()
            return
        if button_id == "save":
            self._save()
            return
        if button_id == "add-profile":
            self.app.push_screen(
                DynamicFormScreen(
                    title="AJOUTER UN PROFIL DE LEURRE",
                    fields=[
                        (
                            "name",
                            (
                                "Nom du profil.\n"
                                "Si Isolation = fixture (ci-dessous), ce nom DOIT etre exactement l'un de :\n"
                                "fake_admin, fake_cms, fake_api, fake_secrets - sinon le leurre ne se\n"
                                "declenchera jamais (aucune erreur visible, l'attaquant tombe sur le\n"
                                "comportement normal). Libre si Isolation = proxy."
                            ),
                            "",
                        ),
                        ("enabled", "Actif (oui/non)", "oui"),
                        (
                            "match_attack_classes",
                            (
                                "Classes d'attaque visees, separees par des virgules. Valeurs possibles :\n"
                                "scan (sondage d'URLs/ports), credential_stuffing (essais massifs de\n"
                                "mots de passe), sqli (injection SQL), xss (script injecte), path_traversal\n"
                                "(ex: ../../etc/passwd), upload_probe (upload de fichier suspect),\n"
                                "api_probe (sondage d'endpoints /api/...), unknown (tout le reste).\n"
                                "Ex : scan,credential_stuffing"
                            ),
                            "",
                        ),
                        (
                            "isolation_level",
                            (
                                "Isolation (fixture/proxy).\n"
                                "fixture = simulation interne integree, rapide et sans risque (voir Nom\n"
                                "du profil ci-dessus pour les 4 noms valides).\n"
                                "proxy = redirige vers un VRAI serveur isole que vous faites tourner\n"
                                "vous-meme, plus realiste mais necessite une zone de leurre (ci-dessous)."
                            ),
                            "fixture",
                        ),
                        (
                            "reverse_proxy_zone_name",
                            (
                                "Zone de leurre associee (requis si Isolation = proxy, laisser vide si\n"
                                "fixture). Doit correspondre au nom exact d'une zone definie dans la\n"
                                "section 'Zones de leurre' plus bas."
                            ),
                            "",
                        ),
                    ],
                ),
                self._add_profile,
            )
            return
        if button_id == "delete-profile" and self._selected_profile_name is not None:
            self.app.push_screen(
                ConfirmScreen(title="SUPPRIMER LE PROFIL", message="Confirmer la suppression de ce profil de leurre ?"),
                self._delete_profile,
            )
            return
        if button_id == "add-decoy-zone":
            self.app.push_screen(
                DynamicFormScreen(
                    title="AJOUTER UNE ZONE DE LEURRE",
                    fields=[
                        (
                            "name",
                            (
                                "Nom de la zone.\n"
                                "Un simple identifiant (PAS une URL, PAS un dossier) - reference depuis\n"
                                "un profil de leurre en Isolation = proxy. C'est une cible reseau pure,\n"
                                "elle n'a besoin d'exister nulle part sur le disque."
                            ),
                            "",
                        ),
                        (
                            "upstreams",
                            (
                                "Upstreams (host:port, separes par des virgules).\n"
                                "Adresse(s) d'un serveur DEJA EN COURS D'EXECUTION que vous controlez -\n"
                                "rien n'est cree automatiquement ici, et aucune verification n'a lieu a\n"
                                "l'enregistrement. Ex : 127.0.0.1:9001\n"
                                "Si rien n'ecoute a cette adresse au moment d'une requete, l'attaquant\n"
                                "recoit simplement une erreur 502 (pas de crash, pas de creation)."
                            ),
                            "",
                        ),
                        ("connect_timeout_seconds", "Delai de connexion (secondes)", "5"),
                        ("read_timeout_seconds", "Delai de lecture (secondes)", "30"),
                        ("verify_upstream_tls", "Verifier le certificat TLS de l'upstream (oui/non)", "oui"),
                    ],
                ),
                self._add_decoy_zone,
            )
            return
        if button_id == "delete-decoy-zone" and self._selected_decoy_zone_name is not None:
            self.app.push_screen(
                ConfirmScreen(title="SUPPRIMER LA ZONE", message="Confirmer la suppression de cette zone de leurre ?"),
                self._delete_decoy_zone,
            )

    def _add_profile(self, values: dict[str, str] | None) -> None:
        if values is None:
            return
        name = values["name"].strip()
        if not name:
            self.query_one("#form-error", Static).update("Le nom du profil ne peut pas etre vide.")
            return
        settings = self._settings()
        deception = dict(settings.get("deception", {}))
        profiles = dict(deception.get("profiles", {}))
        profiles[name] = {
            "enabled": _text_to_bool(values["enabled"]),
            "match_attack_classes": _parse_csv(values["match_attack_classes"]),
            "isolation_level": values["isolation_level"].strip() or "fixture",
            "reverse_proxy_zone_name": values["reverse_proxy_zone_name"].strip() or None,
        }
        deception["profiles"] = profiles
        settings["deception"] = deception
        self._save_settings(settings)

    def _delete_profile(self, confirmed: bool | None) -> None:
        if not confirmed or self._selected_profile_name is None:
            return
        settings = self._settings()
        deception = dict(settings.get("deception", {}))
        profiles = dict(deception.get("profiles", {}))
        profiles.pop(self._selected_profile_name, None)
        deception["profiles"] = profiles
        settings["deception"] = deception
        self._save_settings(settings)

    def _add_decoy_zone(self, values: dict[str, str] | None) -> None:
        if values is None:
            return
        name = values["name"].strip()
        if not name:
            self.query_one("#form-error", Static).update("Le nom de la zone ne peut pas etre vide.")
            return
        upstreams: list[dict[str, object]] = []
        for chunk in values["upstreams"].split(","):
            item = chunk.strip()
            if not item:
                continue
            use_tls = item.lower().startswith("https://")
            if use_tls:
                item = item[len("https://"):]
            elif item.lower().startswith("http://"):
                item = item[len("http://"):]
            host, sep, port_text = item.rpartition(":")
            if not sep:
                self.query_one("#form-error", Static).update(f"Upstream invalide (attendu host:port) : {chunk!r}")
                return
            try:
                port = int(port_text.strip())
            except ValueError:
                self.query_one("#form-error", Static).update(f"Port invalide : {port_text!r}")
                return
            upstreams.append({"host": host.strip(), "port": port, "use_tls": use_tls})
        if not upstreams:
            self.query_one("#form-error", Static).update("Au moins un upstream est requis.")
            return
        try:
            connect_timeout = float(values["connect_timeout_seconds"].strip())
            read_timeout = float(values["read_timeout_seconds"].strip())
        except ValueError:
            self.query_one("#form-error", Static).update("Delais invalides (nombres attendus).")
            return

        settings = self._settings()
        deception = dict(settings.get("deception", {}))
        decoy_zones = dict(deception.get("decoy_zones", {}))
        decoy_zones[name] = {
            "upstreams": upstreams,
            "connect_timeout_seconds": connect_timeout,
            "read_timeout_seconds": read_timeout,
            "verify_upstream_tls": _text_to_bool(values["verify_upstream_tls"]),
        }
        deception["decoy_zones"] = decoy_zones
        settings["deception"] = deception
        self._save_settings(settings)

    def _delete_decoy_zone(self, confirmed: bool | None) -> None:
        if not confirmed or self._selected_decoy_zone_name is None:
            return
        settings = self._settings()
        deception = dict(settings.get("deception", {}))
        decoy_zones = dict(deception.get("decoy_zones", {}))
        decoy_zones.pop(self._selected_decoy_zone_name, None)
        deception["decoy_zones"] = decoy_zones
        settings["deception"] = deception
        self._save_settings(settings)

    # ------------------------------------------------------------------
    # Enregistrement des reglages generaux
    # ------------------------------------------------------------------
    def _save(self) -> None:
        error_widget = self.query_one("#form-error", Static)
        try:
            new_fields = self._collect_general_fields()
        except ValueError as exc:
            error_widget.update(str(exc))
            return
        settings = self._settings()
        # Conserve profiles/decoy_zones (deja geres par leur propre CRUD,
        # jamais retouches par ce formulaire general) - seule la partie
        # "champs simples" du dict est remplacee.
        existing_deception = dict(settings.get("deception", {}))
        new_fields["deception"]["profiles"] = existing_deception.get("profiles", {})
        new_fields["deception"]["decoy_zones"] = existing_deception.get("decoy_zones", {})
        self._save_settings(new_fields)

    def _collect_general_fields(self) -> dict:
        def _int_field(field_id: str, label: str) -> int:
            text = self.query_one(f"#{field_id}", Input).value.strip()
            try:
                return int(text)
            except ValueError as exc:
                raise ValueError(f"{label} invalide (entier attendu) : {text!r}") from exc

        def _float_field(field_id: str, label: str) -> float:
            text = self.query_one(f"#{field_id}", Input).value.strip()
            try:
                return float(text)
            except ValueError as exc:
                raise ValueError(f"{label} invalide (nombre attendu) : {text!r}") from exc

        return {
            "mode": self.query_one("#mode-input", Input).value.strip(),
            "state_ttl_seconds": _int_field("state-ttl-input", "Duree de vie d'un etat"),
            "war_mode": {
                "enabled": _text_to_bool(self.query_one("#war-enabled-input", Input).value),
                "scope": self.query_one("#war-scope-input", Input).value.strip(),
                "actions": _parse_csv(self.query_one("#war-actions-input", Input).value),
                "thresholds": {
                    "suspicious_score": _int_field("war-suspicious-input", "Seuil suspect"),
                    "hostile_score": _int_field("war-hostile-input", "Seuil hostile"),
                    "incident_score": _int_field("war-incident-input", "Seuil incident"),
                    "contained_score": _int_field("war-contained-input", "Seuil confine"),
                },
                "slowdown": {
                    "enabled": _text_to_bool(self.query_one("#slowdown-enabled-input", Input).value),
                    "minimum_ms": _int_field("slowdown-min-input", "Delai minimum"),
                    "maximum_ms": _int_field("slowdown-max-input", "Delai maximum"),
                    "jitter_ms": _int_field("slowdown-jitter-input", "Jitter"),
                },
                "rate_limit": {
                    "requests": _int_field("rate-limit-requests-input", "Nombre de requetes"),
                    "window_seconds": _int_field("rate-limit-window-input", "Fenetre"),
                },
            },
            "deception": {
                "enabled": _text_to_bool(self.query_one("#deception-enabled-input", Input).value),
                "fallback": self.query_one("#deception-fallback-input", Input).value.strip(),
                "assignments_ttl_seconds": _int_field("deception-ttl-input", "Duree de vie d'une affectation"),
            },
            "ioc": {
                "enabled": _text_to_bool(self.query_one("#ioc-enabled-input", Input).value),
                "auto_export_on_close": _text_to_bool(self.query_one("#ioc-auto-export-input", Input).value),
                "formats": _parse_csv(self.query_one("#ioc-formats-input", Input).value),
                "share_policy": self.query_one("#ioc-share-policy-input", Input).value.strip(),
                "minimum_confidence": _int_field("ioc-min-confidence-input", "Confiance minimale"),
            },
            "storage": {
                "database": self.query_one("#storage-database-input", Input).value.strip(),
                "export_dir": self.query_one("#storage-export-dir-input", Input).value.strip(),
            },
            "logging": {
                "enhanced_capture": _text_to_bool(self.query_one("#logging-enhanced-input", Input).value),
                "capture_request_body": _text_to_bool(self.query_one("#logging-capture-body-input", Input).value),
                "max_body_bytes": _int_field("logging-max-body-input", "Taille max du corps"),
                "redact_fields": _parse_csv(self.query_one("#logging-redact-input", Input).value),
                "log_path": self.query_one("#logging-log-path-input", Input).value.strip(),
            },
        }

    # ------------------------------------------------------------------
    # Ecriture reelle (partagee par le formulaire general et les CRUD)
    # ------------------------------------------------------------------
    def _save_settings(self, new_settings: dict) -> None:
        error_widget = self.query_one("#form-error", Static)
        load_result = load_config(self._container.configuration, self._container.config_file)
        if not load_result.success or load_result.config is None:
            error_widget.update("Erreur de configuration - impossible d'enregistrer.")
            return

        # Reutilise la validation domain existante AVANT toute ecriture -
        # jamais une seconde logique de validation divergente.
        candidate = parse_active_defense_config(new_settings)
        errors = validate_active_defense_config(candidate)
        if errors:
            error_widget.update("Erreur :\n" + "\n".join(f"  - {e}" for e in errors))
            return

        existing = load_result.config.options.get("active_defense")
        enabled = existing.enabled if existing is not None else False
        new_options = dict(load_result.config.options)
        new_options["active_defense"] = Option(name="active_defense", enabled=enabled, settings=new_settings)
        new_config = replace(load_result.config, options=new_options)
        self._container.configuration.save(self._container.config_file, new_config)
        error_widget.update("")
        self._refresh()
        # active_defense n'est JAMAIS recharge a chaud (voir docstring de
        # module) - toujours un redemarrage complet, sans exception.
        notify_restart_required(
            self, self._container,
            "Reglages Active Defense enregistres. Necessite un REDEMARRAGE COMPLET pour "
            "prendre effet (active_defense n'est jamais recharge a chaud).",
        )
