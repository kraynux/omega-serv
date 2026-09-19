"""Re-export depuis omega_lib (plan interface §3.2), meme raisonnement
que ports/settings_store.py."""
from __future__ import annotations

from omega_lib.ports.terminal_detector import TerminalDetector

__all__ = ["TerminalDetector"]
