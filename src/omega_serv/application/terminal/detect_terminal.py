"""Cas d'usage : detecter le terminal et resoudre son profil de rendu
(plan interface §3.1, Phase I) - porte depuis omega-check."""
from __future__ import annotations

from omega_lib.terminal.models import TerminalProfile
from omega_lib.terminal.service import resolve_render_profile

from omega_serv.ports.terminal_detector import TerminalDetector


def detect_terminal(*, terminal_detector: TerminalDetector) -> TerminalProfile:
    signals = terminal_detector.detect()
    return resolve_render_profile(signals)
