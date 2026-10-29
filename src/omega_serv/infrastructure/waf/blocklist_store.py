"""Implementation reelle de BlocklistPort : fichier JSON (doc WAF §5 -
"prefer un format structure JSON... plutot qu'un simple fichier
texte"). Ecriture atomique (meme mecanisme que la configuration
principale, infrastructure/config/json_config_repository.py) - jamais
de fichier a moitie ecrit meme sous charge (auto-block)."""
from __future__ import annotations

import json
import sys
from pathlib import Path

from omega_serv.domain.security.waf.blocklist import (
    BlocklistIndex,
    parse_blocklist,
    purge_expired,
    serialize_blocklist,
)
from omega_serv.domain.security.waf.entities import BlocklistEntry
from omega_serv.ports.clock_port import ClockPort
from omega_serv.ports.filesystem_port import FilesystemPort


class BlocklistUnreadableError(OSError):
    """Le fichier de blocklist existe mais ne peut pas etre lu : toute ECRITURE
    est refusee (elle reecrirait le fichier sans les bans existants)."""


class JsonBlocklistStore:
    """Implementation reelle de ports.blocklist_port.BlocklistPort.

    Cache en memoire invalide par mtime (retour utilisateur, audit
    performance 2026-09-14) : `is_blocked()` est appelee pour CHAQUE
    requete des que le WAF est actif, et relisait/re-parsait auparavant
    tout le fichier JSON a chaque fois (I/O disque + `json.loads` +
    reconstruction complete des entrees) - le pire moment possible etant
    justement pendant une attaque reelle, quand la blocklist grossit et
    que la charge est deja maximale. Un simple `stat()` (bien moins
    couteux qu'une lecture complete) suffit desormais a detecter qu'une
    modification externe a eu lieu (le CLI peut toujours modifier le
    fichier pendant que le serveur tourne, angle mort §9.1 - coordination
    CLI <-> serveur, jamais perdue) ; nos PROPRES ecritures
    (add_entry/remove_entry/purge_expired) mettent aussi a jour le cache
    directement plutot que de compter sur la granularite du mtime du
    systeme de fichiers (parfois seulement a la seconde pres)."""

    def __init__(self, filesystem: FilesystemPort, path: Path, clock: ClockPort):
        self._fs = filesystem
        self._path = path
        self._clock = clock
        self._cache: list[BlocklistEntry] | None = None
        self._cache_mtime: float | None = None
        self._last_reported_error: str | None = None
        # Index de recherche de la DERNIERE liste lue (voir is_blocked) ; reconstruit
        # seulement quand la liste change, jamais a chaque requete.
        self._index = BlocklistIndex([])
        self._index_source: list[BlocklistEntry] | None = None

    def _report_read_error(self, error: OSError) -> None:
        """Une seule ligne par erreur DISTINCTE (jamais une par requete)."""
        message = f"{type(error).__name__} : {error}"
        if message != self._last_reported_error:
            self._last_reported_error = message
            print(
                f"ERREUR blocklist illisible ({self._path}) - derniere liste valide conservee, "
                f"aucun ban ne peut etre ajoute tant que le fichier reste illisible : {message}",
                file=sys.stderr,
            )

    def _load(self, *, for_write: bool = False) -> list[BlocklistEntry]:
        """Incident reel du 2026-10-18 (craftdark) : blocklist.json reecrit en
        root:root 600 -> PermissionError a CHAQUE requete, site entier en 502.
        Desormais : en LECTURE (is_blocked, list, count), une erreur garde la
        derniere liste lue correctement (une seule ligne d'erreur sur stderr,
        donc dans journalctl) ; en ECRITURE (`for_write=True`), elle leve
        BlocklistUnreadableError - jamais un fichier reecrit avec une liste
        vide qui effacerait les bans existants."""
        if not self._fs.exists(self._path):
            self._cache = None
            self._cache_mtime = None
            return []
        try:
            current_mtime = self._fs.file_mtime(self._path)
            if self._cache is not None and self._cache_mtime == current_mtime:
                return self._cache
            raw = self._fs.read_text(self._path)
        except OSError as e:
            self._report_read_error(e)
            if for_write:
                raise BlocklistUnreadableError(
                    f"blocklist illisible {self._path} : {e} - écriture refusée pour ne pas effacer les bans existants"
                ) from e
            return list(self._cache or [])
        self._last_reported_error = None
        try:
            data = json.loads(raw)
        except json.JSONDecodeError:
            entries: list[BlocklistEntry] = []
        else:
            entries = parse_blocklist(data)
        self._cache = entries
        self._cache_mtime = current_mtime
        return entries

    def _save(self, entries: list[BlocklistEntry]) -> None:
        content = json.dumps(serialize_blocklist(entries), indent=2, ensure_ascii=False) + "\n"
        self._fs.atomic_write_text(self._path, content)
        self._cache = entries
        self._cache_mtime = self._fs.file_mtime(self._path)

    def is_blocked(self, ip: str) -> BlocklistEntry | None:
        entries = self._load()
        # Liste illisible : `_load` renvoie une COPIE de la derniere liste valide -
        # l'index de cette liste reste valable, inutile de le reconstruire.
        source = self._cache if self._cache is not None else entries
        if source is not self._index_source:
            self._index = BlocklistIndex(source)
            self._index_source = source
        return self._index.find(ip, self._clock.now())

    def list_entries(self) -> tuple[BlocklistEntry, ...]:
        return tuple(self._load())

    def add_entry(self, entry: BlocklistEntry) -> None:
        entries = self._load(for_write=True)
        entries = [e for e in entries if e.network != entry.network]
        entries.append(entry)
        self._save(entries)

    def remove_entry(self, network: str) -> bool:
        entries = self._load(for_write=True)
        remaining = [e for e in entries if e.network != network]
        if len(remaining) == len(entries):
            return False
        self._save(remaining)
        return True

    def purge_expired(self) -> int:
        entries = self._load(for_write=True)
        kept, removed_count = purge_expired(entries, self._clock.now())
        if removed_count:
            self._save(kept)
        return removed_count

    def count_auto_entries(self) -> int:
        return sum(1 for e in self._load() if e.source == "auto")
