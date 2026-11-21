"""Decision d'authentification/autorisation (spec §15.7 : distinguer
authentification - "qui est l'utilisateur ?" - et autorisation - "a-t-il
le droit d'acceder a cette zone et cette methode ?"). Reutilise
domain/routing/zone_resolver.py::resolve_zone (plus-long-prefixe-gagne)
- aucune logique de correspondance de chemin reinventee ici (decision
transverse "ZoneResolver unifie", voir son docstring).

Protection anti-enumeration d'utilisateurs par canal temporel : meme
quand le username est inconnu, une verification scrypt est TOUJOURS
executee (contre un hash factice fixe) avant de repondre - sinon un
attaquant pourrait distinguer "utilisateur inconnu" (reponse immediate)
de "mot de passe incorrect" (scrypt coute, donc lent) par simple mesure
de latence."""
from __future__ import annotations

import hashlib
import hmac
import os
import time
from collections import OrderedDict
from collections.abc import Mapping
from functools import cache

from omega_serv.domain.routing.zone_resolver import Zone, resolve_zone
from omega_serv.domain.security.auth.basic_auth import parse_basic_auth_header
from omega_serv.domain.security.auth.entities import AuthDecision, AuthZone, UserAccount
from omega_serv.domain.security.auth.password_hashing import hash_password, verify_password


@cache
def _dummy_hash() -> str:
    """Hash factice calcule au premier besoin, plus a l'import : chaque processus payait 0,3 s et 16 Mio de scrypt au
    demarrage, meme sans authentification (remesure memoire 3.0.0, 2026-11-18)."""
    return hash_password("dummy-password-constant-time-witness", salt=b"\x00" * 16)


_VERIFIED_TTL_SECONDS = 300.0
_VERIFIED_ABSOLUTE_SECONDS = 3600.0
_VERIFIED_MAX = 4096
"""Valeurs par defaut ; reglables dans le menu Authentification (configure_success_cache, 2026-11-21)."""
_verified: OrderedDict[bytes, tuple[float, float]] = OrderedDict()
_verified_key_secret = os.urandom(32)
"""Scan de securite n° 1 (2026-11-20, F21/F33) : une verification scrypt coute ~0,3 a 0,5 s et 16 Mio, et un navigateur
renvoie ses identifiants a CHAQUE requete d'une zone protegee. Les SUCCES sont retenus sous une empreinte HMAC (cle
aleatoire du processus, jamais ecrite) de l'utilisateur, du mot de passe et du hash : jamais le mot de passe lui-meme ;
un hash change (mot de passe modifie) ne correspond plus. Les echecs ne sont jamais retenus.

Revu le 2026-11-20 (retour utilisateur) : 5 min RENOUVELEES a chaque usage, plafond absolu d'une heure apres la
vraie verification (puis scrypt a nouveau), 4096 entrees au plus avec eviction de la plus anciennement utilisee
(LRU, au lieu de tout vider), purge complete a chaque rechargement des comptes ou des zones."""


def _verified_key(username: str, password: str, password_hash: str) -> bytes:
    material = f"{username}\x00{password}\x00{password_hash}".encode("utf-8", errors="surrogatepass")
    return hmac.new(_verified_key_secret, material, hashlib.sha256).digest()


def _recently_verified(key: bytes, *, renew: bool = False) -> bool:
    entry = _verified.get(key)
    if entry is None:
        return False
    now = time.monotonic()
    until, absolute = entry
    if until <= now or absolute <= now:
        _verified.pop(key, None)
        return False
    if renew:
        _verified[key] = (min(now + _VERIFIED_TTL_SECONDS, absolute), absolute)
        _verified.move_to_end(key)
    return True


def configure_success_cache(ttl_seconds: float, max_age_seconds: float, entries: int) -> None:
    """Reglages du menu Authentification (options.auth.settings.password_protection), relus a chaque rechargement.
    Une duree ou un nombre d'entrees a 0 : aucun succes retenu (scrypt a chaque requete)."""
    global _VERIFIED_TTL_SECONDS, _VERIFIED_ABSOLUTE_SECONDS, _VERIFIED_MAX
    _VERIFIED_TTL_SECONDS, _VERIFIED_ABSOLUTE_SECONDS, _VERIFIED_MAX = ttl_seconds, max_age_seconds, entries
    _verified.clear()


def _remember_verified(key: bytes) -> None:
    if _VERIFIED_TTL_SECONDS <= 0 or _VERIFIED_MAX <= 0:
        return
    now = time.monotonic()
    _verified[key] = (now + _VERIFIED_TTL_SECONDS, now + _VERIFIED_ABSOLUTE_SECONDS)
    _verified.move_to_end(key)
    while len(_verified) > _VERIFIED_MAX:
        _verified.popitem(last=False)


def forget_verified_credentials() -> None:
    """Comptes ou zones recharges (modification depuis la TUI, rechargement) : tout succes retenu est oublie."""
    _verified.clear()


def _check_password(username: str, password: str, password_hash: str) -> bool:
    key = _verified_key(username, password, password_hash)
    if _recently_verified(key, renew=True):
        return True
    if not verify_password(password, password_hash):
        return False
    _remember_verified(key)
    return True


def password_check_is_costly(
    path: str, auth_header: str | None, zones: tuple[Zone[AuthZone], ...], users_by_name: Mapping[str, UserAccount],
) -> bool:
    """Vrai quand authorize_request() va lancer un scrypt (zone protegee, identifiants fournis, pas de succes
    recent) : le serveur la fait alors tourner hors de sa boucle asyncio (scan de securite n° 1, F21/F33) - sinon
    chaque tentative Basic, meme d'un inconnu, gelait TOUT le serveur 0,3 a 0,5 s."""
    if resolve_zone(path, list(zones)) is None:
        return False
    credentials = parse_basic_auth_header(auth_header)
    if credentials is None:
        return False
    username, password = credentials
    user = users_by_name.get(username)
    return user is None or not _recently_verified(_verified_key(username, password, user.password_hash))


def authorize_request(
    path: str,
    method: str,
    auth_header: str | None,
    zones: tuple[Zone[AuthZone], ...],
    users_by_name: Mapping[str, UserAccount],
) -> AuthDecision:
    matched = resolve_zone(path, list(zones))
    if matched is None:
        return AuthDecision(outcome="not_protected")

    zone = matched.data
    if zone.allow_methods and method not in zone.allow_methods:
        return AuthDecision(outcome="forbidden", realm=zone.realm)

    credentials = parse_basic_auth_header(auth_header)
    if credentials is None:
        return AuthDecision(outcome="unauthenticated", realm=zone.realm)

    username, password = credentials
    user = users_by_name.get(username)
    if user is not None:
        password_ok = _check_password(username, password, user.password_hash)
    else:
        password_ok = verify_password(password, _dummy_hash())

    if user is None or not password_ok:
        return AuthDecision(outcome="unauthenticated", realm=zone.realm)

    if username not in zone.allowed_users:
        return AuthDecision(outcome="forbidden", realm=zone.realm, username=username)

    return AuthDecision(outcome="allowed", realm=zone.realm, username=username)
