"""Cas d'usage « Verifier les mises a jour » (Guide d'aide → Contact et support, et `omega-serv version --check`)."""
from __future__ import annotations

from omega_serv.domain.updates.release_check import UpdateCheck, compare_with_published
from omega_serv.ports.release_source_port import ReleaseSourcePort


def check_for_update(source: ReleaseSourcePort, installed: str) -> UpdateCheck:
    return compare_with_published(installed, source.fetch_sha_list())
