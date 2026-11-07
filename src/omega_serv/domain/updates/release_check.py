"""Verification d'une mise a jour (decision utilisateur 2026-11-07 : bouton manuel, aucune connexion sans clic) -
pure, aucune I/O.

Source : `download/sha.txt` du site, qui liste chaque archive publiee (`<empreinte>  omega-serv-2.6.0.tar.gz`).
La version la plus haute est comparee a celle de pyproject.toml : rien n'est envoye, seule cette page est lue."""
from __future__ import annotations

import re
from dataclasses import dataclass
from enum import Enum

DOWNLOAD_BASE_URL = "https://kraynux.snake-mackarel.ts.net/omega-serv/download/"
SHA_LIST_URL = DOWNLOAD_BASE_URL + "sha.txt"

_ARCHIVE = re.compile(r"omega-serv-(\d+(?:\.\d+){1,3})\.tar\.gz")


class UpdateStatus(Enum):
    UP_TO_DATE = "up_to_date"
    UPDATE_AVAILABLE = "update_available"
    AHEAD = "ahead"
    """Version installee plus recente que la derniere publiee (developpement, version en cours)."""
    UNKNOWN = "unknown"
    """Liste illisible ou version installee non reconnue."""


@dataclass(frozen=True)
class UpdateCheck:
    status: UpdateStatus
    installed: str
    latest: str = ""

    @property
    def archive_url(self) -> str:
        return f"{DOWNLOAD_BASE_URL}omega-serv-{self.latest}.tar.gz" if self.latest else ""

    @property
    def notes_url(self) -> str:
        return f"{DOWNLOAD_BASE_URL}omega-serv-{self.latest}-nouveautes.txt" if self.latest else ""


def version_key(version: str) -> tuple[int, ...] | None:
    """« 2.6.0 » -> (2, 6, 0) ; None si ce n'est pas une version numerique."""
    parts = version.strip().split(".")
    if not parts or not all(part.isdigit() for part in parts):
        return None
    return tuple(int(part) for part in parts)


def published_versions(sha_list: str) -> list[str]:
    """Versions des archives citees dans sha.txt, sans doublon, de la plus haute a la plus basse."""
    found = {match.group(1) for match in _ARCHIVE.finditer(sha_list)}
    return sorted(found, key=lambda version: version_key(version) or (), reverse=True)


def compare_with_published(installed: str, sha_list: str | None) -> UpdateCheck:
    installed_key = version_key(installed)
    versions = published_versions(sha_list) if sha_list else []
    if installed_key is None or not versions:
        return UpdateCheck(UpdateStatus.UNKNOWN, installed)
    latest = versions[0]
    latest_key = version_key(latest) or ()
    if latest_key > installed_key:
        return UpdateCheck(UpdateStatus.UPDATE_AVAILABLE, installed, latest)
    if latest_key < installed_key:
        return UpdateCheck(UpdateStatus.AHEAD, installed, latest)
    return UpdateCheck(UpdateStatus.UP_TO_DATE, installed, latest)
