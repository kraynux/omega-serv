# Copyright (c) 2026 kraynux - kraynux@proton.me - Licence MIT (voir fichier LICENSE)
"""Implementation reelle de ProcessRunnerPort - seul point du projet
qui touche reellement `subprocess` (charte : infrastructure/ est la
seule couche autorisee a faire de l'I/O processus). Generique : sert
aussi bien a l'outillage openssl (Phase 6) qu'aux gestionnaires de
service systemd/OpenRC/runit (Phase 9) - deplace hors de
infrastructure/tls/ quand ce second consommateur reel est apparu
(jamais deplace par anticipation, seulement une fois le besoin confirme)."""
from __future__ import annotations

import subprocess

from omega_serv.ports.process_runner_port import ProcessResult


class SubprocessRunner:
    """Implementation reelle de ports.process_runner_port.ProcessRunnerPort."""

    def run(self, args: list[str], input_text: str | None = None, timeout: float | None = None) -> ProcessResult:
        try:
            result = subprocess.run(
                args,
                input=input_text,
                capture_output=True,
                text=True,
                timeout=timeout,
                check=False,
            )
        except FileNotFoundError:
            # Convention shell POSIX ("commande introuvable") - un
            # binaire absent (openssl, systemctl...) n'est pas une
            # panne inattendue a laisser remonter, c'est un resultat de
            # process comme un autre pour l'appelant (qui verifie deja
            # `result.ok`/`result.returncode`, jamais un try/except ici).
            return ProcessResult(returncode=127, stdout="", stderr=f"{args[0]} : commande introuvable")
        return ProcessResult(returncode=result.returncode, stdout=result.stdout, stderr=result.stderr)

    def run_interactive(self, args: list[str]) -> int:
        # Retour utilisateur (audit securite) : jamais `capture_output`
        # ni `stdin`/`stdout`/`stderr` explicites ici - herite tels
        # quels les descripteurs du processus appelant (le vrai
        # terminal, deja libere par App.suspend() cote appelant TUI),
        # pour que sudo puisse gerer lui-meme son invite de mot de passe
        # (desactivation d'echo, lecture, restauration) sans qu'aucun
        # de ses cotes stdin/stdout/stderr ne soit redirige vers un
        # tube invisible.
        try:
            result = subprocess.run(args, check=False)
        except FileNotFoundError:
            return 127
        return result.returncode
