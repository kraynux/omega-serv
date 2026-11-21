"""Echappement HTML des pages produites par le serveur (pages d'erreur, listing de repertoire).

Meme resultat que `html.escape` de la bibliotheque standard, sans charger `html.entities` (table de 2 231
entites, 0,4 Mo par processus, mesure du 2026-11-19) : le serveur n'echappe que, jamais il ne decode."""
from __future__ import annotations


def escape(text: str, quote: bool = True) -> str:
    """`&`, `<`, `>` ; avec `quote`, aussi `"` et `'` (comme `html.escape`)."""
    text = text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
    if quote:
        text = text.replace('"', "&quot;").replace("'", "&#x27;")
    return text
