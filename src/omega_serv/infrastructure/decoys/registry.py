# Copyright (c) 2026 kraynux - kraynux@proton.me - Licence MIT (voir fichier LICENSE)
"""Catalogue des fixtures Niveau 1 connues (plan_active_defense_omega_
serv.md, §"Honeypots V1") - un seul point d'ajout pour chaque nouveau
leurre in-process, jamais une chaine de `if profile_name == ...` dans le
dispatcher."""
from __future__ import annotations

from collections.abc import Callable

from omega_serv.domain.http.request import HttpRequest
from omega_serv.domain.http.response import HttpResponse
from omega_serv.infrastructure.decoys.fake_admin_handler import handle_fake_admin
from omega_serv.infrastructure.decoys.fake_api_handler import handle_fake_api
from omega_serv.infrastructure.decoys.fake_cms_handler import handle_fake_cms
from omega_serv.infrastructure.decoys.fake_secrets_handler import handle_fake_secrets

FIXTURE_HANDLERS: dict[str, Callable[[HttpRequest], HttpResponse]] = {
    "fake_admin": handle_fake_admin,
    "fake_cms": handle_fake_cms,
    "fake_api": handle_fake_api,
    "fake_secrets": handle_fake_secrets,
}
