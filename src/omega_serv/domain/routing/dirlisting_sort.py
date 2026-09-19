"""Tri du directory listing par colonne (retour utilisateur : "pouvoir
voir et trier" - ligne de criteres NOM/DERNIERE MODIFICATION/TAILLE).

Sans JavaScript (aucune page generee par omega-serv n'en utilise a ce
jour) : chaque en-tete de colonne est un lien qui rejoue la MEME page
avec `?sort=<colonne>&order=<sens>` - le tri est donc entierement
recalcule cote serveur a chaque clic, jamais un tri client. `parse_qs`
directement ici (domain/) - meme precedent que `domain/logging/
body_redaction.py` (deja `from urllib.parse import parse_qsl, urlencode`
en domain/, aucune I/O, purement du texte)."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Literal
from urllib.parse import parse_qs, urlencode

SortKey = Literal["name", "mtime", "size"]
SORT_KEYS: tuple[SortKey, ...] = ("name", "mtime", "size")
DEFAULT_SORT_KEY: SortKey = "name"


@dataclass(frozen=True)
class DirEntryInfo:
    """Metadonnees d'une entree, deja lues depuis le disque par l'appelant
    (application/server/serve_static_file.py, seul detenteur d'un
    FilesystemPort) - ce module reste pur, sans I/O. `size`/`mtime` a
    `None` pour un dossier (pas de taille recursive calculee - resterait
    couteux pour un gros dossier, hors perimetre) ou quand la valeur n'a
    pas ete fournie."""

    is_directory: bool = False
    size: int | None = None
    mtime: float | None = None


@dataclass(frozen=True)
class DirlistingSort:
    key: SortKey = DEFAULT_SORT_KEY
    descending: bool = False

    def query_for(self, key: SortKey) -> str:
        """Chaine de requete du lien d'en-tete pour la colonne `key` :
        inverse le sens si c'est deja la colonne active, sinon retombe
        sur l'ordre croissant (premier clic sur une nouvelle colonne)."""
        next_descending = self.key == key and not self.descending
        return urlencode({"sort": key, "order": "desc" if next_descending else "asc"})


def parse_dirlisting_sort(query: str) -> DirlistingSort:
    """Jamais d'erreur sur une requete malformee/perimee (favori navigateur
    sur un ancien lien, parametre bidouille) - retombe silencieusement sur
    le tri par defaut, meme esprit que `icon_registry.icon_for_file` face
    a un mime type inconnu."""
    params = parse_qs(query)
    raw_key = params.get("sort", [DEFAULT_SORT_KEY])[0]
    key: SortKey = raw_key if raw_key in SORT_KEYS else DEFAULT_SORT_KEY
    order = params.get("order", ["asc"])[0]
    return DirlistingSort(key=key, descending=order == "desc")


def sort_entry_names(
    names: list[str], entry_info: dict[str, DirEntryInfo], sort: DirlistingSort
) -> list[str]:
    def sort_key(name: str) -> tuple[int, float] | str:
        info = entry_info.get(name, DirEntryInfo())
        if sort.key == "size":
            return (0, -1.0) if info.size is None else (1, float(info.size))
        if sort.key == "mtime":
            return (0, 0.0) if info.mtime is None else (1, info.mtime)
        return name.lower()

    return sorted(names, key=sort_key, reverse=sort.descending)
