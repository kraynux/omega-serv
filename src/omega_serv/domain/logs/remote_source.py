"""Source distante (SSH) pour la Bibliotheque de logs (OMEGA-SERV_ETUDE-
FAISABILITE_LOGS_DISTANTS.md, 2026-10-15) : permet de recuperer, a la
demande explicite de l'utilisateur, le log d'un backend sur le meme
reseau local via `scp`. Aucun mot de passe nulle part : l'authentification
est entierement deleguee au `ssh`/`scp` du systeme et a la configuration
SSH deja existante de l'utilisateur (agent, ~/.ssh/config) - `identity_file`
n'est jamais qu'un CHEMIN vers une cle deja presente sur le disque,
jamais son contenu."""
from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass
from pathlib import Path

_SLUG_RE = re.compile(r"[^a-z0-9]+")
_MAX_SLUG_LENGTH = 60


@dataclass(frozen=True, slots=True)
class RemoteLogSource:
    label: str
    host: str
    remote_path: str
    user: str | None = None
    port: int | None = None
    identity_file: str | None = None


def build_scp_command(source: RemoteLogSource, local_dest: Path) -> list[str]:
    """Construit l'argv de `scp` sous forme de LISTE, jamais une chaine
    shell - immunise par construction contre toute injection de commande
    via host/remote_path fournis par l'utilisateur (chaque element reste
    un argument separe, jamais concatene/interprete par un shell)."""
    target_host = f"{source.user}@{source.host}" if source.user else source.host
    command = ["scp"]
    if source.port is not None:
        command += ["-P", str(source.port)]
    if source.identity_file:
        command += ["-i", source.identity_file]
    command += ["-o", "ConnectTimeout=10", f"{target_host}:{source.remote_path}", str(local_dest)]
    return command


def safe_cache_filename(label: str, *, suffix: str = ".log") -> str:
    """Nom de fichier de cache local derive du label - jamais le label
    brut utilise comme segment de chemin (aucune traversee de chemin
    possible). Deterministe : un meme label redonne toujours le meme
    nom (re-recuperer ecrase son propre cache, comme l'ajout manuel
    existant de la Bibliotheque). Le suffixe de hash evite une collision
    entre deux labels qui se "sluggifient" identiquement (ex. "Backend A"
    et "Backend_A")."""
    slug = _SLUG_RE.sub("-", label.strip().lower()).strip("-")[:_MAX_SLUG_LENGTH] or "source"
    digest = hashlib.sha256(label.encode("utf-8")).hexdigest()[:8]
    return f"{slug}-{digest}{suffix}"
