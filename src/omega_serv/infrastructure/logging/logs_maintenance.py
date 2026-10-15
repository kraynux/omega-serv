"""Implementation reelle de LogsMaintenancePort (plan interface §3.4/§8).
Reecriture ATOMIQUE du fichier en place (fichier temporaire + remplacement
via `os.replace`, jamais un `write_text` direct) - une panne en cours
d'ecriture laisserait sinon le fichier original tronque/corrompu.

CORRIGE (gestion des logs, refonte menu 2026-10-15) : filtrait auparavant
via `parse_combined_log_line` (format Combined/Common UNIQUEMENT) - des
que "Voir et traiter IP" a ete generalise a N'IMPORTE QUEL log de la
Bibliotheque (auth.log, syslog...), une ligne dans un autre format ne
matchait jamais ce parseur, donc son IP n'etait JAMAIS reconnue ni
retiree, meme explicitement selectionnee par l'utilisateur - bug reel
trouve en generalisant, pas suppose. Remplace par une correspondance
generique a limite de mot sur la chaine IP elle-meme (meme principe
qu'omega-log/application/use_cases/process_ip.py::remove_ip_from_file,
deja valide) - fonctionne identiquement quel que soit le format de la
ligne, y compris l'access log Combined d'Omega-Serv lui-meme."""
from __future__ import annotations

import os
import re
from pathlib import Path


class LogsMaintenance:
    def remove_ip(self, ip: str, log_path: Path) -> int:
        if not log_path.exists():
            return 0

        pattern = re.compile(rf"\b{re.escape(ip)}\b")
        try:
            with log_path.open(encoding="utf-8", errors="replace") as f:
                lines = f.readlines()
        except OSError:
            return 0

        kept_lines = [line for line in lines if not pattern.search(line)]
        removed = len(lines) - len(kept_lines)
        if not removed:
            return 0

        tmp_path = log_path.with_suffix(log_path.suffix + ".omega-serv-tmp")
        tmp_path.write_text("".join(kept_lines), encoding="utf-8")
        try:
            tmp_stat = os.stat(log_path)
            os.chmod(tmp_path, tmp_stat.st_mode)
        except OSError:
            pass
        os.replace(tmp_path, log_path)
        return removed
