"""Operations sur les logs avec sudo (2026-11-07, demande utilisateur : « si les droits bloquent, on peut
demander une authentification (sudo) ? »). Meme mecanisme que l'ecran Service et omega-log : `sudo -v` sur
le vrai terminal (l'ecran est suspendu), puis des commandes `sudo -n` capturees - `-n` : jamais de mot de
passe demande hors du terminal, une authentification expiree echoue proprement.

Seules commandes lancees : lecture (`cat`, `head -c`, `tail -c`) et, pour Sante des logs, `chgrp` + `chmod
g+w` (le compte du service doit ecrire) ou `chmod o-w` (log inscriptible par tout le monde). Jamais `chown`,
jamais recursif, toujours un seul fichier nomme, montre a l'utilisateur avant d'etre lance."""
from __future__ import annotations

from typing import TYPE_CHECKING

from omega_serv.core.platform_info import running_as_root
from omega_serv.domain.logs.exceptions import LogPermissionError

if TYPE_CHECKING:
    from omega_serv.ports.process_runner_port import ProcessRunnerPort

READ_TIMEOUT_SECONDS = 900.0
"""Lecture complete d'un gros log protege (Statistiques « Tout ») : plusieurs minutes possibles."""
SAMPLE_TIMEOUT_SECONDS = 15.0
FIX_TIMEOUT_SECONDS = 15.0


def privileged(args: list[str]) -> list[str]:
    return list(args) if running_as_root() else ["sudo", "-n", *args]


def authenticate(runner: ProcessRunnerPort) -> bool:
    """A appeler ecran suspendu : `sudo -v` demande le mot de passe sur le terminal. Root : rien a faire."""
    return running_as_root() or runner.run_interactive(["sudo", "-v"]) == 0


def read_privileged(runner: ProcessRunnerPort, path: str) -> str:
    """Contenu complet du log. LogPermissionError si sudo refuse (authentification expiree, sudoers)."""
    result = runner.run(privileged(["cat", "--", path]), timeout=READ_TIMEOUT_SECONDS)
    if not result.ok:
        raise LogPermissionError(path)
    return result.stdout


def read_privileged_sample(runner: ProcessRunnerPort, path: str, size: int, sample_bytes: int) -> tuple[str, str] | None:
    """(debut, fin) du fichier, `sample_bytes` octets chacun ; None si sudo refuse."""
    head = runner.run(privileged(["head", "-c", str(sample_bytes), "--", path]), timeout=SAMPLE_TIMEOUT_SECONDS)
    if not head.ok:
        return None
    if size <= sample_bytes:
        return head.stdout, head.stdout
    tail = runner.run(privileged(["tail", "-c", str(sample_bytes), "--", path]), timeout=SAMPLE_TIMEOUT_SECONDS)
    return (head.stdout, tail.stdout) if tail.ok else None


def sudo_fix_commands(code: str, path: str, account: str | None) -> list[list[str]]:
    """Commandes de correction d'un constat de Sante des logs ; [] si sudo n'y peut rien de sur."""
    if code == "writer_cannot_write" and account:
        return [["chgrp", account, "--", path], ["chmod", "g+w", "--", path]]
    if code == "world_writable":
        return [["chmod", "o-w", "--", path]]
    return []


def shown_command(commands: list[list[str]]) -> str:
    """Les commandes telles qu'affichees avant confirmation (sans le `-n` technique)."""
    prefix = "" if running_as_root() else "sudo "
    return " && ".join(prefix + " ".join(part for part in command if part != "--") for command in commands)


def run_sudo_fix(runner: ProcessRunnerPort, commands: list[list[str]]) -> str | None:
    """Lance les commandes dans l'ordre ; message d'erreur de la premiere qui echoue, None si tout passe."""
    for command in commands:
        result = runner.run(privileged(command), timeout=FIX_TIMEOUT_SECONDS)
        if not result.ok:
            return (result.stderr or result.stdout).strip() or str(result.returncode)
    return None
