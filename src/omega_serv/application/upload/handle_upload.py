"""Cas d'usage : traiter une requete d'upload vers une zone deja
resolue (spec §27, plan corrige - voir
OMEGA-SERV_PLAN-DETAILLE_SOUS_SYSTEME_UPLOAD.md).

Pas de streaming (decision V1 explicite, plan corrige §9) : `body` est
deja le corps entier deja lu par infrastructure/server/http_parser.py,
borne par server.max_request_size - jamais un flux incremental."""
from __future__ import annotations

import json
from pathlib import Path

from omega_serv.domain.http.request import HttpRequest
from omega_serv.domain.http.response import HttpResponse
from omega_serv.domain.logging.upload_log_format import format_upload_log_line
from omega_serv.domain.routing.upload_zone import UploadZoneRule
from omega_serv.domain.routing.zone_resolver import Zone
from omega_serv.domain.upload.entities import UploadRequest, UploadResult
from omega_serv.domain.upload.multipart import extract_boundary, parse_multipart
from omega_serv.domain.upload.validation import validate_upload
from omega_serv.ports.clock_port import ClockPort
from omega_serv.ports.logger_port import LoggerPort
from omega_serv.ports.upload_storage_port import UploadStoragePort


def _error_response(status: int, message: str) -> HttpResponse:
    response = HttpResponse.empty(status)
    response.set_header("Content-Type", "application/json")
    response.body = json.dumps({"error": message}).encode()
    return response


def _log(result: UploadResult, logger: LoggerPort | None, log_path: Path | None) -> None:
    if logger is not None and log_path is not None:
        logger.append_line(log_path, format_upload_log_line(result))


def handle_upload(
    request: HttpRequest,
    zone: Zone[UploadZoneRule],
    body: bytes,
    storage: UploadStoragePort,
    clock: ClockPort,
    logger: LoggerPort | None = None,
    upload_log_path: Path | None = None,
) -> HttpResponse:
    rule = zone.data
    now = clock.now()

    content_type_header = request.header("content-type", "") or ""
    boundary = extract_boundary(content_type_header)
    if boundary is None:
        return _error_response(400, "Content-Type multipart/form-data avec boundary attendu.")

    file_part = next((p for p in parse_multipart(body, boundary) if p.filename), None)
    if file_part is None:
        return _error_response(400, "aucun fichier trouve dans le corps multipart.")

    upload_request = UploadRequest(
        zone_prefix=zone.path_prefix,
        filename=file_part.filename or "",
        content_type=file_part.field_content_type,
        size=len(file_part.content),
        source_ip=request.remote_ip,
    )

    error = validate_upload(upload_request, rule.policy)
    if error is not None:
        _log(UploadResult(
            accepted=False, zone=zone.path_prefix, source_ip=upload_request.source_ip,
            filename_original=upload_request.filename, stored_filename=None, stored_path=None,
            size=upload_request.size, reason_rejected=error, timestamp=now,
        ), logger, upload_log_path)
        return _error_response(400, error)

    current_count, current_total = storage.count_and_size(rule.storage_path)
    if rule.policy.max_files_per_zone is not None and current_count >= rule.policy.max_files_per_zone:
        quota_error = "quota de nombre de fichiers atteint pour cette zone"
        _log(UploadResult(
            accepted=False, zone=zone.path_prefix, source_ip=upload_request.source_ip,
            filename_original=upload_request.filename, stored_filename=None, stored_path=None,
            size=upload_request.size, reason_rejected=quota_error, timestamp=now,
        ), logger, upload_log_path)
        return _error_response(507, quota_error)

    if rule.policy.max_total_bytes_per_zone is not None and current_total + upload_request.size > rule.policy.max_total_bytes_per_zone:
        quota_error = "quota de volume total atteint pour cette zone"
        _log(UploadResult(
            accepted=False, zone=zone.path_prefix, source_ip=upload_request.source_ip,
            filename_original=upload_request.filename, stored_filename=None, stored_path=None,
            size=upload_request.size, reason_rejected=quota_error, timestamp=now,
        ), logger, upload_log_path)
        return _error_response(507, quota_error)

    target = storage.store(upload_request, rule.storage_path, file_part.content)

    _log(UploadResult(
        accepted=True, zone=zone.path_prefix, source_ip=upload_request.source_ip,
        filename_original=upload_request.filename, stored_filename=target.name, stored_path=str(target),
        size=upload_request.size, reason_rejected=None, timestamp=now,
    ), logger, upload_log_path)

    response = HttpResponse.empty(201)
    response.set_header("Content-Type", "application/json")
    response.body = json.dumps({"filename": target.name, "size": upload_request.size}).encode()
    return response
