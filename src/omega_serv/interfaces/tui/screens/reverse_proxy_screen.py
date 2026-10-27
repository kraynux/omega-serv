"""Sous-ecran Reverse proxy sortant (OMEGA-SERV_PLAN-DETAILLE_REVERSE_PROXY.md,
phases 2-4 : plusieurs upstreams par zone, chacun HTTP ou HTTPS -
CRUD complet sur `options["reverse_proxy"].settings["zones"]`
(domain/routing/proxy_zone.py::ProxyZone). Verification TLS
(`verify_upstream_tls`) reste une politique de zone, pas par upstream
(§5.3 du document). `websocket_enabled` (§4) autorise la mise a niveau
`Upgrade: websocket` sur cette zone - une fois le tube etabli, UN SEUL
upstream reste fige pour toute sa duree de vie. A ne jamais confondre
avec `server.tls.mode = "behind_proxy"` (OMEGA-SERV DERRIERE un proxy,
mecanisme different) - ici OMEGA-SERV est lui-meme le proxy, vers un ou
plusieurs backends.

Phase 5 (strategies de repartition, §16/§28.1-§28.2) : l'ancien champ
texte a plat "host:port, host:port, ..." est devenu illisible des qu'un
poids s'ajoute - remplace par un CRUD de zone en ETAPES :
(1) `DynamicFormScreen` pour les champs de zone (prefixe, strategie,
delais, options), (2) `UpstreamEditorScreen` pour la liste des backends
(host/port/TLS/poids, un formulaire dedie par backend). Un "Annuler" a
n'importe quelle etape abandonne la saisie ENTIERE (pas de sauvegarde
partielle). `load_balancing` est un champ texte libre valide par
`validate_proxy_zone` contre `PROXY_LOAD_BALANCING_STRATEGIES` (pas un
menu deroulant - Textual `Select` introduirait une divergence d'UX avec
le reste de l'ecran, tous champs `Input`) - le texte d'aide liste les
valeurs admises en clair.

Phase 5bis (affinite de session + routage conditionnel, §17) : 3e etape
ajoutee apres les backends - `RoutingRuleEditorScreen` (optionnel,
"Valider" avec une liste vide reste accepte). Champs sticky
(`sticky_session_enabled`/`sticky_cookie_name`/
`sticky_cookie_max_age_seconds`) rattaches a l'etape 1 (ce sont des
champs simples de ZONE, pas une structure a liste comme les regles).

Phase 7 (charge reelle, §19) : `load_source`/`load_check_path` sont des
champs PAR UPSTREAM (etape 2, `UpstreamEditorScreen`) - une meme zone
peut melanger un backend natif OMEGA-SERV et un backend declaratif
heterogene. Les parametres de polling (`load_poll_interval_seconds`/
`load_poll_timeout_seconds`/`load_smoothing_samples`/
`load_sample_max_age_seconds`) restent des champs de ZONE (etape 1) -
sans effet si aucun upstream n'a `load_source != "none"` NI
`active_health_check_enabled=True` (voir ci-dessous). La strategie
"real_load" rejoint la liste admise par `load_balancing`.

Phase 7bis (backpressure, §20) : `max_concurrent_requests` est aussi un
champ PAR UPSTREAM (etape 2) - `None`/vide (defaut) = illimite, jamais
une limite imposee sans configuration explicite.

Controle actif (§18.2, differe depuis la Phase 6, ferme a la reouverture
du §23 angle mort) : `active_health_check_enabled`/
`active_health_check_path` rejoignent les champs PAR UPSTREAM (etape 2)
- independants de `load_source` (un upstream peut activer la sonde de
charge, la sonde de sante active, les deux, ou aucune), reutilisent le
MEME mecanisme de tache de fond (`load_poll_interval_seconds`/
`load_poll_timeout_seconds` de la zone s'appliquent donc aussi a cette
sonde) mais n'alimentent jamais de score de charge.

Phase 8 (cache, §21) : `cache_enabled`/`cache_default_ttl_seconds`/
`cache_respect_upstream_headers`/`cache_allow_set_cookie` sont des
champs de ZONE (etape 1) - DISTINCTS de la politique `Cache-Control`
existante (fallback fichier statique, §29.1/§30.2, jamais le meme mot
"cache" sans qualificatif). Le plafond de taille GLOBAL
(`cache_max_size_mb`, partage par toutes les zones) et les actions de
purge/statistiques vivent dans l'ecran dedie
`reverse_proxy_cache_screen.py`, pas ici.

L'activation/desactivation de l'option elle-meme reste le role de
l'ecran Options (menu 2, meme convention que access_control_screen.py)
- ce sous-ecran ne touche que le contenu de la liste, jamais
`enabled`.

Bouton "Etat en direct" (§22, reouverture) : ouvre
`ReverseProxyUpstreamStatusScreen` pour la zone selectionnee - ferme
l'angle mort "declencheur TUI DRAINING/MAINTENANCE differe" (§18.3) via
la route `/.omega-serv-admin/health`, jamais une modification en
memoire de CET ecran (qui ne tourne pas dans le processus serveur)."""
from __future__ import annotations

from dataclasses import replace
from typing import TYPE_CHECKING

from textual.app import ComposeResult
from textual.containers import Container, Horizontal, Vertical
from textual.widgets import Button, DataTable, Footer, Header, Static

from omega_serv.application.config.load_config import load_config
from omega_serv.core.i18n import _
from omega_serv.domain.config.option import Option
from omega_serv.domain.routing.proxy_zone import (
    PROXY_LOAD_BALANCING_STRATEGIES,
    ProxyZone,
    RoutingRule,
    UpstreamTarget,
    parse_proxy_zones,
    validate_proxy_zone,
)
from omega_serv.interfaces.tui.screens._base import OmegaScreen
from omega_serv.interfaces.tui.screens._zone_overlap_notice import notify_zone_prefix_overlaps
from omega_serv.interfaces.tui.screens.confirm import ConfirmScreen
from omega_serv.interfaces.tui.screens.dynamic_form_screen import DynamicFormScreen
from omega_serv.interfaces.tui.screens.restart_prompt import notify_reload_required
from omega_serv.interfaces.tui.screens.reverse_proxy_upstream_status_screen import (
    ReverseProxyUpstreamStatusScreen,
)
from omega_serv.interfaces.tui.screens.routing_rule_editor_screen import RoutingRuleEditorScreen
from omega_serv.interfaces.tui.screens.upstream_editor_screen import UpstreamEditorScreen
from omega_serv.interfaces.tui.yes_no import is_no, is_yes, to_text

if TYPE_CHECKING:
    from omega_serv.bootstrap.container import DependencyContainer


class ReverseProxyScreen(OmegaScreen):
    def __init__(self, *, container: DependencyContainer) -> None:
        super().__init__()
        self._container = container
        self._selected_index: int | None = None

    def compose(self) -> ComposeResult:
        yield Header()
        with Vertical(classes="omega-panel"):
            yield Static(_("REVERSE PROXY SORTANT"), classes="omega-title")
            yield Static(
                _("Cette fonction permet à Omega-Serv de se comporter lui-même comme un reverse "
                "proxy : au lieu de servir des fichiers, il redirigé les requêtes reçues vers un "
                "ou plusieurs serveurs backend que vous indiquez, puis renvoie leur réponse au "
                "client. Avant de créer une zone, l'option doit d'abord être activée depuis le "
                "menu Options — sa toute première activation exige un redémarrage complet du "
                "serveur ; modifier les zones ensuite se recharge à chaud, sans coupure.\n\n"
                "Pour créer ou modifier une zone, vous renseignez d'abord ses réglages généraux "
                "(préfixe d'URL à intercepter, stratégie de répartition, délais réseau), puis la "
                "liste de ses serveurs backends (adresse, port, chiffrement, poids) sur un second "
                "écran dédié.\n\n"
                "Si vous indiquez plusieurs backends pour une même zone, le trafic est réparti "
                "entre eux selon la stratégie choisie — à tour de rôle, en tenant compte d'un "
                "poids que vous attribuez à chacun, en privilégiant celui qui a le moins de "
                "connexions en cours, en orientant toujours un même client vers le même backend, "
                "en privilégiant le plus rapide en moyenne, ou en interrogeant en temps réel la "
                "charge effective de chaque backend pour choisir le moins chargé (les valeurs "
                "possibles sont listées dans le champ correspondant).\n\n"
                "Omega-Serv surveille automatiquement la disponibilité de chaque backend et cesse "
                "de lui envoyer du trafic s'il ne répond plus plusieurs fois de suite ; vous "
                "pouvez aussi activer, par backend, une vérification active et périodique "
                "indépendante du trafic réel, ainsi qu'un plafond de connexions simultanées pour "
                "éviter de le saturer. Une fois une zone sélectionnée, le bouton « État en "
                "direct » affiche l'état réel de ses backends et permet d'en mettre un "
                "temporairement en pause, sans toucher à la configuration.\n\n"
                "Vous pouvez également activer le maintien de session (un même client est "
                "toujours redirigé vers le même backend, via un cookie), des règles de routage "
                "selon un en-tête de la requête, la prise en charge du WebSocket, et un cache des "
                "réponses (à configurer et consulter depuis l'écran « Cache du reverse proxy »). "
                "Comme pour le reste des zones du projet, c'est le préfixe le plus long qui "
                "correspond qui l'emporte toujours."),
                classes="omega-hint",
            )
            yield Static("", id="form-error", classes="omega-hint")
            yield DataTable(id="proxy-zones-table")
            with Horizontal(classes="omega-actions"):
                with Container(classes="omega-btn-frame"):
                    yield Button(_("Ajouter"), id="add", variant="primary")
                with Container(classes="omega-btn-frame"):
                    yield Button(_("Modifier"), id="edit", disabled=True)
                with Container(classes="omega-btn-frame"):
                    yield Button(_("Supprimer"), id="delete", variant="error", disabled=True)
                with Container(classes="omega-btn-frame"):
                    yield Button(_("État en direct"), id="live-status", disabled=True)
                with Container(classes="omega-btn-frame"):
                    yield Button(_("Retour"), id="back")
        yield Footer()

    def on_mount(self) -> None:
        table = self.query_one("#proxy-zones-table", DataTable)
        table.cursor_type = "row"
        table.add_columns(_("Préfixe URL"), _("Stratégie"), _("Upstreams"), _("Préserve Host"), _("Vérifie TLS"), "WebSocket", _("Sticky"))
        self._refresh_table()

    def _zones(self) -> list[ProxyZone]:
        result = load_config(self._container.configuration, self._container.config_file)
        if not result.success or result.config is None:
            return []
        option = result.config.options.get("reverse_proxy")
        if option is None:
            return []
        return parse_proxy_zones(option.settings.get("zones", []))

    @staticmethod
    def _format_upstreams(upstreams: tuple[UpstreamTarget, ...]) -> str:
        return ", ".join(
            f"{'https://' if u.use_tls else ''}{u.host}:{u.port}" + ("" if u.weight == 1 else f" (poids {u.weight})")
            for u in upstreams
        )

    def _refresh_table(self) -> None:
        table = self.query_one("#proxy-zones-table", DataTable)
        table.clear()
        for index, zone in enumerate(self._zones()):
            table.add_row(
                zone.url_prefix, zone.load_balancing, self._format_upstreams(zone.upstreams),
                _("Oui") if zone.preserve_host_header else _("Non"),
                _("Oui") if zone.verify_upstream_tls else _("Non"),
                _("Oui") if zone.websocket_enabled else _("Non"),
                _("Oui") if zone.sticky_session_enabled else _("Non"), key=str(index),
            )
        self._selected_index = None
        self.query_one("#edit", Button).disabled = True
        self.query_one("#delete", Button).disabled = True
        self.query_one("#live-status", Button).disabled = True

    def on_data_table_row_selected(self, event: DataTable.RowSelected) -> None:
        self._selected_index = int(str(event.row_key.value))
        self.query_one("#edit", Button).disabled = False
        self.query_one("#delete", Button).disabled = False
        self.query_one("#live-status", Button).disabled = False

    def _fields_for(self, zone: ProxyZone | None) -> list[tuple[str, str, str]]:
        z = zone or ProxyZone(url_prefix="")
        return [
            ("url_prefix", _("Préfixe URL (ex: /api/)"), z.url_prefix),
            (
                "load_balancing",
                _("Stratégie de répartition ({value})").format(value=', '.join(PROXY_LOAD_BALANCING_STRATEGIES)),
                z.load_balancing,
            ),
            ("connect_timeout_seconds", _("Délai de connexion (secondes)"), str(z.connect_timeout_seconds)),
            ("read_timeout_seconds", _("Délai de lecture (secondes)"), str(z.read_timeout_seconds)),
            ("preserve_host_header", _("Préserver le Host: du client (oui/non)"), to_text(z.preserve_host_header)),
            (
                "verify_upstream_tls",
                _("Vérifier le certificat des upstreams HTTPS (oui/non - non = DANGEREUX, MITM possible)"),
                to_text(z.verify_upstream_tls),
            ),
            (
                "websocket_enabled",
                _("Autoriser Upgrade: websocket sur cette zone (oui/non)"),
                to_text(z.websocket_enabled),
            ),
            (
                "sticky_session_enabled",
                _("Affinité de session par cookie (oui/non)"),
                to_text(z.sticky_session_enabled),
            ),
            ("sticky_cookie_name", _("Nom du cookie sticky (sans effet si affinité désactivée)"), z.sticky_cookie_name),
            (
                "sticky_cookie_max_age_seconds",
                _("Durée de vie du cookie sticky (secondes, sans effet si affinité désactivée)"),
                str(z.sticky_cookie_max_age_seconds),
            ),
            (
                "unhealthy_after",
                _("Nombre d'échecs consécutifs avant de marquer un backend hors service (entier >= 1)"),
                str(z.unhealthy_after),
            ),
            (
                "healthy_after",
                _("Nombre de succès consécutifs avant de le remettre en service (entier >= 1)"),
                str(z.healthy_after),
            ),
            (
                "load_poll_interval_seconds",
                _("Période entre deux sondes de charge (secondes, sans effet si aucun backend n'a load_source != none)"),
                str(z.load_poll_interval_seconds),
            ),
            (
                "load_poll_timeout_seconds",
                _("Timeout d'une sonde de charge (secondes, reste COURT - §19.1)"),
                str(z.load_poll_timeout_seconds),
            ),
            (
                "load_smoothing_samples",
                _("Nombre d'échantillons lisses par moyenne glissante (entier >= 1)"),
                str(z.load_smoothing_samples),
            ),
            (
                "load_sample_max_age_seconds",
                _("Âge maximal d'un échantillon de charge avant d'être considéré périmé (secondes)"),
                str(z.load_sample_max_age_seconds),
            ),
            (
                "cache_enabled",
                (_("Mettre en cache les réponses de cette zone (oui/non - §21, DISTINCT de la "
                 "politique Cache-Control du fallback fichier statique)")),
                to_text(z.cache_enabled),
            ),
            (
                "cache_default_ttl_seconds",
                (_("Durée de vie par défaut d'une entrée (secondes, utilisée si le backend ne "
                 "pose pas de Cache-Control exploitable)")),
                str(z.cache_default_ttl_seconds),
            ),
            (
                "cache_respect_upstream_headers",
                (_("Respecter Cache-Control du backend (oui/non - non = DANGEREUX, met en cache "
                 "même un no-store)")),
                to_text(z.cache_respect_upstream_headers),
            ),
            (
                "cache_allow_set_cookie",
                (_("Mettre en cache même une réponse avec Set-Cookie (oui/non - non = défaut sur, "
                 "RISQUE de resservir le cookie d'un client à un autre)")),
                to_text(z.cache_allow_set_cookie),
            ),
        ]

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "back":
            self.dismiss()
            return
        if event.button.id == "add":
            self.app.push_screen(
                DynamicFormScreen(title=_("AJOUTER UNE ZONE PROXY (1/2 : paramètres)"), fields=self._fields_for(None)),
                lambda values: self._zone_fields_confirmed(values, existing_zone=None),
            )
            return
        if event.button.id == "edit" and self._selected_index is not None:
            zone = self._zones()[self._selected_index]
            self.app.push_screen(
                DynamicFormScreen(title=_("MODIFIER LA ZONE PROXY (1/2 : paramètres)"), fields=self._fields_for(zone)),
                lambda values: self._zone_fields_confirmed(values, existing_zone=zone),
            )
            return
        if event.button.id == "delete" and self._selected_index is not None:
            self.app.push_screen(
                ConfirmScreen(title=_("SUPPRIMER LA ZONE"), message=_("Confirmer la suppression de cette zone proxy ?")),
                self._delete_zone,
            )
            return
        if event.button.id == "live-status" and self._selected_index is not None:
            zone = self._zones()[self._selected_index]
            self.app.push_screen(ReverseProxyUpstreamStatusScreen(container=self._container, zone=zone))

    def _zone_from_values(self, values: dict[str, str]) -> ProxyZone | None:
        """Construit une zone PARTIELLE (upstreams et routing_rules
        toujours vides a ce stade - saisis aux etapes 2/3 via
        `UpstreamEditorScreen`/`RoutingRuleEditorScreen`, cf
        `_zone_fields_confirmed`/`_upstreams_confirmed`)."""
        try:
            connect_timeout = float(values["connect_timeout_seconds"].strip())
            read_timeout = float(values["read_timeout_seconds"].strip())
            sticky_max_age = int(values["sticky_cookie_max_age_seconds"].strip())
            unhealthy_after = int(values["unhealthy_after"].strip())
            healthy_after = int(values["healthy_after"].strip())
            load_poll_interval = float(values["load_poll_interval_seconds"].strip())
            load_poll_timeout = float(values["load_poll_timeout_seconds"].strip())
            load_smoothing_samples = int(values["load_smoothing_samples"].strip())
            load_sample_max_age = float(values["load_sample_max_age_seconds"].strip())
            cache_default_ttl = float(values["cache_default_ttl_seconds"].strip())
        except ValueError:
            self.query_one("#form-error", Static).update(_("Delais/duree/seuils invalides (nombres attendus)."))
            return None
        return ProxyZone(
            url_prefix=values["url_prefix"].strip(),
            upstreams=(),
            connect_timeout_seconds=connect_timeout,
            read_timeout_seconds=read_timeout,
            preserve_host_header=is_yes(values["preserve_host_header"]),
            verify_upstream_tls=not is_no(values["verify_upstream_tls"]),
            websocket_enabled=is_yes(values["websocket_enabled"]),
            load_balancing=values["load_balancing"].strip(),
            sticky_session_enabled=is_yes(values["sticky_session_enabled"]),
            sticky_cookie_name=values["sticky_cookie_name"].strip(),
            sticky_cookie_max_age_seconds=sticky_max_age,
            routing_rules=(),
            unhealthy_after=unhealthy_after,
            healthy_after=healthy_after,
            load_poll_interval_seconds=load_poll_interval,
            load_poll_timeout_seconds=load_poll_timeout,
            load_smoothing_samples=load_smoothing_samples,
            load_sample_max_age_seconds=load_sample_max_age,
            cache_enabled=is_yes(values["cache_enabled"]),
            cache_default_ttl_seconds=cache_default_ttl,
            cache_respect_upstream_headers=not is_no(values["cache_respect_upstream_headers"]),
            cache_allow_set_cookie=is_yes(values["cache_allow_set_cookie"]),
        )

    def _zone_fields_confirmed(self, values: dict[str, str] | None, *, existing_zone: ProxyZone | None) -> None:
        if values is None:
            return
        partial_zone = self._zone_from_values(values)
        if partial_zone is None:
            return
        initial_upstreams = list(existing_zone.upstreams) if existing_zone is not None else []
        self.app.push_screen(
            UpstreamEditorScreen(upstreams=initial_upstreams),
            lambda upstreams: self._upstreams_confirmed(upstreams, partial_zone=partial_zone, existing_zone=existing_zone),
        )

    def _upstreams_confirmed(
        self, upstreams: list[UpstreamTarget] | None, *, partial_zone: ProxyZone, existing_zone: ProxyZone | None,
    ) -> None:
        if upstreams is None:
            return
        zone_with_upstreams = replace(partial_zone, upstreams=tuple(upstreams))
        initial_rules = list(existing_zone.routing_rules) if existing_zone is not None else []
        self.app.push_screen(
            RoutingRuleEditorScreen(rules=initial_rules, upstreams=upstreams),
            lambda rules: self._routing_rules_confirmed(rules, zone_with_upstreams=zone_with_upstreams, existing_zone=existing_zone),
        )

    def _routing_rules_confirmed(
        self, rules: list[RoutingRule] | None, *, zone_with_upstreams: ProxyZone, existing_zone: ProxyZone | None,
    ) -> None:
        if rules is None:
            return
        zone = replace(zone_with_upstreams, routing_rules=tuple(rules))
        error = validate_proxy_zone(zone)
        if error is not None:
            self.query_one("#form-error", Static).update(_("Erreur : {error}").format(error=error))
            return
        zones = self._zones()
        if existing_zone is None:
            zones.append(zone)
        else:
            assert self._selected_index is not None  # garanti par le bouton "Modifier" qui a declenche ce flux
            zones[self._selected_index] = zone
        self.query_one("#form-error", Static).update("")
        self._save_zones(zones)

    def _delete_zone(self, confirmed: bool | None) -> None:
        if not confirmed or self._selected_index is None:
            return
        zones = self._zones()
        del zones[self._selected_index]
        self._save_zones(zones)

    def _save_zones(self, zones: list[ProxyZone]) -> None:
        load_result = load_config(self._container.configuration, self._container.config_file)
        if not load_result.success or load_result.config is None:
            self.query_one("#form-error", Static).update(_("Erreur de configuration - impossible d'enregistrer."))
            return
        existing = load_result.config.options.get("reverse_proxy")
        enabled = existing.enabled if existing is not None else False
        new_settings = dict(existing.settings) if existing is not None else {}
        new_settings["zones"] = [
            {
                "url_prefix": z.url_prefix,
                "upstreams": [
                    {
                        "host": u.host, "port": u.port, "use_tls": u.use_tls, "weight": u.weight,
                        "load_source": u.load_source, "load_check_path": u.load_check_path,
                        "max_concurrent_requests": u.max_concurrent_requests,
                        "active_health_check_enabled": u.active_health_check_enabled,
                        "active_health_check_path": u.active_health_check_path,
                    }
                    for u in z.upstreams
                ],
                "connect_timeout_seconds": z.connect_timeout_seconds, "read_timeout_seconds": z.read_timeout_seconds,
                "preserve_host_header": z.preserve_host_header,
                "verify_upstream_tls": z.verify_upstream_tls,
                "websocket_enabled": z.websocket_enabled,
                "load_balancing": z.load_balancing,
                "sticky_session_enabled": z.sticky_session_enabled,
                "sticky_cookie_name": z.sticky_cookie_name,
                "sticky_cookie_max_age_seconds": z.sticky_cookie_max_age_seconds,
                "routing_rules": [
                    {"header_name": r.header_name, "pattern": r.pattern, "upstream_key": r.upstream_key}
                    for r in z.routing_rules
                ],
                "unhealthy_after": z.unhealthy_after,
                "healthy_after": z.healthy_after,
                "load_poll_interval_seconds": z.load_poll_interval_seconds,
                "load_poll_timeout_seconds": z.load_poll_timeout_seconds,
                "load_smoothing_samples": z.load_smoothing_samples,
                "load_sample_max_age_seconds": z.load_sample_max_age_seconds,
                "cache_enabled": z.cache_enabled,
                "cache_default_ttl_seconds": z.cache_default_ttl_seconds,
                "cache_respect_upstream_headers": z.cache_respect_upstream_headers,
                "cache_allow_set_cookie": z.cache_allow_set_cookie,
            }
            for z in zones
        ]
        new_options = dict(load_result.config.options)
        new_options["reverse_proxy"] = Option(name="reverse_proxy", enabled=enabled, settings=new_settings)
        new_config = replace(load_result.config, options=new_options)
        self._container.configuration.save(self._container.config_file, new_config)
        self.query_one("#form-error", Static).update("")
        self._refresh_table()
        notify_zone_prefix_overlaps(self, self._container, "reverse_proxy")
        notify_reload_required(self, self._container, _("Zones de reverse proxy mises à jour."))
