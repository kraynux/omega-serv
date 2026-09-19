"""Contrat de sondage des capacites systeme (plan interface §3.3)."""
from __future__ import annotations

from typing import Protocol

from omega_serv.core.capability import Capability


class CapabilityScannerPort(Protocol):
    def scan(self) -> tuple[Capability, ...]:
        ...
