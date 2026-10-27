"""Implemente ports.ioc_exporter_port.IoCExporterPort - bundle STIX 2.1
(OMEGA-SERV_ETUDE_ACTIVE_DEFENSE_STIX_MISP_CHARGE.md §2.2, decisions du 2026-10-26).

Un fichier par incident : un `identity` (le producteur « omega-serv », sans nom de machine ni de
domaine), un `indicator` par adresse IP partageable (motif `[ipv4-addr:value = '…']` ou
`ipv6-addr`), un `report` qui regroupe l'incident, et le marquage TLP choisi (definitions TLP 1.0
standard de STIX 2.1). L'empreinte du User-Agent n'a pas d'equivalent STIX exploitable : jamais
exportee comme motif.

Identifiants STABLES (UUID v5 derives de l'incident et de la valeur) : reexporter le meme incident
donne les memes identifiants, l'outil qui importe ne cree pas de doublons. JSON ecrit a la main,
bibliotheque standard seulement ; fichier local, jamais envoye."""
from __future__ import annotations

import ipaddress
import json
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from omega_serv.domain.security.active_defense.entities import ExportResult, Incident, Indicator
from omega_serv.domain.security.active_defense.policies import extract_indicators
from omega_serv.infrastructure.exporters.export_checksum import write_export_checksum
from omega_serv.ports.filesystem_port import FilesystemPort

OMEGA_SERV_NAMESPACE = uuid.uuid5(uuid.NAMESPACE_URL, "https://kraynux.snake-mackarel.ts.net/omega-serv/ioc")
"""Espace de noms des UUID v5 (STIX et MISP) - ne jamais le changer : les identifiants deja
importes chez un tiers deviendraient des doublons."""

TLP_MARKING_DEFINITIONS = {
    "white": "marking-definition--613f2e26-407d-48c7-9eca-b8e91df99dc9",
    "green": "marking-definition--34098fce-860f-48ae-8e50-ebd3cc5e41da",
    "amber": "marking-definition--f88d31f6-486f-44da-b317-01333bde0b82",
    "red": "marking-definition--5e57c739-391a-4eb3-b6be-7d15ca92d5ed",
}
"""Definitions TLP 1.0 predefinies par la specification STIX 2.1 (§7.2.1.4)."""
_TLP_CREATED = "2017-01-20T00:00:00.000Z"
_IDENTITY_CREATED = "2026-10-26T00:00:00.000Z"


def stable_uuid(*parts: str) -> str:
    return str(uuid.uuid5(OMEGA_SERV_NAMESPACE, "|".join(parts)))


def stix_timestamp(moment: datetime) -> str:
    """RFC 3339 en UTC avec millisecondes et « Z », forme exigee par STIX 2.1."""
    utc = moment.astimezone(timezone.utc) if moment.tzinfo else moment.replace(tzinfo=timezone.utc)
    return utc.strftime("%Y-%m-%dT%H:%M:%S.") + f"{utc.microsecond // 1000:03d}Z"


def shareable_ip_indicators(incident: Incident) -> list[Indicator]:
    """Indicateurs exportables en STIX/MISP : adresses IP partageables (meme filtre que le CSV),
    validees comme adresses (jamais une valeur arbitraire dans un motif)."""
    kept = []
    for indicator in extract_indicators(incident, id_factory=lambda: str(uuid.uuid4())):
        if indicator.kind != "ip" or not indicator.shareable:
            continue
        try:
            ipaddress.ip_address(indicator.value)
        except ValueError:
            continue
        kept.append(indicator)
    return kept


def build_stix_bundle(incident: Incident, tlp: str) -> dict[str, Any]:
    marking = TLP_MARKING_DEFINITIONS[tlp]
    identity_id = f"identity--{stable_uuid('identity', 'omega-serv')}"
    objects: list[dict[str, Any]] = [
        {
            "type": "marking-definition", "spec_version": "2.1", "id": marking, "created": _TLP_CREATED,
            "definition_type": "tlp", "name": f"TLP:{tlp.upper()}", "definition": {"tlp": tlp},
        },
        {
            "type": "identity", "spec_version": "2.1", "id": identity_id,
            "created": _IDENTITY_CREATED, "modified": _IDENTITY_CREATED,
            "name": "omega-serv", "identity_class": "system",
        },
    ]
    indicator_ids = []
    last_seen = incident.opened_at
    for indicator in shareable_ip_indicators(incident):
        address = ipaddress.ip_address(indicator.value)
        sco_type = "ipv4-addr" if address.version == 4 else "ipv6-addr"
        indicator_id = f"indicator--{stable_uuid('indicator', incident.incident_id, indicator.value)}"
        indicator_ids.append(indicator_id)
        last_seen = max(last_seen, indicator.last_seen)
        objects.append({
            "type": "indicator", "spec_version": "2.1", "id": indicator_id,
            "created": stix_timestamp(indicator.first_seen), "modified": stix_timestamp(indicator.last_seen),
            "created_by_ref": identity_id,
            "name": f"omega-serv: hostile source {address}",
            "description": f"Source observed by omega-serv Active Defense (incident {incident.incident_id}).",
            "indicator_types": ["malicious-activity"],
            "pattern": f"[{sco_type}:value = '{address}']", "pattern_type": "stix",
            "valid_from": stix_timestamp(indicator.first_seen),
            "confidence": max(0, min(100, indicator.confidence)),
            "object_marking_refs": [marking],
        })
    modified = incident.closed_at or last_seen
    objects.append({
        "type": "report", "spec_version": "2.1", "id": f"report--{stable_uuid('report', incident.incident_id)}",
        "created": stix_timestamp(incident.opened_at), "modified": stix_timestamp(max(modified, incident.opened_at)),
        "created_by_ref": identity_id,
        "name": f"omega-serv incident {incident.incident_id}",
        "description": f"Active Defense incident, status {incident.status}.",
        "report_types": ["threat-report"], "published": stix_timestamp(incident.opened_at),
        # object_refs ne peut pas etre vide : sans indicateur partageable, le rapport cite le producteur
        "object_refs": indicator_ids or [identity_id],
        "object_marking_refs": [marking],
    })
    return {"type": "bundle", "id": f"bundle--{stable_uuid('bundle', incident.incident_id)}", "objects": objects}


class StixIoCExporter:
    def __init__(self, filesystem: FilesystemPort, export_dir: Path, tlp: str = "amber") -> None:
        self._filesystem = filesystem
        self._export_dir = export_dir
        self._tlp = tlp

    def export(self, incident: Incident) -> ExportResult:
        content = json.dumps(build_stix_bundle(incident, self._tlp), indent=2, ensure_ascii=False)
        self._filesystem.make_directory(self._export_dir)
        path = self._export_dir / f"{incident.incident_id}.stix.json"
        self._filesystem.atomic_write_text(path, content)
        write_export_checksum(self._filesystem, path, content)
        return ExportResult(path=path, export_format="stix", bytes_written=len(content.encode("utf-8")))
