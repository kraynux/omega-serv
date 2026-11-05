"""Export automatique a la fermeture d'un incident (`ioc.auto_export_on_close`, plan §"Mode guerre") - un seul
endroit pour la regle, quel que soit qui ferme : bouton « Fermer », bouton « Purger maintenant », CLI
`active-defense purge` ou entretien automatique du serveur (2026-11-01). Les exporteurs sont injectes
(jamais importes ici) : l'ecran, la CLI et le serveur fournissent chacun les leurs."""
from __future__ import annotations

from collections.abc import Callable, Iterable

from omega_serv.domain.security.active_defense.config import ActiveDefenseConfig
from omega_serv.domain.security.active_defense.entities import Incident
from omega_serv.ports.incident_repository_port import IncidentRepositoryPort

IOC_FORMATS = frozenset({"json", "csv", "stix", "misp"})


def auto_export_closed_incidents(
    incident_ids: Iterable[str],
    incident_repository: IncidentRepositoryPort,
    config: ActiveDefenseConfig,
    export_ioc: Callable[[Incident, str], object] | None,
    export_report: Callable[[Incident], object] | None,
    report_error: Callable[[str], None] | None = None,
) -> int:
    """Retourne le nombre d'exports ecrits. Rien si l'option est desactivee. Une erreur d'ecriture n'empeche
    jamais les autres exports (signalee par `report_error`)."""
    if not config.ioc.auto_export_on_close:
        return 0
    written = 0
    for incident_id in incident_ids:
        incident = incident_repository.get(incident_id)
        if incident is None:
            continue
        for export_format in config.ioc.formats:
            try:
                if export_format in IOC_FORMATS and export_ioc is not None:
                    if export_ioc(incident, export_format) is not None:
                        written += 1
                elif export_format == "markdown" and export_report is not None:
                    export_report(incident)
                    written += 1
            except OSError as error:
                if report_error is not None:
                    report_error(f"{incident_id} ({export_format}) : {error}")
    return written
