# Copyright (c) 2026 kraynux - kraynux@proton.me - Licence MIT (voir fichier LICENSE)
"""Etat du processus d'administration web (lot 8, OMEGA-SERV_PLAN-DETAILLE_TABLEAU_DE_BORD_WEB.md §9.4).

Ecrit par le processus a chaque demarrage ou rechargement (var/run/admin/etat.json), lu par l'ecran Configuration
distante : « en ecoute » ou la raison de l'arret, par un code stable que la TUI traduit. Un simple essai de connexion
ne suffisait pas : un autre programme sur le meme port (KULA sur 8443, essai reel du 2026-11-17) repondait a sa
place."""
from __future__ import annotations

from dataclasses import dataclass

PROBLEMS = ("config", "inactive", "certificate", "accounts_file", "totp", "fingerprint", "listen")
"""Codes des raisons d'arret : configuration illisible, option inactive, certificat illisible, fichier des comptes
illisible, TOTP manquant hors boucle locale, empreinte illisible, ecoute impossible (port pris, adresse absente)."""


@dataclass(frozen=True)
class AdminRunState:
    pid: int
    listening: bool
    bind: str = ""
    port: int = 0
    problem: str = ""
    """Un des PROBLEMS, vide si en ecoute."""
    detail: str = ""
    """Message d'erreur brut (systeme), affiche tel quel apres la raison traduite."""

    def to_dict(self) -> dict[str, object]:
        return {"pid": self.pid, "listening": self.listening, "bind": self.bind, "port": self.port,
                "problem": self.problem, "detail": self.detail}

    @classmethod
    def from_dict(cls, data: object) -> AdminRunState | None:
        if not isinstance(data, dict):
            return None
        pid, listening, port = data.get("pid"), data.get("listening"), data.get("port", 0)
        if not isinstance(pid, int) or isinstance(pid, bool) or pid <= 0 or not isinstance(listening, bool):
            return None
        if not isinstance(port, int) or isinstance(port, bool):
            return None
        problem = data.get("problem", "")
        if problem not in ("", *PROBLEMS):
            problem = "config"
        return cls(pid, listening, str(data.get("bind", ""))[:100], port, problem, str(data.get("detail", ""))[:300])
