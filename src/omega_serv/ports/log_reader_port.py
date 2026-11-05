"""Lecture incrementale d'un journal (RIPOSTE, lot 2) - implementee par
infrastructure/riposte/log_follower.py::LogFollower."""
from __future__ import annotations

from typing import Protocol

from omega_serv.ports.riposte_store_port import FollowerPosition


class LogReaderPort(Protocol):
    skipped_long_lines: int
    restarts: int

    @property
    def position(self) -> FollowerPosition | None:
        ...

    def read_new_lines(self) -> list[str]:
        ...
