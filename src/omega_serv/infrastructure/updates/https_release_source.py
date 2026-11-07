"""Lecture HTTPS de download/sha.txt (verification manuelle des mises a jour, 2026-11-07) : un GET, bibliotheque
standard seulement (urllib), meme modele que l'envoi de la declaration anonyme
(infrastructure/declaration/https_sender.py). Certificat verifie, 5 s au plus, 64 Kio lus au plus ; ne leve
jamais : tout echec donne None. Rien n'est envoye d'autre que la requete elle-meme (User-Agent avec la version)."""
from __future__ import annotations

import urllib.error
import urllib.request

from omega_serv.domain.updates.release_check import SHA_LIST_URL

TIMEOUT_SECONDS = 5.0
MAX_BYTES = 64 * 1024


class HttpsReleaseSource:
    def __init__(self, version: str, url: str = SHA_LIST_URL, timeout: float = TIMEOUT_SECONDS) -> None:
        self._version = version
        self._url = url
        self._timeout = timeout

    def fetch_sha_list(self) -> str | None:
        request = urllib.request.Request(self._url, headers={"User-Agent": f"omega-serv/{self._version}"})
        try:
            with urllib.request.urlopen(request, timeout=self._timeout) as response:
                if not 200 <= response.status < 300:
                    return None
                body: bytes = response.read(MAX_BYTES)
                return body.decode("utf-8", errors="replace")
        except (urllib.error.URLError, OSError, ValueError):
            return None
