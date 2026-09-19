"""Sous-ecran Reverse proxy sortant (OMEGA-SERV_PLAN-DETAILLE_REVERSE_PROXY.md,
phases 2-4 : plusieurs upstreams par zone avec repartition de charge
round-robin, chacun HTTP ou HTTPS, saisis comme un champ unique
"[https://]host:port, [https://]host:port, ..." (prefixe "https://"
optionnel par upstream, defaut HTTP) - meme convention que `index_files`
dans base_config_screen.py, chaines a plat cote TUI, converties en tuple
d'`UpstreamTarget` cote domaine. Verification TLS (`verify_upstream_tls`)
reste une politique de zone, pas par upstream (§5.3 du document).
`websocket_enabled` (§4) autorise la mise a niveau `Upgrade: websocket`
sur cette zone - une fois le tube etabli, UN SEUL upstream reste fige
pour toute sa duree de vie (plus de round-robin par requete comme pour
le relai HTTP ordinaire) - CRUD complet sur
`options["reverse_proxy"].settings["zones"]` (domain/routing/
proxy_zone.py::ProxyZone). A ne jamais confondre avec `server.tls.mode
= "behind_proxy"` (OMEGA-SERV DERRIERE un proxy, mecanisme different) -
ici OMEGA-SERV est lui-meme le proxy, vers un ou plusieurs backends.

L'activation/desactivation de l'option elle-meme reste le role de
l'ecran Options (menu 2, meme convention que access_control_screen.py)
- ce sous-ecran ne touche que le contenu de la liste, jamais
`enabled`."""
from __future__ import annotations

from dataclasses import replace
from typing import TYPE_CHECKING

from textual.app import ComposeResult
from textual.containers import Container, Horizontal, Vertical
from textual.widgets import Button, DataTable, Footer, Header, Static

from omega_serv.application.config.load_config import load_config
from omega_serv.domain.config.option import Option
from omega_serv.domain.routing.proxy_zone import (
    ProxyZone,
    UpstreamTarget,
    parse_proxy_zones,
    validate_proxy_zone,
)
from omega_serv.interfaces.tui.screens._base import OmegaScreen
from omega_serv.interfaces.tui.screens.confirm import ConfirmScreen
from omega_serv.interfaces.tui.screens.dynamic_form_screen import DynamicFormScreen
from omega_serv.interfaces.tui.screens.restart_prompt import notify_reload_required

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
            yield Static("REVERSE PROXY SORTANT", classes="omega-title")
            yield Static(
                "L'activation de l'option 'reverse_proxy' se fait dans le menu Options - "
                "necessite un REDEMARRAGE COMPLET pour sa premiere activation (jamais un "
                "simple rechargement). Un ou plusieurs upstreams par zone, separes par des "
                "virgules (ex: 127.0.0.1:3000, https://127.0.0.1:3443) - repartition de charge "
                "round-robin si plusieurs, prefixe 'https://' optionnel par upstream. WebSocket "
                "activable par zone (Upgrade: websocket - un seul upstream fige pour la duree du "
                "tube une fois etabli). Plus long prefixe correspondant gagne (meme regle que "
                "le reste du projet).",
                classes="omega-hint",
            )
            yield Static("", id="form-error", classes="omega-hint")
            yield DataTable(id="proxy-zones-table")
            with Horizontal(classes="omega-actions"):
                with Container(classes="omega-btn-frame"):
                    yield Button("Ajouter", id="add", variant="primary")
                with Container(classes="omega-btn-frame"):
                    yield Button("Modifier", id="edit", disabled=True)
                with Container(classes="omega-btn-frame"):
                    yield Button("Supprimer", id="delete", variant="error", disabled=True)
                with Container(classes="omega-btn-frame"):
                    yield Button("Retour", id="back")
        yield Footer()

    def on_mount(self) -> None:
        table = self.query_one("#proxy-zones-table", DataTable)
        table.cursor_type = "row"
        table.add_columns("Prefixe URL", "Upstreams", "Preserve Host", "Verifie TLS", "WebSocket")
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
        return ", ".join(f"{'https://' if u.use_tls else ''}{u.host}:{u.port}" for u in upstreams)

    @staticmethod
    def _parse_upstreams(text: str) -> list[UpstreamTarget] | None:
        """None signale un format invalide (host:port attendu pour
        chaque element separe par des virgules, avec un prefixe
        "https://" optionnel) - distinct d'une liste vide, qui est
        aussi rejetee mais plus loin par validate_proxy_zone (message
        d'erreur different, "au moins un upstream est requis")."""
        upstreams: list[UpstreamTarget] = []
        for chunk in text.split(","):
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
                return None
            try:
                port = int(port_text.strip())
            except ValueError:
                return None
            upstreams.append(UpstreamTarget(host=host.strip(), port=port, use_tls=use_tls))
        return upstreams

    def _refresh_table(self) -> None:
        table = self.query_one("#proxy-zones-table", DataTable)
        table.clear()
        for index, zone in enumerate(self._zones()):
            table.add_row(
                zone.url_prefix, self._format_upstreams(zone.upstreams),
                "Oui" if zone.preserve_host_header else "Non",
                "Oui" if zone.verify_upstream_tls else "Non",
                "Oui" if zone.websocket_enabled else "Non", key=str(index),
            )
        self._selected_index = None
        self.query_one("#edit", Button).disabled = True
        self.query_one("#delete", Button).disabled = True

    def on_data_table_row_selected(self, event: DataTable.RowSelected) -> None:
        self._selected_index = int(str(event.row_key.value))
        self.query_one("#edit", Button).disabled = False
        self.query_one("#delete", Button).disabled = False

    def _fields_for(self, zone: ProxyZone | None) -> list[tuple[str, str, str]]:
        z = zone or ProxyZone(url_prefix="")
        return [
            ("url_prefix", "Prefixe URL (ex: /api/)", z.url_prefix),
            ("upstreams", "Upstreams (host:port, separes par des virgules)", self._format_upstreams(z.upstreams)),
            ("connect_timeout_seconds", "Delai de connexion (secondes)", str(z.connect_timeout_seconds)),
            ("read_timeout_seconds", "Delai de lecture (secondes)", str(z.read_timeout_seconds)),
            ("preserve_host_header", "Preserver le Host: du client (oui/non)", "oui" if z.preserve_host_header else "non"),
            (
                "verify_upstream_tls",
                "Verifier le certificat des upstreams HTTPS (oui/non - non = DANGEREUX, MITM possible)",
                "oui" if z.verify_upstream_tls else "non",
            ),
            (
                "websocket_enabled",
                "Autoriser Upgrade: websocket sur cette zone (oui/non)",
                "oui" if z.websocket_enabled else "non",
            ),
        ]

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "back":
            self.dismiss()
            return
        if event.button.id == "add":
            self.app.push_screen(
                DynamicFormScreen(title="AJOUTER UNE ZONE PROXY", fields=self._fields_for(None)),
                self._add_zone,
            )
            return
        if event.button.id == "edit" and self._selected_index is not None:
            zone = self._zones()[self._selected_index]
            self.app.push_screen(
                DynamicFormScreen(title="MODIFIER LA ZONE PROXY", fields=self._fields_for(zone)),
                self._edit_zone,
            )
            return
        if event.button.id == "delete" and self._selected_index is not None:
            self.app.push_screen(
                ConfirmScreen(title="SUPPRIMER LA ZONE", message="Confirmer la suppression de cette zone proxy ?"),
                self._delete_zone,
            )

    def _zone_from_values(self, values: dict[str, str]) -> ProxyZone | None:
        upstreams = self._parse_upstreams(values["upstreams"])
        if upstreams is None:
            self.query_one("#form-error", Static).update(
                f"Upstreams invalides (attendu : host:port, host:port, ...) : {values['upstreams']!r}"
            )
            return None
        try:
            connect_timeout = float(values["connect_timeout_seconds"].strip())
            read_timeout = float(values["read_timeout_seconds"].strip())
        except ValueError:
            self.query_one("#form-error", Static).update("Delais invalides (nombres attendus).")
            return None
        return ProxyZone(
            url_prefix=values["url_prefix"].strip(),
            upstreams=tuple(upstreams),
            connect_timeout_seconds=connect_timeout,
            read_timeout_seconds=read_timeout,
            preserve_host_header=values["preserve_host_header"].strip().lower() in ("oui", "yes", "true"),
            verify_upstream_tls=values["verify_upstream_tls"].strip().lower() not in ("non", "no", "false"),
            websocket_enabled=values["websocket_enabled"].strip().lower() in ("oui", "yes", "true"),
        )

    def _add_zone(self, values: dict[str, str] | None) -> None:
        if values is None:
            return
        zone = self._zone_from_values(values)
        if zone is None:
            return
        error = validate_proxy_zone(zone)
        if error is not None:
            self.query_one("#form-error", Static).update(f"Erreur : {error}")
            return
        zones = self._zones()
        zones.append(zone)
        self._save_zones(zones)

    def _edit_zone(self, values: dict[str, str] | None) -> None:
        if values is None or self._selected_index is None:
            return
        zone = self._zone_from_values(values)
        if zone is None:
            return
        error = validate_proxy_zone(zone)
        if error is not None:
            self.query_one("#form-error", Static).update(f"Erreur : {error}")
            return
        zones = self._zones()
        zones[self._selected_index] = zone
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
            self.query_one("#form-error", Static).update("Erreur de configuration - impossible d'enregistrer.")
            return
        existing = load_result.config.options.get("reverse_proxy")
        enabled = existing.enabled if existing is not None else False
        new_settings = dict(existing.settings) if existing is not None else {}
        new_settings["zones"] = [
            {
                "url_prefix": z.url_prefix,
                "upstreams": [{"host": u.host, "port": u.port, "use_tls": u.use_tls} for u in z.upstreams],
                "connect_timeout_seconds": z.connect_timeout_seconds, "read_timeout_seconds": z.read_timeout_seconds,
                "preserve_host_header": z.preserve_host_header,
                "verify_upstream_tls": z.verify_upstream_tls,
                "websocket_enabled": z.websocket_enabled,
            }
            for z in zones
        ]
        new_options = dict(load_result.config.options)
        new_options["reverse_proxy"] = Option(name="reverse_proxy", enabled=enabled, settings=new_settings)
        new_config = replace(load_result.config, options=new_options)
        self._container.configuration.save(self._container.config_file, new_config)
        self.query_one("#form-error", Static).update("")
        self._refresh_table()
        notify_reload_required(self, self._container, "Zones de reverse proxy mises a jour.")
