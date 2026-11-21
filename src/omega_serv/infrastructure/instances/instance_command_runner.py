"""Lance la CLI d'une instance de cette machine avec SON environnement virtuel : `<racine>/.venv/bin/python -I -m
omega_serv --config <racine>/config/omega-serve.json ...`, par le lanceur de processus du projet (jamais de shell).
`-I` : ni PYTHONPATH ni le dossier courant de l'instance qui pilote ne peuvent glisser son code a la place de celui
de l'instance visee ; la racine du projet est deduite de l'emplacement reel du code (bootstrap/paths.py)."""
from __future__ import annotations

from collections.abc import Sequence
from pathlib import Path

from omega_serv.core.i18n import _
from omega_serv.domain.services.python_command import python_module_argv
from omega_serv.ports.instance_command_port import CommandReply
from omega_serv.ports.process_runner_port import ProcessRunnerPort

COMMAND_TIMEOUT_SECONDS = 60.0


class InstanceCommandRunner:
    def __init__(self, process: ProcessRunnerPort, timeout: float = COMMAND_TIMEOUT_SECONDS) -> None:
        self._process = process
        self._timeout = timeout

    def run(self, root: Path, arguments: Sequence[str], stdin: str = "") -> CommandReply:
        python = root / ".venv" / "bin" / "python"
        if not python.is_file():
            return CommandReply(127, "", _("environnement virtuel introuvable : {python}").format(python=python))
        done = self._process.run(python_module_argv(str(python), "omega_serv", "--config", str(root / "config" / "omega-serve.json"),
                                                     *arguments, source_root=str(root / "src")),
                                 input_text=stdin, timeout=self._timeout)
        return CommandReply(done.returncode, done.stdout, done.stderr)
