"""Partie legere de l'administration web pour la CLI (remesure memoire 3.0.0, 2026-11-18) : definitions des
commandes `admin-web ...` et superviseur lance par `serve`. Le code des commandes reste dans admin_web_commands.py et
n'est importe qu'au moment ou l'une d'elles s'execute : `serve` construit le meme parseur, et importer ce module
lourd (tableau de bord, comptes, maitre, historique...) coutait environ 10 Mo a chaque processus du serveur, meme
option inactive."""
from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

from omega_serv.application.admin_web.checks import admin_web_settings
from omega_serv.core.i18n import _
from omega_serv.domain.admin_web.accounts import ROLES
from omega_serv.domain.admin_web.master import RIGHTS
from omega_serv.domain.config.entities import OmegaServConfig
from omega_serv.domain.services.python_command import python_module_argv
from omega_serv.interfaces.cli.child_supervisor import ChildSupervisor
from omega_serv.interfaces.cli.command_tree import (
    CommandHandler,
    add_command,
    add_group,
    lazy_command,
)

LABEL = "Administration web"


def _admin(name: str) -> CommandHandler:
    return lazy_command("omega_serv.interfaces.cli.admin_web_commands", name)


def build_admin_web_supervisor(config: OmegaServConfig, config_path: Path) -> ChildSupervisor | None:
    """Rien si l'option est inactive (defaut) : aucun processus, aucun port."""
    if admin_web_settings(config) is None:
        return None
    # Lot 5 : le PID du superviseur (ce processus) est transmis pour « Recharger la configuration » ; le processus
    # d'administration verifie encore que c'est bien son parent avant d'envoyer le signal.
    argv = [*python_module_argv(sys.executable, "omega_serv", "--config", str(config_path), "admin-web", "run"),
            "--supervisor-pid", str(os.getpid())]
    return ChildSupervisor(LABEL, argv)


def register_admin_account_commands(admin_web_sub: argparse._SubParsersAction) -> None:
    account_sub = add_group(admin_web_sub, "account", _(
        "Comptes de l'administration web (créés ici ou dans le TUI, jamais depuis le web)."), "admin_account_command")
    add_command(account_sub, "list", _("Liste les comptes, leur rôle et leur TOTP.")).set_defaults(
        func=_admin("cmd_admin_account_list"))
    add_parser = add_command(account_sub, "add", _("Crée un compte (mot de passe demandé deux fois)."))
    add_parser.add_argument("username", help=_("Identifiant."))
    add_parser.add_argument("--role", choices=ROLES, default="lecture", help=_(
        "lecture : Tableau de bord seulement ; administration : Tableau de bord et Administration."))
    add_parser.set_defaults(func=_admin("cmd_admin_account_add"))
    for name, text, func in (
        ("remove", _("Supprime un compte (ses sessions ouvertes sont fermées)."), _admin("cmd_admin_account_remove")),
        ("password", _("Change le mot de passe (demandé deux fois)."), _admin("cmd_admin_account_password")),
        ("totp-enable", _("Active TOTP : QR code, secret et lien, puis vérification d'un code ; affiche les codes "
                          "de secours."), _admin("cmd_admin_account_totp_enable")),
        ("totp-disable", _("Désactive TOTP pour ce compte."), _admin("cmd_admin_account_totp_disable")),
        ("backup-codes", _("Génère 10 nouveaux codes de secours (les anciens ne marchent plus, le TOTP du téléphone ne "
                           "change pas)."), _admin("cmd_admin_account_backup_codes")),
    ):
        parser = add_command(account_sub, name, text)
        parser.add_argument("username", help=_("Identifiant."))
        parser.set_defaults(func=func)
    role_parser = add_command(account_sub, "role", _("Change le rôle d'un compte."))
    role_parser.add_argument("username", help=_("Identifiant."))
    role_parser.add_argument("role", choices=ROLES, help=_("lecture ou administration."))
    role_parser.set_defaults(func=_admin("cmd_admin_account_role"))


def register_admin_master_commands(admin_web_sub: argparse._SubParsersAction) -> None:
    master_sub = add_group(admin_web_sub, "master", _(
        "Maître accepté par cette instance (un seul) : la suivre et la piloter depuis une autre instance."),
        "admin_master_command")
    add_command(master_sub, "show", _("Montre le maître accepté, ses droits et la fenêtre d'appairage.")).set_defaults(
        func=_admin("cmd_admin_master_show"))
    accept = add_command(master_sub, "accept", _(
        "Accepte un maître (utilisé par « Relier au maître » du TUI) : affiche en JSON le jeton et l'empreinte du "
        "certificat, à déposer chez le maître."))
    accept.add_argument("--master-id", required=True, help=_("Identifiant du maître (admin-web instances identity)."))
    accept.add_argument("--master-name", help=_("Nom du maître, affiché ici."))
    accept.add_argument("--rights", choices=RIGHTS, default="lecture", help=_(
        "lecture : voir seulement ; administration : voir et agir."))
    accept.add_argument("--replace", action="store_true", help=_("Remplace le maître déjà accepté (révoqué aussitôt)."))
    accept.set_defaults(func=_admin("cmd_admin_master_accept"))
    code = add_command(master_sub, "pairing-code", _(
        "Ouvre une fenêtre d'appairage de 10 minutes et affiche le code à saisir sur le maître."))
    code.add_argument("--rights", choices=RIGHTS, default="lecture", help=_(
        "lecture : voir seulement ; administration : voir et agir."))
    code.add_argument("--replace", action="store_true", help=_("Remplace le maître déjà accepté (révoqué aussitôt)."))
    code.set_defaults(func=_admin("cmd_admin_master_pairing_code"))
    add_command(master_sub, "revoke", _("Révoque le maître accepté : ses appels sont refusés aussitôt.")).set_defaults(
        func=_admin("cmd_admin_master_revoke"))

    instances_sub = add_group(admin_web_sub, "instances", _(
        "Instances suivies par ce maître (page Instances du tableau de bord web)."), "admin_instances_command")
    add_command(instances_sub, "identity", _("Affiche en JSON l'identifiant et le nom de ce maître.")).set_defaults(
        func=_admin("cmd_admin_instances_identity"))
    add_command(instances_sub, "list", _("Liste les instances suivies et les sondes.")).set_defaults(
        func=_admin("cmd_admin_instances_list"))
    add = add_command(instances_sub, "add", _(
        "Ajoute une instance avec le jeton et l'empreinte rendus par « admin-web master accept » (« Relier au "
        "maître » du TUI)."))
    add.add_argument("address", help=_("Adresse IP de l'instance."))
    add.add_argument("port", type=int, help=_("Port de son administration web."))
    add.add_argument("--fingerprint", required=True, help=_("Empreinte SHA-256 de son certificat (vide : HTTP en "
                                                           "boucle locale seulement)."))
    add.add_argument("--token", help=_("Jeton ; sans cette option, il est lu sur l'entrée standard (jamais dans "
                                       "l'historique du shell)."))
    add.add_argument("--name", help=_("Nom affiché."))
    add.set_defaults(func=_admin("cmd_admin_instances_add"))
    pair = add_command(instances_sub, "pair", _("Relie une instance avec son code d'appairage."))
    pair.add_argument("address", help=_("Adresse IP de l'instance."))
    pair.add_argument("port", type=int, help=_("Port de son administration web."))
    pair.add_argument("code", help=_("Code affiché par l'instance (comme K7QF-3M9X)."))
    pair.add_argument("--name", help=_("Nom affiché."))
    pair.set_defaults(func=_admin("cmd_admin_instances_pair"))
    probe = add_command(instances_sub, "add-probe", _("Ajoute une sonde HTTP (backend qui n'est pas omega-serv)."))
    probe.add_argument("url", help=_("URL sondée (http://... ou https://...)."))
    probe.add_argument("--name", help=_("Nom affiché."))
    probe.set_defaults(func=_admin("cmd_admin_instances_add_probe"))
    remove = add_command(instances_sub, "remove", _("Retire une instance suivie ou une sonde (identifiant de "
                                                     "« list »)."))
    remove.add_argument("instance_id", help=_("Identifiant à 12 caractères."))
    remove.set_defaults(func=_admin("cmd_admin_instances_remove"))
