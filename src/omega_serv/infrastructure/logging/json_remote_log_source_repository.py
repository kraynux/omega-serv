"""Implementation JSON du port RemoteLogSourceRepositoryPort
(OMEGA-SERV_ETUDE-FAISABILITE_LOGS_DISTANTS.md, 2026-10-15)."""
from __future__ import annotations

import json
from pathlib import Path

from omega_serv.domain.logs.remote_source import RemoteLogSource


class JsonRemoteLogSourceRepository:
    """Deduplique par `label` - un label existant est remplace, jamais
    duplique. Aucun secret n'est jamais ecrit ici : `identity_file`
    n'est qu'un chemin de reference, jamais le contenu d'une cle."""

    def __init__(self, path: Path) -> None:
        self._path = path

    def list_all(self) -> list[RemoteLogSource]:
        if not self._path.exists():
            return []
        raw = json.loads(self._path.read_text(encoding="utf-8"))
        return [
            RemoteLogSource(
                label=entry["label"],
                host=entry["host"],
                remote_path=entry["remote_path"],
                user=entry.get("user"),
                port=entry.get("port"),
                identity_file=entry.get("identity_file"),
            )
            for entry in raw
        ]

    def add(self, source: RemoteLogSource) -> None:
        sources = {s.label: s for s in self.list_all()}
        sources[source.label] = source
        self._write(list(sources.values()))

    def remove(self, label: str) -> None:
        sources = [s for s in self.list_all() if s.label != label]
        self._write(sources)

    def _write(self, sources: list[RemoteLogSource]) -> None:
        self._path.parent.mkdir(parents=True, exist_ok=True)
        payload = [
            {
                "label": s.label, "host": s.host, "remote_path": s.remote_path,
                "user": s.user, "port": s.port, "identity_file": s.identity_file,
            }
            for s in sources
        ]
        self._path.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
