"""Construction des exporteurs d'IoC d'un incident, en un seul endroit (CLI et TUI) : json, csv,
stix (STIX 2.1), misp (evenement MISP). Le marquage TLP et la confiance minimale viennent de
`options.active_defense.ioc` ; le rapport Markdown a son propre exporteur."""
from __future__ import annotations

from pathlib import Path

from omega_serv.domain.security.active_defense.config import IoCConfig
from omega_serv.infrastructure.exporters.csv_ioc_exporter import CsvIoCExporter
from omega_serv.infrastructure.exporters.json_ioc_exporter import JsonIoCExporter
from omega_serv.infrastructure.exporters.misp_ioc_exporter import MispIoCExporter
from omega_serv.infrastructure.exporters.stix_ioc_exporter import StixIoCExporter
from omega_serv.ports.filesystem_port import FilesystemPort
from omega_serv.ports.ioc_exporter_port import IoCExporterPort


def build_ioc_exporters(filesystem: FilesystemPort, export_dir: Path, ioc: IoCConfig) -> dict[str, IoCExporterPort]:
    return {
        "json": JsonIoCExporter(filesystem, export_dir),
        "csv": CsvIoCExporter(filesystem, export_dir),
        "stix": StixIoCExporter(filesystem, export_dir, tlp=ioc.tlp),
        "misp": MispIoCExporter(filesystem, export_dir, tlp=ioc.tlp, minimum_confidence=ioc.minimum_confidence),
    }
