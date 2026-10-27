"""Date de demarrage d'un processus et date du code installe - lectures seules,
jamais une exception (None si l'information est indisponible : autre systeme
que Linux, /proc masque par hidepid, processus disparu)."""
from __future__ import annotations

import os
from datetime import datetime, timezone
from pathlib import Path


def process_start_time(pid: int) -> datetime | None:
    """`/proc/<pid>/stat` champ 22 (ticks depuis le demarrage de la machine)
    + `btime` de `/proc/stat` - lisibles par tout utilisateur, meme pour un
    processus d'un autre compte (le service systemd dedie)."""
    try:
        stat = Path(f"/proc/{pid}/stat").read_text()
        # Le nom du processus (champ 2, entre parentheses) peut contenir des espaces.
        fields = stat[stat.rindex(")") + 2:].split()
        start_ticks = int(fields[19])
        boot_time = next(
            int(line.split()[1]) for line in Path("/proc/stat").read_text().splitlines() if line.startswith("btime ")
        )
        ticks_per_second = os.sysconf("SC_CLK_TCK")
    except (OSError, ValueError, IndexError, StopIteration):
        return None
    return datetime.fromtimestamp(boot_time + start_ticks / ticks_per_second, tz=timezone.utc)


def newest_code_time(package_dir: Path) -> datetime | None:
    """Date de modification la plus recente des fichiers .py du paquet - une
    archive extraite conserve les dates de sa construction, donc une
    reextraction de la MEME archive ne declenche jamais d'avertissement."""
    newest = 0.0
    try:
        for path in package_dir.rglob("*.py"):
            newest = max(newest, path.stat().st_mtime)
    except OSError:
        return None
    return datetime.fromtimestamp(newest, tz=timezone.utc) if newest else None
