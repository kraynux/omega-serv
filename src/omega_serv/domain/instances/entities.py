"""Entite du registre multi-instance (OMEGA-SERV_PLAN-DETAILLE_
MULTI_INSTANCE.md §3) - une ligne du registre global
`~/.config/omega-serv/instances.json`, jamais confondue avec
`OmegaServConfig` (la configuration SERVEUR d'une instance donnee,
qui vit dans le `config/omega-serve.json` de CETTE instance)."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from pathlib import Path


@dataclass(frozen=True)
class InstanceEntry:
    name: str
    path: Path
    """Chemin RESOLU (symlinks suivis, absolu) au moment de
    l'enregistrement - jamais une chaine brute, pour que la
    verification de non-imbrication (domain/instances/registry.py)
    reste fiable meme face a un lien symbolique."""
    bind: str
    port: int
    service_name: str
    created_at: datetime
