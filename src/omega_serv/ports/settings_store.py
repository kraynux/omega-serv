# Copyright (c) 2026 kraynux - kraynux@proton.me - Licence MIT (voir fichier LICENSE)
"""Re-export depuis omega_lib (plan interface §3.2) : garde la convention
'importer depuis omega_serv.ports.X' uniforme dans tout le reste du
code, meme principe que ports/service_manager_port.py::ServiceManagerType."""
from __future__ import annotations

from omega_lib.ports.settings_store import SettingsStore

__all__ = ["SettingsStore"]
