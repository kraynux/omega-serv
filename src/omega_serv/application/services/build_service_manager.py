"""Usine construisant l'adaptateur ServiceManagerPort reel selon le
gestionnaire de service detecte sur le systeme (systemd/OpenRC/runit) -
meme patron "usine" que application/server/start_server.py::build_waf_collaborators
(application/ construit directement des adaptateurs infrastructure/,
volontairement exemptee des contrats import-linter subprocess/ssl, voir
pyproject.toml). interfaces.tui appelle CETTE fonction plutot que de
construire l'adaptateur elle-meme (plan interface §1/§3.6) : un ecran ne
doit jamais importer infrastructure/ directement. Duplique la logique de
interfaces/cli/main.py::_build_service_manager (le CLI construit ses
adaptateurs localement par sa propre convention deja etablie, exemptee
elle aussi) - duplication mineure acceptee plutot qu'un remaniement du
CLI hors perimetre de ce chantier."""
from __future__ import annotations

from omega_serv.infrastructure.process.subprocess_runner import SubprocessRunner
from omega_serv.infrastructure.services.detector import detect_service_manager_type
from omega_serv.infrastructure.services.openrc_service_manager import OpenRCServiceManager
from omega_serv.infrastructure.services.runit_service_manager import RunitServiceManager
from omega_serv.infrastructure.services.systemd_service_manager import SystemdServiceManager
from omega_serv.ports.service_manager_port import ServiceManagerPort


def build_service_manager() -> ServiceManagerPort | None:
    manager_type = detect_service_manager_type()
    if manager_type is None:
        return None
    runner = SubprocessRunner()
    if manager_type == "systemd":
        return SystemdServiceManager(runner)
    if manager_type == "openrc":
        return OpenRCServiceManager(runner)
    return RunitServiceManager(runner)
