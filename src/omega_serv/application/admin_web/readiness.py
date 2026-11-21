# Copyright (c) 2026 kraynux - kraynux@proton.me - Licence MIT (voir fichier LICENSE)
"""Bilan « prêt / ce qui manque » de l'ecran Configuration distante (lot 8, OMEGA-SERV_PLAN-DETAILLE_TABLEAU_DE_BORD_WEB
.md §9.4 ; retour de l'auteur du 2026-11-17 : tout le parcours dans la TUI, jamais une commande a taper ailleurs).

Une ligne par point, chacune avec l'action qui la regle quand il y en a une : activer l'option, generer le
certificat, creer un compte (ou activer son TOTP), redemarrer ou recharger le service. Le pare-feu est seulement
signale, sauf si omega-fire et cette instance sont inscrits dans la zone omega-connect : bouton « Ouvrir le port »
(sous-lot 8b, decisions de l'auteur du 2026-11-17)."""
from __future__ import annotations

import ipaddress
from dataclasses import dataclass

from omega_serv.application.admin_web.checks import admin_web_certificate_paths, port_conflicts
from omega_serv.application.admin_web.firewall_setup import (
    FirewallRecord,
    firewall_sources,
    record_covers,
)
from omega_serv.core.i18n import _
from omega_serv.domain.admin_web.accounts import AdminAccount, accounts_missing_totp
from omega_serv.domain.admin_web.run_state import AdminRunState
from omega_serv.domain.admin_web.settings import OPTION_NAME, AdminWebSettings
from omega_serv.domain.config.entities import OmegaServConfig
from omega_serv.domain.instances.entities import InstanceEntry

ACTION_ENABLE = "enable"
ACTION_CERTIFICATE = "certificate"
ACTION_ACCOUNTS = "accounts"
ACTION_RESTART = "restart"
ACTION_RELOAD = "reload"
ACTION_FIREWALL = "firewall"


@dataclass(frozen=True)
class ReadinessItem:
    ok: bool | None
    """True : pret ; False : manque ; None : information."""
    text: str
    action: str = ""


@dataclass(frozen=True)
class ReadinessFacts:
    """Ce que le conteneur a releve sur la machine ; le bilan lui-meme reste une regle pure."""

    certificate_present: tuple[bool, bool] = (True, True)
    """Certificat et cle presents (sans objet sans TLS)."""
    accounts: tuple[AdminAccount, ...] | None = ()
    """None : fichier des comptes illisible."""
    accounts_error: str = ""
    others: tuple[tuple[InstanceEntry, int | None], ...] = ()
    run_state: AdminRunState | None = None
    service_active: bool | None = None
    """None : pas de service installe (ou etat illisible)."""
    firewall: str = ""
    addresses: tuple[str, ...] = ()
    """Adresses de la machine, pour dire quelle adresse ouvrir sur l'autre appareil."""
    firewall_linked: bool = False
    """Sous-lot 8b : omega-fire et cette instance inscrits dans la zone omega-connect."""
    firewall_opened: FirewallRecord | None = None


def problem_text(state: AdminRunState) -> str:
    texts = {
        "config": _("configuration illisible"),
        "inactive": _("option inactive au dernier démarrage"),
        "certificate": _("certificat illisible"),
        "accounts_file": _("fichier des comptes illisible"),
        "totp": _("TOTP obligatoire hors de cette machine pour les comptes d'administration"),
        "fingerprint": _("empreinte du certificat illisible"),
        "listen": _("écoute impossible sur {bind}:{port} (port pris par un autre programme ou adresse absente de "
                    "cette machine)").format(bind=state.bind, port=state.port),
    }
    text = texts.get(state.problem, state.problem)
    return f"{text} ({state.detail})" if state.detail else text


def _remote_urls(settings: AdminWebSettings, addresses: tuple[str, ...]) -> list[str]:
    scheme = "http" if settings.tls == "none" else "https"
    try:
        unspecified = ipaddress.ip_address(str(settings.bind)).is_unspecified
    except ValueError:
        unspecified = False
    if not unspecified:
        return [settings.url]
    urls = []
    for address in addresses:
        try:
            parsed = ipaddress.ip_address(address)
        except ValueError:
            continue
        if parsed.is_loopback or parsed.version != 4:
            continue
        urls.append(f"{scheme}://{address}:{settings.port}/")
    return urls[:3] or [settings.url]


def admin_web_readiness(config: OmegaServConfig, facts: ReadinessFacts) -> list[ReadinessItem]:
    option = config.options.get(OPTION_NAME)
    enabled = option is not None and option.enabled
    settings = AdminWebSettings.from_settings(option.settings if option is not None else {})
    items: list[ReadinessItem] = []
    if enabled:
        items.append(ReadinessItem(True, _("Option admin_web active.")))
    else:
        items.append(ReadinessItem(False, _("Option admin_web inactive : l'administration web n'est pas lancée."),
                                   ACTION_ENABLE))

    if settings.local_only:
        items.append(ReadinessItem(None, _("Depuis cette machine seulement ({url}). Pour un autre appareil : adresse "
                                           "du réseau local, de Tailscale ou 0.0.0.0 ci-dessous.").format(
            url=settings.url)))
    else:
        items.append(ReadinessItem(None, _("Adresse à ouvrir sur l'autre appareil : {urls}").format(
            urls=", ".join(_remote_urls(settings, facts.addresses)))))

    paths = admin_web_certificate_paths(config, settings)
    if paths is not None:
        if all(facts.certificate_present):
            items.append(ReadinessItem(True, _("Certificat présent ({path}).").format(path=paths[0])))
        elif settings.tls == "own":
            items.append(ReadinessItem(False, _("Certificat dédié absent ({path}).").format(path=paths[0]),
                                       ACTION_CERTIFICATE))
        else:
            items.append(ReadinessItem(False, _("Certificat du site absent ({path}) : écran TLS.").format(
                path=paths[0])))

    if facts.accounts is None:
        items.append(ReadinessItem(False, facts.accounts_error or _("Fichier des comptes illisible."),
                                   ACTION_ACCOUNTS))
    elif not facts.accounts:
        items.append(ReadinessItem(False, _("Aucun compte : créez-en un pour vous connecter."), ACTION_ACCOUNTS))
    else:
        missing = accounts_missing_totp(facts.accounts) if not settings.local_only else ()
        if missing:
            items.append(ReadinessItem(False, _("TOTP à activer (obligatoire hors de cette machine) : {names}.").format(
                names=", ".join(missing)), ACTION_ACCOUNTS))
        else:
            items.append(ReadinessItem(True, _("{count} compte(s).").format(count=len(facts.accounts))))

    for conflict in port_conflicts(settings, list(facts.others)):
        items.append(ReadinessItem(False, conflict))

    if enabled:
        items.append(_listening_item(settings, facts))

    if not settings.local_only:
        firewall = _firewall_item(settings, facts)
        if firewall is not None:
            items.append(firewall)
    return items


def _firewall_item(settings: AdminWebSettings, facts: ReadinessFacts) -> ReadinessItem | None:
    """Sous-lot 8b : omega-fire relie -> bouton « Ouvrir le port » (puis « ouvert ») ; sinon pare-feu actif signale."""
    if facts.firewall_linked and firewall_sources(settings):
        if record_covers(facts.firewall_opened, settings):
            return ReadinessItem(True, _("Port {port}/tcp ouvert par omega-fire pour vos réseaux permis.").format(
                port=settings.port))
        return ReadinessItem(False, _("Port {port}/tcp à ouvrir pour vos réseaux permis : omega-fire, relié par "
                                      "omega-connect, peut l'ouvrir (ufw ou firewalld compris).").format(
            port=settings.port), ACTION_FIREWALL)
    if facts.firewall:
        return ReadinessItem(None, _("Pare-feu {name} actif : il doit laisser passer le port {port}/tcp depuis vos "
                                     "réseaux permis. omega-serv l'ouvre lui-même quand omega-fire est relié par "
                                     "omega-connect ; sinon, par l'outil du pare-feu.").format(
            name=facts.firewall, port=settings.port))
    return None


def _listening_item(settings: AdminWebSettings, facts: ReadinessFacts) -> ReadinessItem:
    state = facts.run_state
    if facts.service_active is False:
        return ReadinessItem(False, _("Service arrêté : l'administration web démarre avec lui."), ACTION_RESTART)
    if state is None:
        return ReadinessItem(False, _("Administration web pas encore lancée : redémarrez le service."), ACTION_RESTART)
    if not state.listening:
        return ReadinessItem(False, _("Administration web arrêtée : {reason}.").format(reason=problem_text(state)),
                             ACTION_RESTART)
    if (state.bind, state.port) != (str(settings.bind), settings.port):
        return ReadinessItem(False, _("En écoute avec les anciens réglages ({bind}:{port}) : rechargez.").format(
            bind=state.bind, port=state.port), ACTION_RELOAD)
    return ReadinessItem(True, _("En écoute ({url}).").format(url=settings.url))
