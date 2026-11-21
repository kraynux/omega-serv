"""Instance maitre : instances suivies, appairage par code, appels et actions a distance, sondes HTTP (tableau de
bord web, lot 6c et 6d ; OMEGA-SERV_PLAN-DETAILLE_TABLEAU_DE_BORD_WEB.md §7.2 a §7.5 et §9.2).

La page Instances lit `overview()` : toutes les instances interrogees en parallele, au plus une fois toutes les 5 s,
et seulement quand une page le demande. Chaque appel part avec le jeton de l'instance et l'empreinte epinglee de son
certificat (infrastructure/admin_web/remote_client.py) ; un certificat change est refuse et signale (une ligne
d'audit). Les lignes sont mises en forme et traduites ici : la page n'affiche que du texte."""
from __future__ import annotations

import asyncio
import secrets
import time
from collections.abc import Callable
from dataclasses import dataclass, replace
from datetime import datetime, timezone
from typing import Any

from omega_serv.application.admin_web.actions import ActionOutcome, AdminState, state_from_dict
from omega_serv.application.admin_web.master_link import clean_name
from omega_serv.core.i18n import _
from omega_serv.domain.admin_web.master import (
    Fleet,
    FollowedInstance,
    MasterIdentity,
    check_instance_address,
    instance_proof,
    is_loopback_address,
    master_proof,
    normalize_pairing_code,
    pairing_key,
    proofs_equal,
    valid_fingerprint,
    valid_instance_id,
    valid_nonce,
)
from omega_serv.ports.admin_remote_port import FleetStorePort, RemoteClientPort, RemoteReply

OVERVIEW_SECONDS = 5.0
MAX_FOLLOWED = 100


@dataclass(frozen=True)
class FleetOutcome:
    ok: bool
    message: str
    instance_id: str = ""


def _now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def kind_label(kind: str) -> str:
    return {"site": _("Site"), "php": "PHP", "proxy": _("Reverse proxy"), "mixed": _("Mixte")}.get(kind, kind or "-")


def reply_problem(reply: RemoteReply) -> str:
    """Pourquoi un appel n'a pas abouti, en clair."""
    if reply.error == "empreinte":
        return _("certificat changé : appel refusé (nouvel appairage nécessaire si c'est voulu)")
    if reply.error == "ecoute":
        return _("port tenu par un autre utilisateur de la machine : jeton non envoyé")
    if reply.error == "delai":
        return _("pas de réponse")
    if reply.error in ("connexion", "tls"):
        return _("injoignable")
    if reply.error:
        return _("réponse illisible")
    if reply.status == 401:
        return _("jeton refusé (ce maître a été révoqué ou remplacé)")
    if reply.status == 403:
        return _("refusé par l'instance (droits, ou adresse du maître hors des réseaux permis)")
    if reply.status == 503:
        return _("administration de l'instance indisponible")
    return _("réponse inattendue (HTTP {status})").format(status=reply.status)


class FleetService:
    def __init__(self, store: FleetStorePort, client: RemoteClientPort, audit: Callable[[str], None],
                 default_name: str, *, new_master_id: Callable[[], str] = lambda: secrets.token_hex(16),
                 new_instance_id: Callable[[], str] = lambda: secrets.token_hex(6),
                 nonce: Callable[[], str] = lambda: secrets.token_hex(32),
                 monotonic: Callable[[], float] = time.monotonic) -> None:
        self._store = store
        self._client = client
        self._audit = audit
        self._default_name = default_name
        self._new_master_id = new_master_id
        self._new_instance_id = new_instance_id
        self._nonce = nonce
        self._monotonic = monotonic
        self._overview: dict[str, Any] | None = None
        self._overview_at = -OVERVIEW_SECONDS
        self._overview_lock = asyncio.Lock()
        self._fingerprint_reported: set[str] = set()

    # ------------------------------------------------------------------ liste
    def identity(self) -> MasterIdentity:
        return self._store.identity(self._new_master_id, self._default_name)

    def fleet(self) -> Fleet:
        return self._store.load()

    def find(self, instance_id: str) -> FollowedInstance | None:
        return self._store.load().find(instance_id) if valid_instance_id(instance_id) else None

    def _save_instance(self, item: FollowedInstance) -> FollowedInstance:
        """Une instance par adresse et port (ou par URL pour une sonde) : un nouvel appairage remplace l'entree."""
        fleet = self._store.load()
        same = next((i for i in fleet.instances if i.kind == item.kind and (
            (i.address, i.port) == (item.address, item.port) if item.kind == "omega-serv" else i.url == item.url)),
            None)
        if same is not None:
            item = replace(item, instance_id=same.instance_id)
        others = tuple(i for i in fleet.instances if same is None or i.instance_id != same.instance_id)
        self._store.save(Fleet((*others, item)))
        self._overview_at = -OVERVIEW_SECONDS
        self._fingerprint_reported.discard(item.instance_id)
        return item

    def _room_left(self) -> bool:
        return len(self._store.load().instances) < MAX_FOLLOWED

    def add_direct(self, name: str, address: str, port: int, token: str, fingerprint: str) -> FleetOutcome:
        """Chemin 1 : jeton et empreinte rendus par `admin-web master accept` sur l'instance (omega-connect, SSH)."""
        problem = check_instance_address(address, port)
        if problem:
            return FleetOutcome(False, _("Adresse ou port invalide."))
        if not valid_fingerprint(fingerprint) or not token or len(token) > 200:
            return FleetOutcome(False, _("Jeton ou empreinte invalide."))
        if not fingerprint and not is_loopback_address(address):
            return FleetOutcome(False, _("Sans TLS (empreinte vide), seule une instance de cette machine (boucle "
                                         "locale) peut être suivie."))
        if not self._room_left():
            return FleetOutcome(False, _("Trop d'instances suivies ({count} au plus).").format(count=MAX_FOLLOWED))
        item = self._save_instance(FollowedInstance(self._new_instance_id(), clean_name(name) or address,
                                                    "omega-serv", address, port, token, fingerprint,
                                                    added=_now_iso()))
        self._audit(f"instance suivie ajoutee (commande) nom={item.name!r} adresse={address}:{port}")
        return FleetOutcome(True, _("Instance {name} ajoutée.").format(name=item.name), item.instance_id)

    def add_probe(self, name: str, url: str) -> FleetOutcome:
        if not url.startswith(("http://", "https://")) or len(url) > 500 or any(c.isspace() for c in url):
            return FleetOutcome(False, _("URL invalide : http://... ou https://..."))
        if not self._room_left():
            return FleetOutcome(False, _("Trop d'instances suivies ({count} au plus).").format(count=MAX_FOLLOWED))
        item = self._save_instance(FollowedInstance(self._new_instance_id(), clean_name(name) or url, "sonde",
                                                    url=url, added=_now_iso()))
        self._audit(f"sonde HTTP ajoutee nom={item.name!r} url={url!r}")
        return FleetOutcome(True, _("Sonde {name} ajoutée.").format(name=item.name), item.instance_id)

    def remove(self, instance_id: str) -> FleetOutcome:
        fleet = self._store.load()
        item = fleet.find(instance_id)
        if item is None:
            return FleetOutcome(False, _("Instance inconnue."))
        self._store.save(Fleet(tuple(i for i in fleet.instances if i.instance_id != instance_id)))
        self._overview_at = -OVERVIEW_SECONDS
        self._audit(f"instance suivie retiree nom={item.name!r} cible={item.target}")
        return FleetOutcome(True, _("{name} retirée (son jeton est oublié ici ; révoquez aussi le maître sur "
                                    "l'instance si elle doit être reliée à un autre).").format(name=item.name))

    # ------------------------------------------------------------------ appairage par code (chemin 2)
    async def pair(self, name: str, address: str, port: int, code_text: str) -> FleetOutcome:
        if check_instance_address(address, port):
            return FleetOutcome(False, _("Adresse ou port invalide."))
        code = normalize_pairing_code(code_text)
        if not code:
            return FleetOutcome(False, _("Code d'appairage invalide (8 caractères, comme K7QF-3M9X)."))
        if not self._room_left():
            return FleetOutcome(False, _("Trop d'instances suivies ({count} au plus).").format(count=MAX_FOLLOWED))
        use_tls = True
        challenge = await self._client.call(address, port, use_tls=True, fingerprint=None, method="POST",
                                            path="/api/appairage/defi")
        if challenge.error in ("tls", "reponse") and is_loopback_address(address):
            use_tls = False  # instance de cette machine sans TLS (127.0.0.1)
            challenge = await self._client.call(address, port, use_tls=False, fingerprint=None, method="POST",
                                                path="/api/appairage/defi")
        if challenge.status != 200:
            return FleetOutcome(False, self._pairing_problem(challenge))
        nonce_i = challenge.payload.get("nonce") if isinstance(challenge.payload, dict) else None
        if not valid_nonce(nonce_i):
            return FleetOutcome(False, _("réponse illisible"))
        assert isinstance(nonce_i, str)
        seen = challenge.fingerprint if use_tls else ""
        identity = self.identity()
        nonce_m = self._nonce()
        key = await asyncio.to_thread(pairing_key, code, nonce_i, nonce_m)
        body = {"nonce_instance": nonce_i, "nonce_maitre": nonce_m, "maitre_id": identity.master_id,
                "maitre_nom": identity.name, "preuve": master_proof(key, nonce_i, nonce_m, seen, identity.master_id)}
        reply = await self._client.call(address, port, use_tls=use_tls, fingerprint=seen, method="POST",
                                        path="/api/appairage/preuve", body=body)
        if reply.status != 200 or not isinstance(reply.payload, dict):
            return FleetOutcome(False, self._pairing_problem(reply))
        token, proof = reply.payload.get("jeton"), reply.payload.get("preuve")
        if not isinstance(token, str) or not isinstance(proof, str) or not proofs_equal(
                instance_proof(key, nonce_i, nonce_m, seen, token), proof):
            self._audit(f"appairage abandonne : preuve de l'instance fausse adresse={address}:{port}")
            return FleetOutcome(False, _("L'instance n'a pas prouvé qu'elle connaît le code : appairage abandonné."))
        shown = clean_name(name) or clean_name(reply.payload.get("nom", "")) or address
        item = self._save_instance(FollowedInstance(self._new_instance_id(), shown, "omega-serv", address, port,
                                                    token, seen, added=_now_iso()))
        rights = str(reply.payload.get("droits", ""))
        if rights not in ("lecture", "administration"):  # scan de securite n° 1 (F39) : valeur de l'instance distante
            rights = ""
        self._audit(f"instance suivie ajoutee (code) nom={item.name!r} adresse={address}:{port} droits={rights}")
        return FleetOutcome(True, _("Instance {name} reliée (droits : {rights}).").format(
            name=item.name, rights=rights_label(rights)), item.instance_id)

    @staticmethod
    def _pairing_problem(reply: RemoteReply) -> str:
        error = reply.payload.get("error") if isinstance(reply.payload, dict) else None
        if reply.status == 403 and error == "fenetre":
            return _("Aucune fenêtre d'appairage ouverte sur cette instance (ou elle a expiré) : ouvrez-en une dans "
                     "son TUI (Configuration distante -> Maître).")
        if reply.status == 403 and error == "preuve":
            return _("Code faux (3 essais faux ferment la fenêtre).")
        if reply.status == 429:
            return _("Trop de demandes en cours sur cette instance : réessayez dans une minute.")
        return reply_problem(reply)

    # ------------------------------------------------------------------ appels
    async def _call(self, item: FollowedInstance, method: str, path: str, body: object = None,
                    account: str = "") -> RemoteReply:
        reply = await self._client.call(item.address, item.port, use_tls=bool(item.fingerprint),
                                        fingerprint=item.fingerprint, method=method, path=path, token=item.token,
                                        body=body, account=account)
        if reply.error == "empreinte" and item.instance_id not in self._fingerprint_reported:
            self._fingerprint_reported.add(item.instance_id)
            self._audit(f"certificat change, appel refuse instance={item.name!r} adresse={item.address}:{item.port} "
                        f"vu={reply.fingerprint}")
        return reply

    async def _row(self, item: FollowedInstance) -> dict[str, Any]:
        if item.kind == "sonde":
            probe = await self._client.probe(item.url)
            if probe.status:
                tone = "ok" if probe.status < 400 else "error" if probe.status >= 500 else "warn"
                state = _("HTTP {status} en {ms} ms").format(status=probe.status, ms=probe.milliseconds)
            else:
                tone = "error"
                state = {"delai": _("pas de réponse"), "url": _("URL invalide")}.get(probe.error, _("injoignable"))
            return {"id": item.instance_id, "link": False, "tone": tone,
                    "cells": [item.name, _("Sonde HTTP"), state, "-", "-", "-", "-", "-", item.url]}
        reply = await self._call(item, "GET", "/api/maitre/resume")
        payload = reply.payload if isinstance(reply.payload, dict) else {}
        if reply.status != 200:
            return {"id": item.instance_id, "link": False, "tone": "error",
                    "cells": [item.name, "omega-serv", reply_problem(reply), "-", "-", "-", "-", "-", item.target]}
        if payload.get("loading"):
            return {"id": item.instance_id, "link": True, "tone": "", "cells": [
                item.name, "omega-serv", _("Chargement..."), "-", "-", "-", "-",
                rights_label(str(payload.get("droits", ""))), item.target]}
        running = payload.get("running")  # None : etat illisible sur l'instance suivie (colonne en erreur)
        incidents, bans = payload.get("incidents"), payload.get("bans")
        tone = "error" if running is False else "warn" if isinstance(incidents, int) and incidents > 0 else "ok"
        state = _("en marche") if running is True else _("arrêté") if running is False else "-"
        return {"id": item.instance_id, "link": True, "tone": tone, "cells": [
            item.name, kind_label(str(payload.get("kind", ""))), state,
            _number(payload.get("rps")), _number(payload.get("errors_5xx")),
            _number(bans), _number(incidents), rights_label(str(payload.get("droits", ""))), item.target]}

    async def overview(self) -> dict[str, Any]:
        async with self._overview_lock:
            if self._overview is not None and self._monotonic() - self._overview_at < OVERVIEW_SECONDS - 0.5:
                return self._overview
            items = self._store.load().instances
            rows = await asyncio.gather(*(self._row(item) for item in items))
            self._overview = {
                "headers": [_("Instance"), _("Type"), _("État"), _("Req/s (1 min)"), _("Erreurs 5xx"), _("Bans"),
                            _("Incidents"), _("Droits"), _("Adresse")],
                "rows": list(rows),
                "empty": _("Aucune instance suivie : ajoutez-en une ci-dessous, ou, pour une instance de cette machine, "
                           "depuis le TUI (Instances -> Relier au maître).")
                if not items else "",
                "updated": datetime.now(timezone.utc).astimezone().strftime("%H:%M:%S"),
            }
            self._overview_at = self._monotonic()
            return self._overview

    async def panel(self, instance_id: str, name: str) -> tuple[int, dict[str, Any]]:
        item = self.find(instance_id)
        if item is None or item.kind != "omega-serv":
            return 404, {"error": "instance"}
        reply = await self._call(item, "GET", f"/api/maitre/vue/{name}")
        if reply.status == 200 and isinstance(reply.payload, dict):
            return 200, reply.payload
        return 200, {"sections": [], "error": reply_problem(reply)}

    async def admin_state(self, item: FollowedInstance) -> AdminState | str:
        reply = await self._call(item, "GET", "/api/maitre/administration")
        if reply.status == 403:
            return _("Ce maître n'a que le droit de lecture sur cette instance : les actions se donnent chez elle "
                     "(TUI : Configuration distante -> Maître).")
        if reply.status != 200:
            return reply_problem(reply)
        try:
            return state_from_dict(reply.payload)
        except ValueError:
            return _("réponse illisible")

    async def action(self, item: FollowedInstance, params: dict[str, str], account: str) -> ActionOutcome:
        reply = await self._call(item, "POST", "/api/maitre/action", {"params": params, "compte": account})
        payload = reply.payload if isinstance(reply.payload, dict) else {}
        if reply.status == 200 and isinstance(payload.get("ok"), bool):
            return ActionOutcome(payload["ok"], str(payload.get("message", ""))[:500])
        if reply.status == 403:
            return ActionOutcome(False, _("Refusé : ce maître n'a que le droit de lecture sur cette instance."))
        return ActionOutcome(False, reply_problem(reply))


def rights_label(rights: str) -> str:
    return {"lecture": _("lecture"), "administration": _("administration")}.get(rights, rights or "-")


def _number(value: object) -> str:
    if isinstance(value, bool) or not isinstance(value, int | float):
        return "-"
    return f"{value:g}" if isinstance(value, float) else str(value)
