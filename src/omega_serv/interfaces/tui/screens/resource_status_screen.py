# Copyright (c) 2026 kraynux - kraynux@proton.me - Licence MIT (voir
# fichier LICENSE)
"""Ecran Etat & Ressources (retour utilisateur 2026-09-09) - remplace
"Simuler une requete" comme raccourci direct du menu principal (la
fonction elle-meme reste disponible, reintroduite ici en bouton -
jamais retiree). Trois cadres, rafraichis toutes les 2s
(`Screen.set_interval`, natif Textual - jamais de thread+Live bricole a
la main) :

1. ETAT DU SERVEUR : fichier PID (`application/services/pid_file.py`
   + `core/platform_info.py::is_process_running`) + statut du
   gestionnaire de service (systemd/OpenRC/runit, meme cas d'usage que
   service_screen.py) + configuration active (profil, options activees,
   TLS, bind:port).
2. FLUX (LOG D'ACCES) : transpose depuis omega-fire (interfaces/cli/
   renderers/logs_live.py::LogBuffer/`_render_stats_panel` - meme
   metriques, meme calcul de debit cumule depuis le debut du suivi)
   mais adapte a la source reelle de SERV : `LiveTailPort` (tail
   incremental deja existant, meme mecanisme que
   log_viewer_screen.py::"Suivre en direct") + `parse_combined_log_line`
   (domain/logging/access_log_parser.py, le VRAI format de SERV) au
   lieu du parseur multi-format devinant heuristiquement de fire (fire
   tire des logs de serveurs tiers dont il ne controle pas le format).
   Latence absente deliberement (le format combine de SERV n'en
   enregistre aucune, contrairement au parseur generique de fire qui
   invente une valeur par defaut faute de mieux).
3. RESSOURCES SYSTEME : transpose depuis omega-fire (interfaces/cli/
   renderers/dashboard.py::collect_os_stats(), integralement generique -
   CPU/RAM/disque/reseau/temperatures/uptime, aucune partie specifique
   au pare-feu) via `container.collect_system_stats()` (psutil).

Le tampon de flux et le lecteur de tail sont crees UNE SEULE FOIS a
`on_mount` (jamais recrees a chaque tick) - le calcul de debit cumule
depuis `started_at` et la position de lecture incrementale ont tous
les deux besoin de persister entre deux rafraichissements."""
from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING, Any

from rich.text import Text
from textual.app import ComposeResult
from textual.containers import Center, Container, Horizontal, Vertical
from textual.widgets import Button, Footer, Header, Static

from omega_serv.application.config.load_config import load_config
from omega_serv.application.services.manage_service import get_service_status
from omega_serv.application.services.pid_file import pid_file_status
from omega_serv.core.platform_info import is_process_running
from omega_serv.domain.config.option import KNOWN_OPTION_NAMES
from omega_serv.domain.logging.access_log_parser import parse_combined_log_line
from omega_serv.domain.logging.live_traffic_stats import LiveTrafficBuffer, LiveTrafficStats
from omega_serv.domain.services.entities import ServiceStatus
from omega_serv.interfaces.tui.screens._base import OmegaScreen
from omega_serv.interfaces.tui.screens.simulate_request_screen import SimulateRequestScreen

if TYPE_CHECKING:
    from omega_serv.bootstrap.container import DependencyContainer
    from omega_serv.ports.live_tail_port import LiveTailPort
    from omega_serv.ports.service_manager_port import ServiceManagerPort

_REFRESH_SECONDS = 2.0
_DEFAULT_SERVICE_NAME = "omega-serv"
_SERVICE_NAME_KEY = "service_name"
"""Meme cle que service_screen.py::_SERVICE_NAME_KEY (settings_store,
var/settings.json) - jamais un nom fige, sinon ce panneau afficherait
le statut d'une unite sans rapport apres un renommage dans l'ecran
SERVICE (bug latent signale, corrige ici)."""


def _bytes_to_human(num_bytes: float) -> str:
    for unit in ("B", "Ko", "Mo", "Go"):
        if num_bytes < 1024:
            return f"{num_bytes:.1f} {unit}"
        num_bytes /= 1024
    return f"{num_bytes:.1f} To"


def _progress_bar(percent: float, width: int = 20) -> str:
    filled = int(width * max(0.0, min(100.0, percent)) / 100)
    empty = width - filled
    return f"[{'█' * filled}{'░' * empty}] {percent:5.1f}%"


class ResourceStatusScreen(OmegaScreen):
    def __init__(self, *, container: DependencyContainer) -> None:
        super().__init__()
        self._container = container
        self._manager: ServiceManagerPort | None = None
        self._tail_reader: LiveTailPort | None = None
        self._traffic_buffer: LiveTrafficBuffer | None = None

    def compose(self) -> ComposeResult:
        yield Header()
        with Vertical(classes="omega-panel"):
            with Center():
                yield Static("ETAT & RESSOURCES", classes="omega-title")
            with Horizontal(id="resource-dashboard-body"):
                with Vertical(classes="resource-dash-col"):
                    yield Static(id="box-server-state", classes="omega-dash-box")
                with Vertical(classes="resource-dash-col"):
                    yield Static(id="box-traffic", classes="omega-dash-box")
                with Vertical(classes="resource-dash-col"):
                    yield Static(id="box-system", classes="omega-dash-box")
            with Center(), Horizontal(classes="omega-actions"):
                with Container(classes="omega-btn-frame"):
                    yield Button("Rafraichir", id="refresh", variant="primary")
                with Container(classes="omega-btn-frame"):
                    yield Button("Simuler une requete", id="simulate-request")
                with Container(classes="omega-btn-frame"):
                    yield Button("Retour", id="back")
        yield Footer()

    def on_mount(self) -> None:
        self.query_one("#box-server-state", Static).border_title = "ETAT DU SERVEUR"
        self.query_one("#box-traffic", Static).border_title = "FLUX (LOG D'ACCES)"
        self.query_one("#box-system", Static).border_title = "RESSOURCES SYSTEME"

        factory = self._container.service_manager_factory
        self._manager = factory() if factory is not None else None

        started_at = self._container.clock.now()
        self._traffic_buffer = LiveTrafficBuffer(started_at)
        self._tail_reader = self._container.build_live_tail_reader(self._access_log_path())

        self._refresh()
        self.set_interval(_REFRESH_SECONDS, self._refresh)

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "back":
            self.dismiss()
            return
        if event.button.id == "refresh":
            self._refresh()
            return
        if event.button.id == "simulate-request":
            self.app.push_screen(SimulateRequestScreen(container=self._container))

    def _access_log_path(self) -> Path:
        load_result = load_config(self._container.configuration, self._container.config_file)
        if not load_result.success or load_result.config is None:
            return self._container.project_root / "var" / "log" / "access.log"
        return self._container.project_root / load_result.config.logs.access

    # ------------------------------------------------------------------
    # Rafraichissement
    # ------------------------------------------------------------------
    def _refresh(self) -> None:
        assert self._traffic_buffer is not None
        if self._tail_reader is not None:
            for line in self._tail_reader.read_new_lines():
                entry = parse_combined_log_line(line)
                if entry is not None:
                    self._traffic_buffer.add(entry)

        self.query_one("#box-server-state", Static).update(self._panel_server_state())
        self.query_one("#box-traffic", Static).update(
            self._panel_traffic(self._traffic_buffer.get_stats(self._container.clock.now()))
        )
        self.query_one("#box-system", Static).update(self._panel_system(self._container.collect_system_stats()))

    # ------------------------------------------------------------------
    # Cadre 1 : Etat du serveur
    # ------------------------------------------------------------------
    def _panel_server_state(self) -> Text:
        content = Text()
        content.append("── PROCESSUS ────────────────\n", style="bold")

        pid_path = self._container.project_root / "var" / "run" / "omega-serv.pid"
        pid, unreadable = pid_file_status(self._container.filesystem, pid_path)
        if pid is not None and is_process_running(pid):
            content.append(f"  Statut  : DEMARRE (PID {pid})\n", style="green")
        elif pid is not None:
            content.append(f"  Statut  : ARRETE (PID {pid} obsolete)\n", style="yellow")
        elif unreadable:
            # Retour utilisateur 2026-09-10 : fenetre exacte entre
            # "Installer l'unite" (partage var/ avec le compte de
            # service dedie) et la reconnexion de session necessaire a
            # la prise en compte du nouveau groupe Unix - le serveur
            # peut etre reellement actif via systemd malgre ce message,
            # jamais affirmer "ARRETE" sans pouvoir le confirmer. Texte
            # volontairement rassurant (pas "illisible"/"INCONNU" comme
            # premiere version) - retour utilisateur : le message
            # original inquietait a tort, sans indiquer que la situation
            # est normale et temporaire (une seule reconnexion suffit,
            # jamais a repeter).
            content.append(
                "  Statut  : a confirmer (rien d'alarmant, normal juste apres "
                "l'installation) - reconnectez votre session UNE SEULE FOIS pour que "
                "cet ecran l'affiche ; verifiez via SERVICE en attendant\n",
                style="yellow",
            )
        else:
            content.append("  Statut  : ARRETE (aucun fichier PID)\n", style="dim")

        content.append("\n── SERVICE SYSTEME ──────────\n", style="bold")
        if self._manager is None:
            content.append("  Aucun gestionnaire de service reconnu\n", style="dim")
        else:
            service_name = self._container.settings_store.get(_SERVICE_NAME_KEY, "") or _DEFAULT_SERVICE_NAME
            result = get_service_status(self._manager, service_name)
            if isinstance(result, ServiceStatus):
                state_style = "green" if result.is_running else ("red" if result.is_failed else "yellow")
                content.append(f"  Actif   : {result.active}\n", style=state_style)
                content.append(f"  Demarrage auto : {result.enabled}\n")
                content.append(f"  Etat    : {result.state} ({result.sub_state})\n")
            else:
                content.append(f"  {result.message}\n", style="dim")

        content.append("\n── CONFIGURATION ACTIVE ─────\n", style="bold")
        load_result = load_config(self._container.configuration, self._container.config_file)
        if not load_result.success or load_result.config is None:
            content.append("  Erreur de configuration : " + "; ".join(load_result.errors) + "\n", style="red")
            return content
        config = load_result.config

        content.append(f"  Profil  : {config.profile}\n")
        content.append(f"  Ecoute  : {config.server.bind}:{config.server.port}\n")
        content.append(f"  TLS     : {'active (' + config.tls.mode + ')' if config.tls.enabled else 'desactive'}\n")

        enabled_options = sorted(name for name, opt in config.options.items() if opt.enabled)
        content.append(f"\n  Options actives ({len(enabled_options)}/{len(KNOWN_OPTION_NAMES)}) :\n")
        if enabled_options:
            for name in enabled_options:
                content.append(f"    - {name}\n", style="green")
        else:
            content.append("    (aucune)\n", style="dim")
        return content

    # ------------------------------------------------------------------
    # Cadre 2 : Flux (log d'acces)
    # ------------------------------------------------------------------
    def _panel_traffic(self, stats: LiveTrafficStats) -> Text:
        content = Text()
        content.append("── RENDEMENT ────────────────\n", style="bold")
        content.append(f"  Debit    : {stats.rps:.2f} req/s\n")
        content.append(f"  Volume   : {_bytes_to_human(stats.bps)}/s\n\n")

        content.append("── STATUTS HTTP ─────────────\n", style="bold")
        content.append(f"  Total    : {stats.total}\n")
        content.append(f"  Succes 2xx    : {stats.success_2xx}\n", style="green")
        content.append(f"  Redirect 3xx  : {stats.redirect_3xx}\n")
        content.append(f"  Erreurs 4xx   : {stats.errors_4xx}\n", style="yellow")
        content.append(f"  Erreurs 5xx   : {stats.errors_5xx}\n\n", style="red")

        content.append("── CLIENTS ──────────────────\n", style="bold")
        content.append(f"  IPs uniques   : {stats.unique_ips}\n")
        content.append(f"  Top IP        : {stats.top_ip}\n\n")

        content.append("── SANTE ────────────────────\n", style="bold")
        health_style = "green" if stats.error_rate < 5 else ("yellow" if stats.error_rate < 15 else "red")
        content.append(f"  Taux d'erreur : {stats.error_rate:.1f}%\n", style=health_style)
        content.append(f"  Taille moy.   : {_bytes_to_human(stats.avg_size)}\n")
        content.append(f"  Tampon        : {stats.buffer_size}\n")
        return content

    # ------------------------------------------------------------------
    # Cadre 3 : Ressources systeme
    # ------------------------------------------------------------------
    def _panel_system(self, stats: dict[str, Any]) -> Text:
        content = Text()
        content.append(f"  CPU  : {_progress_bar(stats['cpu_percent'])}\n")
        if stats.get("temps"):
            temp_str = " / ".join(f"{v:.0f}°C" for v in list(stats["temps"].values())[:3])
            content.append(f"         Temp: {temp_str}\n", style="dim")

        content.append(f"\n  RAM  : {_progress_bar(stats['mem_percent'])}\n")
        content.append(
            f"         ({_bytes_to_human(stats['mem_used'])} / {_bytes_to_human(stats['mem_total'])})\n",
            style="dim",
        )

        content.append(f"\n  Disk : {_progress_bar(stats['disk_percent'])}\n")
        content.append(
            f"         ({_bytes_to_human(stats['disk_used'])} / {_bytes_to_human(stats['disk_total'])})\n",
            style="dim",
        )

        content.append(
            f"\n  Swap : {stats['swap_percent']:5.1f}% "
            f"({_bytes_to_human(stats['swap_used'])} / {_bytes_to_human(stats['swap_total'])})\n"
        )
        content.append(
            f"  Load : {stats['load_1']:.2f} {stats['load_5']:.2f} {stats['load_15']:.2f}"
            f"   Processus: {stats['num_processes']}\n"
        )

        uptime_sec = stats["uptime_seconds"]
        days, rem = divmod(int(uptime_sec), 86400)
        hours, rem = divmod(rem, 3600)
        minutes = rem // 60
        content.append(f"  Uptime: {days}j {hours}h {minutes}m\n\n")

        content.append("── RESEAU ───────────────────\n", style="bold")
        content.append(
            f"  Debit : ↓{_bytes_to_human(stats['net_bytes_recv'])}  ↑{_bytes_to_human(stats['net_bytes_sent'])}\n"
        )
        content.append(f"  TCP etablies : {stats['tcp_established']}\n")
        content.append(f"  IP sortante  : {stats['outbound_ip']}\n")
        content.append(f"  Passerelle   : {stats.get('gateway') or 'N/A'}\n")
        users = stats.get("user_names") or []
        content.append(f"  Utilisateurs : {', '.join(users) if users else 'aucun'}\n")
        return content
