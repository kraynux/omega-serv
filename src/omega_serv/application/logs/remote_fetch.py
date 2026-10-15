"""Cas d'usage "Recuperer maintenant" d'une source distante
(OMEGA-SERV_ETUDE-FAISABILITE_LOGS_DISTANTS.md, 2026-10-15) - lance
`scp` via le `ProcessRunnerPort` deja existant (aucun nouveau port :
"lancer une commande, recuperer le resultat" couvre deja ce besoin)."""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from omega_serv.domain.logs.remote_source import RemoteLogSource, build_scp_command
from omega_serv.ports.process_runner_port import ProcessRunnerPort

_DEFAULT_TIMEOUT_SECONDS = 120.0
"""`-o ConnectTimeout=10` dans l'argv borne deja la phase de connexion -
ce timeout global doit, lui, couvrir tout le transfert (potentiellement
plusieurs dizaines de Mo sur un reseau local lent), pas seulement la
poignee de main."""


@dataclass(frozen=True, slots=True)
class RemoteFetchResult:
    success: bool
    message: str


def fetch_remote_log(
    process_runner: ProcessRunnerPort, source: RemoteLogSource, local_dest: Path,
    *, timeout: float = _DEFAULT_TIMEOUT_SECONDS,
) -> RemoteFetchResult:
    local_dest.parent.mkdir(parents=True, exist_ok=True)
    result = process_runner.run(build_scp_command(source, local_dest), timeout=timeout)
    if result.ok:
        return RemoteFetchResult(success=True, message=f"Recupere dans {local_dest}.")
    detail = result.stderr.strip() or f"code de retour {result.returncode}"
    return RemoteFetchResult(success=False, message=f"Echec de la recuperation : {detail}")
