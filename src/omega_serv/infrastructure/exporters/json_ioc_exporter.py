# Copyright (c) 2026 kraynux - kraynux@proton.me - Licence MIT (voir fichier LICENSE)
"""Implemente ports.ioc_exporter_port.IoCExporterPort - export JSON
versionne (plan_active_defense_omega_serv.md, §"IoC et rapports").
Ecrit via FilesystemPort (jamais un Path.write_text direct - seul
sqlite_active_defense_connection.py a une exception documentee a cette
regle, pour sqlite3 lui-meme, jamais pour l'ecriture de fichiers
ordinaires)."""
from __future__ import annotations

import json
import uuid
from pathlib import Path

from omega_serv.domain.security.active_defense.entities import ExportResult, Incident
from omega_serv.domain.security.active_defense.policies import extract_indicators
from omega_serv.infrastructure.exporters.export_checksum import write_export_checksum
from omega_serv.ports.filesystem_port import FilesystemPort


class JsonIoCExporter:
    def __init__(self, filesystem: FilesystemPort, export_dir: Path) -> None:
        self._filesystem = filesystem
        self._export_dir = export_dir

    def export(self, incident: Incident) -> ExportResult:
        indicators = extract_indicators(incident, id_factory=lambda: str(uuid.uuid4()))
        payload = {
            "schema_version": 1,
            "incident_id": incident.incident_id,
            "subject_id": incident.subject_id,
            "status": incident.status,
            "opened_at": incident.opened_at.isoformat(),
            "closed_at": incident.closed_at.isoformat() if incident.closed_at else None,
            "indicators": [
                {
                    "kind": indicator.kind, "value": indicator.value, "confidence": indicator.confidence,
                    "first_seen": indicator.first_seen.isoformat(), "last_seen": indicator.last_seen.isoformat(),
                    "shareable": indicator.shareable,
                }
                for indicator in indicators
            ],
        }
        content = json.dumps(payload, indent=2, ensure_ascii=False)
        self._filesystem.make_directory(self._export_dir)
        path = self._export_dir / f"{incident.incident_id}.json"
        self._filesystem.atomic_write_text(path, content)
        write_export_checksum(self._filesystem, path, content)
        return ExportResult(path=path, export_format="json", bytes_written=len(content.encode("utf-8")))
