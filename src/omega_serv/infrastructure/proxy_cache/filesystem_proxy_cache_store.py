"""Stockage sur disque du cache de reponses proxiees (OMEGA-SERV_PLAN-
DETAILLE_REVERSE_PROXY.md §21 : Phase 8) - `var/cache/reverse_proxy/`.

Patron DIFFERENT de `infrastructure/waf/blocklist_store.py::JsonBlocklistStore`
(un seul petit fichier JSON admin-editable, invalidation par mtime) -
plus proche de `infrastructure/persistence/backup_metadata_store.py`
(un fichier par entite dans un repertoire), adapte ici avec un
sous-repertoire PAR ZONE (`<base_dir>/<prefixe_zone_assaini>/<cle>.json`)
pour que "purger une zone" reste un simple `shutil.rmtree` du
sous-repertoire, jamais un parcours filtrant.

**`stats()`/`clear()` scannent TOUJOURS le disque directement**, jamais
l'index memoire - le TUI (processus SEPARE du serveur, verifie a la
Phase 6 §18.3) construit sa PROPRE instance de ce store pointant vers le
meme repertoire : une purge declenchee depuis le TUI est une simple
suppression de fichiers, sans jamais avoir besoin d'atteindre l'etat
memoire du serveur en cours. L'index memoire (`_index`) ne sert QUE a
l'eviction LRU, uniquement pertinent DANS le processus serveur qui sert
reellement le trafic - s'il devient partiellement perime apres une
purge externe, `get()` s'auto-corrige (`FileNotFoundError` -> retire de
l'index, jamais une erreur remontee a l'appelant)."""
from __future__ import annotations

import base64
import json
import shutil
import time
from dataclasses import dataclass
from pathlib import Path

from omega_serv.domain.routing.proxy_cache import ProxyCacheEntry
from omega_serv.ports.proxy_cache_store_port import ProxyCacheStats


def _sanitize_zone_key(zone_key: str) -> str:
    return zone_key.strip("/").replace("/", "_") or "_root_"


@dataclass
class _IndexEntry:
    path: Path
    size_bytes: int
    last_accessed_at: float


class FilesystemProxyCacheStore:
    def __init__(self, base_dir: Path, *, max_size_mb: int = 100) -> None:
        self._base_dir = base_dir
        self._max_size_bytes = max_size_mb * 1024 * 1024
        self._index: dict[tuple[str, str], _IndexEntry] = {}
        self._rebuild_index()

    def _rebuild_index(self) -> None:
        """Scan unique au demarrage (stat seule, jamais le contenu) -
        donne a l'eviction LRU une vision realiste du disque des la
        premiere requete, plutot que de ne "voir" que les entrees
        creees/touchees DANS cette execution (sous-estimerait
        l'occupation reelle apres un redemarrage sans purge)."""
        if not self._base_dir.exists():
            return
        for zone_dir in self._base_dir.iterdir():
            if not zone_dir.is_dir():
                continue
            for entry_path in zone_dir.glob("*.json"):
                try:
                    stat = entry_path.stat()
                except OSError:
                    continue
                zone_key = zone_dir.name
                cache_key = entry_path.stem
                self._index[(zone_key, cache_key)] = _IndexEntry(
                    path=entry_path, size_bytes=stat.st_size, last_accessed_at=stat.st_mtime,
                )

    def _entry_path(self, zone_key: str, cache_key: str) -> Path:
        return self._base_dir / _sanitize_zone_key(zone_key) / f"{cache_key}.json"

    def get(self, zone_key: str, cache_key: str) -> ProxyCacheEntry | None:
        path = self._entry_path(zone_key, cache_key)
        try:
            raw = path.read_bytes()
        except OSError:
            self._index.pop((zone_key, cache_key), None)
            return None
        now = time.time()
        index_entry = self._index.get((zone_key, cache_key))
        if index_entry is not None:
            index_entry.last_accessed_at = now
        else:
            self._index[(zone_key, cache_key)] = _IndexEntry(path=path, size_bytes=len(raw), last_accessed_at=now)
        return _decode_entry(raw)

    def get_variants(self, zone_key: str, primary_key: str) -> tuple[ProxyCacheEntry, ...]:
        zone_dir = self._base_dir / _sanitize_zone_key(zone_key)
        if not zone_dir.exists():
            return ()
        now = time.time()
        entries: list[ProxyCacheEntry] = []
        for path in sorted(zone_dir.glob(f"{primary_key}--*.json")):
            try:
                raw = path.read_bytes()
            except OSError:
                continue
            cache_key = path.stem
            index_entry = self._index.get((zone_key, cache_key))
            if index_entry is not None:
                index_entry.last_accessed_at = now
            entries.append(_decode_entry(raw))
        return tuple(entries)

    def set(self, zone_key: str, cache_key: str, entry: ProxyCacheEntry) -> None:
        path = self._entry_path(zone_key, cache_key)
        path.parent.mkdir(parents=True, exist_ok=True)
        raw = _encode_entry(entry)
        path.write_bytes(raw)
        now = time.time()
        self._index[(zone_key, cache_key)] = _IndexEntry(path=path, size_bytes=len(raw), last_accessed_at=now)
        self._evict_if_needed()

    def delete(self, zone_key: str, cache_key: str) -> None:
        self._entry_path(zone_key, cache_key).unlink(missing_ok=True)
        self._index.pop((zone_key, cache_key), None)

    def clear(self, *, zone_key: str | None = None) -> int:
        if zone_key is None:
            if not self._base_dir.exists():
                return 0
            count = sum(1 for _ in self._base_dir.rglob("*.json"))
            for child in self._base_dir.iterdir():
                if child.is_dir():
                    shutil.rmtree(child, ignore_errors=True)
                elif child.is_file():
                    child.unlink(missing_ok=True)
            self._index.clear()
            return count
        zone_dir = self._base_dir / _sanitize_zone_key(zone_key)
        if not zone_dir.exists():
            return 0
        count = sum(1 for _ in zone_dir.glob("*.json"))
        shutil.rmtree(zone_dir, ignore_errors=True)
        for key in [k for k in self._index if k[0] == zone_key]:
            self._index.pop(key, None)
        return count

    def stats(self, *, zone_key: str | None = None) -> ProxyCacheStats:
        base = self._base_dir / _sanitize_zone_key(zone_key) if zone_key is not None else self._base_dir
        if not base.exists():
            return ProxyCacheStats(entry_count=0, total_size_bytes=0)
        paths = base.glob("*.json") if zone_key is not None else base.rglob("*.json")
        count = 0
        total = 0
        for p in paths:
            try:
                total += p.stat().st_size
            except OSError:
                continue
            count += 1
        return ProxyCacheStats(entry_count=count, total_size_bytes=total)

    def _evict_if_needed(self) -> None:
        total = sum(e.size_bytes for e in self._index.values())
        if total <= self._max_size_bytes:
            return
        for key, index_entry in sorted(self._index.items(), key=lambda kv: kv[1].last_accessed_at):
            if total <= self._max_size_bytes:
                break
            index_entry.path.unlink(missing_ok=True)
            total -= index_entry.size_bytes
            self._index.pop(key, None)


def _encode_entry(entry: ProxyCacheEntry) -> bytes:
    payload = {
        "status_code": entry.status_code,
        "headers": list(entry.headers),
        "body": base64.b64encode(entry.body).decode("ascii"),
        "stored_at": entry.stored_at,
        "ttl_seconds": entry.ttl_seconds,
        "vary_header_names": list(entry.vary_header_names),
        "vary_header_values": list(entry.vary_header_values),
    }
    return json.dumps(payload).encode("utf-8")


def _decode_entry(raw: bytes) -> ProxyCacheEntry:
    payload = json.loads(raw.decode("utf-8"))
    return ProxyCacheEntry(
        status_code=payload["status_code"],
        headers=tuple((h[0], h[1]) for h in payload["headers"]),
        body=base64.b64decode(payload["body"]),
        stored_at=payload["stored_at"],
        ttl_seconds=payload["ttl_seconds"],
        vary_header_names=tuple(payload["vary_header_names"]),
        vary_header_values=tuple(payload["vary_header_values"]),
    )
