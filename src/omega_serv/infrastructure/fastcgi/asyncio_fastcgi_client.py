# Copyright (c) 2026 kraynux - kraynux@proton.me - Licence MIT (voir fichier LICENSE)
"""Implementation reelle de FastCgiClientPort - socket Unix asyncio
(spec §21.2 : "utiliser de preference un socket Unix local"). Une
connexion neuve par requete, fermee a la fin (`keep_conn=False`) -
pas de pool de connexions en V1, PHP-FPM gere deja son propre pool de
process workers cote serveur."""
from __future__ import annotations

import asyncio
import contextlib
from collections.abc import Mapping
from pathlib import Path

from omega_serv.domain.http.fastcgi_protocol import (
    FCGI_END_REQUEST,
    FCGI_PARAMS,
    FCGI_RESPONDER,
    FCGI_STDERR,
    FCGI_STDIN,
    FCGI_STDOUT,
    HEADER_SIZE,
    DecodedHeader,
    FastCgiConnectionError,
    FastCgiProtocolError,
    decode_end_request_body,
    decode_record_header,
    encode_begin_request,
    encode_params,
    encode_record,
    parse_cgi_response,
)
from omega_serv.ports.fastcgi_client_port import FastCgiResult

_REQUEST_ID = 1  # une seule requete par connexion (pas de multiplexage FastCGI en V1)


class AsyncioFastCgiClient:
    async def send_request(
        self,
        socket_path: Path,
        env: Mapping[str, str],
        body: bytes,
        connect_timeout: float,
        read_timeout: float,
    ) -> FastCgiResult:
        try:
            reader, writer = await asyncio.wait_for(
                asyncio.open_unix_connection(path=str(socket_path)), timeout=connect_timeout,
            )
        except (OSError, asyncio.TimeoutError) as e:
            raise FastCgiConnectionError(f"connexion au socket FastCGI impossible ({socket_path}) : {e}") from e

        try:
            writer.write(encode_begin_request(_REQUEST_ID, role=FCGI_RESPONDER, keep_conn=False))
            writer.write(encode_record(FCGI_PARAMS, _REQUEST_ID, encode_params(env)))
            writer.write(encode_record(FCGI_PARAMS, _REQUEST_ID, b""))  # terminateur FCGI_PARAMS
            if body:
                writer.write(encode_record(FCGI_STDIN, _REQUEST_ID, body))
            writer.write(encode_record(FCGI_STDIN, _REQUEST_ID, b""))  # terminateur FCGI_STDIN
            await writer.drain()

            stdout = bytearray()
            stderr = bytearray()
            end_body = None

            async def _read_one_record() -> tuple[DecodedHeader, bytes]:
                header_bytes = await reader.readexactly(HEADER_SIZE)
                header = decode_record_header(header_bytes)
                content = await reader.readexactly(header.content_length) if header.content_length else b""
                if header.padding_length:
                    await reader.readexactly(header.padding_length)
                return header, content

            while end_body is None:
                header, content = await asyncio.wait_for(_read_one_record(), timeout=read_timeout)
                if header.type == FCGI_STDOUT:
                    stdout += content
                elif header.type == FCGI_STDERR:
                    stderr += content
                elif header.type == FCGI_END_REQUEST:
                    end_body = decode_end_request_body(content)
                # tout autre type de trame est ignore (defensif - aucune
                # trame FCGI_GET_VALUES envoyee, donc aucune reponse de
                # gestion n'est attendue en retour).

        except (asyncio.IncompleteReadError, asyncio.TimeoutError, FastCgiProtocolError, OSError) as e:
            raise FastCgiConnectionError(f"erreur de communication FastCGI ({socket_path}) : {e}") from e
        finally:
            writer.close()
            with contextlib.suppress(Exception):
                await writer.wait_closed()

        cgi_response = parse_cgi_response(bytes(stdout))
        return FastCgiResult(
            status_code=cgi_response.status_code,
            headers=cgi_response.headers,
            body=cgi_response.body,
            stderr=bytes(stderr),
        )
