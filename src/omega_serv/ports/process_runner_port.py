# Copyright (c) 2026 kraynux - kraynux@proton.me - Licence MIT (voir fichier LICENSE)
"""Contrat d'execution de processus externe (doc TLS §2 : "ports/ :
ProcessRunnerPort"). Le CLI ne doit jamais appeler subprocess
directement - un adaptateur d'infrastructure/ execute le processus reel
(openssl aujourd'hui, reutilisable par d'autres outils externes plus
tard sans dupliquer ce contrat)."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol


@dataclass(frozen=True)
class ProcessResult:
    returncode: int
    stdout: str
    stderr: str

    @property
    def ok(self) -> bool:
        return self.returncode == 0


class ProcessRunnerPort(Protocol):
    def run(self, args: list[str], input_text: str | None = None, timeout: float | None = None) -> ProcessResult:
        ...

    def run_interactive(self, args: list[str]) -> int:
        """Execute en HERITANT INTEGRALEMENT les descripteurs du
        terminal reel (jamais de capture stdout/stderr/stdin) - reserve
        aux commandes qui ont reellement besoin d'un terminal
        interactif complet, typiquement `sudo -v` pour authentifier/
        rafraichir le cache sudo AVANT une commande privilegiee
        capturee separement (retour utilisateur, audit securite : une
        commande privilegiee lancee directement avec une sortie
        capturee empechait l'invite de mot de passe sudo de s'afficher
        et de fonctionner correctement sur le vrai terminal - mot de
        passe systematiquement refuse). Ne retourne QUE le code de
        retour, aucune sortie a capturer par construction."""
        ...
