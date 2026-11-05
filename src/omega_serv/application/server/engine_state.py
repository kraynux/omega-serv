"""Etat du moteur HTTP en cours d'execution (plan moteur C++ lot 3, §16.5 : « toujours visible »).

Ecrit par le superviseur (`serve`) dans var/run/engine-state.json au demarrage, a chaque rechargement et
periodiquement (sante du natif) ; lu par l'ecran Etat et `omega-serv engine status`. Le lecteur compare
`supervisor_pid` au fichier PID pour ne jamais presenter l'etat d'un serveur arrete comme actuel : sans serveur
vivant, l'interface affiche la PREVISION de `decide_engine` pour la configuration actuelle."""
from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from pathlib import Path

from omega_serv.ports.filesystem_port import FilesystemPort

ENGINE_STATE_RELATIVE_PATH = Path("var") / "run" / "engine-state.json"


@dataclass(frozen=True)
class EngineState:
    requested: str
    effective: str
    reasons: tuple[str, ...] = ()
    notices: tuple[str, ...] = ()
    supervisor_pid: int = 0
    native_pid: int = 0
    binary_version: str = ""
    generation: int = 0
    connections: int = 0
    requests: int = 0
    rejected: int = 0
    restarts: int = 0
    last_reload: str = ""
    """Resultat du dernier rechargement (texte du journal), vide si aucun."""
    updated_at: str = ""
    start_failure: str = ""
    """Echec du natif au demarrage (cause du repli), vide sinon."""
    extra: dict[str, str] = field(default_factory=dict)


def write_engine_state(filesystem: FilesystemPort, project_root: Path, state: EngineState) -> None:
    data = asdict(state)
    data["reasons"] = list(state.reasons)
    data["notices"] = list(state.notices)
    try:
        filesystem.atomic_write_text(project_root / ENGINE_STATE_RELATIVE_PATH,
                                     json.dumps(data, ensure_ascii=False, indent=1))
    except OSError:
        pass  # information d'affichage : jamais une cause d'arret du serveur


def read_engine_state(filesystem: FilesystemPort, project_root: Path) -> EngineState | None:
    try:
        data = json.loads(filesystem.read_text(project_root / ENGINE_STATE_RELATIVE_PATH))
    except (OSError, ValueError):
        return None
    if not isinstance(data, dict) or not isinstance(data.get("requested"), str) or not isinstance(data.get("effective"), str):
        return None
    known = {name for name in EngineState.__dataclass_fields__}
    values = {key: value for key, value in data.items() if key in known}
    values["reasons"] = tuple(str(r) for r in values.get("reasons", []) or [])
    values["notices"] = tuple(str(n) for n in values.get("notices", []) or [])
    try:
        return EngineState(**values)
    except TypeError:
        return None
