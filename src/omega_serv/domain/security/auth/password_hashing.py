# Copyright (c) 2026 kraynux - kraynux@proton.me - Licence MIT (voir fichier LICENSE)
"""Hachage de mot de passe (spec §15.5 : "sel et parametres de cout
obligatoires" ; OMEGA-SERV_PLAN_DEVELOPPEMENT.md §6 : "hashlib.scrypt,
stdlib, aucune dependance ajoutee" - decision explicite de l'utilisateur
plutot que bcrypt/Argon2id).

Le format encode est auto-descriptif (`scrypt$n$r$p$sel$hash`, tout en
hexadecimal) : changer les parametres de cout plus tard reste
compatible avec les hashes existants, pas de migration de format requise."""
from __future__ import annotations

import hashlib
import hmac
import os

_ALGO = "scrypt"
_DEFAULT_N = 16384  # 2**14 - cout memoire, ~16 Mio, cible interactive (login humain, pas une API a tres haut debit)
_DEFAULT_R = 8
# Retour utilisateur (audit securite, 2026-09-14) : p=1 avec N=2**14 est
# SOUS le minimum actuellement recommande par l'OWASP (Password Storage
# Cheat Sheet) - aucune des configurations scrypt qu'elle liste comme
# acceptables n'accepte p=1 en dessous de N=2**17. p=5 est precisement
# la valeur que l'OWASP associe a N=2**14 pour compenser un cout memoire
# volontairement contraint (~16 Mio, cible materiel modeste) - le cout
# MEMOIRE de scrypt depend de N*r, jamais de p (p ne fait qu'augmenter
# le temps CPU, en serie ici puisque `hashlib.scrypt` ne parallelise
# jamais reellement les threads), donc cette hausse ne change rien a
# l'empreinte memoire ~16 Mio deja jugee adaptee a du materiel modeste.
# Format auto-descriptif : les hashs existants generes avec p=1 restent
# verifiables tels quels (p est relu depuis le hash, jamais suppose).
_DEFAULT_P = 5
_DEFAULT_DKLEN = 32
_SALT_BYTES = 16


def hash_password(password: str, salt: bytes | None = None) -> str:
    """`salt` expose uniquement pour des tests deterministes - en usage
    reel, ne jamais l'appeler avec un sel fixe (os.urandom par defaut)."""
    if salt is None:
        salt = os.urandom(_SALT_BYTES)
    derived = hashlib.scrypt(
        password.encode("utf-8"), salt=salt, n=_DEFAULT_N, r=_DEFAULT_R, p=_DEFAULT_P, dklen=_DEFAULT_DKLEN,
    )
    return f"{_ALGO}${_DEFAULT_N}${_DEFAULT_R}${_DEFAULT_P}${salt.hex()}${derived.hex()}"


def verify_password(password: str, encoded_hash: str) -> bool:
    """Jamais de comparaison `==` sur un hash (canal temporel) - toujours
    `hmac.compare_digest`. Un hash malforme est traite comme "ne
    correspond pas", jamais comme une erreur qui remonterait."""
    try:
        algo, n_str, r_str, p_str, salt_hex, hash_hex = encoded_hash.split("$")
        if algo != _ALGO:
            return False
        salt = bytes.fromhex(salt_hex)
        expected = bytes.fromhex(hash_hex)
        computed = hashlib.scrypt(
            password.encode("utf-8"), salt=salt, n=int(n_str), r=int(r_str), p=int(p_str), dklen=len(expected),
        )
    except (ValueError, TypeError):
        return False
    return hmac.compare_digest(computed, expected)
