"""Empreinte du certificat de l'administration web (tableau de bord web, lot 6) : SHA-256 du premier certificat du
fichier PEM, celui que le serveur presente. C'est elle que le maitre epingle a l'appairage."""
from __future__ import annotations

import hashlib
import ssl
from pathlib import Path

_BEGIN = "-----BEGIN CERTIFICATE-----"
_END = "-----END CERTIFICATE-----"


def certificate_fingerprint(path: Path) -> str:
    """Leve OSError (fichier illisible) ou ValueError (aucun certificat PEM)."""
    text = path.read_text(encoding="ascii", errors="replace")
    start = text.find(_BEGIN)
    end = text.find(_END, start)
    if start < 0 or end < 0:
        raise ValueError(f"aucun certificat PEM dans {path}")
    der = ssl.PEM_cert_to_DER_cert(text[start:end + len(_END)] + "\n")
    return hashlib.sha256(der).hexdigest()
