# Copyright (c) 2026 kraynux - kraynux@proton.me - Licence MIT (voir fichier LICENSE)
"""Implemente ports.incident_report_exporter_port.IncidentReportExporterPort
- rapport Markdown local (plan_active_defense_omega_serv.md, §"IoC et
rapports"). Genere par simple assemblage de chaines - jamais jinja2
(contrat import-linter "jinja2 seulement dans infrastructure.exporters.
html_exporter", ce module en est explicitement exclu), un rapport a mise
en page fixe n'a pas besoin d'un moteur de templates."""
from __future__ import annotations

import uuid
from pathlib import Path

from omega_serv.domain.security.active_defense.entities import ExportResult, Incident
from omega_serv.domain.security.active_defense.policies import extract_indicators
from omega_serv.infrastructure.exporters.export_checksum import write_export_checksum
from omega_serv.ports.filesystem_port import FilesystemPort


def render_incident_report_markdown(incident: Incident) -> str:
    indicators = extract_indicators(incident, id_factory=lambda: str(uuid.uuid4()))
    lines = [
        f"# Incident {incident.incident_id}",
        "",
        f"- Source : `{incident.subject_id}`",
        f"- Statut : {incident.status}",
        f"- Ouvert le : {incident.opened_at.isoformat()}",
        f"- Ferme le : {incident.closed_at.isoformat() if incident.closed_at else '-'}",
        "",
        "## Chronologie",
        "",
    ]
    if incident.events:
        for event in incident.events:
            lines.append(f"- `{event.occurred_at.isoformat()}` **{event.kind}** - {event.detail}")
    else:
        lines.append("_Aucun evenement enregistre._")
    lines += ["", "## Indicateurs de compromission (IoC)", ""]
    if indicators:
        lines.append("| Type | Valeur | Confiance | Premiere observation | Derniere observation |")
        lines.append("|---|---|---|---|---|")
        for indicator in indicators:
            lines.append(
                f"| {indicator.kind} | `{indicator.value}` | {indicator.confidence} | "
                f"{indicator.first_seen.isoformat()} | {indicator.last_seen.isoformat()} |"
            )
    else:
        lines.append("_Aucun IoC extrait._")
    lines.append("")
    return "\n".join(lines)


class MarkdownIncidentReportExporter:
    def __init__(self, filesystem: FilesystemPort, export_dir: Path) -> None:
        self._filesystem = filesystem
        self._export_dir = export_dir

    def render(self, incident: Incident) -> ExportResult:
        content = render_incident_report_markdown(incident)
        self._filesystem.make_directory(self._export_dir)
        path = self._export_dir / f"{incident.incident_id}.md"
        self._filesystem.atomic_write_text(path, content)
        write_export_checksum(self._filesystem, path, content)
        return ExportResult(path=path, export_format="markdown", bytes_written=len(content.encode("utf-8")))
