# Copyright (c) 2026 kraynux - kraynux@proton.me - Licence MIT (voir fichier LICENSE)
"""Adaptateur systeme de l'ecran Configuration distante (lot 8) : voir ports/admin_web_setup_port.py."""
from __future__ import annotations

import errno
import grp
import ipaddress
import json
import os
import socket
from pathlib import Path

import psutil

from omega_serv.core.i18n import _
from omega_serv.ports.admin_web_setup_port import (
    LISTEN_DENIED,
    LISTEN_IN_USE,
    LISTEN_NO_ADDRESS,
    SHARE_NEEDS_PRIVILEGE,
    SHARE_NO_GROUP,
    FirewallOpening,
)
from omega_serv.ports.process_runner_port import ProcessRunnerPort

FIREWALLS = ("ufw", "firewalld", "nftables")


class SystemAdminWebSetup:
    def __init__(self, process: ProcessRunnerPort) -> None:
        self._process = process

    def can_listen(self, bind: str, port: int) -> str:
        host = bind or "0.0.0.0"
        try:
            family = socket.AF_INET6 if ipaddress.ip_address(host).version == 6 else socket.AF_INET
        except ValueError:
            family = socket.AF_INET
        try:
            with socket.socket(family, socket.SOCK_STREAM) as probe:
                probe.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)  # comme le serveur (asyncio)
                probe.bind((host, port))
                probe.listen(1)
        except OSError as error:
            if error.errno == errno.EADDRINUSE:
                return LISTEN_IN_USE
            if error.errno == errno.EADDRNOTAVAIL:
                return LISTEN_NO_ADDRESS
            if error.errno == errno.EACCES:
                return LISTEN_DENIED
            return error.strerror or str(error)
        return ""

    def machine_names(self) -> tuple[str, tuple[str, ...]]:
        addresses: list[str] = []
        try:
            interfaces = psutil.net_if_addrs()
        except OSError:
            interfaces = {}
        for entries in interfaces.values():
            for entry in entries:
                if entry.family not in (socket.AF_INET, socket.AF_INET6):
                    continue
                text = entry.address.split("%", 1)[0]
                try:
                    parsed = ipaddress.ip_address(text)
                except ValueError:
                    continue
                if not parsed.is_link_local and text not in addresses:
                    addresses.append(text)
        if "127.0.0.1" not in addresses:
            addresses.insert(0, "127.0.0.1")
        return socket.gethostname(), tuple(addresses)

    def active_firewall(self) -> str:
        for name in FIREWALLS:
            try:
                result = self._process.run(["systemctl", "is-active", "--quiet", f"{name}.service"], timeout=3)
            except OSError:
                return ""
            if result.returncode == 0:
                return name
            if result.returncode == 127:  # pas de systemctl
                return ""
        return ""

    def share_with_group(self, directories: tuple[Path, ...], key: Path, certificate: Path, group: str, *,
                         privileged: bool) -> str:
        try:
            gid = grp.getgrnam(group).gr_gid
        except KeyError:
            return SHARE_NO_GROUP
        modes = [*((path, 0o750) for path in directories), (key, 0o640), (certificate, 0o644)]
        links = [str(path) for path, _mode in modes if path.is_symlink()]
        if links:  # jamais de droits poses au travers d'un lien
            return _("lien symbolique refusé : {paths}").format(paths=", ".join(links))
        if not privileged:
            if gid != os.getegid() and gid not in os.getgroups():
                return SHARE_NEEDS_PRIVILEGE
            try:
                for path, mode in modes:
                    os.chown(path, -1, gid, follow_symlinks=False)
                    os.chmod(path, mode)
            except PermissionError:
                return SHARE_NEEDS_PRIVILEGE
            except OSError as error:
                return error.strerror or str(error)
            return ""
        prefix: list[str] = []
        if os.geteuid() != 0:
            if self._process.run_interactive(["sudo", "-v"]) != 0:
                return "sudo"
            prefix = ["sudo"]
        commands = [[*prefix, "chgrp", "-h", group, *(str(path) for path, _mode in modes)]]
        commands += [[*prefix, "chmod", oct(mode)[2:], str(path)] for path, mode in modes]
        for command in commands:
            result = self._process.run(command, timeout=30)
            if not result.ok:
                return result.stderr.strip() or _("code {code}").format(code=result.returncode)
        return ""

    # ------------------------------------------------------------------ pare-feu relie (sous-lot 8b)
    def linked_firewall(self, project_root: Path) -> str:
        from omega_lib.infrastructure.synchro.files import read_contract, zone_dir
        from omega_lib.synchro.constants import TOOL_LAUNCHERS, ZONE_REGISTRY
        from omega_lib.synchro.registry import ZoneState, registry_from_dict

        result = read_contract(zone_dir() / ZONE_REGISTRY, registry_from_dict)  # jamais d'exception
        registry = result.value
        if registry is None or registry.state is not ZoneState.ACTIVE:
            return ""
        mine = project_root.resolve()
        if not any(entry.tool == "omega-serv" and _same_path(entry.root, mine) for entry in registry.installations):
            return ""
        fire = next((entry for entry in registry.installations if entry.tool == "omega-fire"), None)
        if fire is None:
            return ""
        launcher = Path(fire.root) / TOOL_LAUNCHERS["omega-fire"]
        return str(launcher) if launcher.is_file() and not launcher.is_symlink() else ""

    def open_firewall_port(self, launcher: str, port: int, sources: tuple[str, ...], label: str) -> FirewallOpening:
        prefix: list[str] = []
        if os.geteuid() != 0:
            if self._process.run_interactive(["sudo", "-v"]) != 0:
                return FirewallOpening(False, error="sudo")
            prefix = ["sudo", "-n"]
        result = self._process.run([*prefix, launcher, "port", "ouvrir", "--port", str(port), "--sources",
                                    ",".join(sources), "--pour", label, "--format", "json"], timeout=180)
        try:
            data = json.loads(result.stdout.strip().splitlines()[-1])
        except (ValueError, IndexError):
            data = None
        if not isinstance(data, dict):
            return FirewallOpening(False, error=result.stderr.strip()[-300:] or _("code {code}").format(
                code=result.returncode))
        lines = tuple((str(line.get("cible", "")), str(line.get("source", "")), str(line.get("etat", "")))
                      for line in data.get("lignes", []) if isinstance(line, dict))
        ok = data.get("ok") is True and result.ok
        error = "" if ok else (str(data.get("erreur") or "") or result.stderr.strip()[-300:])
        return FirewallOpening(ok, lines, error)


def _same_path(raw: str, mine: Path) -> bool:
    try:
        return Path(raw).resolve() == mine
    except (OSError, ValueError):
        return False

