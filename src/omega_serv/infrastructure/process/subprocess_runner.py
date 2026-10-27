"""Implementation reelle de ProcessRunnerPort - seul point du projet
qui touche reellement `subprocess` (charte : infrastructure/ est la
seule couche autorisee a faire de l'I/O processus). Generique : sert
aussi bien a l'outillage openssl (Phase 6) qu'aux gestionnaires de
service systemd/OpenRC/runit (Phase 9) - deplace hors de
infrastructure/tls/ quand ce second consommateur reel est apparu
(jamais deplace par anticipation, seulement une fois le besoin confirme)."""
from __future__ import annotations

import subprocess

from omega_serv.core.i18n import _
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
            return ProcessResult(returncode=127, stdout="", stderr=_("{value} : commande introuvable").format(value=args[0]))
        except subprocess.TimeoutExpired:
            # 124 : convention deja utilisee par la commande coreutils `timeout(1)`
            # (jamais une exception qui remonterait brute jusqu'a l'appelant - le
            # contrat du port est "retourne toujours un ProcessResult, ne leve jamais").
            return ProcessResult(
                returncode=124,
                stdout="",
                stderr=_("{value} : délai dépassé ({timeout:.0f}s) - processus bloqué, interrompu").format(value=args[0], timeout=timeout),
            )
        return ProcessResult(returncode=result.returncode, stdout=result.stdout, stderr=result.stderr)

    def run_interactive(self, args: list[str]) -> int:
        try:
            result = subprocess.run(args, check=False)
        except FileNotFoundError:
            return 127
        return result.returncode
