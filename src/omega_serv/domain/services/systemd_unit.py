"""Generation d'unite systemd durcie (spec §24.3, OMEGA-SERV_PLAN_DEVELOPPEMENT.md
§6 : durcissement "par defaut, pas a etudier"). Code neuf (contrairement
au reste du module services/, qui porte omega-fire) - fonction pure de
gabarit texte, aucune I/O ici (l'ecriture du fichier est une
responsabilite d'infrastructure/application, voir
application/services/install_service.py)."""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

DEFAULT_SYSTEM_USER = "omega-serv"
DEFAULT_SYSTEM_GROUP = "omega-serv"
"""Compte systeme dedie, IDENTIQUE pour toutes les instances (angle mort
§8.1 du document multi-instance : jamais derive du nom d'instance/de
service) - centralise ici plutot que duplique en litteral dans
`service_screen.py`/`uninstall_instance.py`, pour que les deux cotes
(creation ET suppression) restent necessairement synchronises."""


@dataclass(frozen=True)
class SystemdUnitParams:
    service_name: str
    description: str
    python_executable: Path
    project_root: Path
    config_path: Path
    user: str
    group: str
    stop_timeout_seconds: int = 15


def generate_systemd_unit(params: SystemdUnitParams) -> str:
    """Durcissement non negociable (plan §6) : NoNewPrivileges,
    PrivateTmp, ProtectHome, ProtectSystem=strict + ReadWritePaths
    limite a var/, User/Group dedies obligatoires, UMask=0007,
    Restart=on-failure. Pas de drop de privileges apres bind cote
    Python - CAP_NET_BIND_SERVICE via systemd est le mecanisme prevu
    si un port <1024 est un jour necessaire (non ajoute ici tant
    qu'aucun profil ne le demande, voir §21.2 "port non privilegie
    avec reverse proxy" - comportement par defaut de ce projet).

    ExecReload=/bin/kill -HUP $MAINPID - retour utilisateur 2026-09-11 :
    sans cette directive, `systemctl reload` echoue purement et
    simplement (systemd ne sait pas quoi faire d'une unite sans
    ExecReload declare), la seule facon de declencher le rechargement
    a chaud deja code cote applicatif (interfaces/cli/main.py::
    run_server_until_stopped, gestionnaire SIGHUP - WAF/Auth/aliases/
    redirects/rewrites/cache/access_control/dirlisting/upload/
    error_pages/trusted_proxy/limites hors max_connections, jamais
    bind/port/TLS) etait un `kill -HUP` manuel en dehors de
    l'application. Signal HUP choisi car deja celui attendu par le
    gestionnaire existant, aucun nouveau protocole invente.

    ProtectHome=read-only (jamais =true) - retour utilisateur
    2026-09-10, vrai bug trouve : "true" rend /home/, /root et
    /run/user INACCESSIBLES ET VIDES pour le service (man
    systemd.exec), or ce projet s'installe et se lance depuis le
    HOME de l'utilisateur (~/DEV/SERV/omega-serv, meme install.sh) -
    avec ProtectHome=true, le service ne pouvait meme pas voir son
    propre interpreteur Python, echouant a chaque demarrage
    ("connection refused" cote client, rien n'ecoutait jamais).
    "read-only" garde l'essentiel du durcissement (rien d'ecrivable
    sous /home hors ReadWritePaths ci-dessous, deja limite a var/)
    tout en restant compatible avec l'emplacement d'installation reel
    du projet.

    UMask=0007 (jamais 0077) - retour utilisateur 2026-09-10, second
    vrai bug trouve juste apres le premier : meme une fois le compte
    dedie cree ET var/ rendu accessible en ecriture au GROUPE dedie
    (infrastructure/services/systemd_service_manager.py::
    grant_directory_access), un fichier cree par le service avec
    UMask=0077 (rw pour le proprietaire SEUL) restait illisible par
    l'utilisateur interactif - le fichier PID existait mais l'ecran
    Etat & Ressources ne pouvait pas en lire le contenu. 0007 (refuse
    uniquement "other", conserve groupe rw) permet au proprietaire du
    projet, ajoute au groupe dedie a l'installation, de continuer a
    lire ce que le service ecrit (PID, journaux)."""
    var_dir = params.project_root / "var"
    return f"""[Unit]
Description={params.description}
After=network.target

[Service]
Type=simple
ExecStart={params.python_executable} -m omega_serv --config {params.config_path} serve
ExecReload=/bin/kill -HUP $MAINPID
WorkingDirectory={params.project_root}
User={params.user}
Group={params.group}
Restart=on-failure
RestartSec=2
TimeoutStopSec={params.stop_timeout_seconds}

NoNewPrivileges=true
PrivateTmp=true
ProtectHome=read-only
ProtectSystem=strict
ReadWritePaths={var_dir}
UMask=0007

[Install]
WantedBy=multi-user.target
"""


def find_conflicting_unit(
    unit_contents: dict[str, str], project_root: Path, exclude_service_name: str
) -> str | None:
    """Retour utilisateur 2026-09-10 : rien n'empechait d'installer une
    DEUXIEME unite (nom different) pointant vers ce MEME repertoire -
    var/ (donc le fichier PID), le fichier de config et le compte
    systeme dedie sont tous codes en dur par repertoire, jamais par nom
    de service (`service_screen.py::_install_if_confirmed`) : deux
    unites sur le meme repertoire se marchent dessus (meme port si
    meme config, sinon collision silencieuse sur le fichier PID).
    `unit_contents` : {nom_de_fichier: contenu} de toutes les unites
    deja presentes sous /etc/systemd/system/ (lues sans privilege,
    644/755 par defaut) - `exclude_service_name` est le nom en cours
    d'installation (une reinstallation de la MEME unite sur le MEME
    repertoire n'est jamais un conflit). Retourne le nom du service en
    conflit (sans `.service`) si trouve, sinon None. La vraie multi-
    instance (plusieurs serveurs, ports differents) reste possible et
    propre en installant une copie separee du projet dans un autre
    repertoire (`bootstrap/paths.py::PROJECT_ROOT` derive tout de
    l'emplacement reel des fichiers) - le pilotage (demarrer/arreter/
    statut) de N'IMPORTE QUELLE unite deja installee, meme d'une autre
    copie, reste possible depuis une seule interface en tapant son nom
    (`application/services/manage_service.py` n'a jamais besoin du
    repertoire projet, seul `systemctl <verbe> <nom>` compte) - seule
    l'INSTALLATION initiale doit se faire depuis le bon repertoire."""
    marker = f"WorkingDirectory={project_root}"
    for filename, content in unit_contents.items():
        service_name = filename.removesuffix(".service")
        if service_name == exclude_service_name:
            continue
        if any(line.strip() == marker for line in content.splitlines()):
            return service_name
    return None


def find_name_hijack(unit_contents: dict[str, str], project_root: Path, service_name: str) -> Path | None:
    """Sens INVERSE de `find_conflicting_unit` (retour utilisateur
    2026-09-10, meme conversation) : deux repertoires DIFFERENTS
    utilisant le MEME nom de service (le nom par defaut "omega-serv"
    n'est jamais change en pratique) ne sont PAS detectes par
    `find_conflicting_unit` seul - `write_unit_file` (sudo tee) ecrase
    silencieusement le fichier d'unite existant sans jamais verifier a
    qui il appartenait. Cette fonction verifie si `{service_name}.service`
    existe deja et pointe vers un AUTRE repertoire que `project_root` -
    si oui, l'installer ici detournerait purement et simplement le nom,
    orphelinant le controle (demarrer/arreter/statut) de l'installation
    d'origine. Retourne le repertoire d'origine si un vol de nom serait
    reel, sinon None (absent, ou deja le meme repertoire - reinstallation
    normale)."""
    content = unit_contents.get(f"{service_name}.service")
    if content is None:
        return None
    for line in content.splitlines():
        stripped = line.strip()
        if stripped.startswith("WorkingDirectory="):
            existing_root = Path(stripped.removeprefix("WorkingDirectory="))
            return existing_root if existing_root != project_root else None
    return None


def find_account_in_use(unit_contents: dict[str, str], user: str, exclude_service_name: str) -> str | None:
    """OMEGA-SERV_PLAN-DETAILLE_MULTI_INSTANCE.md §8.1/§9 Phase E : le
    compte systeme dedie est IDENTIQUE pour toutes les instances (jamais
    derive par instance) - avant de le supprimer a la desinstallation
    d'UNE instance, verifier qu'aucune AUTRE unite installee ne le
    reference encore (`User={user}`), sinon la suppression casserait
    silencieusement le service d'une instance totalement differente qui
    partage le meme compte. `exclude_service_name` : l'unite de
    l'instance en cours de desinstallation (deja retiree du disque a ce
    stade dans le flux normal, mais exclue explicitement au cas ou -
    meme prudence que `find_conflicting_unit`/`find_name_hijack`).
    Retourne le nom du service qui reference encore ce compte, ou None
    si la suppression du compte est sans danger."""
    marker = f"User={user}"
    for filename, content in unit_contents.items():
        service_name = filename.removesuffix(".service")
        if service_name == exclude_service_name:
            continue
        if any(line.strip() == marker for line in content.splitlines()):
            return service_name
    return None
