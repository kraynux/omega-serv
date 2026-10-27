"""Fichiers statiques pre-compresses (OMEGA-SERV_ETUDE_PERFORMANCE.md, priorite 5).

Si le navigateur accepte `br` ou `gzip` et qu'un `fichier.br` / `fichier.gz` existe a cote de
l'original (cree par l'administrateur : `brotli -k`, `gzip -k`), c'est lui qui est envoye avec
`Content-Encoding` - jamais de compression a la volee. Limite aux types texte : les images,
videos et archives sont deja compressees, aucune verification supplementaire pour elles.

Fonctions pures : aucune I/O."""
from __future__ import annotations

COMPRESSIBLE_EXTENSIONS: frozenset[str] = frozenset({
    ".html", ".htm", ".css", ".js", ".mjs", ".json", ".map", ".svg", ".xml", ".txt", ".md", ".csv",
})

# Ordre de preference du serveur, a qualite egale : brotli compresse mieux le texte.
ENCODING_SUFFIXES: tuple[tuple[str, str], ...] = (("br", ".br"), ("gzip", ".gz"))


def is_compressible(filename: str) -> bool:
    dot_index = filename.rfind(".")
    return dot_index != -1 and filename[dot_index:].lower() in COMPRESSIBLE_EXTENSIONS


def _quality(parameters: list[str]) -> float:
    for parameter in parameters:
        name, _, value = parameter.strip().partition("=")
        if name.strip().lower() == "q":
            try:
                return float(value)
            except ValueError:
                return 0.0
    return 1.0


def preferred_encodings(accept_encoding: str | None) -> list[tuple[str, str]]:
    """(codage, suffixe) acceptes par le navigateur (q > 0), du plus au moins voulu ;
    `*` couvre les codages non cites explicitement (RFC 9110 §12.5.3)."""
    if not accept_encoding:
        return []
    qualities: dict[str, float] = {}
    for item in accept_encoding.split(","):
        token, *parameters = item.split(";")
        name = token.strip().lower()
        if name:
            qualities[name] = _quality(parameters)
    wildcard = qualities.get("*", 0.0)
    ranked = [
        (qualities.get(encoding, wildcard), -position, encoding, suffix)
        for position, (encoding, suffix) in enumerate(ENCODING_SUFFIXES)
    ]
    return [(encoding, suffix) for quality, _, encoding, suffix in sorted(ranked, reverse=True) if quality > 0]
