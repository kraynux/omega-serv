# Copyright (c) 2026 kraynux - kraynux@proton.me - Licence MIT (voir fichier LICENSE)
"""Encodage/decodage purs du protocole FastCGI 1.0 (spec §21 : "socket
Unix local... vers PHP-FPM"). Aucune I/O ici - la communication reseau
reelle est infrastructure/fastcgi/asyncio_fastcgi_client.py, qui
consomme ce module plutot que de dupliquer le format binaire.

Reference du protocole : FastCGI Specification v1.0 (Open Market,
1996), format stable et inchange depuis - implemente directement ici
(stdlib uniquement, aucune bibliotheque tierce)."""
from __future__ import annotations

import struct
from collections.abc import Mapping
from dataclasses import dataclass

FCGI_VERSION_1 = 1
MAX_RECORD_CONTENT_LENGTH = 65535  # champ 16 bits, borne dure du format

# Types d'enregistrement
FCGI_BEGIN_REQUEST = 1
FCGI_ABORT_REQUEST = 2
FCGI_END_REQUEST = 3
FCGI_PARAMS = 4
FCGI_STDIN = 5
FCGI_STDOUT = 6
FCGI_STDERR = 7
FCGI_DATA = 8
FCGI_GET_VALUES = 9
FCGI_GET_VALUES_RESULT = 10
FCGI_UNKNOWN_TYPE = 11

# Roles
FCGI_RESPONDER = 1

# Statuts de protocole (FCGI_EndRequestBody.protocolStatus)
FCGI_REQUEST_COMPLETE = 0
FCGI_CANT_MPX_CONN = 1
FCGI_OVERLOADED = 2
FCGI_UNKNOWN_ROLE = 3

_HEADER_STRUCT = struct.Struct("!BBHHBx")  # version, type, requestId, contentLength, paddingLength (+ reserved)


class FastCgiProtocolError(Exception):
    """Trame FastCGI malformee ou inattendue recue du process PHP-FPM."""


class FastCgiConnectionError(Exception):
    """Connexion au socket FastCGI impossible, ou coupee/expiree en
    cours d'echange - leve par infrastructure/fastcgi/, jamais par ce
    module (regroupe ici avec FastCgiProtocolError car les deux sont
    "ce qui peut echouer en parlant FastCGI", meme si l'origine reelle
    de celle-ci est l'I/O reseau)."""


@dataclass(frozen=True)
class FastCgiRecord:
    type: int
    request_id: int
    content: bytes


def encode_record(record_type: int, request_id: int, content: bytes) -> bytes:
    """Encode un enregistrement, en le decoupant en plusieurs trames si
    `content` depasse la limite du champ de longueur 16 bits (rare en
    pratique pour FCGI_PARAMS/FCGI_STDIN, mais pas interdit par le
    protocole - jamais suppose que ca n'arrivera pas)."""
    chunks = []
    offset = 0
    if not content:
        chunks.append(b"")
    while offset < len(content) or (offset == 0 and not content):
        chunk = content[offset:offset + MAX_RECORD_CONTENT_LENGTH]
        chunks.append(chunk)
        offset += len(chunk)
        if not chunk:
            break

    out = bytearray()
    for chunk in (chunks if content else [b""]):
        out += _HEADER_STRUCT.pack(FCGI_VERSION_1, record_type, request_id, len(chunk), 0)
        out += chunk
    return bytes(out)


def encode_name_value_pair(name: bytes, value: bytes) -> bytes:
    """Format de longueur FastCGI : 1 octet si < 128, sinon 4 octets
    avec le bit de poids fort du premier octet a 1 (spec FastCGI 1.0,
    "Name-Value Pairs")."""
    def encode_length(length: int) -> bytes:
        if length < 128:
            return bytes([length])
        return struct.pack("!I", length | 0x80000000)

    return encode_length(len(name)) + encode_length(len(value)) + name + value


def encode_params(params: Mapping[str, str]) -> bytes:
    out = bytearray()
    for name, value in params.items():
        out += encode_name_value_pair(name.encode("utf-8"), value.encode("utf-8"))
    return bytes(out)


def encode_begin_request(request_id: int, role: int = FCGI_RESPONDER, keep_conn: bool = False) -> bytes:
    body = struct.pack("!HB5x", role, 1 if keep_conn else 0)
    return encode_record(FCGI_BEGIN_REQUEST, request_id, body)


@dataclass(frozen=True)
class EndRequestBody:
    app_status: int
    protocol_status: int


def decode_end_request_body(content: bytes) -> EndRequestBody:
    if len(content) < 8:
        raise FastCgiProtocolError(f"FCGI_END_REQUEST trop court : {len(content)} octets")
    app_status, protocol_status = struct.unpack("!IB3x", content[:8])
    return EndRequestBody(app_status=app_status, protocol_status=protocol_status)


HEADER_SIZE = 8


@dataclass(frozen=True)
class DecodedHeader:
    type: int
    request_id: int
    content_length: int
    padding_length: int


def decode_record_header(header: bytes) -> DecodedHeader:
    """Decode les 8 octets d'en-tete deja lus par l'appelant (l'I/O
    reelle - combien d'octets lire ensuite pour le contenu/padding -
    est une responsabilite d'infrastructure/fastcgi/asyncio_fastcgi_client.py,
    qui orchestre la lecture incrementale ; ce module reste pur)."""
    if len(header) != HEADER_SIZE:
        raise FastCgiProtocolError(f"en-tete FastCGI incomplet : {len(header)} octets")
    version, record_type, request_id, content_length, padding_length = _HEADER_STRUCT.unpack(header)
    if version != FCGI_VERSION_1:
        raise FastCgiProtocolError(f"version FastCGI non supportee : {version}")
    return DecodedHeader(type=record_type, request_id=request_id, content_length=content_length, padding_length=padding_length)


@dataclass(frozen=True)
class CgiResponse:
    """Reponse CGI classique decodee depuis FCGI_STDOUT (spec §21 :
    PHP-FPM repond au format CGI - en-tetes `Nom: Valeur` termines par
    une ligne vide, puis le corps)."""
    status_code: int
    headers: tuple[tuple[str, str], ...]
    body: bytes


def parse_cgi_response(raw: bytes) -> CgiResponse:
    """Le header `Status: 200 OK` (optionnel) fixe le code - absent,
    200 est le defaut CGI standard. Un en-tete `Status` malforme est
    traite comme absent plutot que de faire echouer toute la reponse -
    un script PHP legerement non conforme ne doit pas empecher
    l'affichage de sa sortie."""
    separator = b"\r\n\r\n"
    idx = raw.find(separator)
    if idx == -1:
        separator = b"\n\n"
        idx = raw.find(separator)
    if idx == -1:
        return CgiResponse(status_code=200, headers=(), body=raw)

    header_block = raw[:idx].decode("latin-1", errors="replace")
    body = raw[idx + len(separator):]

    status_code = 200
    headers: list[tuple[str, str]] = []
    for line in header_block.split("\n"):
        line = line.strip("\r")
        if not line or ":" not in line:
            continue
        name, _, value = line.partition(":")
        name = name.strip()
        value = value.strip()
        if name.lower() == "status":
            try:
                status_code = int(value.split(" ", 1)[0])
            except ValueError:
                pass
            continue
        headers.append((name, value))

    return CgiResponse(status_code=status_code, headers=tuple(headers), body=body)
