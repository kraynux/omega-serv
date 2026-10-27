"""Implemente ports.ioc_exporter_port.IoCExporterPort - evenement MISP au format JSON
(OMEGA-SERV_ETUDE_ACTIVE_DEFENSE_STIX_MISP_CHARGE.md §2.3, decisions du 2026-10-26).

A importer par l'interface de MISP (« Add Event → Populate from → MISP JSON ») : aucun appel a
l'API MISP depuis omega-serv, fichier local seulement. Distribution « votre organisation
seulement » (0) : c'est l'exploitant qui elargit dans MISP. Une adresse IP partageable = un
attribut `ip-src` ; `to_ids` seulement a partir de `ioc.minimum_confidence`. Niveau de menace
deduit de la confiance la plus haute : >= 90 eleve (1), >= 70 moyen (2), sinon faible (3)."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from omega_serv.domain.security.active_defense.entities import ExportResult, Incident
from omega_serv.infrastructure.exporters.export_checksum import write_export_checksum
from omega_serv.infrastructure.exporters.stix_ioc_exporter import (
    shareable_ip_indicators,
    stable_uuid,
)
from omega_serv.ports.filesystem_port import FilesystemPort


def misp_threat_level(confidence: int) -> str:
    if confidence >= 90:
        return "1"
    if confidence >= 70:
        return "2"
    return "3"


def build_misp_event(incident: Incident, tlp: str, minimum_confidence: int) -> dict[str, Any]:
    indicators = shareable_ip_indicators(incident)
    top_confidence = max((i.confidence for i in indicators), default=0)
    last_seen = max([incident.opened_at, *(i.last_seen for i in indicators)])
    attributes = [
        {
            "uuid": stable_uuid("misp-attribute", incident.incident_id, indicator.value),
            "type": "ip-src", "category": "Network activity", "value": indicator.value,
            "to_ids": indicator.confidence >= minimum_confidence,
            "distribution": "5",  # comme l'evenement
            "comment": f"omega-serv Active Defense, confidence {indicator.confidence}",
            "first_seen": indicator.first_seen.isoformat(), "last_seen": indicator.last_seen.isoformat(),
            "timestamp": str(int(indicator.last_seen.timestamp())),
        }
        for indicator in indicators
    ]
    return {
        "Event": {
            "uuid": stable_uuid("misp-event", incident.incident_id),
            "info": f"omega-serv: incident {incident.incident_id}",
            "date": incident.opened_at.date().isoformat(),
            "threat_level_id": misp_threat_level(top_confidence),
            "analysis": "2" if incident.status == "closed" else "0",
            "distribution": "0",
            "published": False,
            "timestamp": str(int((incident.closed_at or last_seen).timestamp())),
            "Tag": [{"name": f"tlp:{tlp}"}],
            "Attribute": attributes,
        },
    }


class MispIoCExporter:
    def __init__(self, filesystem: FilesystemPort, export_dir: Path, tlp: str = "amber", minimum_confidence: int = 70) -> None:
        self._filesystem = filesystem
        self._export_dir = export_dir
        self._tlp = tlp
        self._minimum_confidence = minimum_confidence

    def export(self, incident: Incident) -> ExportResult:
        content = json.dumps(build_misp_event(incident, self._tlp, self._minimum_confidence), indent=2, ensure_ascii=False)
        self._filesystem.make_directory(self._export_dir)
        path = self._export_dir / f"{incident.incident_id}.misp.json"
        self._filesystem.atomic_write_text(path, content)
        write_export_checksum(self._filesystem, path, content)
        return ExportResult(path=path, export_format="misp", bytes_written=len(content.encode("utf-8")))
