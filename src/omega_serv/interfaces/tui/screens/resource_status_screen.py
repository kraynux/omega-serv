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
   TLS, bind:port). Seule cette partie appelle un subprocess
   (`get_service_status`, jusqu'a 10s si le gestionnaire de service est
   degrade, retour utilisateur 2026-09-21) - calculee dans un thread de
   travail (`run_worker(thread=True)`, PAS le "thread+Live bricole" que
   la phrase precedente ecarte : ici le rafraichissement periodique
   reste `set_interval`, seule la RECUPERATION d'UNE donnee lente en
   sort) pour ne jamais bloquer les deux autres cadres ni la saisie
   clavier pendant l'attente.
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
   au pare-feu) via `container.collect_system_stats()` (psutil). Gel
   TOTAL reproduit sur Archcraft (retour utilisateur 2026-09-26) MALGRE
   le worker deja en place pour le point 1 - preuve que `collect_system_stats()`
   (une dizaine d'appels psutil lisant /proc et /sys - temperatures,
   ventilateurs, connexions TCP...) restait le seul appel bloquant
   synchrone du thread UI. Meme traitement desormais : deporte dans son
   propre thread de travail (`_compute_system_stats`), aucun des deux
   n'attend l'autre.

Enrichi le 2026-11-05 (retour utilisateur : deux cadres « maigrichons ») : le flux relit a
l'ouverture les 15 dernieres minutes du journal d'acces (plus de cadre vide au depart), ajoute les
debits sur 1 et 5 minutes, les top 5 (IP, chemins, 404), une section SECURITE (journal d'alertes du
WAF, refus 403/429, IP de la liste de blocage) et les dernieres requetes ; les ressources gagnent une
section OMEGA-SERV (ses processus, ses connexions, ses journaux, l'espace libre de var/) et le debit
reseau devient un vrai debit par seconde (c'etait le total depuis le demarrage de la machine).

Le tampon de flux et le lecteur de tail sont crees UNE SEULE FOIS a
`on_mount` (jamais recrees a chaque tick) - le calcul de debit cumule
depuis `started_at` et la position de lecture incrementale ont tous
les deux besoin de persister entre deux rafraichissements."""
from __future__ import annotations

import time
from collections import deque
from datetime import datetime, timedelta
from pathlib import Path
from typing import TYPE_CHECKING, Any

from rich.text import Text
from textual.app import ComposeResult
from textual.color import Color
from textual.containers import Center, Container, Horizontal, Vertical, VerticalScroll
from textual.widgets import Button, Footer, Header, Static

from omega_serv.application.config.load_config import load_config
from omega_serv.application.server.engine_status import engine_connector_rows, engine_status_rows
from omega_serv.application.services.manage_service import get_service_status
from omega_serv.application.services.pid_file import pid_file_status
from omega_serv.core.i18n import _
from omega_serv.core.platform_info import is_process_running
from omega_serv.domain.config.option import KNOWN_OPTION_NAMES
from omega_serv.domain.instances.entities import InstanceEntry
from omega_serv.domain.logging.access_log_parser import parse_combined_log_line
from omega_serv.domain.logging.live_traffic_stats import LiveTrafficBuffer, LiveTrafficStats
from omega_serv.domain.security.riposte.events import parse_waf_alert_line
from omega_serv.domain.security.waf.config import parse_waf_config
from omega_serv.domain.services.entities import ServiceStatus
from omega_serv.interfaces.tui.rendering.aligned_block import (
    SECTION_WIDTH,
    AlignedBlock,
    centered_section_title,
)
from omega_serv.interfaces.tui.screens._base import OmegaScreen
from omega_serv.interfaces.tui.screens.log_simple_viewer_screen import LogSimpleViewerScreen
from omega_serv.interfaces.tui.screens.simulate_request_screen import SimulateRequestScreen

if TYPE_CHECKING:
    from omega_serv.bootstrap.container import DependencyContainer
    from omega_serv.ports.live_tail_port import LiveTailPort
    from omega_serv.ports.service_manager_port import ServiceManagerPort

_REFRESH_SECONDS = 2.0
_HISTORY = timedelta(minutes=15)
"""Relu a l'ouverture : le cadre FLUX n'est jamais vide au depart."""
_HISTORY_MAX_BYTES = 4 * 1024 * 1024
"""Lecture de la fin du journal bornee : jamais un gros access.log lu en entier."""
_PATH_WIDTH = 34
_DEFAULT_SERVICE_NAME = "omega-serv"
_SERVICE_NAME_KEY = "service_name"
"""Meme cle que service_screen.py::_SERVICE_NAME_KEY (settings_store,
var/settings.json) - jamais un nom fige, sinon ce panneau afficherait
le statut d'une unite sans rapport apres un renommage dans l'ecran
SERVICE (bug latent signale, corrige ici)."""


def _bytes_to_human(num_bytes: float) -> str:
    units = (_("o"), _("Ko"), _("Mo"), _("Go"))
    for unit in units:
        if num_bytes < 1024:
            return f"{num_bytes:.1f} {unit}"
        num_bytes /= 1024
    return f"{num_bytes:.1f} {_('To')}"


_INSTANCE_ROWS = 3
"""Instances listees au plus dans la section INSTANCE (le reste est resume en une ligne)."""
_SPARK_SAMPLES = 60
"""Historique du graphique TCP/UDP : 60 releves, soit 2 min au rythme de rafraichissement."""
_SPARK_BARS = "▁▂▃▄▅▆▇█"


def sparkline(values: list[float], width: int) -> str:
    """Les `width` dernieres valeurs en barres, a l'echelle de la plus grande (tout a plat si 0)."""
    shown = values[-width:] if width > 0 else []
    peak = max(shown, default=0.0)
    if peak <= 0:
        return _SPARK_BARS[0] * len(shown)
    top = len(_SPARK_BARS) - 1
    return "".join(_SPARK_BARS[min(top, int(v / peak * top + 0.5))] for v in shown)
"""Instances listees au plus dans la section INSTANCE (le reste est resume en une ligne)."""


def _icon(icon: str, label: str) -> str:
    """Icone devant un libelle de ligne (2026-11-05) : emoji de largeur 2 SANS selecteur de variante
    (U+FE0F), seuls a occuper la meme largeur partout - l'alignement des « : » en depend."""
    return f"{icon} {label}"


def _short(text: str, width: int = _PATH_WIDTH) -> str:
    return text if len(text) <= width else text[: width - 1] + "…"


def _duration(seconds: float) -> str:
    days, rem = divmod(int(seconds), 86400)
    hours, rem = divmod(rem, 3600)
    return _("{days} j {hours} h {minutes} min").format(days=days, hours=hours, minutes=rem // 60)


_GAUGE_LEVELS = ((50.0, "success"), (75.0, "warning"), (95.0, "orange"), (float("inf"), "error"))
"""Seuils des jauges (2026-11-05) : 0-49 vert, 50-74 jaune, 75-94 orange, 95-100 rouge."""


def gauge_level(percent: float) -> str:
    """Nom de la teinte de la jauge (cle de `_gauge_colors`) pour un pourcentage."""
    return next(name for limit, name in _GAUGE_LEVELS if percent < limit)


def _progress_bar(percent: float, color: str = "", width: int = 20) -> Text:
    filled = int(width * max(0.0, min(100.0, percent)) / 100)
    empty = width - filled
    bar = Text("[")
    bar.append("█" * filled, style=color)
    bar.append("░" * empty + "] ")
    bar.append(f"{percent:5.1f}%", style=color)
    return bar


class ResourceStatusScreen(OmegaScreen):
    def __init__(self, *, container: DependencyContainer) -> None:
        super().__init__()
        self._container = container
        self._manager: ServiceManagerPort | None = None
        self._tail_reader: LiveTailPort | None = None
        self._traffic_buffer: LiveTrafficBuffer | None = None
        self._server_state_worker_running = False
        """Retour utilisateur 2026-09-21 : meme apres l'ajout d'un timeout
        cote systemd/openrc/runit (10s), ce panneau interroge le
        gestionnaire de service (subprocess) toutes les 2s - laisser cet
        appel synchrone sur le thread UI bloquerait Textual jusqu'a 10s a
        CHAQUE tick des que la machine est degradee (gel percu par
        intermittence, meme sans gel definitif). Calcule desormais dans
        un thread de travail (`run_worker(thread=True)`, meme patron que
        capabilities_screen.py::_scan_in_thread) - ce booleen evite
        d'empiler un nouveau thread bloquant par-dessus un precedent
        encore en cours."""
        self._system_stats_worker_running = False
        """Meme garde-fou que `_server_state_worker_running` (retour
        utilisateur 2026-09-26) - `collect_system_stats()` egalement
        deporte dans un thread, voir `_compute_system_stats`."""
        self._waf_tail_reader: LiveTailPort | None = None
        self._waf_counts = {"attack": 0, "blocklist_hit": 0, "rate_limited": 0}
        self._banned: tuple[int, int] | None = None
        """(IP en liste de blocage, dont posees par RIPOSTE) ; None si inconnu ou WAF inactif."""
        self._box_widths = {"server-state": SECTION_WIDTH, "traffic": SECTION_WIDTH, "system": SECTION_WIDTH}
        """Largeur utile de chaque cadre (barre de defilement deduite), relue sur le thread UI a chaque
        rafraichissement : les titres de section sont centres dessus (2026-11-05)."""
        self._gauge_colors: dict[str, str] = {}
        """Teintes des jauges tirees des variables du theme actif ($success, $warning, $error) ;
        l'orange, absent des themes, est le melange a parts egales de $warning et $error."""
        self._packet_previous: tuple[float, int, int] | None = None
        self._packet_history: dict[str, deque[float]] = {
            "tcp": deque(maxlen=_SPARK_SAMPLES), "udp": deque(maxlen=_SPARK_SAMPLES)}
        """Paquets/s TCP et UDP des derniers releves (graphique sous « Debit »)."""
        self._sent_since: datetime | None = None
        self._sent_offset: int | None = None
        self._sent_total: int | None = None
        """Octets de reponse de l'access log depuis le demarrage du serveur (None : pas encore calcule)."""
        self._sent_worker_running = False
        self._pending_sent_since: datetime | None = None
        """Demarrage du serveur releve par le fil des ressources ; le fil UI lance le calcul du volume."""
        self._net_previous: tuple[float, int, int] | None = None
        """(instant, octets recus, octets envoyes) du releve precedent : debit = difference / duree."""

    def compose(self) -> ComposeResult:
        yield Header()
        with Vertical(id="resource-panel", classes="omega-panel"):
            with Center():
                yield Static(_("ÉTAT & RESSOURCES"), classes="omega-title")
            with Horizontal(id="resource-dashboard-body"):
                # Cadre = zone qui defile (2026-11-05) : un Static seul a hauteur fixe coupait la fin de son
                # contenu au lieu de defiler (constate sur le cadre FLUX enrichi).
                with Vertical(classes="resource-dash-col"), \
                        VerticalScroll(id="frame-server-state", classes="omega-dash-box"):
                    yield Static(id="box-server-state")
                with Vertical(classes="resource-dash-col"), VerticalScroll(id="frame-traffic", classes="omega-dash-box"):
                    yield Static(id="box-traffic")
                with Vertical(classes="resource-dash-col"), VerticalScroll(id="frame-system", classes="omega-dash-box"):
                    yield Static(id="box-system")
            with Center(), Horizontal(classes="omega-actions"):
                with Container(classes="omega-btn-frame"):
                    yield Button(_("Rafraîchir"), id="refresh", variant="primary")
                with Container(classes="omega-btn-frame"):
                    yield Button(_("Simuler une requête"), id="simulate-request")
                with Container(classes="omega-btn-frame"):
                    yield Button("access.log", id="open-access-log")  # nom de fichier : jamais traduit
                with Container(classes="omega-btn-frame"):
                    yield Button(_("Retour"), id="back")
        yield Footer()

    def on_mount(self) -> None:
        loading = "  " + _("Chargement...")
        self.query_one("#frame-server-state", VerticalScroll).border_title = _("ÉTAT DU SERVEUR")
        self.query_one("#box-server-state", Static).update(loading)
        self.query_one("#frame-traffic", VerticalScroll).border_title = _("FLUX (LOG D'ACCÈS)")
        self.query_one("#frame-system", VerticalScroll).border_title = _("RESSOURCES SYSTÈME")
        self.query_one("#box-system", Static).update(loading)

        factory = self._container.service_manager_factory
        self._manager = factory() if factory is not None else None

        started_at = self._container.clock.now() - _HISTORY
        self._traffic_buffer = LiveTrafficBuffer(started_at)
        access_log = self._access_log_path()
        for line in self._history_lines(access_log):
            entry = parse_combined_log_line(line)
            if entry is not None and entry.timestamp >= started_at:
                self._traffic_buffer.add(entry)
        self._tail_reader = self._container.build_live_tail_reader(access_log)
        waf_log = self._waf_alert_log_path()
        if waf_log is not None:
            self._count_waf_alerts(self._history_lines(waf_log), started_at)
            self._waf_tail_reader = self._container.build_live_tail_reader(waf_log)

        self._refresh()
        self.set_interval(_REFRESH_SECONDS, self._refresh)

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "back":
            self.dismiss()
            return
        if event.button.id == "refresh":
            self._refresh()
            return
        if event.button.id == "open-access-log":
            # Raccourci (2026-11-05) : viewer Simple directement sur l'access log de cette instance, sans
            # passer par Gestion des logs (ni selection, ni confirmation).
            self.app.push_screen(LogSimpleViewerScreen(container=self._container, path=str(self._access_log_path())))
            return
        if event.button.id == "simulate-request":
            self.app.push_screen(SimulateRequestScreen(container=self._container))

    def _history_lines(self, path: Path) -> list[str]:
        try:
            return self._container.file_access.read_tail_lines(path, _HISTORY_MAX_BYTES)
        except OSError:
            return []

    def _count_waf_alerts(self, lines: list[str], since: datetime | None = None) -> None:
        for line in lines:
            event = parse_waf_alert_line(line).event
            if event is not None and (since is None or event.timestamp >= since) and event.kind in self._waf_counts:
                self._waf_counts[event.kind] += 1

    def _waf_alert_log_path(self) -> Path | None:
        load_result = load_config(self._container.configuration, self._container.config_file)
        if not load_result.success or load_result.config is None:
            return None
        option = load_result.config.options.get("waf")
        if option is None or not option.enabled:
            return None
        return self._container.project_root / parse_waf_config(option.settings).logging.path

    def _access_log_path(self) -> Path:
        load_result = load_config(self._container.configuration, self._container.config_file)
        if not load_result.success or load_result.config is None:
            return self._container.project_root / "var" / "log" / "access.log"
        return self._container.project_root / load_result.config.logs.access

    def _read_layout_and_theme(self) -> None:
        """Thread UI uniquement : les workers lisent ensuite ces deux attributs sans toucher aux widgets."""
        for box in self._box_widths:
            width = self.query_one(f"#box-{box}", Static).size.width
            if width > 0:
                self._box_widths[box] = width
        variables = self.app.get_css_variables()
        warning, error = Color.parse(variables["warning"]), Color.parse(variables["error"])
        self._gauge_colors = {"success": variables["success"], "warning": variables["warning"],
                              "orange": warning.blend(error, 0.5).hex, "error": variables["error"],
                              "primary": variables["primary"]}

    def _title(self, title: str, box: str, icon: str = "") -> str:
        return centered_section_title(f"{icon} {title}" if icon else title, self._box_widths[box])

    def _gauge(self, percent: float) -> Text:
        return _progress_bar(percent, self._gauge_colors.get(gauge_level(percent), ""))

    def _level_color(self, percent: float) -> str:
        return self._gauge_colors.get(gauge_level(percent), "")

    def _swap_value(self, stats: dict[str, Any]) -> Text:
        """Pourcentage de swap UTILISE (psutil), donc meme bareme que CPU/RAM/Disque : 100 % = swap plein."""
        value = Text(f"{stats['swap_percent']:5.1f}%", style=self._level_color(stats["swap_percent"]))
        value.append(f" ({_bytes_to_human(stats['swap_used'])} / {_bytes_to_human(stats['swap_total'])})")
        return value

    def _load_value(self, stats: dict[str, Any]) -> Text:
        """Charge moyenne 1/5/15 min, colorée rapportée au nombre de cœurs logiques (charge = cœurs -> 100 %)."""
        cores = max(1, int(stats.get("cpu_count") or 1))
        value = Text()
        for key in ("load_1", "load_5", "load_15"):
            value.append(f"{stats[key]:.2f}", style=self._level_color(100.0 * stats[key] / cores))
            value.append(" ")
        value.append(_("({count} cœurs)").format(count=cores), style="dim")
        return value

    def _refresh(self) -> None:
        assert self._traffic_buffer is not None
        self._read_layout_and_theme()
        if self._tail_reader is not None:
            for line in self._tail_reader.read_new_lines():
                entry = parse_combined_log_line(line)
                if entry is not None:
                    self._traffic_buffer.add(entry)
        if self._waf_tail_reader is not None:
            self._count_waf_alerts(self._waf_tail_reader.read_new_lines())

        self.query_one("#box-traffic", Static).update(
            self._panel_traffic(self._traffic_buffer.get_stats(self._container.clock.now()))
        )

        if not self._server_state_worker_running:
            self._server_state_worker_running = True
            self.run_worker(self._compute_server_state, thread=True, exclusive=True, group="resource-server-state")

        since = self._pending_sent_since
        if since is not None and not self._sent_worker_running:
            self._sent_worker_running = True
            self.run_worker(lambda: self._compute_sent_bytes(since), thread=True, group="resource-sent-bytes")

        if not self._system_stats_worker_running:
            self._system_stats_worker_running = True
            self.run_worker(self._compute_system_stats, thread=True, exclusive=True, group="resource-system-stats")

    def _compute_server_state(self) -> None:
        """Tourne dans un thread reel (`run_worker(thread=True)`) - `_panel_server_state()`
        peut invoquer un subprocess (`get_service_status`) qui bloque jusqu'a
        10s si le gestionnaire de service est degrade ; ne JAMAIS appeler
        depuis ici de widget Textual directement (pas thread-safe), seul
        `call_from_thread` peut repasser la main au thread UI.

        Retour utilisateur 2026-09-26 (Archcraft, IndexError reel dans
        _parse_state - corrige a la source) : try/except large ici en
        complement, jamais a sa place - un widget Textual peut recevoir
        n'importe quelle donnee systeme imprevue (format de sortie
        systemctl/OpenRC/runit different selon la machine) ; sans ce
        filet, une exception non prevue remonte comme un toast Textual
        generique ("Worker raised exception") plutot que le message clair
        et localise habituel de ce panneau."""
        try:
            self._banned = self._count_banned()
            content = self._panel_server_state()
        except Exception as e:  # noqa: BLE001 - filet de secours large, volontaire
            content = Text("  " + _("ERREUR INATTENDUE : {error}").format(error=e) + "\n", style="bold red")
        self.app.call_from_thread(self._apply_server_state, content)

    def _count_banned(self) -> tuple[int, int] | None:
        """Entrees en vigueur de la liste de blocage (meme port que l'ecran WAF - Etat)."""
        factory = self._container.blocklist_port_factory
        load_result = load_config(self._container.configuration, self._container.config_file)
        if factory is None or not load_result.success or load_result.config is None:
            return None
        option = load_result.config.options.get("waf")
        if option is None or not option.enabled:
            return None
        entries = factory(load_result.config, self._container.filesystem, self._container.project_root,
                          self._container.clock).list_entries()
        now = self._container.clock.now().isoformat()
        active = [e for e in entries if e.expires_at is None or e.expires_at > now]
        return len(active), sum(1 for e in active if e.source == "riposte")

    def _apply_server_state(self, content: Text) -> None:
        self._server_state_worker_running = False
        self.query_one("#box-server-state", Static).update(content)

    def _compute_system_stats(self) -> None:
        """Tourne dans un thread reel (retour utilisateur 2026-09-26, gel
        total reproduit sur Archcraft MALGRE le passage en worker de
        `_panel_server_state()` - preuve que ce n'etait pas systemctl le
        seul appel bloquant synchrone restant sur le thread UI).
        `collect_system_stats()` (infrastructure/probe/system_stats.py)
        enchaine une dizaine d'appels psutil (temperatures/fans/
        connexions TCP/utilisateurs...) qui lisent /proc et /sys - aucun
        timeout Python ne protege un read() bloque sur un pilote/sysfs
        degrade (un try/except ne peut rien contre un appel qui ne revient
        jamais). Meme patron que _compute_server_state : jamais de widget
        touche ici directement, seul `call_from_thread` repasse la main.

        Try/except large egalement ici (meme raison que
        _compute_server_state - retour utilisateur 2026-09-26) : psutil
        peut renvoyer des structures partielles/inattendues selon le
        systeme (capteurs, interfaces reseau...) - jamais un toast
        generique a la place, toujours un message localise dans CE
        panneau precis."""
        try:
            stats = self._container.collect_system_stats()
            self._record_packets(stats)
            content = self._panel_omega_serv(self._server_stats())
            content.append("\n")
            content.append_text(self._panel_system(stats))
        except Exception as e:  # noqa: BLE001 - filet de secours large, volontaire
            content = Text("  " + _("ERREUR INATTENDUE : {error}").format(error=e) + "\n", style="bold red")
        self.app.call_from_thread(self._apply_system_stats, content)

    def _record_packets(self, stats: dict[str, Any]) -> None:
        packets = stats.get("packets")
        if packets is None:
            return
        now = time.monotonic()
        previous, self._packet_previous = self._packet_previous, (now, packets[0], packets[1])
        if previous is None or now <= previous[0]:
            return
        elapsed = now - previous[0]
        self._packet_history["tcp"].append(max(0, packets[0] - previous[1]) / elapsed)
        self._packet_history["udp"].append(max(0, packets[1] - previous[2]) / elapsed)

    def _packet_lines(self, block: AlignedBlock) -> None:
        """Graphique TCP/UDP sous « Debit » : une ligne par protocole, couleurs du theme ($success, $primary)."""
        for key, label, color in (("tcp", "TCP", "success"), ("udp", "UDP", "primary")):
            history = list(self._packet_history[key])
            if not history:
                continue
            legend = "  " + _("{count} paq/s max").format(count=f"{max(history):.0f}")
            width = self._box_widths["system"] - 2 - len(label) - 1 - len(legend)
            line = Text(f"{label} ")
            line.append(sparkline(history, width), style=self._gauge_colors.get(color, ""))
            line.append(legend, style="dim")
            block.line(line)

    def _compute_sent_bytes(self, since: datetime) -> None:
        """Thread de travail dedie : la premiere lecture d'un gros access log peut durer (jamais dans
        le fil des autres cadres) ; les suivantes ne lisent que les nouvelles lignes."""
        try:
            if since != self._sent_since:  # nouveau demarrage du serveur : on repart de zero
                self._sent_since, self._sent_offset, self._sent_total = since, None, None
            added, self._sent_offset = self._container.access_log_sent_bytes(
                self._access_log_path(), since, self._sent_offset)
            self._sent_total = (self._sent_total or 0) + added
        finally:
            self._sent_worker_running = False

    def _network_rate(self, stats: dict[str, Any]) -> str:
        """Debit par seconde entre deux releves (les compteurs de psutil sont des totaux depuis le
        demarrage de la machine - c'est ce total qui etait affiche avant le 2026-11-05)."""
        now, received, sent = time.monotonic(), int(stats["net_bytes_recv"]), int(stats["net_bytes_sent"])
        previous, self._net_previous = self._net_previous, (now, received, sent)
        if previous is None or now <= previous[0]:
            return _("mesure en cours...")
        elapsed = now - previous[0]
        down = max(0, received - previous[1]) / elapsed
        up = max(0, sent - previous[2]) / elapsed
        return f"↓{_bytes_to_human(down)}/s  ↑{_bytes_to_human(up)}/s"

    def _server_stats(self) -> dict[str, Any]:
        pid_path = self._container.project_root / "var" / "run" / "omega-serv.pid"
        pid, _unreadable = pid_file_status(self._container.filesystem, pid_path)
        if pid is not None and not is_process_running(pid):
            pid = None
        load_result = load_config(self._container.configuration, self._container.config_file)
        port = load_result.config.server.port if load_result.success and load_result.config else 0
        stats = self._container.collect_server_stats(pid, port)
        stats["pid"], stats["port"] = pid, port
        if stats.get("running"):
            since = (self._container.clock.now() - timedelta(seconds=stats["uptime_seconds"])).replace(microsecond=0)
            if self._sent_since is not None and abs((since - self._sent_since).total_seconds()) <= 2:
                since = self._sent_since  # meme demarrage (arrondi de la duree) : on garde la reprise
            self._pending_sent_since = since
        return stats

    def _apply_system_stats(self, content: Text) -> None:
        self._system_stats_worker_running = False
        self.query_one("#box-system", Static).update(content)

    def _panel_server_state(self) -> Text:
        content = Text()
        content.append(self._title(_("PROCESSUS"), "server-state", "🔋"), style="bold")
        status_label = _icon("🚦", _("Statut"))
        process = AlignedBlock()
        pid_path = self._container.project_root / "var" / "run" / "omega-serv.pid"
        pid, unreadable = pid_file_status(self._container.filesystem, pid_path)
        if pid is not None and is_process_running(pid):
            process.row(status_label, _("DÉMARRÉ (PID {pid})").format(pid=pid), "green")
        elif pid is not None:
            process.row(status_label, _("ARRÊTÉ (PID {pid} obsolète)").format(pid=pid), "yellow")
        elif unreadable:
            process.row(status_label, _(
                "à confirmer (rien d'alarmant, normal juste après l'installation) - reconnectez "
                "votre session UNE SEULE FOIS pour que cet écran l'affiche ; vérifiez via SERVICE "
                "en attendant"
            ), "yellow")
        else:
            process.row(status_label, _("ARRÊTÉ (aucun fichier PID)"), "dim")
        process.render_into(content)

        content.append("\n" + self._title(_("SERVICE SYSTÈME"), "server-state", "🧰"), style="bold")
        if self._manager is None:
            content.append("  " + _("Aucun gestionnaire de service reconnu") + "\n", style="dim")
        else:
            service_name = self._container.settings_store.get(_SERVICE_NAME_KEY, "") or _DEFAULT_SERVICE_NAME
            result = get_service_status(self._manager, service_name)
            if isinstance(result, ServiceStatus):
                state_style = "green" if result.is_running else ("red" if result.is_failed else "yellow")
                AlignedBlock() \
                    .row(_("Actif"), str(result.active), state_style) \
                    .row(_("Démarrage auto"), str(result.enabled)) \
                    .row(_("État"), f"{result.state} ({result.sub_state})") \
                    .render_into(content)
            else:
                # Erreur remontee par status() (ex. timeout systemctl/rc-service/sv -
                # retour utilisateur 2026-09-21 : jamais laisser cet ecran se figer en
                # silence, afficher clairement de quoi corriger a la place) - visible,
                # jamais "dim" comme le message informatif "aucun gestionnaire reconnu".
                AlignedBlock().row(_("ERREUR STATUT"), result.message, style="bold red").render_into(content)

        self._append_instances(content)

        content.append("\n" + self._title(_("SAUVEGARDE"), "server-state", "📀"), style="bold")
        backups = self._container.list_backups()  # menu Sauvegarde, var/backups/config-snapshots (2026-11-05)
        if backups:
            AlignedBlock() \
                .row(_icon("📅", _("Dernière")), backups[0].created_at.astimezone().strftime("%Y-%m-%d %H:%M")) \
                .row(_("Nombre"), str(len(backups))) \
                .render_into(content)
        else:
            content.append("  " + _("Aucune sauvegarde") + "\n", style="dim")

        content.append("\n" + self._title(_("CONFIGURATION ACTIVE"), "server-state", "📋"), style="bold")
        load_result = load_config(self._container.configuration, self._container.config_file)
        if not load_result.success or load_result.config is None:
            content.append("  " + _("Erreur de configuration : ") + "; ".join(load_result.errors) + "\n", style="red")
            return content
        config = load_result.config

        tls = _("activé ({mode})").format(mode=config.tls.mode) if config.tls.enabled else _("désactivé")
        AlignedBlock() \
            .row(_("Profil"), str(config.profile)) \
            .row(_("Écoute"), f"{config.server.bind}:{config.server.port}") \
            .row(_("TLS"), tls) \
            .render_into(content)

        # Moteur HTTP (plan moteur C++ §16.5) : demande / effectif / raison, toujours visible.
        content.append("\n" + self._title(_("MOTEUR HTTP"), "server-state", "🚀"), style="bold")
        engine_block = AlignedBlock()
        engine = self._container.engine_status(config)
        for label, value, style in engine_status_rows(engine):
            engine_block.row(label, value, style or None)
        engine_block.render_into(content)
        connector_rows = engine_connector_rows(engine)
        if connector_rows:
            content.append("\n" + self._title(_("CONNECTEURS (NATIF)"), "server-state", "🔗"), style="bold")
            connector_block = AlignedBlock()
            for label, value, style in connector_rows:
                connector_block.row(label, value, style or None)
            connector_block.render_into(content)

        enabled_options = sorted(name for name, opt in config.options.items() if opt.enabled)
        content.append("\n" + self._title(_("CONFIGURATION OPTIONS"), "server-state", "🔧"), style="bold")
        content.append("  " + _("Options actives ({enabled}/{known}) :").format(
            enabled=len(enabled_options), known=len(KNOWN_OPTION_NAMES)) + "\n")
        if enabled_options:
            for name in enabled_options:
                content.append(f"    - {name}\n", style="green")
        else:
            content.append("    " + _("(aucune)") + "\n", style="dim")
        return content

    def _append_instances(self, content: Text) -> None:
        """Section INSTANCE (2026-11-05) : nombre d'instances du registre, celle qui affiche cet ecran, puis
        au plus `_INSTANCE_ROWS` instances (la courante d'abord, puis celles en marche) avec leur PID."""
        content.append("\n" + self._title(_("INSTANCE"), "server-state", "🧩"), style="bold")
        filesystem = self._container.filesystem
        current_path = filesystem.resolve_real_path(self._container.project_root)
        entries = self._container.instance_registry.load()
        current = next((e for e in entries if e.path == current_path), None)
        if current is None:  # instance jamais inscrite au registre (installation principale) : elle compte quand meme
            current = InstanceEntry(current_path.name, current_path, "", 0, "", self._container.clock.now())
            entries = [current, *entries]
        AlignedBlock() \
            .row(_("Nombre"), str(len(entries))) \
            .row(_("Cette instance"), current.name) \
            .render_into(content)
        rows = []
        for entry in entries:
            pid, unreadable = pid_file_status(filesystem, entry.path / "var" / "run" / "omega-serv.pid")
            running = pid is not None and is_process_running(pid)
            rows.append((entry is not current, not running, entry, pid if running else None, unreadable))
        rows.sort(key=lambda row: row[:2])
        block = AlignedBlock()
        for _other, _stopped, entry, pid, unreadable in rows[:_INSTANCE_ROWS]:
            name = _("{name} (courante)").format(name=entry.name) if entry is current else entry.name
            if pid is not None:
                block.row(name, _("PID {pid}").format(pid=pid), "green")
            elif unreadable:
                block.row(name, _("PID illisible"), "yellow")
            else:
                block.row(name, _("arrêtée"), "dim")
        block.render_into(content)
        if len(rows) > _INSTANCE_ROWS:
            content.append("  " + _("+ {count} autre(s)").format(count=len(rows) - _INSTANCE_ROWS) + "\n", style="dim")

    def _panel_traffic(self, stats: LiveTrafficStats) -> Text:
        content = Text()
        since = self._container.clock.now() - _HISTORY
        content.append("  " + _("Depuis {time} (15 min relues à l'ouverture)").format(
            time=since.astimezone().strftime("%H:%M")) + "\n", style="dim")
        content.append(self._title(_("RENDEMENT"), "traffic", "⚡"), style="bold")
        AlignedBlock() \
            .row(_("Dernière minute"), _("{rate:.2f} req/s").format(rate=stats.rps_1m)) \
            .row(_("5 dernières min"), _("{rate:.2f} req/s").format(rate=stats.rps_5m)) \
            .row(_("Moyenne"), _("{rate:.2f} req/s").format(rate=stats.rps)) \
            .row(_("Volume"), _("{size}/s").format(size=_bytes_to_human(stats.bps))) \
            .render_into(content)

        content.append("\n" + self._title(_("STATUTS HTTP"), "traffic", "📊"), style="bold")
        health_style = "green" if stats.error_rate < 5 else ("yellow" if stats.error_rate < 15 else "red")
        AlignedBlock() \
            .row(_("Total"), str(stats.total)) \
            .row(_("Succès 2xx"), str(stats.success_2xx), "green") \
            .row(_("Redirections 3xx"), str(stats.redirect_3xx)) \
            .row(_("Erreurs 4xx"), str(stats.errors_4xx), "yellow") \
            .row(_("Erreurs 5xx"), str(stats.errors_5xx), "red") \
            .row(_icon("📉", _("Taux d'erreur")), f"{stats.error_rate:.1f}%", health_style) \
            .row(_("Taille moy."), _bytes_to_human(stats.avg_size)) \
            .render_into(content)

        content.append("\n" + self._title(_("SÉCURITÉ"), "traffic", "🔒"), style="bold")
        security = AlignedBlock()
        if self._waf_tail_reader is None:
            security.row(_("WAF"), _("inactif"), "dim")
        else:
            security.row(_icon("🚨", _("Attaques bloquées")), str(self._waf_counts["attack"]),
                         "red" if self._waf_counts["attack"] else None)
            security.row(_("Refus liste blocage"), str(self._waf_counts["blocklist_hit"]))
            security.row(_("Limite de débit"), str(self._waf_counts["rate_limited"]))
        security.row(_("Refus 403"), str(stats.forbidden_403))
        security.row(_("Refus 429"), str(stats.rate_limited_429))
        if self._banned is not None:
            banned, by_riposte = self._banned
            security.row(_icon("⛔", _("IP bannies")), _("{count} (dont RIPOSTE : {riposte})").format(count=banned, riposte=by_riposte))
        security.render_into(content)

        content.append("\n" + self._title(_("CLIENTS"), "traffic", "👥"), style="bold")
        AlignedBlock().row(_("IPs uniques"), str(stats.unique_ips)).render_into(content)
        self._top_into(content, stats.top_ips)

        content.append("\n" + self._title(_("CHEMINS LES PLUS DEMANDÉS"), "traffic", "📂"), style="bold")
        self._top_into(content, stats.top_paths)
        content.append("\n" + self._title(_("CHEMINS EN 404"), "traffic", "🚫"), style="bold")
        self._top_into(content, stats.top_not_found, "yellow")

        content.append("\n" + self._title(_("DERNIÈRES REQUÊTES"), "traffic", "🕑"), style="bold")
        if not stats.recent:
            content.append("  " + _("(aucune)") + "\n", style="dim")
        for entry in stats.recent:
            status_style = "green" if entry.status_code < 400 else ("yellow" if entry.status_code < 500 else "red")
            content.append(f"  {entry.timestamp.astimezone().strftime('%H:%M:%S')}  {entry.ip:<15} ")
            content.append(f"{entry.status_code} ", style=status_style)
            content.append(_short(entry.path or "-") + "\n")
        return content

    @staticmethod
    def _top_into(content: Text, items: tuple[tuple[str, int], ...], style: str | None = None) -> None:
        if not items:
            content.append("  " + _("(aucun)") + "\n", style="dim")
            return
        for value, count in items:
            content.append(f"  {count:>6}  ", style="bold")
            content.append(_short(value) + "\n", style=style or "")

    def _panel_omega_serv(self, stats: dict[str, Any]) -> Text:
        content = Text()
        content.append(self._title(_("OMEGA-SERV"), "system", "🌀"), style="bold")
        block = AlignedBlock()
        if stats.get("running"):
            block.row(_("Processus"), _("{count} (PID {pid})").format(count=stats["process_count"], pid=stats["pid"]),
                      "green")
            block.row(_icon("🧠", _("CPU")), f"{stats['cpu_percent']:.1f}%")
            block.row(_icon("💾", _("RAM")), _bytes_to_human(stats["rss"]))
            block.row(_("Fils"), str(stats["threads"]))
            block.row(_("Fichiers ouverts"), str(stats["open_files"]) if stats["open_files"] is not None
                      else _("N/D (compte du service)"))
            block.row(_("Lancé depuis"), _duration(stats["uptime_seconds"]))
        else:
            block.row(_("Processus"), _("arrêté"), "dim")
        connections = stats.get("connections")
        block.row(_icon("🔗", _("Connexions")), (f"{connections}  (:{stats['port']})" if connections is not None else _("N/D")))
        if stats.get("running"):
            block.row(_icon("📤", _("Envoyé")), _bytes_to_human(self._sent_total) if self._sent_total is not None
                      else _("calcul en cours..."))
            # Ligne libre (pleine largeur) : en detail, alignee sur les valeurs, elle passait sur deux lignes.
            block.line(Text(_("(réponses depuis le démarrage)"), style="dim"))
        block.row(_("Journaux"), _bytes_to_human(stats["log_total"]))
        if stats.get("log_largest_name"):
            block.row(_("Plus gros"), f"{_short(stats['log_largest_name'], 20)} "
                                              f"({_bytes_to_human(stats['log_largest_size'])})")
        if stats.get("state_free") is not None:
            free_percent = 100.0 * stats["state_free"] / stats["state_total"] if stats["state_total"] else 0.0
            block.row(_icon("📦", _("Libre (var/)")), Text(
                f"{_bytes_to_human(stats['state_free'])} / {_bytes_to_human(stats['state_total'])} ({free_percent:.0f}%)",
                style=self._level_color(100.0 - free_percent)))  # espace LIBRE : bareme retourne
        block.render_into(content)
        return content

    def _panel_system(self, stats: dict[str, Any]) -> Text:
        content = Text()
        content.append(self._title(_("MACHINE"), "system", "💻"), style="bold")
        system = AlignedBlock().row(_icon("🧠", _("CPU")), self._gauge(stats["cpu_percent"]))
        if stats.get("temps"):
            temp_str = " / ".join(f"{v:.0f}°C" for v in list(stats["temps"].values())[:3])
            system.detail(_("Temp. : {values}").format(values=temp_str))
        system.row(_icon("💾", _("RAM")), self._gauge(stats["mem_percent"]))
        system.detail(f"({_bytes_to_human(stats['mem_used'])} / {_bytes_to_human(stats['mem_total'])})")
        system.row(_icon("💽", _("Disque")), self._gauge(stats["disk_percent"]))
        system.detail(f"({_bytes_to_human(stats['disk_used'])} / {_bytes_to_human(stats['disk_total'])})")
        system.render_into(content)

        content.append("\n")
        # Bloc separe des barres : un libelle long ici ne decale jamais les barres CPU/RAM/Disque.
        AlignedBlock() \
            .row(_icon("🔄", _("Swap")), self._swap_value(stats)) \
            .row(_icon("📈", _("Charge")), self._load_value(stats)) \
            .row(_("Processus"), str(stats["num_processes"])) \
            .row(_icon("⏰", _("Uptime")), _duration(stats["uptime_seconds"])) \
            .render_into(content)

        content.append("\n" + self._title(_("RÉSEAU"), "system", "🌐"), style="bold")
        users = stats.get("user_names") or []
        AlignedBlock() \
            .row(_icon("📶", _("Débit")), self._network_rate(stats)) \
            .apply(self._packet_lines) \
            .row(_("TCP établies"), str(stats["tcp_established"])) \
            .row(_("IP sortante"), str(stats["outbound_ip"])) \
            .row(_("Passerelle"), str(stats.get("gateway") or _("N/D"))) \
            .row(_("Utilisateurs"), ", ".join(users) if users else _("aucun")) \
            .render_into(content)

        content.append("\n" + self._title(_("INTERFACES"), "system", "🔌"), style="bold")
        links = stats.get("links") or []
        if not links:
            content.append("  " + _("(aucune)") + "\n", style="dim")
        block = AlignedBlock()
        for link in links:  # ● = interface de la route par defaut (celle qui sort), en vert
            active = link["name"] == stats.get("default_interface")
            if not link["up"]:
                block.row(link["name"], f"○ {link['kind']}  " + _("déconnectée"), "dim")
            else:
                block.row(link["name"], f"{'●' if active else '○'} {link['kind']}  {link['ip'] or _('sans IP')}",
                          "bold green" if active else None)
        block.render_into(content)
        return content
