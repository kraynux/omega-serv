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

Tableau de bord par type d'instance (Projets 3.0.0 §9, chantier 3, decision de l'auteur du 2026-11-16) : le type
(site, application PHP, reverse proxy, mixte) s'affiche en tete du premier cadre ; pour un reverse proxy ou une
instance mixte, le cadre FLUX gagne une section BACKENDS (une ligne par backend : etat, requetes, en cours, 502/504,
temps moyen), lue en direct par `/.omega-serv-admin/backends` dans le processus serveur (meme chemin que « Etat en
direct »), placee avant les chemins les plus demandes et les 404. Direct seulement, aucun historique. Pour un site ou
une application PHP, le cadre FLUX ne change pas.

Tableau de bord web, lot 1 (OMEGA-SERV_PLAN-DETAILLE_TABLEAU_DE_BORD_WEB.md §2.1, 2026-11-16) : toute la collecte
decrite ci-dessus vit desormais dans application/status/instance_status.py (`InstanceStatusCollector`, instantanes
de donnees pures), partagee avec la CLI et le futur tableau de bord web. Cet ecran ne garde que l'affichage, les
fils de travail et les couleurs du theme. Le collecteur est cree UNE SEULE FOIS (ouvert a `on_mount`) : positions
de lecture des journaux, releve reseau precedent et volume envoye doivent persister entre deux rafraichissements."""
from __future__ import annotations

from collections.abc import Callable
from datetime import datetime
from typing import TYPE_CHECKING, Any

from rich.text import Text
from textual.app import ComposeResult
from textual.color import Color
from textual.containers import Center, Container, Horizontal, Vertical, VerticalScroll
from textual.widgets import Button, Footer, Header, Static

from omega_serv.application.server.engine_status import engine_connector_rows, engine_status_rows
from omega_serv.application.status.formatting import (
    bytes_to_human,
    duration_text,
    instance_kind_label,
    response_time_text,
)
from omega_serv.application.status.instance_status import (
    KINDS_WITH_BACKENDS,
    BackendsSnapshot,
    InstanceStatusCollector,
    ServerStateSnapshot,
    SystemSnapshot,
    TrafficSnapshot,
)
from omega_serv.core.i18n import _
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

_REFRESH_SECONDS = 2.0
_PATH_WIDTH = 34


_INSTANCE_ROWS = 3
"""Instances listees au plus dans la section INSTANCE (le reste est resume en une ligne)."""
_SPARK_BARS = "▁▂▃▄▅▆▇█"


def sparkline(values: list[float], width: int) -> str:
    """Les `width` dernieres valeurs en barres, a l'echelle de la plus grande (tout a plat si 0)."""
    shown = values[-width:] if width > 0 else []
    peak = max(shown, default=0.0)
    if peak <= 0:
        return _SPARK_BARS[0] * len(shown)
    top = len(_SPARK_BARS) - 1
    return "".join(_SPARK_BARS[min(top, int(v / peak * top + 0.5))] for v in shown)


def _icon(icon: str, label: str) -> str:
    """Icone devant un libelle de ligne (2026-11-05) : emoji de largeur 2 SANS selecteur de variante
    (U+FE0F), seuls a occuper la meme largeur partout - l'alignement des « : » en depend."""
    return f"{icon} {label}"


def _short(text: str, width: int = _PATH_WIDTH) -> str:
    return text if len(text) <= width else text[: width - 1] + "…"


def backend_status_label(status: str) -> tuple[str, str]:
    """(libelle, style) d'un etat de backend ; DRAINING et MAINTENANCE gardent le nom des boutons de l'ecran
    « Etat en direct »."""
    if status == "up":
        return _("en service"), "green"
    if status == "down":
        return _("hors service"), "bold red"
    return status.upper(), "yellow"


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
        self._collector = InstanceStatusCollector(container)
        """Lot 1 du tableau de bord web (2026-11-16) : toute la collecte vit dans application/status/
        instance_status.py, partagee avec la CLI et le futur tableau de bord web ; cet ecran ne fait plus que
        l'affichage."""
        self._server_state_worker_running = False
        """Retour utilisateur 2026-09-21 : l'etat du serveur interroge le gestionnaire de service (subprocess,
        jusqu'a 10 s s'il est degrade) - calcule dans un fil de travail ; ce booleen evite d'empiler un nouveau
        fil bloquant par-dessus un precedent encore en cours."""
        self._system_stats_worker_running = False
        """Meme garde-fou (retour utilisateur 2026-09-26) : psutil peut bloquer sur un /sys degrade."""
        self._sent_worker_running = False
        self._backends_worker_running = False
        self._banned: tuple[int, int] | None = None
        """(IP en liste de blocage, dont posees par RIPOSTE) ; None si inconnu ou WAF inactif."""
        self._box_widths = {"server-state": SECTION_WIDTH, "traffic": SECTION_WIDTH, "system": SECTION_WIDTH}
        """Largeur utile de chaque cadre (barre de defilement deduite), relue sur le thread UI a chaque
        rafraichissement : les titres de section sont centres dessus (2026-11-05)."""
        self._gauge_colors: dict[str, str] = {}
        """Teintes des jauges tirees des variables du theme actif ($success, $warning, $error) ;
        l'orange, absent des themes, est le melange a parts egales de $warning et $error."""
        self._backends: BackendsSnapshot | None = None
        """Dernier releve des backends (type d'instance compris) ; None avant le premier."""
        self._python_processes = 1
        """Processus Python prevus (engine_status.workers) : au-dela d'un, une zone servie par Python n'est comptee
        que dans le processus qui repond a l'administration."""

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
        self._collector.open()
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
            self.app.push_screen(LogSimpleViewerScreen(container=self._container, path=str(self._collector.access_log_path())))
            return
        if event.button.id == "simulate-request":
            self.app.push_screen(SimulateRequestScreen(container=self._container))





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
        value.append(f" ({bytes_to_human(stats['swap_used'])} / {bytes_to_human(stats['swap_total'])})")
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
        self._read_layout_and_theme()
        self.query_one("#box-traffic", Static).update(self._panel_traffic(self._collector.traffic()))

        if not self._server_state_worker_running:
            self._server_state_worker_running = True
            self.run_worker(self._compute_server_state, thread=True, exclusive=True, group="resource-server-state")

        since = self._collector.pending_sent_since
        if since is not None and not self._sent_worker_running:
            self._sent_worker_running = True
            self.run_worker(lambda: self._compute_sent_bytes(since), thread=True, group="resource-sent-bytes")

        if not self._system_stats_worker_running:
            self._system_stats_worker_running = True
            self.run_worker(self._compute_system_stats, thread=True, exclusive=True, group="resource-system-stats")

        if not self._backends_worker_running:
            self._backends_worker_running = True
            self.run_worker(self._fetch_backends(), exclusive=True, group="resource-backends")

    async def _fetch_backends(self) -> None:
        """Type d'instance, puis mesures des backends par l'administration (reverse proxy ou mixte seulement)."""
        try:
            self._backends = await self._collector.backends()
        finally:
            self._backends_worker_running = False

    def _compute_server_state(self) -> None:
        """Fil de travail (`run_worker(thread=True)`) : l'etat du serveur peut invoquer un subprocess
        (gestionnaire de service) qui bloque jusqu'a 10 s ; ne JAMAIS toucher un widget d'ici, seul
        `call_from_thread` repasse la main au fil UI.

        Try/except large en complement (retour utilisateur 2026-09-26, IndexError reel sur Archcraft) : un
        format de sortie systemctl/OpenRC/runit imprevu donne un message clair dans CE panneau plutot qu'un
        toast Textual generique."""
        try:
            self._banned = self._collector.banned_counts()
            content = self._panel_server_state(self._collector.server_state())
        except Exception as e:  # noqa: BLE001 - filet de secours large, volontaire
            content = Text("  " + _("ERREUR INATTENDUE : {error}").format(error=e) + "\n", style="bold red")
        self.app.call_from_thread(self._apply_server_state, content)


    def _apply_server_state(self, content: Text) -> None:
        self._server_state_worker_running = False
        self.query_one("#box-server-state", Static).update(content)

    def _compute_system_stats(self) -> None:
        """Fil de travail (retour utilisateur 2026-09-26, gel total sur Archcraft) : psutil enchaine une dizaine
        d'appels qui lisent /proc et /sys, et aucun delai Python ne protege un read() bloque sur un pilote
        degrade. Meme filet de secours que `_compute_server_state`."""
        try:
            snapshot = self._collector.system()
            content = self._panel_omega_serv(snapshot)
            content.append("\n")
            content.append_text(self._panel_system(snapshot))
        except Exception as e:  # noqa: BLE001 - filet de secours large, volontaire
            content = Text("  " + _("ERREUR INATTENDUE : {error}").format(error=e) + "\n", style="bold red")
        self.app.call_from_thread(self._apply_system_stats, content)


    def _packet_lines(self, packets: dict[str, tuple[float, ...]]) -> Callable[[AlignedBlock], None]:
        """Graphique TCP/UDP sous « Debit » : une ligne par protocole, couleurs du theme ($success, $primary)."""
        def add(block: AlignedBlock) -> None:
            for key, label, color in (("tcp", "TCP", "success"), ("udp", "UDP", "primary")):
                history = list(packets.get(key, ()))
                if not history:
                    continue
                legend = "  " + _("{count} paq/s max").format(count=f"{max(history):.0f}")
                width = self._box_widths["system"] - 2 - len(label) - 1 - len(legend)
                line = Text(f"{label} ")
                line.append(sparkline(history, width), style=self._gauge_colors.get(color, ""))
                line.append(legend, style="dim")
                block.line(line)
        return add

    def _compute_sent_bytes(self, since: datetime) -> None:
        """Fil de travail dedie : la premiere lecture d'un gros access log peut durer."""
        try:
            self._collector.update_sent_bytes(since)
        finally:
            self._sent_worker_running = False

    @staticmethod
    def _network_rate(rate: tuple[float, float] | None) -> str:
        """Debit par seconde entre deux releves (avant le 2026-11-05, le total depuis le demarrage de la machine)."""
        if rate is None:
            return _("mesure en cours...")
        down, up = rate
        return f"↓{bytes_to_human(down)}/s  ↑{bytes_to_human(up)}/s"


    def _apply_system_stats(self, content: Text) -> None:
        self._system_stats_worker_running = False
        self.query_one("#box-system", Static).update(content)

    def _panel_server_state(self, state: ServerStateSnapshot) -> Text:
        content = Text()
        if state.config is not None:
            AlignedBlock().row(_icon("🧭", _("Type d'instance")), instance_kind_label(state.config.kind),
                               "bold").render_into(content)
            content.append("\n")
        content.append(self._title(_("PROCESSUS"), "server-state", "🔋"), style="bold")
        status_label = _icon("🚦", _("Statut"))
        process = AlignedBlock()
        pid, unreadable = state.process.pid, state.process.unreadable
        if pid is not None and state.process.running:
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
        if not state.service.manager_found:
            content.append("  " + _("Aucun gestionnaire de service reconnu") + "\n", style="dim")
        else:
            result = state.service.status
            if result is not None:
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
                AlignedBlock().row(_("ERREUR STATUT"), state.service.error or "", style="bold red").render_into(content)

        self._append_instances(content, state)

        content.append("\n" + self._title(_("SAUVEGARDE"), "server-state", "📀"), style="bold")
        if state.latest_backup is not None:  # menu Sauvegarde, var/backups/config-snapshots (2026-11-05)
            AlignedBlock() \
                .row(_icon("📅", _("Dernière")), state.latest_backup.astimezone().strftime("%Y-%m-%d %H:%M")) \
                .row(_("Nombre"), str(state.backup_count)) \
                .render_into(content)
        else:
            content.append("  " + _("Aucune sauvegarde") + "\n", style="dim")

        content.append("\n" + self._title(_("CONFIGURATION ACTIVE"), "server-state", "📋"), style="bold")
        config = state.config
        if config is None:
            content.append("  " + _("Erreur de configuration : ") + "; ".join(state.config_errors) + "\n", style="red")
            return content

        tls = _("activé ({mode})").format(mode=config.tls_mode) if config.tls_enabled else _("désactivé")
        AlignedBlock() \
            .row(_("Profil"), config.profile) \
            .row(_("Écoute"), f"{config.bind}:{config.port}") \
            .row(_("TLS"), tls) \
            .render_into(content)

        # Moteur HTTP (plan moteur C++ §16.5) : demande / effectif / raison, toujours visible.
        content.append("\n" + self._title(_("MOTEUR HTTP"), "server-state", "🚀"), style="bold")
        engine_block = AlignedBlock()
        engine = config.engine
        self._python_processes = engine.workers
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

        enabled_options = config.enabled_options
        content.append("\n" + self._title(_("CONFIGURATION OPTIONS"), "server-state", "🔧"), style="bold")
        content.append("  " + _("Options actives ({enabled}/{known}) :").format(
            enabled=len(enabled_options), known=config.known_options) + "\n")
        if enabled_options:
            for name in enabled_options:
                content.append(f"    - {name}\n", style="green")
        else:
            content.append("    " + _("(aucune)") + "\n", style="dim")
        return content

    def _append_instances(self, content: Text, state: ServerStateSnapshot) -> None:
        """Section INSTANCE (2026-11-05) : nombre d'instances du registre, celle qui affiche cet ecran, puis
        au plus `_INSTANCE_ROWS` instances (la courante d'abord, puis celles en marche) avec leur PID."""
        content.append("\n" + self._title(_("INSTANCE"), "server-state", "🧩"), style="bold")
        instances = state.instances
        AlignedBlock() \
            .row(_("Nombre"), str(instances.count)) \
            .row(_("Cette instance"), instances.current_name) \
            .render_into(content)
        block = AlignedBlock()
        for row in instances.rows[:_INSTANCE_ROWS]:
            name = _("{name} (courante)").format(name=row.name) if row.current else row.name
            if row.pid is not None:
                block.row(name, _("PID {pid}").format(pid=row.pid), "green")
            elif row.unreadable:
                block.row(name, _("PID illisible"), "yellow")
            else:
                block.row(name, _("arrêtée"), "dim")
        block.render_into(content)
        if len(instances.rows) > _INSTANCE_ROWS:
            content.append("  " + _("+ {count} autre(s)").format(count=len(instances.rows) - _INSTANCE_ROWS) + "\n",
                           style="dim")

    def _panel_traffic(self, traffic: TrafficSnapshot) -> Text:
        stats = traffic.stats
        content = Text()
        since = traffic.since
        content.append("  " + _("Depuis {time} (15 min relues à l'ouverture)").format(
            time=since.astimezone().strftime("%H:%M")) + "\n", style="dim")
        content.append(self._title(_("RENDEMENT"), "traffic", "⚡"), style="bold")
        AlignedBlock() \
            .row(_("Dernière minute"), _("{rate:.2f} req/s").format(rate=stats.rps_1m)) \
            .row(_("5 dernières min"), _("{rate:.2f} req/s").format(rate=stats.rps_5m)) \
            .row(_("Moyenne"), _("{rate:.2f} req/s").format(rate=stats.rps)) \
            .row(_("Volume"), _("{size}/s").format(size=bytes_to_human(stats.bps))) \
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
            .row(_("Taille moy."), bytes_to_human(stats.avg_size)) \
            .render_into(content)

        content.append("\n" + self._title(_("SÉCURITÉ"), "traffic", "🔒"), style="bold")
        security = AlignedBlock()
        if not traffic.waf_active:
            security.row(_("WAF"), _("inactif"), "dim")
        else:
            security.row(_icon("🚨", _("Attaques bloquées")), str(traffic.waf_counts["attack"]),
                         "red" if traffic.waf_counts["attack"] else None)
            security.row(_("Refus liste blocage"), str(traffic.waf_counts["blocklist_hit"]))
            security.row(_("Limite de débit"), str(traffic.waf_counts["rate_limited"]))
        security.row(_("Refus 403"), str(stats.forbidden_403))
        security.row(_("Refus 429"), str(stats.rate_limited_429))
        if self._banned is not None:
            banned, by_riposte = self._banned
            security.row(_icon("⛔", _("IP bannies")), _("{count} (dont RIPOSTE : {riposte})").format(count=banned, riposte=by_riposte))
        security.render_into(content)

        content.append("\n" + self._title(_("CLIENTS"), "traffic", "👥"), style="bold")
        AlignedBlock().row(_("IPs uniques"), str(stats.unique_ips)).render_into(content)
        self._top_into(content, stats.top_ips)

        if self._backends is not None and self._backends.kind in KINDS_WITH_BACKENDS:
            self._backends_into(content)

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

    def _backends_into(self, content: Text) -> None:
        """Section BACKENDS : par zone (dans l'ordre de la configuration), chaque backend avec son etat et ses mesures
        depuis le demarrage du serveur."""
        content.append("\n" + self._title(_("BACKENDS"), "traffic", "🔀"), style="bold")
        snapshot = self._backends
        if snapshot is None or snapshot.rows is None:
            content.append("  " + self._backends_problem_text(snapshot) + "\n", style="dim")
            return
        rows = snapshot.rows
        if not rows:
            content.append("  " + _("(aucun backend)") + "\n", style="dim")
            return
        width = max(12, self._box_widths["traffic"] - 4)
        zone = None
        for row in rows:
            if row.zone != zone:
                zone = row.zone
                engine = _("natif") if row.engine == "natif" else "Python"
                content.append(("" if zone == rows[0].zone else "\n") + "  ")
                content.append(_short(f"{zone} · {engine}", width), style="bold")
                content.append("\n")
            label, style = backend_status_label(row.status)
            content.append("  ● ", style=style)
            content.append(_short(row.address, width) + "\n")
            errors = row.errors_502 + row.errors_504
            AlignedBlock() \
                .row(_("État"), label, style) \
                .row(_("Requêtes"), str(row.requests)) \
                .row(_("En cours"), str(row.active)) \
                .row("502 / 504", f"{row.errors_502} / {row.errors_504}", "red" if errors else None) \
                .row(_("Temps moyen"), response_time_text(row.avg_ms)) \
                .render_into(content)
        if self._python_processes > 1 and any(row.engine == "python" for row in rows):
            content.append("  " + _("Zones servies par Python avec plusieurs processus : chiffres d'un seul "
                                    "processus.") + "\n", style="dim")

    @staticmethod
    def _backends_problem_text(snapshot: BackendsSnapshot | None) -> str:
        if snapshot is None or snapshot.problem is None:
            return _("Chargement...")
        if snapshot.problem == "stopped":
            return _("Serveur arrêté ou injoignable.")
        if snapshot.problem == "refused":
            return _("Administration refusée : ajoutez 127.0.0.1 aux réseaux de confiance (trusted_proxy).")
        return _("Réponse inattendue du serveur (statut {status}).").format(status=snapshot.status)

    @staticmethod
    def _top_into(content: Text, items: tuple[tuple[str, int], ...], style: str | None = None) -> None:
        if not items:
            content.append("  " + _("(aucun)") + "\n", style="dim")
            return
        for value, count in items:
            content.append(f"  {count:>6}  ", style="bold")
            content.append(_short(value) + "\n", style=style or "")

    def _panel_omega_serv(self, snapshot: SystemSnapshot) -> Text:
        stats = snapshot.server
        content = Text()
        content.append(self._title(_("OMEGA-SERV"), "system", "🌀"), style="bold")
        block = AlignedBlock()
        if stats.get("running"):
            block.row(_("Processus"), _("{count} (PID {pid})").format(count=stats["process_count"], pid=stats["pid"]),
                      "green")
            block.row(_icon("🧠", _("CPU")), f"{stats['cpu_percent']:.1f}%")
            block.row(_icon("💾", _("RAM")), bytes_to_human(stats["rss"]))
            block.row(_("Fils"), str(stats["threads"]))
            block.row(_("Fichiers ouverts"), str(stats["open_files"]) if stats["open_files"] is not None
                      else _("N/D (compte du service)"))
            block.row(_("Lancé depuis"), duration_text(stats["uptime_seconds"]))
        else:
            block.row(_("Processus"), _("arrêté"), "dim")
        connections = stats.get("connections")
        block.row(_icon("🔗", _("Connexions")), (f"{connections}  (:{stats['port']})" if connections is not None else _("N/D")))
        if stats.get("running"):
            block.row(_icon("📤", _("Envoyé")), bytes_to_human(snapshot.sent_total) if snapshot.sent_total is not None
                      else _("calcul en cours..."))
            # Ligne libre (pleine largeur) : en detail, alignee sur les valeurs, elle passait sur deux lignes.
            block.line(Text(_("(réponses depuis le démarrage)"), style="dim"))
        block.row(_("Journaux"), bytes_to_human(stats["log_total"]))
        if stats.get("log_largest_name"):
            block.row(_("Plus gros"), f"{_short(stats['log_largest_name'], 20)} "
                                              f"({bytes_to_human(stats['log_largest_size'])})")
        if stats.get("state_free") is not None:
            free_percent = 100.0 * stats["state_free"] / stats["state_total"] if stats["state_total"] else 0.0
            block.row(_icon("📦", _("Libre (var/)")), Text(
                f"{bytes_to_human(stats['state_free'])} / {bytes_to_human(stats['state_total'])} ({free_percent:.0f}%)",
                style=self._level_color(100.0 - free_percent)))  # espace LIBRE : bareme retourne
        block.render_into(content)
        return content

    def _panel_system(self, snapshot: SystemSnapshot) -> Text:
        stats = snapshot.machine
        content = Text()
        content.append(self._title(_("MACHINE"), "system", "💻"), style="bold")
        system = AlignedBlock().row(_icon("🧠", _("CPU")), self._gauge(stats["cpu_percent"]))
        if stats.get("temps"):
            temp_str = " / ".join(f"{v:.0f}°C" for v in list(stats["temps"].values())[:3])
            system.detail(_("Temp. : {values}").format(values=temp_str))
        system.row(_icon("💾", _("RAM")), self._gauge(stats["mem_percent"]))
        system.detail(f"({bytes_to_human(stats['mem_used'])} / {bytes_to_human(stats['mem_total'])})")
        system.row(_icon("💽", _("Disque")), self._gauge(stats["disk_percent"]))
        system.detail(f"({bytes_to_human(stats['disk_used'])} / {bytes_to_human(stats['disk_total'])})")
        system.render_into(content)

        content.append("\n")
        # Bloc separe des barres : un libelle long ici ne decale jamais les barres CPU/RAM/Disque.
        AlignedBlock() \
            .row(_icon("🔄", _("Swap")), self._swap_value(stats)) \
            .row(_icon("📈", _("Charge")), self._load_value(stats)) \
            .row(_("Processus"), str(stats["num_processes"])) \
            .row(_icon("⏰", _("Uptime")), duration_text(stats["uptime_seconds"])) \
            .render_into(content)

        content.append("\n" + self._title(_("RÉSEAU"), "system", "🌐"), style="bold")
        users = stats.get("user_names") or []
        AlignedBlock() \
            .row(_icon("📶", _("Débit")), self._network_rate(snapshot.net_rate)) \
            .apply(self._packet_lines(snapshot.packets)) \
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
                          style="bold green" if active else None)
        block.render_into(content)
        return content
