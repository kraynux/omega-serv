"""Moteur HTTP affiche (ecran Etat & Ressources, `omega-serv engine status`) - plan moteur C++ §16.5 : « moteur
demande / moteur effectif / raison », toujours visible, meme texte partout (une seule fonction de rendu).

Serveur en marche (fichier PID vivant = superviseur de l'etat ecrit) : ce qui tourne reellement, lu dans
var/run/engine-state.json. Serveur arrete, ou etat d'un autre lancement : la PREVISION de `decide_engine` pour la
configuration actuelle, presentee comme telle.

Lot 9 : nombre de processus et tableau des connecteurs (plan §7 : fonction par fonction, natif / via Python /
repli), affiches ici - ecran Etat & Ressources, section MOTEUR HTTP (Q6). Plan §25 (2026-11-04) : plus de nom de
niveau, seulement ce qui tourne ; une valeur `server.workers` ramenee au maximum de la machine est signalee."""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from omega_serv.application.server.engine_levels import (
    describe_connector,
    engine_connectors,
    resolved_worker_count,
    worker_count_notice,
)
from omega_serv.application.server.engine_selection import (
    EngineDecision,
    decide_engine,
    describe_reason,
)
from omega_serv.application.server.engine_state import EngineState, read_engine_state
from omega_serv.application.services.pid_file import pid_file_status
from omega_serv.core.i18n import _
from omega_serv.core.platform_info import cpu_info, is_process_running
from omega_serv.domain.config.entities import OmegaServConfig
from omega_serv.ports.filesystem_port import FilesystemPort


@dataclass(frozen=True)
class EngineStatus:
    running: EngineState | None
    """Etat du serveur EN MARCHE (None : arrete, ou etat perime d'un autre lancement)."""
    forecast: EngineDecision
    """Ce que donnerait un demarrage avec la configuration actuelle."""
    workers: int = 1
    """`server.workers` tel qu'il sera applique avec le moteur effectif prevu (ramene au maximum de la machine)."""
    workers_notice: str | None = None
    """Pourquoi `workers` differe de `server.workers` (None : applique tel quel)."""
    connectors: list[tuple[str, str]] = field(default_factory=list)
    """Fonctions actives et qui les sert avec le natif (engine_levels.engine_connectors)."""


def engine_status(filesystem: FilesystemPort, project_root: Path, config: OmegaServConfig,
                  binary_problem: str | None) -> EngineStatus:
    forecast = decide_engine(config, binary_problem)
    pid, _unreadable = pid_file_status(filesystem, project_root / "var" / "run" / "omega-serv.pid")
    state = read_engine_state(filesystem, project_root)
    alive = pid is not None and is_process_running(pid)
    running = state if (alive and state is not None and state.supervisor_pid == pid) else None
    cpu = cpu_info()
    workers = resolved_worker_count(config.server.workers, forecast.effective, cpu.usable_cores)
    notice = worker_count_notice(config.server.workers, forecast.effective, cpu.usable_cores)
    return EngineStatus(running, forecast, workers, notice, engine_connectors(config))


def _engine_label(engine: str) -> str:
    return _("natif (omega-http-core)") if engine == "native" else _("Python")


def engine_status_rows(status: EngineStatus) -> list[tuple[str, str, str]]:
    """(libelle, valeur, style) - style : "" normal, "green", "yellow", "red", "dim"."""
    rows: list[tuple[str, str, str]] = []
    state = status.running
    if state is None:
        decision = status.forecast
        rows.append((_("Serveur"), _("arrêté - prévision au prochain démarrage"), "dim"))
        rows.append((_("Demandé"), _engine_label(decision.requested), ""))
        rows.append((_("Effectif"), _engine_label(decision.effective), "yellow" if decision.fallback else "green"))
        rows += _workers_rows(status)
        rows += [(_("Raison"), describe_reason(code), "yellow") for code in decision.reasons]
        rows += [(_("Remarque"), describe_reason(code), "dim") for code in decision.notices]
        return rows

    fallback = state.requested != state.effective
    rows.append((_("Demandé"), _engine_label(state.requested), ""))
    rows.append((_("Effectif"), _engine_label(state.effective), "yellow" if fallback else "green"))
    rows += _workers_rows(status)
    rows += [(_("Raison"), describe_reason(code), "yellow") for code in state.reasons
             if not code.startswith("native_")]
    if state.start_failure:
        rows.append((_("Échec au démarrage"), state.start_failure, "yellow"))
    rows += [(_("Remarque"), describe_reason(code), "dim") for code in state.notices]
    if state.effective == "native":
        rows.append((_("Binaire"), f"{state.binary_version} (PID {state.native_pid})", ""))
        rows.append((_("Génération"), str(state.generation), ""))
        rows.append((_("Connexions ouvertes"), str(state.connections), ""))
        rows.append((_("Requêtes servies"), str(state.requests), ""))
        if state.rejected:
            rows.append((_("Refus (capacité)"), str(state.rejected), "yellow"))
        if state.restarts:
            rows.append((_("Relances du natif"), str(state.restarts), "yellow"))
    if state.last_reload:
        rows.append((_("Dernier rechargement"), state.last_reload,
                     "red" if "REFUSE" in state.last_reload else ""))
    forecast = status.forecast
    if (forecast.requested, forecast.effective) != (state.requested, state.effective):
        rows.append((_("Au prochain démarrage"), _("{requested} demandé, {effective} effectif").format(
            requested=_engine_label(forecast.requested), effective=_engine_label(forecast.effective)), "yellow"))
    return rows


def _workers_rows(status: EngineStatus) -> list[tuple[str, str, str]]:
    rows = [(_("Processus"), str(status.workers), "")]
    if status.workers_notice:
        rows.append((_("Remarque"), status.workers_notice, "yellow"))
    return rows


def engine_connector_rows(status: EngineStatus) -> list[tuple[str, str, str]]:
    """Tableau des connecteurs (plan §7), bloc a part de l'ecran Etat et de `engine status` : seulement quand le
    natif sert (ou servira) - avec le moteur Python, tout est Python et le tableau n'apprendrait rien."""
    effective = status.running.effective if status.running is not None else status.forecast.effective
    if effective != "native":
        return []
    return [(label, describe_connector(mode), "green" if mode == "native" else "") for label, mode in status.connectors]
