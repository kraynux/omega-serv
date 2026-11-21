# Copyright (c) 2026 kraynux - kraynux@proton.me - Licence MIT (voir fichier LICENSE)
"""Corps binaires que le WAF n'inspecte pas comme du texte (lot 11, constat F2, decision de l'auteur du 2026-11-14).

Mesure du §7 : 1 Mo d'octets aleatoires envoye derriere le WAF en mode block -> 403 a chaque envoi (motifs de
commande shell trouves par hasard dans les 64 premiers Kio), et ~80 ms d'inspection par envoi. Une image ou une archive
reelle subit le meme sort.

**Le format est reconnu au CONTENU REEL** : la signature des premiers octets (« nombre magique »), jamais l'extension
du nom de fichier ni le seul type annonce par le client. Deux conditions pour ne pas inspecter :

1. le type annonce (`Content-Type`) n'est PAS un type texte qu'une application lit comme des champs (formulaire
   urlencoded, JSON, XML, texte...) : un formulaire precede d'une fausse signature PNG reste inspecte en entier ;
2. les premiers octets portent la signature d'un format de la liste `waf.inspect.binary_formats`.

En multipart/form-data, seules les parties FICHIER (`filename=` dans Content-Disposition) dont le contenu porte une
signature connue sont retirees ; les champs texte du formulaire restent inspectes. Un corps sans signature connue
(octets aleatoires, executable, format absent de la liste) reste inspecte comme avant.

Limite assumee : un fichier valide peut contenir du texte (commentaire d'image, metadonnees) ; il n'est pas inspecte,
comme le ferait un WAF qui ignore les envois de fichiers. Le danger vise par les regles du corps (injection SQL, de
commande, XSS) suppose une application qui lit ce corps comme des champs, ce que la condition 1 couvre."""
from __future__ import annotations

import re

# nom -> signatures (decalage, octets). Formats d'envoi courants ; aucun executable.
_SIGNATURES: dict[str, tuple[tuple[int, bytes], ...]] = {
    "png": ((0, b"\x89PNG\r\n\x1a\n"),),
    "jpeg": ((0, b"\xff\xd8\xff"),),
    "gif": ((0, b"GIF87a"), (0, b"GIF89a")),
    "webp": ((0, b"RIFF"), (8, b"WEBP")),
    "tiff": ((0, b"II*\x00"), (0, b"MM\x00*")),
    "ico": ((0, b"\x00\x00\x01\x00"),),
    "mp4": ((4, b"ftyp"),),  # conteneur ISO : MP4, MOV, M4A, HEIC, AVIF
    "webm": ((0, b"\x1a\x45\xdf\xa3"),),  # WebM, MKV
    "ogg": ((0, b"OggS"),),
    "mp3": ((0, b"ID3"),),
    "wav": ((0, b"RIFF"), (8, b"WAVE")),
    "flac": ((0, b"fLaC"),),
    "pdf": ((0, b"%PDF-"),),
    "zip": ((0, b"PK\x03\x04"), (0, b"PK\x05\x06")),  # aussi DOCX, XLSX, ODT, EPUB
    "gzip": ((0, b"\x1f\x8b\x08"),),
    "bzip2": ((0, b"BZh"),),
    "xz": ((0, b"\xfd7zXZ\x00"),),
    "7z": ((0, b"7z\xbc\xaf\x27\x1c"),),
    "rar": ((0, b"Rar!\x1a\x07"),),
    "zstd": ((0, b"\x28\xb5\x2f\xfd"),),
}
_ALL_REQUIRED = frozenset({"webp", "wav"})
"""Formats dont TOUTES les signatures doivent etre presentes (RIFF + WEBP) ; les autres : une seule suffit."""

KNOWN_BINARY_FORMATS: tuple[str, ...] = tuple(_SIGNATURES)
DEFAULT_BINARY_FORMATS: tuple[str, ...] = KNOWN_BINARY_FORMATS

_TEXT_TYPES = ("application/x-www-form-urlencoded", "application/json", "application/xml", "application/javascript",
               "application/graphql", "application/x-ndjson", "application/soap+xml")


def detect_format(data: bytes, formats: tuple[str, ...]) -> str | None:
    """Nom du format de `formats` dont `data` porte la signature (premiers octets), sinon None."""
    for name in formats:
        signatures = _SIGNATURES.get(name)
        if not signatures:
            continue
        matches = [data[offset:offset + len(magic)] == magic for offset, magic in signatures]
        if all(matches) if name in _ALL_REQUIRED else any(matches):
            return name
    return None


_BINARY_TYPES = frozenset({
    "application/octet-stream", "application/pdf", "application/zip", "application/gzip", "application/x-gzip",
    "application/x-bzip2", "application/x-xz", "application/x-7z-compressed", "application/vnd.rar",
    "application/x-rar-compressed", "application/zstd", "application/x-tar", "application/epub+zip",
})
_BINARY_PREFIXES = ("image/", "audio/", "video/", "font/", "application/vnd.openxmlformats-officedocument.",
                    "application/vnd.oasis.opendocument.")
_MEDIA_TYPE_END = re.compile(r"[;,\s]")


def _media_type(content_type: str | None) -> str:
    """Type annonce, coupe comme le fait PHP (scan de securite n° 2 du 2026-11-20, F17) : au premier `;`, `,` ou
    blanc. `application/x-www-form-urlencoded,` etait lu tel quel (type inconnu, donc corps « binaire » non
    inspecte) alors que PHP en tirait un formulaire."""
    return _MEDIA_TYPE_END.split((content_type or "").strip(), maxsplit=1)[0].lower()


def _is_binary_media_type(media: str) -> bool:
    return media in _BINARY_TYPES or media.startswith(_BINARY_PREFIXES)


def is_text_media_type(content_type: str | None) -> bool:
    media = _media_type(content_type)
    return media.startswith("text/") or media in _TEXT_TYPES or media.endswith(("+json", "+xml"))


_BOUNDARY = re.compile(r'boundary="?([^";,]+)"?', re.IGNORECASE)


def _header_parameters(value: bytes) -> list[bytes]:
    """Noms des parametres d'un en-tete (`form-data; name="a"; filename="b"`), guillemets respectes. Lineaire."""
    names: list[bytes] = []
    quoted = False
    start = 0
    for index in range(len(value) + 1):
        char = value[index:index + 1]
        if char == b'"':
            quoted = not quoted
        elif (char == b";" and not quoted) or index == len(value):
            piece = value[start:index]
            if b"=" in piece:
                names.append(piece.split(b"=", 1)[0].strip().lower())
            start = index + 1
    return names


def _is_file_part(head: bytes) -> bool:
    """Partie fichier = parametre EXACT `filename` dans Content-Disposition, comme PHP (F17). Avant, une regex
    `content-disposition:[^\\r\\n]*\\bfilename\\*?=` cherchait `filename` n'importe ou sur la ligne (`xfilename=`
    dans une valeur suffisait) et revenait en arriere de facon quadratique sur une longue ligne (F18)."""
    for line in head.split(b"\r\n"):
        name, separator, value = line.partition(b":")
        if separator and name.strip().lower() == b"content-disposition":
            return b"filename" in _header_parameters(value)
    return False


def _without_binary_files(body: bytes, boundary: bytes, formats: tuple[str, ...]) -> bytes:
    """multipart/form-data : retire le contenu des parties fichier qui portent une signature connue."""
    delimiter = b"--" + boundary
    pieces = body.split(delimiter)
    kept = [pieces[0]]
    for piece in pieces[1:]:
        head_end = piece.find(b"\r\n\r\n")
        if head_end >= 0 and _is_file_part(piece[:head_end]) and detect_format(piece[head_end + 4:], formats):
            piece = piece[:head_end + 4]  # en-tetes de la partie gardes (nom du champ, nom du fichier)
        kept.append(piece)
    return delimiter.join(kept)


def inspectable_body(body: bytes, content_type: str | None, formats: tuple[str, ...]) -> bytes:
    """Partie du corps a inspecter comme du texte : vide pour un fichier binaire reconnu, le corps sans les fichiers
    binaires reconnus pour un formulaire multipart, le corps entier sinon."""
    if not formats or not body or is_text_media_type(content_type):
        return body
    media = _media_type(content_type)
    if media == "multipart/form-data":
        match = _BOUNDARY.search(content_type or "")
        return _without_binary_files(body, match.group(1).encode("latin-1"), formats) if match else body
    # F17 : corps non inspecte seulement pour un type EXPLICITEMENT binaire dont la signature correspond ; un type
    # inconnu, absent ou mal ecrit reste inspecte comme du texte.
    return b"" if _is_binary_media_type(media) and detect_format(body, formats) else body


def validate_binary_formats(value: object) -> list[str]:
    """Noms inconnus ou forme invalide (liste de noms attendue)."""
    if not isinstance(value, (list, tuple)) or not all(isinstance(item, str) for item in value):
        return ["format"]
    return [item for item in value if item not in _SIGNATURES]
