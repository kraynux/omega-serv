"""Enregistrement (bookkeeping seul) des automatisations de rotation de
logs demandees par l'utilisateur - meme comportement que
omega-fire/interfaces/tui/screens/rotate_logs_screen.py::scheduled_
rotations.json : une regle enregistree ici declare l'INTENTION d'une
rotation periodique (frequence + log cible), mais rien dans ce fichier
ni ailleurs cote SERV ne l'execute automatiquement - omega-fire lui-meme
n'a aucun executeur reel pour ce mecanisme (verifie directement dans son
code), ce n'est donc pas une regression par rapport a la reference mais
une fidelite honnete a son comportement reel. Une vraie execution
periodique (cron/systemd timer/tache de fond dans le serveur asyncio)
resterait a construire separement si un besoin confirme apparait."""
from __future__ import annotations

import json
from pathlib import Path


class RotationAutomationStore:
    def __init__(self, path: Path) -> None:
        self._path = path

    def list_all(self) -> list[dict[str, object]]:
        if not self._path.exists():
            return []
        try:
            data: list[dict[str, object]] = json.loads(self._path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return []
        return data

    def add(self, automation: dict[str, object]) -> None:
        automations = self.list_all()
        automations.append(automation)
        self._save(automations)

    def delete(self, index: int) -> bool:
        automations = self.list_all()
        if not (0 <= index < len(automations)):
            return False
        automations.pop(index)
        self._save(automations)
        return True

    def _save(self, automations: list[dict[str, object]]) -> None:
        self._path.parent.mkdir(parents=True, exist_ok=True)
        self._path.write_text(json.dumps(automations, indent=2, ensure_ascii=False), encoding="utf-8")
