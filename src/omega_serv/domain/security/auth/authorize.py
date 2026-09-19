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

from collections.abc import Mapping

from omega_serv.domain.routing.zone_resolver import Zone, resolve_zone
from omega_serv.domain.security.auth.basic_auth import parse_basic_auth_header
from omega_serv.domain.security.auth.entities import AuthDecision, AuthZone, UserAccount
from omega_serv.domain.security.auth.password_hashing import hash_password, verify_password

_DUMMY_HASH = hash_password("dummy-password-constant-time-witness", salt=b"\x00" * 16)


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
    hash_to_check = user.password_hash if user is not None else _DUMMY_HASH
    password_ok = verify_password(password, hash_to_check)

    if user is None or not password_ok:
        return AuthDecision(outcome="unauthenticated", realm=zone.realm)

    if username not in zone.allowed_users:
        return AuthDecision(outcome="forbidden", realm=zone.realm, username=username)

    return AuthDecision(outcome="allowed", realm=zone.realm, username=username)
