"""Sondes systeme reelles (plan interface §3.3, tableau §7.2 de la
spec repris tel quel). Le jeu de sondes est 100% propre a SERV (fire ne
sonde que nftables/iptables/fail2ban/conntrack, rien de reutilisable
ici) - chaque sonde construit directement sa `Capability`, pas
d'indirection via un mapper generique de type "resultat de commande"/
"resultat de service" (omega-fire en a un, `CapabilityMapper`, mais ses
2 formes ne correspondent a aucune des sondes SERV reelles - en
inventer une troisieme juste pour le faire correspondre n'aurait rien
apporte de reel). CGI volontairement absent (retire du perimetre V1,
§13 README) - aucune Capability generee pour cette ligne."""
from __future__ import annotations

import importlib.metadata
import importlib.util
import resource
import shutil
import socket
import sys
from pathlib import Path

from omega_serv.core.capability import Capability, CapabilityStatus
from omega_serv.core.platform_info import MIN_PYTHON_VERSION, python_version_supported
from omega_serv.infrastructure.services.detector import detect_service_manager_type
from omega_serv.ports.filesystem_port import FilesystemPort

_MIN_FD_SOFT_LIMIT = 1024
_MIN_DISK_FREE_BYTES = 100 * 1024 * 1024
_OPTIONAL_BINARIES = ("logrotate", "openssl", "tailscale", "lnav", "certbot", "scp")
"""`certbot` (etude OMEGA-SERV_PLAN-DETAILLE_TLS_AUTO.md, Phase 1) : simple
detection en lecture seule (comme les autres binaires ci-dessus) - aucune
ecriture, aucun appel a certbot lui-meme. Le pont Certbot -> secure/
certificates/ (import de certificat, hook de renouvellement) reste a
construire en phases suivantes, hors de ce fichier.

`scp` (OMEGA-SERV_ETUDE-FAISABILITE_LOGS_DISTANTS.md, 2026-10-15) :
meme regime - detection LOCALE de la presence du binaire uniquement,
jamais un test de joignabilite d'un hote distant (qui exigerait deja
une tentative de connexion, hors perimetre de ce scanner). Purement
informatif : aucun autre ecran ne bloque un bouton sur cette capacite,
`SubprocessRunner` produit deja un message "commande introuvable" clair
si `scp` est absent au moment d'une recuperation reelle."""
_REVERSE_PROXY_BINARIES = ("nginx", "caddy")


class SystemCapabilityScanner:
    """Implementation reelle de CapabilityScannerPort. `configured_port`
    et `fastcgi_socket` sont figes a la construction (deja resolus
    depuis la configuration chargee par l'appelant) - `scan()` lui-meme
    ne prend aucun parametre, conformement au port."""

    def __init__(
        self,
        project_root: Path,
        filesystem: FilesystemPort,
        configured_port: int,
        fastcgi_socket: Path | None,
    ) -> None:
        self._project_root = project_root
        self._filesystem = filesystem
        self._configured_port = configured_port
        self._fastcgi_socket = fastcgi_socket

    def scan(self) -> tuple[Capability, ...]:
        capabilities: list[Capability] = [
            self._probe_service_manager(),
            self._probe_python_version(),
            self._probe_port(self._configured_port, "port-configure", "Port configure"),
            *self._probe_fastcgi_socket(),
            self._probe_magnet_dependency(),
            *(self._probe_binary(name, (name,), "outil") for name in _OPTIONAL_BINARIES),
            self._probe_directory("var"),
            self._probe_directory("secure"),
            self._probe_directory("webroot"),
            self._probe_disk_space("var/log", "espace-disque-logs"),
            self._probe_disk_space("var/uploads", "espace-disque-uploads"),
            self._probe_fd_limit(),
            self._probe_port(80, "port-80", "Port 80"),
            self._probe_port(443, "port-443", "Port 443"),
            self._probe_reverse_proxy(),
        ]
        return tuple(capabilities)

    def _probe_service_manager(self) -> Capability:
        manager_type = detect_service_manager_type()
        if manager_type is None:
            return Capability(
                id="service-manager", status=CapabilityStatus.MISSING,
                reason="Aucun gestionnaire de service reconnu (systemd/OpenRC/runit)", category="systeme",
            )
        return Capability(
            id="service-manager", status=CapabilityStatus.AVAILABLE,
            reason=f"Gestionnaire detecte : {manager_type}", category="systeme",
        )

    def _probe_python_version(self) -> Capability:
        version = f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}"
        if python_version_supported():
            return Capability(
                id="python-version", status=CapabilityStatus.AVAILABLE,
                reason=f"Python {version} (minimum requis {'.'.join(map(str, MIN_PYTHON_VERSION))})",
                category="systeme",
            )
        return Capability(
            id="python-version", status=CapabilityStatus.DISQUALIFIED,
            reason=f"Python {version} trop ancien (minimum requis {'.'.join(map(str, MIN_PYTHON_VERSION))})",
            category="systeme",
        )

    def _probe_port(self, port: int, capability_id: str, label: str) -> Capability:
        try:
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
                sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
                sock.bind(("0.0.0.0", port))
        except PermissionError:
            return Capability(
                id=capability_id, status=CapabilityStatus.DEGRADED,
                reason=f"{label} : liaison refusee (privileges insuffisants pour un port < 1024)", category="reseau",
            )
        except OSError as exc:
            return Capability(
                id=capability_id, status=CapabilityStatus.MISSING,
                reason=f"{label} : deja occupe ({exc.strerror or exc})", category="reseau",
            )
        return Capability(
            id=capability_id, status=CapabilityStatus.AVAILABLE, reason=f"{label} : libre", category="reseau",
        )

    def _probe_fastcgi_socket(self) -> tuple[Capability, ...]:
        if self._fastcgi_socket is None:
            return ()
        try:
            with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as sock:
                sock.settimeout(1.0)
                sock.connect(str(self._fastcgi_socket))
        except OSError as exc:
            return (Capability(
                id="fastcgi-socket", status=CapabilityStatus.MISSING,
                reason=f"Socket PHP-FPM injoignable ({self._fastcgi_socket}) : {exc.strerror or exc}",
                category="fastcgi",
            ),)
        return (Capability(
            id="fastcgi-socket", status=CapabilityStatus.AVAILABLE,
            reason=f"Socket PHP-FPM operationnel ({self._fastcgi_socket})", category="fastcgi",
        ),)

    def _probe_magnet_dependency(self) -> Capability:
        """Script WAF complementaire "magnet" (options.waf.magnet,
        infrastructure/waf/lua_waf_adapter.py) - correction d'une sonde
        anterieure qui testait un binaire systeme `lua`/`lua5.4` sur le
        PATH, SANS RAPPORT avec le besoin reel : `lupa` embarque son
        propre runtime Lua statiquement compile (confirme empiriquement,
        voir D4 du plan d'integration magnet) et ne requiert AUCUN
        interpreteur `lua` systeme. L'ancienne sonde pouvait donc
        afficher AVAILABLE alors que magnet etait inutilisable (lupa
        absent) et inversement signaler MISSING sur une machine sans lua
        systeme alors que magnet fonctionnait parfaitement (lupa installe).
        La vraie dependance a sonder est le paquet Python 'lupa' lui-meme,
        extra optionnel (pyproject.toml, jamais installe par defaut).
        Detection par METADONNEES (`importlib.util.find_spec`/
        `importlib.metadata.version`), jamais un `import lupa` reel ici -
        ce fichier n'est PAS dans la liste d'exclusion du contrat
        import-linter "lupa seulement dans infrastructure.waf.
        lua_waf_adapter" (pyproject.toml), deliberement strict : seul ce
        module a le droit d'importer `lupa` pour de vrai."""
        if importlib.util.find_spec("lupa") is None:
            return Capability(
                id="waf-magnet", status=CapabilityStatus.MISSING,
                reason=(
                    "Dependance Python 'lupa' absente - requise pour le script WAF complementaire "
                    "'magnet' (options.waf.magnet, import d'un script mod_magnet externe sans le "
                    "reecrire). Installer l'extra optionnel : pip install -e \".[magnet]\"."
                ),
                category="waf",
            )
        try:
            version = importlib.metadata.version("lupa")
        except importlib.metadata.PackageNotFoundError:
            version = "?"
        return Capability(
            id="waf-magnet", status=CapabilityStatus.AVAILABLE,
            reason=f"lupa {version} disponible - le script WAF complementaire 'magnet' est utilisable",
            category="waf",
        )

    def _probe_binary(self, capability_id: str, candidates: tuple[str, ...], category: str) -> Capability:
        for name in candidates:
            path = shutil.which(name)
            if path is not None:
                return Capability(
                    id=capability_id, status=CapabilityStatus.AVAILABLE, reason=f"{name} trouve : {path}",
                    category=category,
                )
        return Capability(
            id=capability_id, status=CapabilityStatus.MISSING,
            reason=f"Aucun de {', '.join(candidates)} trouve dans le PATH", category=category,
        )

    def _probe_directory(self, relative_path: str) -> Capability:
        path = self._project_root / relative_path
        capability_id = f"repertoire-{relative_path}"
        if not self._filesystem.exists(path):
            return Capability(
                id=capability_id, status=CapabilityStatus.MISSING, reason=f"{path} n'existe pas encore",
                category="filesystem",
            )
        if not self._filesystem.is_dir(path):
            return Capability(
                id=capability_id, status=CapabilityStatus.DISQUALIFIED,
                reason=f"{path} existe mais n'est pas un dossier", category="filesystem",
            )
        return Capability(
            id=capability_id, status=CapabilityStatus.AVAILABLE, reason=f"{path} present", category="filesystem",
        )

    def _probe_disk_space(self, relative_path: str, capability_id: str) -> Capability:
        path = self._project_root / relative_path
        probed_path = path if path.exists() else self._project_root
        try:
            usage = shutil.disk_usage(probed_path)
        except OSError as exc:
            return Capability(
                id=capability_id, status=CapabilityStatus.MISSING,
                reason=f"Impossible de sonder l'espace disque de {probed_path} : {exc}", category="filesystem",
            )
        detail = {"free_bytes": usage.free, "total_bytes": usage.total}
        if usage.free < _MIN_DISK_FREE_BYTES:
            return Capability(
                id=capability_id, status=CapabilityStatus.DEGRADED,
                reason=f"Espace disque faible sur {probed_path} : {usage.free // (1024 * 1024)} Mo libres",
                detail=detail, category="filesystem",
            )
        return Capability(
            id=capability_id, status=CapabilityStatus.AVAILABLE,
            reason=f"{usage.free // (1024 * 1024)} Mo libres sur {probed_path}", detail=detail, category="filesystem",
        )

    def _probe_fd_limit(self) -> Capability:
        soft_limit, hard_limit = resource.getrlimit(resource.RLIMIT_NOFILE)
        detail = {"soft": soft_limit, "hard": hard_limit}
        if soft_limit < _MIN_FD_SOFT_LIMIT:
            return Capability(
                id="limite-descripteurs", status=CapabilityStatus.DEGRADED,
                reason=f"Limite de descripteurs basse : {soft_limit} (recommande >= {_MIN_FD_SOFT_LIMIT})",
                detail=detail, category="systeme",
            )
        return Capability(
            id="limite-descripteurs", status=CapabilityStatus.AVAILABLE,
            reason=f"Limite de descripteurs : {soft_limit}", detail=detail, category="systeme",
        )

    def _probe_reverse_proxy(self) -> Capability:
        for name in _REVERSE_PROXY_BINARIES:
            path = shutil.which(name)
            if path is not None:
                return Capability(
                    id="reverse-proxy", status=CapabilityStatus.AVAILABLE,
                    reason=f"{name} trouve : {path}", category="reseau",
                )
        return Capability(
            id="reverse-proxy", status=CapabilityStatus.MISSING,
            reason="Aucun reverse proxy local detecte (nginx/caddy) - non bloquant", category="reseau",
        )
