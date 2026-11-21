"""Reglages de l'option « administration web » (`options.admin_web`), lot 2 du plan
OMEGA-SERV_PLAN-DETAILLE_TABLEAU_DE_BORD_WEB.md (decisions de l'auteur du 2026-11-16).

Le tableau de bord web est servi par un processus d'administration a part, sur son propre port, jamais sur le port
public. Regles :
- defaut sur : boucle locale (127.0.0.1), port 9643, sans TLS ;
- hors boucle locale, TLS obligatoire (certificat du site ou certificat dedie) ;
- reseaux permis par defaut (Q6) : boucle locale, Tailscale et LAN ; une adresse hors liste recoit 403 avant meme la
  page de connexion ; l'authentification reste toujours exigee (lot 3)."""
from __future__ import annotations

import ipaddress
from dataclasses import dataclass, field
from typing import Any, Literal

from omega_lib.theme.policies import TUI_THEMES

from omega_serv.core.i18n import _
from omega_serv.domain.admin_web.alerts import threshold_errors

OPTION_NAME = "admin_web"
TlsSource = Literal["none", "site", "own"]
TLS_SOURCES: tuple[TlsSource, ...] = ("none", "site", "own")

DEFAULT_BIND = "127.0.0.1"
DEFAULT_PORT = 9643
DEFAULT_CERTIFICATE = "secure/certificates/admin/admin.pem"
DEFAULT_PRIVATE_KEY = "secure/certificates/admin/admin.key"
DEFAULT_ALLOWED_NETWORKS: tuple[str, ...] = (
    "127.0.0.0/8", "::1/128",                                   # la machine elle-meme
    "100.64.0.0/10", "fd7a:115c:a1e0::/48",                     # Tailscale
    "10.0.0.0/8", "172.16.0.0/12", "192.168.0.0/16", "fc00::/7",  # LAN
)


@dataclass(frozen=True)
class AdminWebSettings:
    bind: str = DEFAULT_BIND
    port: int = DEFAULT_PORT
    tls: str = "none"
    """none : HTTP (boucle locale seulement) ; site : certificat du site (tls.certificate) ; own : certificat dedie."""
    certificate_path: str = DEFAULT_CERTIFICATE
    private_key_path: str = DEFAULT_PRIVATE_KEY
    allowed_networks: tuple[str, ...] = field(default=DEFAULT_ALLOWED_NETWORKS)
    history: bool = True
    """Graphes 1 h et 24 h (lot 7) : releve toutes les 10 s par le processus d'administration ; false l'arrete."""
    theme: str = "tui"
    alerts: Any = None
    stats_mask_ip: bool = False
    """Vue Trafic (etude modules, module 2) : adresses IP des visiteurs masquees (dernier octet, /48 en IPv6)."""
    """Alertes locales (etude modules, module 1) : {regle: seuil ou false} ; absent = seuils par defaut."""
    """Theme du panneau (plan §9.7, 2026-11-17) : « tui » suit le theme de la TUI de l'instance, sinon l'un des 10."""

    @classmethod
    def from_settings(cls, settings: dict[str, Any]) -> AdminWebSettings:
        """Valeurs brutes gardees telles quelles (types compris) : `validate_admin_web` les refuse avec un message
        clair plutot qu'une conversion silencieuse."""
        defaults = cls()
        networks = settings.get("allowed_networks", list(defaults.allowed_networks))
        return cls(
            bind=settings.get("bind", defaults.bind),
            port=settings.get("port", defaults.port),
            tls=settings.get("tls", defaults.tls),
            certificate_path=settings.get("certificate_path", defaults.certificate_path),
            private_key_path=settings.get("private_key_path", defaults.private_key_path),
            allowed_networks=tuple(networks) if isinstance(networks, list | tuple) else networks,
            history=settings.get("history", defaults.history),
            theme=settings.get("theme", defaults.theme),
            alerts=settings.get("alerts"),
            stats_mask_ip=settings.get("stats_mask_ip", defaults.stats_mask_ip),
        )

    def to_settings(self) -> dict[str, Any]:
        return {"bind": self.bind, "port": self.port, "tls": self.tls, "certificate_path": self.certificate_path,
                "private_key_path": self.private_key_path, "allowed_networks": list(self.allowed_networks),
                "history": self.history, "theme": self.theme, "stats_mask_ip": self.stats_mask_ip,
                **({"alerts": self.alerts} if self.alerts is not None else {})}

    @property
    def local_only(self) -> bool:
        return is_loopback_bind(self.bind)

    @property
    def url(self) -> str:
        host = f"[{self.bind}]" if ":" in str(self.bind) else self.bind
        return f"{'http' if self.tls == 'none' else 'https'}://{host}:{self.port}/"


def is_loopback_bind(bind: object) -> bool:
    try:
        return ipaddress.ip_address(str(bind)).is_loopback
    except ValueError:
        return str(bind) == "localhost"


def binds_overlap(first: str, second: str) -> bool:
    """Deux ecoutes sur le meme port se genent si les adresses sont egales ou si l'une ecoute partout."""
    def unspecified(bind: str) -> bool:
        try:
            return ipaddress.ip_address(bind).is_unspecified
        except ValueError:
            return False
    return first == second or unspecified(first) or unspecified(second)


def validate_admin_web(settings: AdminWebSettings, *, server_bind: str, server_port: int) -> list[str]:
    errors: list[str] = []
    prefix = "options.admin_web"
    if not isinstance(settings.bind, str) or not settings.bind:
        errors.append(_("{prefix}.bind doit être une adresse IP").format(prefix=prefix))
    else:
        try:
            ipaddress.ip_address(settings.bind)
        except ValueError:
            errors.append(_("{prefix}.bind doit être une adresse IP (reçu : {value!r})").format(
                prefix=prefix, value=settings.bind))
    port_ok = isinstance(settings.port, int) and not isinstance(settings.port, bool) and 1 <= settings.port <= 65535
    if not port_ok:
        errors.append(_("{prefix}.port doit être un entier de 1 à 65535").format(prefix=prefix))
    if settings.tls not in TLS_SOURCES:
        errors.append(_("{prefix}.tls invalide : {value!r} (attendu : none, site ou own)").format(
            prefix=prefix, value=settings.tls))
    elif settings.tls == "none" and isinstance(settings.bind, str) and not is_loopback_bind(settings.bind):
        errors.append(_("{prefix} : hors de la boucle locale ({bind}), TLS est obligatoire (tls = site ou own)").format(
            prefix=prefix, bind=settings.bind))
    if settings.tls == "own":
        for key, value in (("certificate_path", settings.certificate_path), ("private_key_path", settings.private_key_path)):
            if not isinstance(value, str) or not value.strip():
                errors.append(_("{prefix}.{key} ne peut pas être vide avec tls = own").format(prefix=prefix, key=key))
    if not isinstance(settings.history, bool):
        errors.append(_("{prefix}.history doit être true ou false").format(prefix=prefix))
    if settings.theme != "tui" and settings.theme not in TUI_THEMES:
        errors.append(_("{prefix}.theme inconnu : {value!r} (attendu : tui ou l'un des thèmes omega)").format(
            prefix=prefix, value=settings.theme))
    if not isinstance(settings.stats_mask_ip, bool):
        errors.append(_("{prefix}.stats_mask_ip doit être true ou false").format(prefix=prefix))
    for key, rule in threshold_errors(settings.alerts):
        errors.append(_("{prefix}.alerts.{key} : seuil de {low:g} à {high:g} ou false").format(
            prefix=prefix, key=key or "?", low=rule.low, high=rule.high))
    if not isinstance(settings.allowed_networks, tuple) or not settings.allowed_networks:
        errors.append(_("{prefix}.allowed_networks doit être une liste non vide de réseaux").format(prefix=prefix))
    else:
        for network in settings.allowed_networks:
            try:
                ipaddress.ip_network(str(network), strict=False)
            except ValueError:
                errors.append(_("{prefix}.allowed_networks : réseau invalide {value!r}").format(
                    prefix=prefix, value=network))
    if port_ok and isinstance(settings.bind, str) and settings.port == server_port and binds_overlap(
            settings.bind, server_bind):
        errors.append(_("{prefix}.port ({port}) est celui du site : l'administration web a toujours son propre "
                        "port").format(prefix=prefix, port=settings.port))
    return errors
