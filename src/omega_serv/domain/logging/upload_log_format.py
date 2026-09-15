# Copyright (c) 2026 kraynux - kraynux@proton.me - Licence MIT (voir fichier LICENSE)
"""Formatage pur des lignes de journalisation d'upload (plan corrige,
voir OMEGA-SERV_PLAN-DETAILLE_SOUS_SYSTEME_UPLOAD.md §10) - JSON Lines,
un enregistrement par tentative d'upload (acceptee ou refusee). Aucune
I/O ici (meme patron que domain/logging/waf_alert_format.py) -
l'ecriture reelle passe par LoggerPort.

Jamais de contenu de fichier journalise, seulement le nom original
(deja filtre par domain/upload/validation.py::validate_filename, liste
blanche stricte) et les metadonnees de la tentative."""
from __future__ import annotations

import json

from omega_serv.domain.logging.access_log_format import sanitize_log_field
from omega_serv.domain.upload.entities import UploadResult


def format_upload_log_line(result: UploadResult) -> str:
    record = result.to_log_fields()
    record["zone"] = sanitize_log_field(record["zone"], 128)
    record["source_ip"] = sanitize_log_field(record["source_ip"], 64)
    record["filename_original"] = sanitize_log_field(record["filename_original"], 255)
    if record["reason_rejected"] is not None:
        record["reason_rejected"] = sanitize_log_field(record["reason_rejected"], 256)
    return json.dumps(record, ensure_ascii=False)
