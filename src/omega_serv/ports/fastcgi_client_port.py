"""Contrat de communication avec un backend FastCGI (spec §21)."""
from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol


@dataclass(frozen=True)
class FastCgiResult:
    status_code: int
    headers: tuple[tuple[str, str], ...]
    body: bytes
    stderr: bytes


class FastCgiClientPort(Protocol):
    async def send_request(
        self,
        socket_path: Path,
        env: Mapping[str, str],
        body: bytes,
        connect_timeout: float,
        read_timeout: float,
    ) -> FastCgiResult:
        ...
