# Copyright (c) 2026 kraynux - kraynux@proton.me - Licence MIT (voir fichier LICENSE)
"""Implemente ports.ioc_exporter_port.IoCExporterPort - export CSV
LIMITE aux IoC partageables (plan_active_defense_omega_serv.md,
§"IoC et rapports" : "CSV limite aux IoC partageables"), jamais les
memes lignes que l'export JSON tel quel."""
from __future__ import annotations

import csv
import io
import uuid
from pathlib import Path

from omega_serv.domain.security.active_defense.entities import ExportResult, Incident
from omega_serv.domain.security.active_defense.policies import extract_indicators
from omega_serv.infrastructure.exporters.export_checksum import write_export_checksum
from omega_serv.ports.filesystem_port import FilesystemPort

_FIELDNAMES = ("kind", "value", "confidence", "first_seen", "last_seen")


class CsvIoCExporter:
    def __init__(self, filesystem: FilesystemPort, export_dir: Path) -> None:
        self._filesystem = filesystem
        self._export_dir = export_dir

    def export(self, incident: Incident) -> ExportResult:
        indicators = extract_indicators(incident, id_factory=lambda: str(uuid.uuid4()))
        shareable = [i for i in indicators if i.shareable]
        buffer = io.StringIO()
        writer = csv.DictWriter(buffer, fieldnames=_FIELDNAMES)
        writer.writeheader()
        for indicator in shareable:
            writer.writerow({
                "kind": indicator.kind, "value": indicator.value, "confidence": indicator.confidence,
                "first_seen": indicator.first_seen.isoformat(), "last_seen": indicator.last_seen.isoformat(),
            })
        content = buffer.getvalue()
        self._filesystem.make_directory(self._export_dir)
        path = self._export_dir / f"{incident.incident_id}.csv"
        self._filesystem.atomic_write_text(path, content)
        write_export_checksum(self._filesystem, path, content)
        return ExportResult(path=path, export_format="csv", bytes_written=len(content.encode("utf-8")))
