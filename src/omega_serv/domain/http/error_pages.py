# Copyright (c) 2026 kraynux - kraynux@proton.me - Licence MIT (voir fichier LICENSE)
"""Page d'erreur HTML par defaut (retour utilisateur 2026-09-09 : "on
mettra des pages html d'erreur fournies de base"). Toujours utilisee
pour toute reponse d'erreur (statut >= 400) dont le corps est vide -
voir infrastructure/server/asyncio_server.py::_write_response, seul
point d'injection (jamais chaque gestionnaire individuellement).

Generation en chaine pure, meme convention que
domain/routing/dirlisting.py : jinja2 est confine a
infrastructure.exporters.html_exporter par contrat import-linter, et
une page d'erreur (rendue a chaque requete, potentiellement sous
charge) n'a pas besoin d'un moteur de template pour un contenu aussi
simple."""
from __future__ import annotations

from html import escape

from omega_serv.domain.http.status_codes import reason_phrase_for


def render_default_error_page(status: int) -> bytes:
    reason = reason_phrase_for(status) or "Erreur"
    title = escape(f"{status} {reason}")
    return (
        "<!doctype html><html lang=\"fr\"><head><meta charset=\"utf-8\">"
        f"<title>{title}</title>"
        "<style>"
        "body{font-family:ui-monospace,Consolas,monospace;background:#0a0e1a;"
        "color:#e0e0e0;display:flex;align-items:center;justify-content:center;"
        "height:100vh;margin:0}"
        ".box{text-align:center}"
        "h1{font-size:2.5rem;margin:0 0 .5rem;color:#00d4ff}"
        "p{color:#b4c2e0;margin:0}"
        "</style></head><body><div class=\"box\">"
        f"<h1>{status}</h1><p>{escape(reason)}</p>"
        "</div></body></html>"
    ).encode()
