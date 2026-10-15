"""Ecran Cache du reverse proxy (OMEGA-SERV_PLAN-DETAILLE_REVERSE_PROXY.md
§21 : Phase 8) - DISTINCT de la politique `Cache-Control` existante
(fallback fichier statique, §29.1/§30.2 - jamais le meme mot "cache"
sans qualificatif dans un libelle).

Nombre d'entrees et taille sur disque sont lus directement de
`var/cache/reverse_proxy/` (meme instance `FilesystemProxyCacheStore`
que celle que le serveur utiliserait, pointant vers le MEME repertoire -
`stats()`/`clear()` scannent toujours le disque, jamais un etat memoire
partage entre processus, voir docstring du store) - fonctionne a froid
(serveur eteint) comme a chaud (serveur en cours), toujours correct.

**Ratio hits/miss** (§22, reouverture - l'ecart assume depuis la Phase 8
initiale est desormais ferme) : lu via `/.omega-serv-admin/cache-stats`
(meme route et meme regime d'injection - `container.admin_request_runner`
- que `reverse_proxy_upstream_status_screen.py`), un vrai appel HTTP
local vers le PROCESSUS SERVEUR reellement en cours d'execution. Jamais
bloquant pour le reste de l'ecran : un serveur eteint ou injoignable
affiche "indisponible" pour CE SEUL champ, les statistiques disque
restent toujours correctes independamment. Compteurs EN MEMOIRE,
"depuis le dernier demarrage" (jamais persistes, voir
`domain/routing/proxy_cache_metrics.py`) - un rechargement SIGHUP ne les
remet jamais a zero, seul un redemarrage complet le fait. Le diagnostic
PAR REQUETE reste l'en-tete `X-Omega-Cache` (HIT/MISS/BYPASS),
consultable via les outils du navigateur ou `curl -I`."""
from __future__ import annotations

from dataclasses import replace
from typing import TYPE_CHECKING

from textual.app import ComposeResult
from textual.containers import Container, Horizontal, Vertical
from textual.widgets import Button, Footer, Header, Static

from omega_serv.application.config.load_config import load_config
from omega_serv.domain.config.option import Option
from omega_serv.interfaces.tui.screens._base import OmegaScreen
from omega_serv.interfaces.tui.screens.confirm import ConfirmScreen
from omega_serv.interfaces.tui.screens.dynamic_form_screen import DynamicFormScreen

if TYPE_CHECKING:
    from omega_serv.bootstrap.container import DependencyContainer
    from omega_serv.ports.proxy_cache_store_port import ProxyCacheStorePort

_DEFAULT_CACHE_MAX_SIZE_MB = 100


class ReverseProxyCacheScreen(OmegaScreen):
    def __init__(self, *, container: DependencyContainer) -> None:
        super().__init__()
        self._container = container

    def compose(self) -> ComposeResult:
        yield Header()
        with Vertical(classes="omega-panel"):
            yield Static("CACHE DU REVERSE PROXY", classes="omega-title")
            yield Static(
                "Nombre d'entrees et taille occupee sur disque (var/cache/reverse_proxy/) - "
                "lus directement, fonctionne que le serveur soit demarre ou non. Ratio hits/miss "
                "interroge le serveur en direct (indisponible s'il est eteint ou injoignable).",
                classes="omega-hint",
            )
            yield Static("", id="cache-stats")
            yield Static("", id="cache-ratio", classes="omega-hint")
            yield Static("", id="cache-error", classes="omega-hint")
            with Horizontal(classes="omega-actions"):
                with Container(classes="omega-btn-frame"):
                    yield Button("Actualiser", id="refresh", variant="primary")
                with Container(classes="omega-btn-frame"):
                    yield Button("Modifier le plafond", id="edit-max-size")
            with Horizontal(classes="omega-actions"):
                with Container(classes="omega-btn-frame"):
                    yield Button("Purger une zone", id="purge-zone")
                with Container(classes="omega-btn-frame"):
                    yield Button("Purger tout", id="purge-all", variant="error")
                with Container(classes="omega-btn-frame"):
                    yield Button("Retour", id="back")
        yield Footer()

    def on_mount(self) -> None:
        self.run_worker(self._refresh(), exclusive=True)

    def _max_size_mb(self) -> int:
        result = load_config(self._container.configuration, self._container.config_file)
        if not result.success or result.config is None:
            return _DEFAULT_CACHE_MAX_SIZE_MB
        option = result.config.options.get("reverse_proxy")
        if option is None:
            return _DEFAULT_CACHE_MAX_SIZE_MB
        return int(option.settings.get("cache_max_size_mb", _DEFAULT_CACHE_MAX_SIZE_MB))

    def _store(self) -> ProxyCacheStorePort:
        return self._container.build_proxy_cache_store(max_size_mb=self._max_size_mb())

    def _port(self) -> int | None:
        result = load_config(self._container.configuration, self._container.config_file)
        if not result.success or result.config is None:
            return None
        return result.config.server.port

    async def _fetch_hit_ratio_text(self) -> str:
        runner = self._container.admin_request_runner
        if runner is None:
            return "Ratio hits/miss : indisponible dans cet environnement."
        port = self._port()
        if port is None:
            return "Ratio hits/miss : indisponible (configuration illisible)."
        result = await runner(port, "GET", "/.omega-serv-admin/cache-stats")
        if result is None:
            return (
                "Ratio hits/miss : serveur injoignable - verifiez qu'il est demarre et que "
                "trusted_proxy autorise 127.0.0.1."
            )
        status, body = result
        if status != 200 or body is None:
            return f"Ratio hits/miss : indisponible (statut {status})."
        hits, misses = int(body.get("hits", 0)), int(body.get("misses", 0))
        total = hits + misses
        if total == 0:
            return "Ratio hits/miss : aucune requete cacheable servie depuis le dernier demarrage."
        return (
            f"Ratio hits/miss depuis le dernier demarrage du serveur : {hits} hit(s) / "
            f"{misses} miss(es) ({hits / total * 100:.0f}% de hits)."
        )

    async def _refresh(self) -> None:
        stats = self._store().stats()
        size_mb = stats.total_size_bytes / (1024 * 1024)
        self.query_one("#cache-stats", Static).update(
            f"{stats.entry_count} entree(s) - {size_mb:.2f} Mo sur disque "
            f"(plafond configure : {self._max_size_mb()} Mo)"
        )
        self.query_one("#cache-ratio", Static).update(await self._fetch_hit_ratio_text())

    async def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "back":
            self.dismiss()
            return
        if event.button.id == "refresh":
            await self._refresh()
            return
        if event.button.id == "edit-max-size":
            self.app.push_screen(
                DynamicFormScreen(
                    title="PLAFOND DE TAILLE DU CACHE",
                    fields=[("cache_max_size_mb", "Taille maximale (Mo, entier >= 1)", str(self._max_size_mb()))],
                ),
                self._apply_max_size,
            )
            return
        if event.button.id == "purge-zone":
            self.app.push_screen(
                DynamicFormScreen(title="PURGER UNE ZONE", fields=[("zone_prefix", "Prefixe de la zone (ex: /api/)", "")]),
                self._confirm_purge_zone,
            )
            return
        if event.button.id == "purge-all":
            self.app.push_screen(
                ConfirmScreen(
                    title="PURGER TOUT LE CACHE",
                    message="Supprimer TOUTES les entrees de cache du reverse proxy, pour TOUTES les zones ?",
                ),
                self._purge_all_if_confirmed,
            )

    def _apply_max_size(self, values: dict[str, str] | None) -> None:
        if values is None:
            return
        try:
            max_size_mb = int(values["cache_max_size_mb"].strip())
        except ValueError:
            self.query_one("#cache-error", Static).update("Plafond invalide (nombre entier attendu).")
            return
        if max_size_mb < 1:
            self.query_one("#cache-error", Static).update("Plafond invalide (doit etre >= 1).")
            return
        load_result = load_config(self._container.configuration, self._container.config_file)
        if not load_result.success or load_result.config is None:
            self.query_one("#cache-error", Static).update("Erreur de configuration - impossible d'enregistrer.")
            return
        existing = load_result.config.options.get("reverse_proxy")
        enabled = existing.enabled if existing is not None else False
        new_settings = dict(existing.settings) if existing is not None else {}
        new_settings["cache_max_size_mb"] = max_size_mb
        new_options = dict(load_result.config.options)
        new_options["reverse_proxy"] = Option(name="reverse_proxy", enabled=enabled, settings=new_settings)
        new_config = replace(load_result.config, options=new_options)
        self._container.configuration.save(self._container.config_file, new_config)
        self.query_one("#cache-error", Static).update("")
        self.run_worker(self._refresh(), exclusive=True)

    def _confirm_purge_zone(self, values: dict[str, str] | None) -> None:
        if values is None:
            return
        zone_prefix = values["zone_prefix"].strip()
        if not zone_prefix:
            self.query_one("#cache-error", Static).update("Prefixe de zone requis.")
            return
        self.app.push_screen(
            ConfirmScreen(title="PURGER CETTE ZONE", message=f"Purger le cache de la zone {zone_prefix!r} ?"),
            lambda confirmed: self._purge_zone_if_confirmed(confirmed, zone_prefix),
        )

    def _purge_zone_if_confirmed(self, confirmed: bool | None, zone_prefix: str) -> None:
        if not confirmed:
            return
        removed = self._store().clear(zone_key=zone_prefix)
        self.query_one("#cache-error", Static).update("")
        self.app.notify(f"{removed} entree(s) purgee(s) pour la zone {zone_prefix!r}.")
        self.run_worker(self._refresh(), exclusive=True)

    def _purge_all_if_confirmed(self, confirmed: bool | None) -> None:
        if not confirmed:
            return
        removed = self._store().clear()
        self.app.notify(f"{removed} entree(s) purgee(s) (toutes zones).")
        self.run_worker(self._refresh(), exclusive=True)
