"""Implementation reelle de LogsMaintenancePort (plan interface §3.4/§8).
Reecriture du fichier en place (jamais un fichier d'exclusion separe) -
lignes non reconnues par le parseur (format inattendu) sont conservees
telles quelles plutot que retirees a tort."""
from __future__ import annotations

from pathlib import Path

from omega_serv.domain.logging.access_log_parser import parse_combined_log_line


class LogsMaintenance:
    def remove_ip(self, ip: str, log_path: Path) -> int:
        if not log_path.exists():
            return 0

        kept_lines: list[str] = []
        removed = 0
        with log_path.open(encoding="utf-8", errors="replace") as f:
            for line in f:
                entry = parse_combined_log_line(line)
                if entry is not None and entry.ip == ip:
                    removed += 1
                    continue
                kept_lines.append(line)

        if removed:
            log_path.write_text("".join(kept_lines), encoding="utf-8")
        return removed
