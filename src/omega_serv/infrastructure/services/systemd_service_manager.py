"""Implementation reelle de ServiceManagerPort pour systemd - portee
depuis omega-fire (infrastructure/backends/service_manager/systemd.py,
audite reutilisable, voir OMEGA-SERV_PLAN_DEVELOPPEMENT.md §5), commandes
`systemctl` inchangees. Difference avec l'original : passe par
ProcessRunnerPort (deja construit Phase 6 pour openssl, generique) au
lieu d'appeler `subprocess` directement - seul point technique adapte
a la convention deja en place dans ce projet, la logique metier
(codes de retour, parsing du texte de statut) reste identique.

Elevation de privileges (plan interface §3.6, 2026-09-08) : les
operations mutantes (start/stop/restart/enable/disable, daemon-reload,
ecriture/suppression du fichier d'unite) prefixent leur commande par
`sudo` UNIQUEMENT si le processus courant n'est pas deja root
(`running_as_root()`) - jamais en exigeant que l'application entiere
soit lancee en root (omega-serv refuse deja root pour `serve` lui-meme,
meme principe applique ici a l'envers : elevation ponctuelle par
action, pas par lancement). Les operations en lecture seule
(status/is-active/is-enabled/--version) restent toujours non
privilegiees - systemd les autorise nativement a tout utilisateur."""
from __future__ import annotations

from pathlib import Path

from omega_serv.core.platform_info import running_as_root
from omega_serv.domain.services.entities import ServiceStatus
from omega_serv.domain.services.exceptions import (
    ServiceControlError,
    ServiceNotFoundError,
    ServiceStatusError,
)
from omega_serv.ports.process_runner_port import ProcessResult, ProcessRunnerPort
from omega_serv.ports.service_manager_port import ServiceManagerType

_TIMEOUT_SECONDS = 10.0
"""`systemctl` interroge le bus systemd/D-Bus - s'il ne repond pas
(bus indisponible, machine chargee), l'appel peut bloquer indefiniment.
Retour utilisateur 2026-09-21 (Archcraft) : sans timeout, cet appel
synchrone geait l'ecran Etat & Ressources (boucle asyncio Textual unique,
aucun Ctrl+C possible - kill obligatoire)."""
_TIMEOUT_RETURNCODE = 124
_NOT_FOUND_RETURNCODE = 127


class SystemdServiceManager:
    def __init__(self, process_runner: ProcessRunnerPort):
        self._runner = process_runner
        self._systemctl = "systemctl"

    def manager_type(self) -> ServiceManagerType:
        return "systemd"

    def _run_privileged(self, args: list[str], input_text: str | None = None) -> ProcessResult:
        if running_as_root():
            return self._runner.run(args, input_text=input_text, timeout=_TIMEOUT_SECONDS)

        auth_code = self._runner.run_interactive(["sudo", "-v"])
        if auth_code != 0:
            return ProcessResult(returncode=auth_code, stdout="", stderr="Authentification sudo echouee ou annulee.")
        return self._runner.run(["sudo", *args], input_text=input_text, timeout=_TIMEOUT_SECONDS)

    def _control(self, service_name: str, operation: str) -> bool:
        result = self._run_privileged([self._systemctl, operation, service_name])
        if result.returncode == 0:
            return True
        if result.returncode == 5:
            raise ServiceNotFoundError(service_name, "systemd")
        raise ServiceControlError(service_name, operation, result.stderr.strip() or f"code {result.returncode}", "systemd")

    def start(self, service_name: str) -> bool:
        return self._control(service_name, "start")

    def stop(self, service_name: str) -> bool:
        return self._control(service_name, "stop")

    def restart(self, service_name: str) -> bool:
        return self._control(service_name, "restart")

    def reload(self, service_name: str) -> bool:
        return self._control(service_name, "reload")

    def enable(self, service_name: str) -> bool:
        return self._control(service_name, "enable")

    def disable(self, service_name: str) -> bool:
        return self._control(service_name, "disable")

    def status(self, service_name: str) -> ServiceStatus:
        result = self._runner.run([self._systemctl, "status", service_name], timeout=_TIMEOUT_SECONDS)
        if result.returncode in (_TIMEOUT_RETURNCODE, _NOT_FOUND_RETURNCODE):
            raise ServiceStatusError(
                service_name,
                f"{result.stderr.strip()} - verifiez `systemctl status {service_name}` manuellement, "
                "ou (re)installez le service depuis l'ecran SERVICE",
                "systemd",
            )
        if result.returncode == 4:
            raise ServiceNotFoundError(service_name, "systemd")
        active = result.returncode in (0, 3)
        return ServiceStatus(
            service_name=service_name,
            active=active,
            enabled=self.is_enabled(service_name),
            state=self._parse_state(result.stdout),
            sub_state=self._parse_sub_state(result.stdout),
            description=self._parse_description(result.stdout),
        )

    def is_active(self, service_name: str) -> bool:
        result = self._runner.run([self._systemctl, "is-active", service_name], timeout=_TIMEOUT_SECONDS)
        return result.returncode == 0

    def is_enabled(self, service_name: str) -> bool:
        result = self._runner.run([self._systemctl, "is-enabled", service_name], timeout=_TIMEOUT_SECONDS)
        return result.returncode == 0

    def is_available(self) -> bool:
        result = self._runner.run([self._systemctl, "--version"], timeout=_TIMEOUT_SECONDS)
        return result.returncode == 0

    def reload_daemon(self) -> bool:
        """Pas dans ServiceManagerPort (specifique a systemd - OpenRC et
        runit n'ont pas d'equivalent) : necessaire apres avoir ecrit ou
        retire un fichier d'unite, pour que systemd relise sa config
        sans redemarrer quoi que ce soit. Les appelants generiques
        (application/services/install_service.py) testent sa presence
        via `getattr` avant de l'appeler."""
        result = self._run_privileged([self._systemctl, "daemon-reload"])
        return result.returncode == 0

    def write_unit_file(self, unit_path: Path, content: str) -> None:
        """Pas dans ServiceManagerPort (specifique a systemd, meme
        raison que reload_daemon ci-dessus). Ecrit via `sudo tee` plutot
        que FilesystemPort : `/etc/systemd/system/` echappe au perimetre
        projet que FilesystemPort modelise (var/config/secure/webroot),
        c'est une ecriture privilegiee des le depart - jamais un
        write_text() suivi d'un chmod, ca echouerait deja a l'ecriture
        elle-meme si le processus n'est pas root."""
        result = self._run_privileged(["tee", str(unit_path)], input_text=content)
        if result.returncode != 0:
            raise ServiceControlError(
                str(unit_path), "write-unit-file", result.stderr.strip() or f"code {result.returncode}", "systemd"
            )

    def remove_unit_file(self, unit_path: Path) -> None:
        result = self._run_privileged(["rm", "-f", str(unit_path)])
        if result.returncode != 0:
            raise ServiceControlError(
                str(unit_path), "remove-unit-file", result.stderr.strip() or f"code {result.returncode}", "systemd"
            )

    def create_system_user(self, user: str, group: str) -> None:
        """Cree le compte systeme dedie (retour utilisateur 2026-09-10,
        vrai bug trouve : l'unite generee referencait toujours
        `User=omega-serv`/`Group=omega-serv` sans que rien ne les cree
        jamais - le service echouait a chaque demarrage, l'utilisateur
        n'existant pas). Idempotent : `groupadd`/`useradd` renvoient le
        code 9 si le groupe/utilisateur existe deja, traite comme un
        succes plutot qu'une erreur - jamais un echec de reinstallation.
        Compte systeme sans shell de connexion ni repertoire personnel
        (`--no-create-home`, `--shell /usr/sbin/nologin`) - jamais
        utilisable pour une connexion interactive."""
        _ALREADY_EXISTS = 9
        group_result = self._run_privileged(["groupadd", "--system", group])
        if group_result.returncode not in (0, _ALREADY_EXISTS):
            raise ServiceControlError(
                group, "create-system-group", group_result.stderr.strip() or f"code {group_result.returncode}", "systemd",
            )
        user_result = self._run_privileged([
            "useradd", "--system", "--no-create-home", "--shell", "/usr/sbin/nologin", "--gid", group, user,
        ])
        if user_result.returncode not in (0, _ALREADY_EXISTS):
            raise ServiceControlError(
                user, "create-system-user", user_result.stderr.strip() or f"code {user_result.returncode}", "systemd",
            )

    def remove_system_user(self, user: str, group: str) -> None:
        """Symetrique de `create_system_user` (OMEGA-SERV_PLAN-DETAILLE_
        MULTI_INSTANCE.md §9 Phase E) - appele par l'appelant SEULEMENT
        apres avoir verifie qu'aucune AUTRE unite installee ne
        reference plus ce compte (`find_account_in_use`, jamais fait
        ici : cette methode fait ce qu'on lui demande, sans re-verifier
        elle-meme). Idempotent comme `create_system_user` : code 6
        ("specified user/group doesn't exist") traite comme un succes,
        jamais une erreur - la suppression peut etre redemandee sans
        risque si le compte etait deja absent. `userdel` avant
        `groupdel` (jamais l'inverse) : le groupe reste le groupe
        primaire du compte tant que celui-ci existe, `groupdel` seul
        echouerait sinon (code 8, "cannot remove the user's primary
        group")."""
        _NOT_FOUND = 6
        user_result = self._run_privileged(["userdel", user])
        if user_result.returncode not in (0, _NOT_FOUND):
            raise ServiceControlError(
                user, "remove-system-user", user_result.stderr.strip() or f"code {user_result.returncode}", "systemd",
            )
        group_result = self._run_privileged(["groupdel", group])
        if group_result.returncode not in (0, _NOT_FOUND):
            raise ServiceControlError(
                group, "remove-system-group", group_result.stderr.strip() or f"code {group_result.returncode}", "systemd",
            )

    def grant_directory_access(self, path: Path, group: str, extra_user: str) -> None:
        """Partage `path` (typiquement `var/`) avec le compte systeme
        dedie (retour utilisateur 2026-09-10, second vrai bug trouve
        juste apres la creation du compte : le service crash-loopait
        toujours, `journalctl` montrant `PermissionError` en ecrivant
        le fichier PID - `ReadWritePaths=` (systemd_unit.py) leve
        uniquement la restriction sandbox de systemd, jamais les
        permissions Unix classiques du repertoire, restees
        `kraynux:kraynux 755` sans droit d'ecriture pour quiconque
        d'autre). Bascule le groupe proprietaire vers `group`, rend le
        groupe lecture/ecriture (+execution sur les repertoires via
        `g+rwX`), pose le bit setgid sur chaque repertoire (nouveaux
        fichiers/sous-repertoires heritent automatiquement de `group`),
        puis ajoute `extra_user` (l'utilisateur interactif qui installe
        l'unite) au groupe dedie - sans cette derniere etape, l'ecran
        Etat & Ressources (tourne comme `extra_user`, jamais comme le
        compte de service) ne pourrait toujours rien lire de ce que le
        service ecrit desormais. Voir aussi `systemd_unit.py::
        UMask=0007` (necessaire en plus de ceci : sans quoi les
        NOUVEAUX fichiers crees par le service restent illisibles au
        groupe malgre le repertoire partage)."""
        commands: list[tuple[list[str], str]] = [
            (["chgrp", "-R", group, str(path)], "grant-directory-access-chgrp"),
            (["chmod", "-R", "g+rwX", str(path)], "grant-directory-access-chmod"),
            (["find", str(path), "-type", "d", "-exec", "chmod", "g+s", "{}", "+"], "grant-directory-access-setgid"),
            (["usermod", "-aG", group, extra_user], "grant-directory-access-usermod"),
        ]
        for args, operation in commands:
            result = self._run_privileged(args)
            if result.returncode != 0:
                raise ServiceControlError(
                    str(path), operation, result.stderr.strip() or f"code {result.returncode}", "systemd",
                )

    @staticmethod
    def _parse_state(output: str) -> str:
        for line in output.split("\n"):
            if "Active:" in line:
                parts = line.split(":")
                if len(parts) > 1:
                    return parts[1].strip().split()[0]
        return "unknown"

    @staticmethod
    def _parse_sub_state(output: str) -> str:
        for line in output.split("\n"):
            if "Active:" in line:
                parts = line.split("(")
                if len(parts) > 1:
                    return parts[1].split(")")[0]
        return "unknown"

    @staticmethod
    def _parse_description(output: str) -> str:
        for line in output.split("\n"):
            stripped = line.strip()
            if stripped.startswith(("●", "○")):
                parts = line.split(" - ", 1)
                if len(parts) > 1:
                    return parts[1].strip()
        return ""
