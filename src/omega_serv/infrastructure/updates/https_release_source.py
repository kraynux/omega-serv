# Copyright (c) 2026 kraynux - kraynux@proton.me - Licence MIT (voir fichier LICENSE)
"""Liste des versions publiees (verification MANUELLE des mises a jour, sur clic) : depuis le 2026-11-22, la Release
GitHub, puis le site kraynux, puis le site craftdark (procedure de l'auteur), lues par omega-lib
(`default_release_source` : HTTPS, certificat verifie, 5 s au plus, taille bornee ; ne leve jamais, tout echec donne
None). Auparavant : le seul download/sha.txt du site kraynux."""
from __future__ import annotations

TIMEOUT_SECONDS = 5.0
MAX_BYTES = 64 * 1024


class HttpsReleaseSource:
    """GitHub, puis le site kraynux, puis le site craftdark (omega-lib `default_release_source`) ; `base_url` et
    `from_github` : la source qui a repondu (liens d'archive et de nouveautes)."""

    def __init__(self, version: str, timeout: float = TIMEOUT_SECONDS) -> None:
        from omega_lib.infrastructure.declaration.https_release_source import default_release_source

        self._chain = default_release_source("omega-serv", version)
        self._timeout = timeout
        self.base_url = ""
        self.from_github = False

    def fetch_sha_list(self) -> str | None:
        text = self._chain.fetch_sha_list()
        self.base_url = self._chain.base_url
        self.from_github = self._chain.from_github
        return text
