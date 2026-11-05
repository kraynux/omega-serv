"""Envoi d'une declaration anonyme : un POST HTTPS, bibliotheque standard seulement (urllib).

Certificat verifie (contexte par defaut), 5 s au plus pour la connexion et la reponse. Ne leve
jamais : tout echec devient un SendOutcome. Le delai d'urllib ne couvre pas la resolution DNS :
c'est pourquoi l'envoi quotidien tourne dans un processus a part (jamais dans le serveur)."""
from __future__ import annotations

import json
import urllib.error
import urllib.request

from omega_serv.domain.declaration.model import RECEPTION_URL
from omega_serv.ports.declaration_port import SendOutcome

TIMEOUT_SECONDS = 5.0


class HttpsDeclarationSender:
    def __init__(self, version: str, url: str = RECEPTION_URL, timeout: float = TIMEOUT_SECONDS) -> None:
        self._version = version
        self._url = url
        self._timeout = timeout

    def send(self, payload: dict[str, object]) -> SendOutcome:
        body = json.dumps(payload, separators=(",", ":")).encode("utf-8")
        request = urllib.request.Request(
            self._url, data=body, method="POST",
            headers={"Content-Type": "application/json", "User-Agent": f"omega-serv/{self._version}"},
        )
        try:
            with urllib.request.urlopen(request, timeout=self._timeout) as response:
                status = response.status
        except urllib.error.HTTPError as error:
            return SendOutcome(False, f"http-{error.code}")
        except (urllib.error.URLError, OSError, ValueError):
            return SendOutcome(False, "unreachable")
        if 200 <= status < 300:
            return SendOutcome(True)
        return SendOutcome(False, f"http-{status}")
