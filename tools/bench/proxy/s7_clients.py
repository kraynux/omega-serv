# Copyright (c) 2026 kraynux - kraynux@proton.me - Licence MIT (voir fichier LICENSE)
"""Clients particuliers de la mesure du §7 (plan proxy natif v2, lot 11) - outil de developpement, sans dependance.

  s7_clients.py slowread  PORT CHEMIN N OCTETS_PAR_S       N clients qui lisent lentement (petit tampon de reception)
  s7_clients.py slowhead  PORT N                           N clients qui envoient leur tete au compte-gouttes
  s7_clients.py slowbody  PORT CHEMIN N TAILLE OCTETS_PAR_S N clients qui envoient un corps au compte-gouttes
  s7_clients.py fetch     PORT CHEMIN N SHA256             N telechargements en parallele, corps verifie (chunked ou non)
  s7_clients.py mixed     PORT N_REQUETES                  statique et proxy en alternance sur UNE connexion

Chaque commande affiche une ligne « cle=valeur » : ce qui a reussi, echoue, la duree, et le detail utile."""
from __future__ import annotations

import asyncio
import hashlib
import socket
import sys
import time

HOST = "127.0.0.1"


async def _open(port: int, rcvbuf: int | None = None):
    if rcvbuf is None:
        return await asyncio.open_connection(HOST, port)
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_RCVBUF, rcvbuf)
    sock.setblocking(False)
    await asyncio.get_running_loop().sock_connect(sock, (HOST, port))
    return await asyncio.open_connection(sock=sock, limit=rcvbuf * 4)


async def _read_head(reader) -> tuple[int, dict[str, str]]:
    head = await reader.readuntil(b"\r\n\r\n")
    lines = head.decode("latin-1").split("\r\n")
    status = int(lines[0].split()[1])
    headers = {}
    for line in lines[1:]:
        if ":" in line:
            key, value = line.split(":", 1)
            headers[key.strip().lower()] = value.strip()
    return status, headers


async def _read_body(reader, headers: dict[str, str], *, chunk: int = 65536, rate: float | None = None,
                     digest=None) -> int:
    """Lit le corps (Content-Length ou chunked) ; `rate` : octets par seconde au plus. Rend le nombre d'octets."""
    total = 0

    async def take(size: int) -> bytes:
        nonlocal total
        data = await reader.readexactly(size)
        total += len(data)
        if digest is not None:
            digest.update(data)
        return data

    async def take_paced(size: int) -> None:
        left = size
        while left:
            step = min(left, chunk)
            started = time.monotonic()
            await take(step)
            left -= step
            if rate:
                await asyncio.sleep(max(0.0, step / rate - (time.monotonic() - started)))

    if headers.get("transfer-encoding", "").lower() == "chunked":
        while True:
            size = int((await reader.readuntil(b"\r\n")).split(b";")[0], 16)
            if size == 0:
                await reader.readuntil(b"\r\n")
                return total
            await take_paced(size)
            await reader.readexactly(2)
    await take_paced(int(headers.get("content-length", "0")))
    return total


def _request(path: str, method: str = "GET", body_size: int = 0, close: bool = False) -> bytes:
    head = f"{method} {path} HTTP/1.1\r\nHost: {HOST}\r\nAccept-Encoding: identity\r\nUser-Agent: s7\r\n"
    if body_size:
        head += f"Content-Length: {body_size}\r\nContent-Type: application/octet-stream\r\n"
    if close:
        head += "Connection: close\r\n"
    return (head + "\r\n").encode()


async def slowread(port: int, path: str, n: int, rate: float) -> None:
    async def one():
        reader, writer = await _open(port, rcvbuf=4096)
        try:
            writer.write(_request(path, close=True))
            await writer.drain()
            status, headers = await _read_head(reader)
            got = await _read_body(reader, headers, chunk=1024, rate=rate)
            return status, got, int(headers.get("content-length", got))
        finally:
            writer.close()
    started = time.monotonic()
    results = await asyncio.gather(*(one() for _ in range(n)), return_exceptions=True)
    ok = sum(1 for r in results if not isinstance(r, BaseException) and r[0] == 200 and r[1] == r[2])
    cut = [r for r in results if isinstance(r, BaseException)]
    kinds = {}
    for r in cut:
        kinds[type(r).__name__] = kinds.get(type(r).__name__, 0) + 1
    print(f"slowread complets={ok}/{n} coupes={len(cut)} {kinds} duree_s={time.monotonic() - started:.1f}")


async def slowhead(port: int, n: int) -> None:
    """Une ligne de requete puis un octet d'en-tete par seconde : quand le serveur ferme-t-il ?"""
    async def one():
        reader, writer = await _open(port)
        started = time.monotonic()
        writer.write(b"GET /small.html HTTP/1.1\r\nHost: 127.0.0.1\r\nX-Lent: ")
        try:
            for _ in range(120):
                await asyncio.sleep(1)
                writer.write(b"a")
                await writer.drain()
                if reader.at_eof():
                    break
                try:
                    await asyncio.wait_for(reader.read(4096), 0.01)
                    break  # reponse (408, 400...) ou fermeture : le serveur a tranche
                except asyncio.TimeoutError:
                    pass
        except (ConnectionError, OSError):
            pass
        finally:
            writer.close()
        return time.monotonic() - started
    durations = sorted(await asyncio.gather(*(one() for _ in range(n))))
    print(f"slowhead n={n} fermees_apres_s min={durations[0]:.1f} mediane={durations[n // 2]:.1f} "
          f"max={durations[-1]:.1f}")


async def slowbody(port: int, path: str, n: int, size: int, rate: float) -> None:
    async def one():
        reader, writer = await _open(port)
        started = time.monotonic()
        try:
            writer.write(_request(path, "POST", size, close=True))
            sent, block = 0, b"x" * 1024
            while sent < size:
                writer.write(block[: min(1024, size - sent)])
                await writer.drain()
                sent += min(1024, size - sent)
                await asyncio.sleep(1024 / rate)
            status, _headers = await _read_head(reader)
            return status, time.monotonic() - started
        except (ConnectionError, OSError, asyncio.IncompleteReadError) as exc:
            return type(exc).__name__, time.monotonic() - started
        finally:
            writer.close()
    results = await asyncio.gather(*(one() for _ in range(n)))
    outcome = {}
    for status, _ in results:
        outcome[str(status)] = outcome.get(str(status), 0) + 1
    print(f"slowbody n={n} taille={size} debit={rate:.0f}o/s resultats={outcome} "
          f"duree_max_s={max(d for _, d in results):.1f}")


async def fetch(port: int, path: str, n: int, sha: str) -> None:
    async def one():
        reader, writer = await _open(port)
        try:
            writer.write(_request(path, close=True))
            await writer.drain()
            status, headers = await _read_head(reader)
            digest = hashlib.sha256()
            got = await _read_body(reader, headers, chunk=1 << 20, digest=digest)
            return status, got, digest.hexdigest() == sha, headers.get("transfer-encoding", "")
        finally:
            writer.close()
    started = time.monotonic()
    results = await asyncio.gather(*(one() for _ in range(n)), return_exceptions=True)
    elapsed = time.monotonic() - started
    good = [r for r in results if not isinstance(r, BaseException) and r[0] == 200 and r[2]]
    volume = sum(r[1] for r in results if not isinstance(r, BaseException))
    encodings = {r[3] or "longueur" for r in results if not isinstance(r, BaseException)}
    print(f"fetch intacts={len(good)}/{n} encodage={','.join(sorted(encodings))} Mo/s={volume / elapsed / 1e6:.1f} "
          f"duree_s={elapsed:.1f}")


async def mixed(port: int, count: int) -> None:
    """Une seule connexion : /small.html (statique, sans X-Backend) puis /api/small.html (proxy, X-Backend: 1)."""
    reader, writer = await _open(port)
    wrong = 0
    started = time.monotonic()
    for i in range(count):
        proxied = i % 2 == 1
        writer.write(_request("/api/small.html" if proxied else "/small.html"))
        await writer.drain()
        status, headers = await _read_head(reader)
        size = await _read_body(reader, headers)
        if status != 200 or size != 1024 or (headers.get("x-backend") == "1") != proxied:
            wrong += 1
        if headers.get("connection", "").lower() == "close":
            print(f"mixed connexion_fermee_apres={i + 1}")
            break
    writer.close()
    elapsed = time.monotonic() - started
    print(f"mixed requetes={count} incorrectes={wrong} une_connexion=oui req/s={count / elapsed:.0f}")


def main(argv: list[str]) -> None:
    command, args = argv[0], argv[1:]
    port = int(args[0])
    if command == "slowread":
        asyncio.run(slowread(port, args[1], int(args[2]), float(args[3])))
    elif command == "slowhead":
        asyncio.run(slowhead(port, int(args[1])))
    elif command == "slowbody":
        asyncio.run(slowbody(port, args[1], int(args[2]), int(args[3]), float(args[4])))
    elif command == "fetch":
        asyncio.run(fetch(port, args[1], int(args[2]), args[3]))
    elif command == "mixed":
        asyncio.run(mixed(port, int(args[1])))
    else:
        raise SystemExit(f"commande inconnue : {command}")


if __name__ == "__main__":
    main(sys.argv[1:])
