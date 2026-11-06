"""Implementation reelle de BlocklistPort : fichier JSON (doc WAF §5 -
"prefer un format structure JSON... plutot qu'un simple fichier
texte"). Ecriture atomique (meme mecanisme que la configuration
principale, infrastructure/config/json_config_repository.py) - jamais
de fichier a moitie ecrit meme sous charge (auto-block).

Ecritures entre processus (OMEGA-SERV_PLAN-DETAILLE_RIPOSTE.md, lot 0) : chaque
« lire -> modifier -> remplacer » se fait sous un verrou exclusif (`<blocklist>.lock`,
infrastructure/filesystem/file_lock.py) et relit TOUJOURS le fichier sous ce verrou
(jamais le cache, dont le mtime peut n'avoir qu'une seconde de precision) - sinon deux
workers du mode boost, ou un worker et la CLI, qui bannissent au meme moment partent de
la meme liste et le second efface le ban du premier. Verrou indisponible (fichier
inouvrable, tenu trop longtemps) : l'ecriture se fait quand meme, sans verrou, comme
avant ce lot, avec une ligne sur stderr - jamais un ban refuse ni un serveur fige."""
from __future__ import annotations

import json
import sys
from collections.abc import Callable
from contextlib import AbstractContextManager
from pathlib import Path

from omega_serv.domain.security.waf.blocklist import (
    BlocklistIndex,
    is_stronger_entry,
    parse_blocklist,
    purge_expired,
    serialize_blocklist,
)
from omega_serv.domain.security.waf.entities import BlocklistEntry
from omega_serv.infrastructure.filesystem.file_lock import exclusive_file_lock
from omega_serv.ports.clock_port import ClockPort
from omega_serv.ports.filesystem_port import FilesystemPort

# Ecrite par le service ET par la CLI sous un autre compte (pont omega-jail, RIPOSTE, `blocklist add`) : lecture et
# ecriture pour le groupe du service, quel que soit l'umask de celui qui ecrit (incident craftdark 2026-11-06).
SHARED_BLOCKLIST_MODE = 0o660


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
        self._lock_path = path.with_name(f"{path.name}.lock")
        self._last_reported_lock_problem: str | None = None
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

    def _report_lock_problem(self, reason: str, detail: str) -> None:
        """Une seule ligne par probleme DISTINCT (jamais une par ecriture) - message du
        processus serveur (journalctl), en francais (D18, comme « ERREUR blocklist illisible »)."""
        key = f"{reason}:{detail}"
        if key == self._last_reported_lock_problem:
            return
        self._last_reported_lock_problem = key
        if reason == "timeout":
            print(f"AVERTISSEMENT blocklist ecrite sans verrou entre processus : verrou {self._lock_path} "
                  f"occupe depuis plus de {detail} s", file=sys.stderr)
        else:
            print(f"AVERTISSEMENT blocklist ecrite sans verrou entre processus : verrou {self._lock_path} "
                  f"impossible a ouvrir ({detail})", file=sys.stderr)

    def _write_lock(self) -> AbstractContextManager[bool]:
        return exclusive_file_lock(self._lock_path, on_unavailable=self._report_lock_problem)

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
            current_cache = self._cache if self._cache_mtime == current_mtime else None
            if current_cache is not None and not for_write:
                return current_cache
            try:
                # En ecriture, toujours relu (lot 0) : un autre processus a pu ecrire dans la
                # meme seconde que notre derniere lecture, sans changer le mtime visible.
                raw = self._fs.read_text(self._path)
            except OSError:
                if for_write and current_cache is not None:
                    # Fichier devenu illisible mais INCHANGE depuis notre derniere lecture
                    # valide : le cache est son contenu, la reecriture reste sure (2026-10-18).
                    return list(current_cache)
                raise
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
        self._fs.atomic_write_text(self._path, content, min_mode=SHARED_BLOCKLIST_MODE)
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
        with self._write_lock():
            entries = self._load(for_write=True)
            entries = [e for e in entries if e.network != entry.network]
            entries.append(entry)
            self._save(entries)

    def add_entry_unless_stronger(self, entry: BlocklistEntry) -> bool:
        with self._write_lock():
            entries = self._load(for_write=True)
            now = self._clock.now()
            if any(e.network == entry.network and is_stronger_entry(e, entry, now) for e in entries):
                return False
            entries = [e for e in entries if e.network != entry.network]
            entries.append(entry)
            self._save(entries)
            return True

    def remove_entry(self, network: str) -> bool:
        return self.remove_entry_if(network, lambda _entry: True)

    def remove_entry_if(self, network: str, predicate: Callable[[BlocklistEntry], bool]) -> bool:
        with self._write_lock():
            entries = self._load(for_write=True)
            remaining = [e for e in entries if not (e.network == network and predicate(e))]
            if len(remaining) == len(entries):
                return False
            self._save(remaining)
            return True

    def purge_expired(self) -> int:
        with self._write_lock():
            entries = self._load(for_write=True)
            kept, removed_count = purge_expired(entries, self._clock.now())
            if removed_count:
                self._save(kept)
            return removed_count

    def count_auto_entries(self) -> int:
        return sum(1 for e in self._load() if e.source == "auto")
