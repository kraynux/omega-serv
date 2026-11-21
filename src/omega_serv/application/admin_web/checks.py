"""Controles de l'administration web (tableau de bord web, lot 2, OMEGA-SERV_PLAN-DETAILLE_TABLEAU_DE_BORD_WEB.md).

Jamais un refus de demarrer le site : un probleme ici n'empeche que le processus d'administration (raison dans
error.log), et s'affiche en avertissement dans « Verifier la configuration » et `config check`. Les erreurs de
forme (port, adresse, TLS obligatoire hors boucle locale) sont, elles, des erreurs de configuration ordinaires
(domain/admin_web/settings.py::validate_admin_web)."""
from __future__ import annotations

from pathlib import Path

from omega_serv.core.i18n import _
from omega_serv.domain.admin_web.accounts import AdminAccount, accounts_missing_totp
from omega_serv.domain.admin_web.settings import OPTION_NAME, AdminWebSettings, binds_overlap
from omega_serv.domain.config.entities import OmegaServConfig
from omega_serv.domain.instances.entities import InstanceEntry
from omega_serv.ports.filesystem_port import FilesystemPort


def admin_web_settings(config: OmegaServConfig) -> AdminWebSettings | None:
    """Reglages de l'administration web si l'option est active, sinon None."""
    option = config.options.get(OPTION_NAME)
    if option is None or not option.enabled:
        return None
    return AdminWebSettings.from_settings(option.settings)


def admin_web_certificate_paths(config: OmegaServConfig, settings: AdminWebSettings) -> tuple[str, str] | None:
    """Certificat et cle : ceux du site (tls = site) ou les siens (tls = own) ; None sans TLS (boucle locale)."""
    if settings.tls == "site":
        return config.tls.certificate_path, config.tls.private_key_path
    if settings.tls == "own":
        return settings.certificate_path, settings.private_key_path
    return None


def admin_web_warnings(config: OmegaServConfig, filesystem: FilesystemPort, project_root: Path,
                       others: list[tuple[InstanceEntry, int | None]] | None = None,
                       accounts: tuple[AdminAccount, ...] | None = None) -> list[str]:
    """Ce qui empecherait l'administration web de demarrer : certificat absent en TLS, port deja pris par une autre
    instance du registre (`others` : instance et port d'administration de sa configuration, None si inactive)."""
    settings = admin_web_settings(config)
    if settings is None:
        return []
    warnings = []
    paths = admin_web_certificate_paths(config, settings)
    for label, relative in zip((_("certificat"), _("clé privée")), paths or (), strict=False):
        if not filesystem.is_file(project_root / relative):
            warnings.append(_("Administration web : {label} introuvable ({path}) - elle ne démarrera pas tant qu'il "
                              "manque (le site, lui, démarre)").format(label=label, path=relative))
    if accounts is not None and not accounts:
        warnings.append(_("Administration web : aucun compte - créez-en un (Instances -> Configuration distante -> "
                          "Comptes) pour pouvoir vous connecter"))
    missing = accounts_missing_totp(accounts or ())
    if missing and not settings.local_only:
        warnings.append(_("Administration web : TOTP obligatoire hors de cette machine pour les comptes "
                          "d'administration {names} - elle ne démarrera pas tant qu'ils ne l'ont pas activé").format(
            names=", ".join(missing)))
    return warnings + port_conflicts(settings, others or [])


def port_conflicts(settings: AdminWebSettings, others: list[tuple[InstanceEntry, int | None]]) -> list[str]:
    """Port d'administration deja pris par une autre instance du registre (son site ou sa propre administration)."""
    conflicts = []
    for entry, admin_port in others:
        if entry.port == settings.port and binds_overlap(entry.bind, str(settings.bind)):
            conflicts.append(_("Administration web : le port {port} est celui du site de l'instance {name!r}").format(
                port=settings.port, name=entry.name))
        elif admin_port == settings.port:
            conflicts.append(_("Administration web : le port {port} est déjà celui de l'administration web de "
                               "l'instance {name!r}").format(port=settings.port, name=entry.name))
    return conflicts
