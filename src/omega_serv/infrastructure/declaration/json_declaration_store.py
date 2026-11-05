"""Stockage de la declaration anonyme sous var/lib/declaration/ (etat ecrit sous var/ seulement).

- declaration.json : ecrit par l'interface / la CLI (compte de l'utilisateur) ;
- envois-service.json : ecrit par le service (compte dedie).
Un fichier par ecrivain : jamais deux comptes qui reecrivent le meme fichier. Dossier cree en
2775 (groupe partage + setgid, comme les autres dossiers d'etat partages) et fichiers en 0664 :
chaque compte lit l'autre fichier. Ecriture atomique (fichier temporaire puis rename)."""
from __future__ import annotations

import contextlib
import json
import os
from datetime import datetime
from pathlib import Path

from omega_serv.domain.declaration.model import Declaration
from omega_serv.ports.declaration_port import ServiceSendLog, StoredDeclaration

DECLARATION_DIR = Path("var") / "lib" / "declaration"
_DECLARATION_FILE = "declaration.json"
_SERVICE_LOG_FILE = "envois-service.json"
_DIR_MODE = 0o2775
_FILE_MODE = 0o664


def _date(value: object) -> datetime | None:
    if not isinstance(value, str) or not value:
        return None
    try:
        return datetime.fromisoformat(value)
    except ValueError:
        return None


def _text(value: datetime | None) -> str:
    return value.isoformat() if value is not None else ""


class JsonDeclarationStore:
    def __init__(self, project_root: Path) -> None:
        self._dir = project_root / DECLARATION_DIR

    @property
    def directory(self) -> Path:
        return self._dir

    def _read(self, name: str) -> dict:
        try:
            data = json.loads((self._dir / name).read_text(encoding="utf-8"))
        except (OSError, ValueError):
            return {}
        return data if isinstance(data, dict) else {}

    def _write(self, name: str, data: dict) -> None:
        if not self._dir.is_dir():
            self._dir.mkdir(parents=True, exist_ok=True)
            with contextlib.suppress(OSError):
                os.chmod(self._dir, _DIR_MODE)
        path = self._dir / name
        tmp = path.with_name(f".{name}.{os.getpid()}.tmp")
        fd = os.open(tmp, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as handle:
                handle.write(json.dumps(data, indent=2, ensure_ascii=False) + "\n")
                handle.flush()
                os.fchmod(handle.fileno(), _FILE_MODE)
            os.replace(tmp, path)
        except BaseException:
            tmp.unlink(missing_ok=True)
            raise

    def load(self) -> StoredDeclaration | None:
        data = self._read(_DECLARATION_FILE)
        key, mode = data.get("cle"), data.get("envoi")
        declared_at = _date(data.get("declare_le"))
        if not isinstance(key, str) or not isinstance(mode, str) or declared_at is None:
            return None
        declaration = Declaration(key, mode, str(data.get("continent") or ""), str(data.get("pays") or ""))
        return StoredDeclaration(
            declaration, declared_at, _date(data.get("dernier_essai")), _date(data.get("dernier_succes")),
            str(data.get("derniere_erreur") or ""),
        )

    def save(self, stored: StoredDeclaration) -> None:
        declaration = stored.declaration
        self._write(_DECLARATION_FILE, {
            "cle": declaration.key,
            "envoi": declaration.mode,
            "continent": declaration.continent,
            "pays": declaration.country,
            "declare_le": _text(stored.declared_at),
            "dernier_essai": _text(stored.last_attempt),
            "dernier_succes": _text(stored.last_success),
            "derniere_erreur": stored.last_error,
        })

    def delete(self) -> None:
        for name in (_DECLARATION_FILE, _SERVICE_LOG_FILE):
            with contextlib.suppress(OSError):
                (self._dir / name).unlink(missing_ok=True)

    def load_service_log(self) -> ServiceSendLog:
        data = self._read(_SERVICE_LOG_FILE)
        return ServiceSendLog(_date(data.get("dernier_essai")), _date(data.get("dernier_succes")),
                              str(data.get("derniere_erreur") or ""))

    def save_service_log(self, log: ServiceSendLog) -> None:
        self._write(_SERVICE_LOG_FILE, {
            "dernier_essai": _text(log.last_attempt),
            "dernier_succes": _text(log.last_success),
            "derniere_erreur": log.last_error,
        })
