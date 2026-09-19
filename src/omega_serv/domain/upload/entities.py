"""Entites metier du sous-systeme d'upload (spec §27, plan corrige - voir
OMEGA-SERV_PLAN-DETAILLE_SOUS_SYSTEME_UPLOAD.md §3).

Pas de champ authenticated_user : la protection d'une zone d'upload est
deja assuree en amont par les zones Auth existantes
(infrastructure/server/asyncio_server.py::authorize_request, appele
avant route_request()) - HttpRequest ne porte lui-meme aucun champ
authenticated_user, voir domain/http/request.py."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime


@dataclass(frozen=True)
class UploadRequest:
    zone_prefix: str
    filename: str
    content_type: str
    size: int
    source_ip: str


@dataclass(frozen=True)
class UploadResult:
    accepted: bool
    zone: str
    source_ip: str
    filename_original: str
    stored_filename: str | None
    stored_path: str | None
    size: int
    reason_rejected: str | None
    timestamp: datetime

    def to_log_fields(self) -> dict:
        return {
            "accepted": self.accepted,
            "zone": self.zone,
            "source_ip": self.source_ip,
            "filename_original": self.filename_original,
            "stored_filename": self.stored_filename,
            "size": self.size,
            "reason_rejected": self.reason_rejected,
            "timestamp": self.timestamp.isoformat(),
        }
