"""Actions du mode Administration, tableau de bord web lot 5 (OMEGA-SERV_PLAN-DETAILLE_TABLEAU_DE_BORD_WEB.md §6).

Seulement ce que le compte du service peut faire sans sudo et sans toucher a la configuration :
- bannir / debannir une adresse IP (intervention manuelle, blocklist sous var/lib/waf ; jamais un ban pose par le WAF,
  RIPOSTE ou la recidive) ;
- fermer un incident Active Defense (export IoC automatique s'il est regle) ;
- arret d'urgence de RIPOSTE (laisser finir ou lever les actions en cours) et sa levee ;
- DRAINING / MAINTENANCE / retour a l'automatique d'un backend (route d'administration locale du serveur) ;
- archiver maintenant un journal de l'instance (archive dans var/backups/logs, fichier vide ensuite) et supprimer
  une archive ;
- recharger la configuration (signal au superviseur, comme `systemctl reload`).

Chaque cible vient d'une liste relue a chaque action (bans manuels, incidents ouverts, backends, journaux, archives) :
jamais un chemin ni un nom libre venu du navigateur. Les controles d'acces (role, mode, CSRF, nouvelle saisie, audit)
sont faits par web_app.py avant d'arriver ici."""
from __future__ import annotations

from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Protocol
from urllib.parse import urlencode

from omega_serv.application.active_defense.manage_incidents import close_incident
from omega_serv.application.active_defense.queries import list_incidents
from omega_serv.application.riposte.console import (
    emergency_stop,
    emergency_stop_active,
    resume,
    riposte_enabled,
)
from omega_serv.application.security.manual_intervention import (
    ban_address,
    check_ban_request,
    manual_bans,
    protected_networks,
    unban_address,
    waf_enabled,
)
from omega_serv.application.status.instance_status import ADMIN_BACKENDS_PATH, KINDS_WITH_BACKENDS
from omega_serv.core.i18n import _
from omega_serv.domain.config.entities import OmegaServConfig
from omega_serv.domain.routing.proxy_backend_traffic import BackendTraffic, instance_kind
from omega_serv.domain.security.active_defense.entities import IncidentFilters
from omega_serv.ports.blocklist_port import BlocklistPort
from omega_serv.ports.clock_port import ClockPort
from omega_serv.ports.incident_repository_port import IncidentRepositoryPort
from omega_serv.ports.riposte_store_port import RiposteStorePort

HOUR = 3600
BAN_DURATIONS: dict[str, int | None] = {
    "1h": HOUR, "6h": 6 * HOUR, "24h": 24 * HOUR, "7j": 7 * 24 * HOUR, "30j": 30 * 24 * HOUR, "permanent": None,
}
BACKEND_STATUSES = ("draining", "maintenance", "clear")
LOG_KEYS = ("access", "error", "waf_alerts", "breakage", "uploads")
ADMIN_HEALTH_PATH = "/.omega-serv-admin/health"


@dataclass(frozen=True)
class ActionOutcome:
    ok: bool
    message: str


@dataclass(frozen=True)
class ManualBan:
    network: str
    reason: str
    expires_at: str | None


@dataclass(frozen=True)
class OpenIncident:
    incident_id: str
    subject: str
    opened_at: datetime


@dataclass(frozen=True)
class BackendLine:
    zone: str
    name: str
    status: str


@dataclass(frozen=True)
class LogLine:
    key: str
    path: Path
    size: int | None


@dataclass(frozen=True)
class ArchiveLine:
    name: str
    size: int
    modified: str


@dataclass
class AdminState:
    """Ce que la page Administration affiche ; chaque source absente ou illisible donne un texte, jamais une
    exception."""
    bans: list[ManualBan] = field(default_factory=list)
    bans_problem: str = ""
    incidents: list[OpenIncident] = field(default_factory=list)
    incidents_problem: str = ""
    riposte_stopped: bool | None = None
    riposte_problem: str = ""
    backends: list[BackendLine] = field(default_factory=list)
    backends_problem: str = ""
    backends_shown: bool = False
    logs: list[LogLine] = field(default_factory=list)
    archives: list[ArchiveLine] = field(default_factory=list)
    archives_problem: str = ""
    reload_problem: str = ""


class ActionSources(Protocol):
    """Ce que le processus d'administration fournit (interfaces/cli/admin_web_commands.py)."""

    def config(self) -> OmegaServConfig | None: ...

    @property
    def clock(self) -> ClockPort: ...

    @property
    def project_root(self) -> Path: ...

    def blocklist(self, config: OmegaServConfig) -> BlocklistPort | None: ...

    def incident_repository(self, config: OmegaServConfig) -> IncidentRepositoryPort | None: ...

    def export_closed_incident(self, config: OmegaServConfig, incident_id: str) -> None: ...

    def riposte_store(self, config: OmegaServConfig, write: bool) -> RiposteStorePort:
        """Leve FileNotFoundError (RIPOSTE jamais lance) ou OSError (base illisible ou non modifiable)."""
        ...

    def admin_call(self, port: int, method: str, path: str) -> Awaitable[tuple[int, dict | None] | None]: ...

    def file_size(self, path: Path) -> int | None: ...

    def rotate_now(self, log_path: Path, keep: int) -> ActionOutcome: ...

    def archives(self) -> list[ArchiveLine]: ...

    def delete_archive(self, name: str) -> bool: ...

    def reload_problem(self) -> str:
        """Vide si le rechargement est possible (processus lance par le serveur), sinon la raison."""
        ...

    def request_reload(self) -> None: ...


def _riposte_problem(error: OSError, write: bool) -> str:
    if isinstance(error, FileNotFoundError):
        return _("RIPOSTE n'a encore jamais été lancé sur cette instance.")
    message = _("Base RIPOSTE illisible : {error}").format(error=error)
    if write:
        message += " " + _("Droits d'écriture sur la base requis (groupe du service omega-serv).")
    return message


class AdminActions:
    def __init__(self, sources: ActionSources) -> None:
        self._sources = sources

    def _config(self) -> OmegaServConfig | None:
        return self._sources.config()

    # ------------------------------------------------------------------ etat affiche
    async def state(self) -> AdminState:
        state = AdminState()
        config = self._config()
        if config is None:
            problem = _("Configuration illisible.")
            state.bans_problem = state.incidents_problem = state.riposte_problem = problem
            state.backends_problem = problem
            return state
        self._bans_state(config, state)
        self._incidents_state(config, state)
        self._riposte_state(config, state)
        await self._backends_state(config, state)
        root = self._sources.project_root
        state.logs = [LogLine(key, root / getattr(config.logs, key), self._sources.file_size(root / getattr(
            config.logs, key))) for key in LOG_KEYS]
        try:
            state.archives = self._sources.archives()
        except OSError as error:  # essai de l'auteur du 2026-11-17 : var/backups ferme au service -> page plantee
            state.archives_problem = _("Archives illisibles par le service ({error}) : dans la TUI, Accueil -> "
                                       "Service -> Réparer les permissions.").format(error=error)
        state.reload_problem = self._sources.reload_problem()
        return state

    def _bans_state(self, config: OmegaServConfig, state: AdminState) -> None:
        if not waf_enabled(config):
            state.bans_problem = _("WAF inactif : bannir demande l'option WAF.")
            return
        try:
            port = self._sources.blocklist(config)
            if port is None:
                state.bans_problem = _("Blocklist indisponible dans cet environnement.")
                return
            state.bans = [ManualBan(e.network, e.reason, e.expires_at) for e in manual_bans(port)]
        except OSError as error:
            state.bans_problem = _("Blocklist illisible : {error}").format(error=error)

    def _incidents_state(self, config: OmegaServConfig, state: AdminState) -> None:
        if not config.option_enabled("active_defense"):
            state.incidents_problem = _("Active Defense inactif.")
            return
        try:
            repository = self._sources.incident_repository(config)
        except OSError as error:
            state.incidents_problem = _("Base Active Defense illisible : {error}").format(error=error)
            return
        if repository is None:
            state.incidents_problem = _("Active Defense inactif.")
            return
        state.incidents = [OpenIncident(i.incident_id, i.subject_id, i.opened_at)
                           for i in list_incidents(repository, IncidentFilters(status="open"))]

    def _riposte_state(self, config: OmegaServConfig, state: AdminState) -> None:
        if not riposte_enabled(config):
            state.riposte_problem = _("RIPOSTE inactif.")
            return
        try:
            store = self._sources.riposte_store(config, False)
        except OSError as error:
            state.riposte_problem = _riposte_problem(error, write=False)
            return
        try:
            state.riposte_stopped = emergency_stop_active(store)
        finally:
            store.close()

    async def _backend_rows(self, config: OmegaServConfig) -> tuple[list[BackendLine] | None, str]:
        result = await self._sources.admin_call(config.server.port, "GET", ADMIN_BACKENDS_PATH)
        if result is None:
            return None, _("Serveur arrêté ou injoignable.")
        status, body = result
        if status == 403:
            return None, _("Administration refusée : ajoutez 127.0.0.1 aux réseaux de confiance (trusted_proxy).")
        if status != 200 or not isinstance(body, dict) or not isinstance(body.get("backends"), list):
            return None, _("Réponse inattendue du serveur (statut {status}).").format(status=status)
        lines: list[BackendLine] = []
        seen: set[tuple[str, str]] = set()
        for raw in body["backends"]:
            row = BackendTraffic.from_dict(raw) if isinstance(raw, dict) else None
            if row is not None and (row.zone, row.name) not in seen:  # un nom DNS a plusieurs adresses : une ligne
                seen.add((row.zone, row.name))
                lines.append(BackendLine(row.zone, row.name, row.status))
        return lines, ""

    async def _backends_state(self, config: OmegaServConfig, state: AdminState) -> None:
        if instance_kind(config) not in KINDS_WITH_BACKENDS:
            return
        state.backends_shown = True
        rows, state.backends_problem = await self._backend_rows(config)
        state.backends = rows or []

    def log_name(self, key: str) -> str:
        config = self._config()
        if config is None or key not in LOG_KEYS:
            return key
        return Path(getattr(config.logs, key)).name

    # ------------------------------------------------------------------ bans
    def check_ban(self, address: str, duration: str) -> tuple[str | None, str, tuple[str, ...]]:
        """(adresse normalisee, erreur, avertissements a confirmer) ; rien n'est ecrit."""
        config = self._config()
        if config is None:
            return None, _("Configuration illisible."), ()
        if duration not in BAN_DURATIONS:
            return None, _("Durée inconnue."), ()
        if not waf_enabled(config):
            return None, _("WAF inactif : bannir demande l'option WAF."), ()
        try:
            port = self._sources.blocklist(config)
            if port is None:
                return None, _("Blocklist indisponible dans cet environnement."), ()
            check = check_ban_request(port, address.strip(), BAN_DURATIONS[duration] is None,
                                      protected_networks(config), self._sources.clock.now())
        except OSError as error:
            return None, _("Blocklist illisible : {error}").format(error=error), ()
        return check.network, check.error, check.warnings

    def ban(self, address: str, duration: str, reason: str) -> ActionOutcome:
        network, error, _warnings = self.check_ban(address, duration)
        config = self._config()
        if network is None or config is None:
            return ActionOutcome(False, error)
        port = self._sources.blocklist(config)
        assert port is not None
        # Scan de securite n° 2 (2026-11-20, F41) : motif saisi a distance, relu par `blocklist list` et la TUI -
        # caracteres de controle (C0, DEL, C1) retires a la creation.
        clean_reason = "".join(char for char in reason if not (ord(char) < 0x20 or 0x7F <= ord(char) < 0xA0))
        result = ban_address(port, network, clean_reason[:200], BAN_DURATIONS[duration], self._sources.clock.now())
        return ActionOutcome(result.success, result.message)

    def unban(self, network: str) -> ActionOutcome:
        config = self._config()
        if config is None:
            return ActionOutcome(False, _("Configuration illisible."))
        try:
            port = self._sources.blocklist(config)
            if port is None:
                return ActionOutcome(False, _("Blocklist indisponible dans cet environnement."))
            if network not in {e.network for e in manual_bans(port)}:
                return ActionOutcome(False, _("Ce ban n'est plus dans la liste des bans manuels."))
            result = unban_address(port, network)
        except OSError as error:
            return ActionOutcome(False, _("Blocklist illisible : {error}").format(error=error))
        return ActionOutcome(result.success, result.message)

    # ------------------------------------------------------------------ incidents
    def close_incident(self, incident_id: str) -> ActionOutcome:
        config = self._config()
        repository = self._sources.incident_repository(config) if config is not None else None
        if config is None or repository is None:
            return ActionOutcome(False, _("Active Defense inactif."))
        closed = close_incident(repository, self._sources.clock, incident_id)
        if closed is None:
            return ActionOutcome(False, _("Incident introuvable ou déjà fermé."))
        self._sources.export_closed_incident(config, closed.incident_id)
        return ActionOutcome(True, _("Incident {incident_id!r} fermé.").format(incident_id=closed.incident_id))

    # ------------------------------------------------------------------ RIPOSTE
    def riposte_stop(self, revoke: bool) -> ActionOutcome:
        return self._riposte(lambda store: emergency_stop(store, self._sources.clock.now(), revoke=revoke), _(
            "Arrêt d'urgence ACTIF : aucune nouvelle action, même après un redémarrage, jusqu'à « Reprendre »."))

    def riposte_resume(self) -> ActionOutcome:
        return self._riposte(lambda store: resume(store, self._sources.clock.now()),
                             _("Arrêt d'urgence levé : RIPOSTE reprend ses décisions."))

    def _riposte(self, change: Callable[[RiposteStorePort], object], done: str) -> ActionOutcome:
        config = self._config()
        if config is None or not riposte_enabled(config):
            return ActionOutcome(False, _("RIPOSTE inactif."))
        try:
            store = self._sources.riposte_store(config, True)
        except OSError as error:
            return ActionOutcome(False, _riposte_problem(error, write=True))
        try:
            change(store)
        except OSError as error:
            return ActionOutcome(False, _riposte_problem(error, write=True))
        finally:
            store.close()
        return ActionOutcome(True, done)

    # ------------------------------------------------------------------ backends
    async def set_backend(self, zone: str, name: str, status: str) -> ActionOutcome:
        config = self._config()
        if config is None:
            return ActionOutcome(False, _("Configuration illisible."))
        if status not in BACKEND_STATUSES:
            return ActionOutcome(False, _("État inconnu."))
        rows, problem = await self._backend_rows(config)
        if rows is None:
            return ActionOutcome(False, problem)
        if not any(row.zone == zone and row.name == name for row in rows):
            return ActionOutcome(False, _("Backend introuvable : {name}").format(name=name))
        query = urlencode({"zone": zone, "upstream": name, "status": status})
        result = await self._sources.admin_call(config.server.port, "POST", f"{ADMIN_HEALTH_PATH}?{query}")
        if result is None:
            return ActionOutcome(False, _("Serveur injoignable - le changement n'a pas pu être appliqué."))
        if result[0] != 200:
            return ActionOutcome(False, _("Le serveur a refusé ce changement (statut {status}).").format(
                status=result[0]))
        label = {"draining": "DRAINING", "maintenance": "MAINTENANCE", "clear": _("automatique")}[status]
        return ActionOutcome(True, _("{name} ({zone}) : {status}.").format(name=name, zone=zone, status=label))

    # ------------------------------------------------------------------ journaux
    def rotate_log(self, key: str) -> ActionOutcome:
        config = self._config()
        if config is None:
            return ActionOutcome(False, _("Configuration illisible."))
        if key not in LOG_KEYS:
            return ActionOutcome(False, _("Journal inconnu."))
        return self._sources.rotate_now(self._sources.project_root / getattr(config.logs, key),
                                        config.logs.rotation.keep)

    def delete_archive(self, name: str) -> ActionOutcome:
        try:
            known = {archive.name for archive in self._sources.archives()}
        except OSError as error:
            return ActionOutcome(False, _("Archives illisibles par le service ({error}) : dans la TUI, Accueil -> "
                                          "Service -> Réparer les permissions.").format(error=error))
        if name not in known:
            return ActionOutcome(False, _("Archive introuvable : {selected_name}").format(selected_name=name))
        if not self._sources.delete_archive(name):
            return ActionOutcome(False, _("Archive introuvable : {selected_name}").format(selected_name=name))
        return ActionOutcome(True, _("Archive supprimée : {selected_name}").format(selected_name=name))

    # ------------------------------------------------------------------ rechargement
    def reload(self) -> ActionOutcome:
        problem = self._sources.reload_problem()
        if problem:
            return ActionOutcome(False, problem)
        self._sources.request_reload()
        return ActionOutcome(True, _("Rechargement demandé : la configuration est relue (comme systemctl reload)."))

    # ------------------------------------------------------------------ aiguillage commun (lot 6)
    async def run(self, params: dict[str, str]) -> ActionOutcome:
        """Une action du §6 par son nom : page Administration (session) et appel d'un maitre (jeton)."""
        name = params.get("action", "")
        if name == "bannir":
            return self.ban(params.get("adresse", ""), params.get("duree", ""), params.get("raison", ""))
        if name == "debannir":
            return self.unban(params.get("reseau", ""))
        if name == "fermer_incident":
            return self.close_incident(params.get("incident", ""))
        if name in ("riposte_arret", "riposte_arret_lever"):
            return self.riposte_stop(revoke=name == "riposte_arret_lever")
        if name == "riposte_reprise":
            return self.riposte_resume()
        if name == "backend":
            return await self.set_backend(params.get("zone", ""), params.get("backend", ""), params.get("etat", ""))
        if name == "archiver":
            return self.rotate_log(params.get("journal", ""))
        if name == "supprimer_archive":
            return self.delete_archive(params.get("archive", ""))
        if name == "recharger":
            return self.reload()
        return ActionOutcome(False, _("Action inconnue."))


# ---------------------------------------------------------------------- etat transmis a un maitre (lot 6)
def state_to_dict(state: AdminState) -> dict[str, object]:
    return {
        "bans": [{"network": b.network, "reason": b.reason, "expires_at": b.expires_at} for b in state.bans],
        "bans_problem": state.bans_problem,
        "incidents": [{"id": i.incident_id, "subject": i.subject, "opened_at": i.opened_at.isoformat()}
                      for i in state.incidents],
        "incidents_problem": state.incidents_problem,
        "riposte_stopped": state.riposte_stopped,
        "riposte_problem": state.riposte_problem,
        "backends": [{"zone": b.zone, "name": b.name, "status": b.status} for b in state.backends],
        "backends_problem": state.backends_problem,
        "backends_shown": state.backends_shown,
        "logs": [{"key": line.key, "name": line.path.name, "size": line.size} for line in state.logs],
        "archives": [{"name": a.name, "size": a.size, "modified": a.modified} for a in state.archives],
        "reload_problem": state.reload_problem,
    }


def state_from_dict(data: object) -> AdminState:
    """Etat recu d'une instance suivie : types verifies, tout texte reste du texte (echappe a l'affichage). Une
    donnee mal formee leve ValueError."""
    if not isinstance(data, dict):
        raise ValueError("etat")  # noqa: TRY004 - un seul type d'erreur pour l'appelant : donnee mal formee

    def text(value: object) -> str:
        if not isinstance(value, str):
            raise TypeError("texte")
        return value[:500]

    def items(key: str) -> list[dict[str, object]]:
        value = data.get(key, [])
        if not isinstance(value, list) or not all(isinstance(item, dict) for item in value):
            raise TypeError(key)
        return value[:1000]

    def size(value: object) -> int | None:
        if value is None:
            return None
        if not isinstance(value, int) or isinstance(value, bool):
            raise TypeError("taille")
        return value

    try:
        stopped = data.get("riposte_stopped")
        if stopped is not None and not isinstance(stopped, bool):
            raise TypeError("riposte")
        incidents = [OpenIncident(text(i["id"]), text(i["subject"]), datetime.fromisoformat(text(i["opened_at"])))
                     for i in items("incidents")]
        return AdminState(
            bans=[ManualBan(text(b["network"]), text(b["reason"]),
                            None if b.get("expires_at") is None else text(b["expires_at"])) for b in items("bans")],
            bans_problem=text(data.get("bans_problem", "")),
            incidents=incidents,
            incidents_problem=text(data.get("incidents_problem", "")),
            riposte_stopped=stopped,
            riposte_problem=text(data.get("riposte_problem", "")),
            backends=[BackendLine(text(b["zone"]), text(b["name"]), text(b["status"])) for b in items("backends")],
            backends_problem=text(data.get("backends_problem", "")),
            backends_shown=bool(data.get("backends_shown", False)),
            logs=[LogLine(text(line["key"]), Path(Path(text(line["name"])).name), size(line.get("size")))
                  for line in items("logs")],
            archives=[ArchiveLine(text(a["name"]), size(a["size"]) or 0, text(a["modified"])) for a in items("archives")],
            reload_problem=text(data.get("reload_problem", "")),
        )
    except (KeyError, TypeError) as error:
        raise ValueError(str(error)) from error
