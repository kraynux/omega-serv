"""Appels d'un maitre vers ses instances suivies, et sondes HTTP (tableau de bord web, lot 6 ; plan §7.3 a §7.5).

Empreinte epinglee : le certificat presente par l'instance est compare a l'empreinte enregistree a l'appairage AVANT
d'envoyer quoi que ce soit (le jeton ne part jamais vers un certificat inconnu). Un certificat auto-signe suffit :
la confiance vient de l'empreinte, pas d'une autorite. HTTP seulement vers la boucle locale (empreinte vide).
Reponses bornees (4 Mo), delais bornes (4 s), une connexion par appel (Connection: close)."""
from __future__ import annotations

import asyncio
import contextlib
import hashlib
import json
import os
import ssl
import time
from pathlib import Path
from urllib.parse import urlsplit

from omega_serv.ports.admin_remote_port import ProbeReply, RemoteReply

TIMEOUT_SECONDS = 4.0
MAX_RESPONSE_BYTES = 4 * 1024 * 1024
PROBE_READ_BYTES = 8192


def _client_context() -> ssl.SSLContext:
    context = ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
    context.check_hostname = False
    context.verify_mode = ssl.CERT_NONE  # la confiance vient de l'empreinte epinglee, verifiee juste apres
    context.minimum_version = ssl.TLSVersion.TLSv1_2
    return context


def _seen_fingerprint(writer: asyncio.StreamWriter) -> str:
    ssl_object = writer.get_extra_info("ssl_object")
    if ssl_object is None:
        return ""
    certificate = ssl_object.getpeercert(binary_form=True)
    return hashlib.sha256(certificate).hexdigest() if certificate else ""


async def _close(writer: asyncio.StreamWriter) -> None:
    writer.close()
    with contextlib.suppress(Exception):
        await asyncio.wait_for(writer.wait_closed(), 1.0)


async def _read_all(reader: asyncio.StreamReader, limit: int) -> bytes:
    chunks: list[bytes] = []
    size = 0
    while True:
        chunk = await reader.read(65536)
        if not chunk:
            return b"".join(chunks)
        size += len(chunk)
        if size > limit:
            raise ValueError("reponse trop grande")
        chunks.append(chunk)


def _status_of(head: bytes) -> int:
    parts = head.split(b"\r\n", 1)[0].split(b" ", 2)
    if len(parts) < 2 or not parts[0].startswith(b"HTTP/") or not parts[1].isdigit():
        raise ValueError("ligne de statut")
    return int(parts[1])


_SYSTEM_UID_MAX = 999
"""Comptes systeme (useradd --system : les comptes de service d'omega-serv en font partie)."""


def _loopback_listener_uids(port: int) -> set[int] | None:
    """Comptes proprietaires des sockets en ecoute sur `port` (boucle locale ou toutes adresses), lus dans
    /proc/net/tcp et tcp6 ; None si illisible (systeme sans /proc)."""
    uids: set[int] = set()
    wanted = f"{port:04X}"
    found_table = False
    for table in ("/proc/net/tcp", "/proc/net/tcp6"):
        try:
            with open(table, encoding="ascii") as handle:
                lines = handle.read().splitlines()[1:]
        except OSError:
            continue
        found_table = True
        for line in lines:
            fields = line.split()
            if len(fields) < 8 or fields[3] != "0A":  # 0A = LISTEN
                continue
            address, _sep, local_port = fields[1].partition(":")
            if local_port != wanted:
                continue
            loopback = address in ("0100007F", "00000000", "00000000000000000000000001000000",
                                   "00000000000000000000000000000000", "0000000000000000FFFF00000100007F")
            if loopback:
                uids.add(int(fields[7]))
    return uids if found_table else None


def _trusted_loopback_listener(port: int) -> bool:
    """Scan de securite n° 2 (2026-11-20, F38) : une instance suivie sur la meme machine, sans TLS, recevait le
    jeton du maitre en clair, sans que rien ne prouve qui ecoutait le port - un processus local quelconque qui
    prenait le port pendant un rechargement du suiveur recuperait le jeton (droits du maitre). Le jeton n'est
    envoye que si le port est tenu par root, un compte systeme (compte de service), le compte de ce processus ou
    le proprietaire de l'installation ; jamais par un autre utilisateur de la machine."""
    uids = _loopback_listener_uids(port)
    if not uids:
        return False
    trusted = {0, os.geteuid()}
    with contextlib.suppress(OSError):
        trusted.add(os.stat(Path(__file__).resolve().parents[4]).st_uid)
    return all(uid in trusted or uid <= _SYSTEM_UID_MAX for uid in uids)


class RemoteInstanceClient:
    def __init__(self, timeout: float = TIMEOUT_SECONDS) -> None:
        self._timeout = timeout

    async def call(self, address: str, port: int, *, use_tls: bool, fingerprint: str | None, method: str,
                   path: str, token: str = "", body: object = None, account: str = "") -> RemoteReply:
        """`fingerprint` None : accepte le certificat vu et le rend (appairage seulement)."""
        try:
            reader, writer = await asyncio.wait_for(
                asyncio.open_connection(address, port, ssl=_client_context() if use_tls else None), self._timeout)
        except TimeoutError:
            return RemoteReply(0, error="delai")
        except ssl.SSLError:
            return RemoteReply(0, error="tls")
        except OSError:
            return RemoteReply(0, error="connexion")
        try:
            seen = _seen_fingerprint(writer)
            if fingerprint is not None and seen != fingerprint:
                return RemoteReply(0, fingerprint=seen, error="empreinte")
            if token and not use_tls and not _trusted_loopback_listener(port):
                return RemoteReply(0, error="ecoute")
            content = json.dumps(body).encode() if body is not None else b""
            host = f"[{address}]" if ":" in address else address
            lines = [f"{method} {path} HTTP/1.1", f"Host: {host}:{port}", "Accept: application/json",
                     "Connection: close", f"Content-Length: {len(content)}"]
            if content:
                lines.append("Content-Type: application/json")
            if token:
                lines.append(f"Authorization: Bearer {token}")
            writer.write(("\r\n".join(lines) + "\r\n\r\n").encode("latin-1") + content)
            await asyncio.wait_for(writer.drain(), self._timeout)
            raw = await asyncio.wait_for(_read_all(reader, MAX_RESPONSE_BYTES), self._timeout)
            head, _sep, payload_bytes = raw.partition(b"\r\n\r\n")
            status = _status_of(head)
            try:
                payload = json.loads(payload_bytes.decode("utf-8")) if payload_bytes else None
            except (UnicodeDecodeError, ValueError):
                payload = None
            return RemoteReply(status, payload, seen)
        except TimeoutError:
            return RemoteReply(0, error="delai")
        except ssl.SSLError:
            return RemoteReply(0, error="tls")
        except (OSError, ValueError):
            return RemoteReply(0, error="reponse")
        finally:
            await _close(writer)

    async def probe(self, url: str) -> ProbeReply:
        """Sonde de sante d'un backend qui n'est pas omega-serv (§7.5) : statut et temps de reponse, rien d'autre."""
        parts = urlsplit(url)
        if parts.scheme not in ("http", "https") or not parts.hostname:
            return ProbeReply(0, 0, "url")
        port = parts.port or (443 if parts.scheme == "https" else 80)
        started = time.monotonic()
        try:
            reader, writer = await asyncio.wait_for(asyncio.open_connection(
                parts.hostname, port, ssl=_client_context() if parts.scheme == "https" else None), self._timeout)
        except TimeoutError:
            return ProbeReply(0, 0, "delai")
        except (OSError, ssl.SSLError):
            return ProbeReply(0, 0, "connexion")
        try:
            host = f"[{parts.hostname}]" if ":" in parts.hostname else parts.hostname
            target = (parts.path or "/") + (f"?{parts.query}" if parts.query else "")
            writer.write(f"GET {target} HTTP/1.1\r\nHost: {host}\r\nUser-Agent: omega-serv-sonde\r\n"
                         f"Connection: close\r\n\r\n".encode("latin-1"))
            await asyncio.wait_for(writer.drain(), self._timeout)
            head = await asyncio.wait_for(reader.read(PROBE_READ_BYTES), self._timeout)
            status = _status_of(head)
            return ProbeReply(status, int((time.monotonic() - started) * 1000))
        except TimeoutError:
            return ProbeReply(0, 0, "delai")
        except (OSError, ssl.SSLError, ValueError, UnicodeError):
            return ProbeReply(0, 0, "reponse")
        finally:
            await _close(writer)
