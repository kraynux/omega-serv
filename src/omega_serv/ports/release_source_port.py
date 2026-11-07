"""Lecture de la liste des versions publiees (download/sha.txt du site) - verification manuelle des mises a jour."""
from __future__ import annotations

from typing import Protocol


class ReleaseSourcePort(Protocol):
    def fetch_sha_list(self) -> str | None:
        """Contenu de sha.txt, ou None si le site est injoignable (reseau, DNS, delai, certificat, HTTP)."""
        ...
