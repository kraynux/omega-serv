"""Cas d'usage : surcharger (ou remettre en automatique) le profil de
rendu - porte depuis omega-check (ecran Reglages)."""
from __future__ import annotations

from omega_lib.terminal.models import RenderProfile

from omega_serv.ports.settings_store import SettingsStore

_RENDER_PROFILE_OVERRIDE_KEY = "render_profile_override"


def select_render_profile(*, settings_store: SettingsStore, render_profile: RenderProfile | None) -> None:
    settings_store.set(_RENDER_PROFILE_OVERRIDE_KEY, render_profile.value if render_profile else "")
