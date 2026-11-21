# Copyright (c) 2026 kraynux - kraynux@proton.me - Licence MIT (voir fichier LICENSE)
"""Limite des echecs d'authentification Basic AVANT le hachage (retour utilisateur 2026-11-20).

Le cache des succes ne sert qu'aux visiteurs legitimes : chaque mauvais mot de passe coute toujours un scrypt
(~0,3 a 0,5 s, 16 Mio). Ici, des compteurs d'echecs par adresse et par nom d'utilisateur sont consultes AVANT le
calcul : au-dela du seuil, refus immediat (429 + Retry-After) sans aucun hachage, jusqu'a la fin de la fenetre.
Un succes efface le compteur de son adresse (une faute de frappe ne bloque pas un visiteur). Le compteur par
utilisateur freine une attaque repartie sur de nombreuses adresses ; il ne bloque pas un utilisateur dont le
succes est deja retenu (le cache est consulte avant). Les recidivistes restent l'affaire de RIPOSTE/fail2ban
(reponses 401/429 du journal d'acces).

Memoire bornee (entrees expirees purgees, sinon la plus ancienne retiree). Par processus : en mode boost, chaque
processus de travail compte de son cote."""
from __future__ import annotations

from collections import OrderedDict

WINDOW_SECONDS = 300.0
IP_FAILURES_MAX = 10
USER_FAILURES_MAX = 30
_KEYS_MAX = 10000


class AuthFailureLimiter:
    def __init__(self, *, window: float = WINDOW_SECONDS, ip_max: int = IP_FAILURES_MAX,
                 user_max: int = USER_FAILURES_MAX, keys_max: int = _KEYS_MAX) -> None:
        self._window = window
        self._limits = {"ip": ip_max, "user": user_max}
        self._keys_max = keys_max
        self._counts: OrderedDict[tuple[str, str], tuple[float, int]] = OrderedDict()

    def retry_after(self, ip: str, username: str | None, now: float) -> float:
        """Secondes avant une nouvelle tentative ; 0 si le hachage peut avoir lieu."""
        wait = 0.0
        for key in self._keys(ip, username):
            entry = self._counts.get(key)
            if entry is None:
                continue
            start, count = entry
            if start + self._window <= now:
                del self._counts[key]
            elif count >= self._limits[key[0]]:
                wait = max(wait, start + self._window - now)
        return wait

    def record_failure(self, ip: str, username: str | None, now: float) -> None:
        for key in self._keys(ip, username):
            start, count = self._counts.get(key, (now, 0))
            if start + self._window <= now:
                start, count = now, 0
            self._counts[key] = (start, count + 1)
            self._counts.move_to_end(key)
        self._prune(now)

    def record_success(self, ip: str) -> None:
        self._counts.pop(("ip", ip), None)

    def clear(self) -> None:
        self._counts.clear()

    @staticmethod
    def _keys(ip: str, username: str | None) -> list[tuple[str, str]]:
        return [("ip", ip)] + ([("user", username)] if username else [])

    def _prune(self, now: float) -> None:
        if len(self._counts) <= self._keys_max:
            return
        for key in [k for k, (start, _count) in self._counts.items() if start + self._window <= now]:
            del self._counts[key]
        while len(self._counts) > self._keys_max:
            self._counts.popitem(last=False)
