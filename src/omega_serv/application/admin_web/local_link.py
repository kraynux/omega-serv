"""« Relier au maître » entre deux instances de CETTE machine (ecran Instances ; decisions de l'auteur du
2026-11-16 : chaque liaison passe par la commande de l'instance elle-meme ; omega-serv ne gere que ses propres
instances, les autres machines passent par le code d'appairage, ou plus tard par omega-connect).

Ordre : identite du maitre (`admin-web instances identity`, sur le maitre) -> l'instance suivie accepte ce maitre
(`admin-web master accept`, sur elle : jeton cree, seul son hache est garde, jeton + empreinte rendus une fois) ->
le maitre enregistre l'instance (`admin-web instances add`, jeton lu sur l'entree standard, jamais sur la ligne de
commande). Si le maitre refuse l'ajout, le maitre fraichement accepte est revoque aussitot sur l'instance suivie :
pas de jeton orphelin."""
from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

from omega_serv.core.i18n import _
from omega_serv.domain.admin_web.master import RIGHTS, valid_fingerprint, valid_master_id
from omega_serv.ports.instance_command_port import CommandReply, InstanceCommandPort

EXIT_MASTER_EXISTS = 3
"""Meme valeur que `interfaces/cli/admin_web_commands.py::EXIT_MASTER_EXISTS` (contrat de la commande)."""


@dataclass(frozen=True)
class LocalLinkRequest:
    follower_root: Path
    follower_name: str
    follower_address: str
    """Adresse par laquelle le maitre joint l'administration de l'instance suivie (domain.local_admin_address)."""
    follower_port: int
    master_root: Path
    rights: str
    replace: bool = False


@dataclass(frozen=True)
class LocalLinkOutcome:
    ok: bool
    message: str
    exists: bool = False
    """L'instance suivie a deja un autre maitre : redemander avec `replace=True` apres confirmation."""


def _json_line(reply: CommandReply) -> dict[str, object] | None:
    """Derniere ligne JSON de la sortie (une banniere eventuelle avant est ignoree)."""
    for line in reversed(reply.stdout.splitlines()):
        line = line.strip()
        if line.startswith("{"):
            try:
                data = json.loads(line)
            except ValueError:
                return None
            return data if isinstance(data, dict) else None
    return None


def _failure(step: str, reply: CommandReply) -> LocalLinkOutcome:
    return LocalLinkOutcome(False, _("{step} : échec ({reason}).").format(
        step=step, reason=reply.last_line() or _("code {code}").format(code=reply.code)))


def link_local_master(runner: InstanceCommandPort, request: LocalLinkRequest) -> LocalLinkOutcome:
    if request.rights not in RIGHTS:
        return LocalLinkOutcome(False, _("Droits inconnus."))
    if request.follower_root == request.master_root:
        return LocalLinkOutcome(False, _("Une instance ne peut pas être son propre maître."))

    reply = runner.run(request.master_root, ("admin-web", "instances", "identity"))
    identity = _json_line(reply) if reply.code == 0 else None
    master_id = identity.get("maitre_id") if identity else None
    master_name = str(identity.get("nom", "")) if identity else ""
    if identity is None or not valid_master_id(master_id):
        return _failure(_("Identité du maître"), reply)
    assert isinstance(master_id, str)

    accept = ["admin-web", "master", "accept", "--master-id", master_id, "--master-name", master_name,
              "--rights", request.rights]
    if request.replace:
        accept.append("--replace")
    reply = runner.run(request.follower_root, accept)
    if reply.code == EXIT_MASTER_EXISTS:
        return LocalLinkOutcome(False, reply.last_line(), exists=True)
    given = _json_line(reply) if reply.code == 0 else None
    token = given.get("jeton") if given else None
    fingerprint = given.get("empreinte") if given else None
    if given is None or not isinstance(token, str) or not token or not valid_fingerprint(fingerprint):
        return _failure(_("Acceptation du maître sur {name}").format(name=request.follower_name), reply)
    assert isinstance(fingerprint, str)

    reply = runner.run(request.master_root, (
        "admin-web", "instances", "add", request.follower_address, str(request.follower_port),
        "--fingerprint", fingerprint, "--name", request.follower_name), stdin=token + "\n")
    if reply.code != 0:
        runner.run(request.follower_root, ("admin-web", "master", "revoke"))
        return _failure(_("Ajout de {name} sur le maître").format(name=request.follower_name), reply)
    rights = {"lecture": _("lecture"), "administration": _("administration")}[request.rights]
    return LocalLinkOutcome(True, _("{name} est reliée au maître {master} (droits : {rights}). Elle apparaît dans "
                                    "la page Instances du tableau de bord web du maître.").format(
        name=request.follower_name, master=master_name or master_id[:8], rights=rights))
