"""Configuration des zones d'upload (spec §27, plan corrige - voir
OMEGA-SERV_PLAN-DETAILLE_SOUS_SYSTEME_UPLOAD.md §7). Modele de zones en
liste (comme aliases/redirects), resolues via le meme
domain/routing/zone_resolver.py::Zone/resolve_zone que le reste du
routage - pas un mecanisme de correspondance de prefixe dedie."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class UploadPolicy:
    max_file_size_bytes: int = 10_485_760
    allowed_extensions: tuple[str, ...] = ()
    allowed_content_types: tuple[str, ...] = ()
    max_files_per_zone: int | None = None
    max_total_bytes_per_zone: int | None = None

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> UploadPolicy:
        defaults = cls()
        max_files = data.get("max_files_per_zone", defaults.max_files_per_zone)
        max_total = data.get("max_total_bytes_per_zone", defaults.max_total_bytes_per_zone)
        return cls(
            max_file_size_bytes=int(data.get("max_file_size_bytes", defaults.max_file_size_bytes)),
            allowed_extensions=tuple(data.get("allowed_extensions", defaults.allowed_extensions)),
            allowed_content_types=tuple(data.get("allowed_content_types", defaults.allowed_content_types)),
            max_files_per_zone=int(max_files) if max_files is not None else None,
            max_total_bytes_per_zone=int(max_total) if max_total is not None else None,
        )


@dataclass(frozen=True)
class UploadZoneRule:
    url_prefix: str
    storage_path: str
    policy: UploadPolicy


def parse_upload_zone_rules(raw_list: list[dict[str, Any]]) -> list[UploadZoneRule]:
    return [
        UploadZoneRule(
            url_prefix=item["url_prefix"],
            storage_path=item["storage_path"],
            policy=UploadPolicy.from_dict(item.get("policy", {})),
        )
        for item in raw_list
    ]


def validate_upload_zone_rule(rule: UploadZoneRule) -> str | None:
    """Validation structurelle pure (pas d'I/O) - la porte
    "max_file_size_bytes <= server.max_request_size" exige la
    configuration serveur complete et vit dans
    application/config/validate_config.py (meme separation que
    validate_fastcgi_config_structure vs _validate_fastcgi_environment)."""
    if not rule.url_prefix.startswith("/"):
        return f"url_prefix doit commencer par '/' : {rule.url_prefix!r}"

    if not rule.storage_path:
        return "storage_path ne peut pas etre vide"
    if rule.storage_path.startswith("/"):
        return f"storage_path doit etre relatif a la racine du projet : {rule.storage_path!r}"
    if "\x00" in rule.storage_path:
        return "storage_path contient un caractere NUL"
    segments = rule.storage_path.replace("\\", "/").split("/")
    if ".." in segments:
        return f"storage_path ne peut pas remonter au-dessus de la racine ('..') : {rule.storage_path!r}"

    if rule.policy.max_file_size_bytes <= 0:
        return "policy.max_file_size_bytes doit etre strictement positif"
    if rule.policy.max_files_per_zone is not None and rule.policy.max_files_per_zone <= 0:
        return "policy.max_files_per_zone doit etre strictement positif s'il est defini"
    if rule.policy.max_total_bytes_per_zone is not None and rule.policy.max_total_bytes_per_zone <= 0:
        return "policy.max_total_bytes_per_zone doit etre strictement positif s'il est defini"

    return None
