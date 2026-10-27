"""Regles metier pures sur le registre multi-instance (OMEGA-SERV_PLAN-
DETAILLE_MULTI_INSTANCE.md §2.3/§4) - aucune I/O, uniquement des
verifications sur des `InstanceEntry` deja charges."""
from __future__ import annotations

from pathlib import Path

from omega_serv.core.i18n import _
from omega_serv.domain.instances.entities import InstanceEntry


def is_path_nested(candidate: Path, other: Path) -> bool:
    """True si `candidate` et `other` sont identiques, ou si l'un est
    un descendant de l'autre - les DEUX chemins doivent deja etre
    RESOLUS par l'appelant (§2.3 : une comparaison sur chemins non
    resolus laisserait un lien symbolique contourner la regle)."""
    return candidate == other or candidate in other.parents or other in candidate.parents


def find_nesting_conflict(entries: list[InstanceEntry], candidate: Path) -> InstanceEntry | None:
    """§2.3 : le seul vrai risque de collision entre deux instances
    (Architecture A, repertoires separes) - creer une instance a
    l'interieur d'une autre pourrait exposer son contenu via le
    serveur HTTP de l'instance englobante."""
    for entry in entries:
        if is_path_nested(candidate, entry.path):
            return entry
    return None


def find_port_conflict(entries: list[InstanceEntry], bind: str, port: int) -> InstanceEntry | None:
    """§4 : compare TOUJOURS bind+port ensemble, jamais le port seul -
    127.0.0.1:8080 et 0.0.0.0:8080 ne sont pas un vrai conflit OS."""
    for entry in entries:
        if entry.bind == bind and entry.port == port:
            return entry
    return None


def find_name_conflict(entries: list[InstanceEntry], name: str) -> InstanceEntry | None:
    for entry in entries:
        if entry.name == name:
            return entry
    return None


def validate_new_instance(
    entries: list[InstanceEntry], *, name: str, path: Path, bind: str, port: int,
) -> str | None:
    """Point d'entree unique des 3 verifications de creation - retourne
    un message d'erreur (str) ou None si tout est valide. `path` doit
    deja etre resolu par l'appelant."""
    if not name.strip():
        return _("le nom d'instance ne peut pas être vide")
    if find_name_conflict(entries, name) is not None:
        return _("une instance nommée {name!r} existe déjà dans le registre").format(name=name)
    nesting = find_nesting_conflict(entries, path)
    if nesting is not None:
        return (
            _("{path} est imbriqué avec l'instance {name!r} ({path2}) - deux instances doivent être des répertoires frères, jamais l'un dans l'autre").format(path=path, name=nesting.name, path2=nesting.path)
        )
    port_conflict = find_port_conflict(entries, bind, port)
    if port_conflict is not None:
        return _("{bind}:{port} est déjà utilisé par l'instance {name!r}").format(bind=bind, port=port, name=port_conflict.name)
    return None
