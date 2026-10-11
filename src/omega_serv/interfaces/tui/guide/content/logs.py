"""Fiches guide : Gestion des logs - menu + 8 sous-ecrans (plan guide
d'aide, Phase 6)."""
from __future__ import annotations

from omega_serv.interfaces.tui.guide.model import FieldGuide, ScreenGuide

LOGS_MENU_SCREEN = ScreenGuide(
    screen_class_name="LogsMenuScreen",
    title="Gestion des logs (menu)",
    acces="Accueil -> Gestion des logs",
    definition="Sous-menu regroupant les 8 ecrans de consultation, suivi, rotation/archivage et statistiques des logs.",
    fields=(),
    consequences="Aucune - purement navigation.",
)

LOG_VIEWER_SCREEN = ScreenGuide(
    screen_class_name="LogViewerScreen",
    title="Voir / suivre un fichier log",
    acces="Accueil -> Gestion des logs -> Voir / suivre un fichier log",
    definition=(
        "Affiche les 200 dernieres lignes d'un log connu (access/error/waf-alerts, "
        "plus les 2 logs du script WAF complementaire magnet - options.waf.magnet, §7) "
        "et peut suivre son evolution en direct."
    ),
    fields=(
        FieldGuide(
            label="access / error / waf-alerts (boutons)",
            definition="Choisit le fichier de log a afficher.",
            utilisation="Un clic ouvre le fichier correspondant, s'il existe.",
            action="Charge et affiche les 200 dernieres lignes.",
            reaction="Aucun effet sur le serveur (lecture seule) - un fichier absent affiche un message, jamais une erreur.",
        ),
        FieldGuide(
            label="waf magnet (alertes) / waf magnet (blocklist) (boutons)",
            definition=(
                "Chemins de log du script WAF complementaire importe en mode magnet "
                "(options.waf.magnet.paths.alerts_log/blocklist_log) - toujours proposes, "
                "meme si le magnet n'est jamais configure."
            ),
            utilisation=(
                "Grises (desactives) tant que options.waf.magnet.enabled n'est pas actif - "
                "evite un clic qui ne menerait qu'a un message d'erreur. Une fois actif, un "
                "clic ouvre le fichier meme s'il n'existe pas encore (log vide, jamais une "
                "erreur - aucune alerte declenchee pour l'instant)."
            ),
            action="Charge et affiche les 200 dernieres lignes, ou un message explicite si le fichier est vide/absent.",
            reaction="Aucun effet sur le serveur (lecture seule).",
        ),
        FieldGuide(
            label="Suivre en direct",
            definition="Rafraichit l'affichage automatiquement toutes les secondes avec les nouvelles lignes.",
            utilisation="Bascule marche/arret - necessite d'avoir d'abord ouvert un fichier.",
            action="Demarre/arrete le suivi periodique.",
            reaction="Aucun effet sur le serveur (lecture seule).",
        ),
    ),
    consequences="Purement consultatif, aucun effet sur le serveur ou sa configuration.",
    points_de_vigilance=(
        (
            "Un fichier appartenant au compte systeme dedie du service peut rester illisible "
            "depuis une session qui n'a pas encore pris en compte son appartenance de groupe "
            "(memes causes que le piege deja documente pour SERVICE - reconnectez votre session)."
        ),
    ),
)

LNAV_SCREEN = ScreenGuide(
    screen_class_name="LnavScreen",
    title="Suivre les logs fusionnes (lnav)",
    acces="Accueil -> Gestion des logs -> Suivre les logs fusionnes (lnav)",
    definition="Lance l'outil externe lnav sur un ou plusieurs logs fusionnes chronologiquement, dans un vrai terminal.",
    fields=(
        FieldGuide(
            label="Cases a cocher (Access/Error/WAF alerts log/WAF magnet)",
            definition=(
                "Choisit quels logs connus fusionner dans la meme vue lnav - inclut d'office "
                "les 2 logs du script WAF complementaire magnet (options.waf.magnet.paths, §7), "
                "meme si le magnet n'est pas actif."
            ),
            utilisation=(
                "Une ou plusieurs cases, au moins un fichier existant requis. Un log coche mais "
                "absent (ex. magnet jamais active) est simplement ignore au lancement, jamais "
                "bloquant pour les autres."
            ),
            action="Pris en compte au clic sur Lancer lnav.",
            reaction="Aucun effet sur le serveur (lecture seule).",
        ),
        FieldGuide(
            label="Chemins epingles (cases a cocher dynamiques)",
            definition=(
                "Chemins manuels ajoutes par 'Epingler ce chemin' - persistent entre sessions "
                "(contrairement au champ manuel ci-dessous), affiches comme des logs connus "
                "supplementaires."
            ),
            utilisation="Une case par chemin epingle - coche ou non, comme les logs connus.",
            action="Pris en compte au clic sur Lancer lnav.",
            reaction="Aucun effet sur le serveur (lecture seule).",
        ),
        FieldGuide(
            label="Chemin manuel + Epingler ce chemin",
            definition="Saisit un chemin de log hors des logs connus, et le conserve pour les prochains lancements.",
            utilisation=(
                "Chemin relatif au projet ou absolu. 'Epingler ce chemin' l'ajoute a la liste "
                "des epingles (ci-dessus) ET vide ce champ - sans epinglage, le chemin ne sert "
                "qu'une seule fois, pour ce lancement."
            ),
            action="Chemin non epingle : pris en compte au clic sur Lancer lnav, pour cette fois seulement. Epingle : persiste (voir settings.json) jusqu'a retrait explicite.",
            reaction="Aucun effet sur le serveur.",
        ),
        FieldGuide(
            label="Retirer une epingle choisie",
            definition="Retire definitivement un chemin de la liste des epingles.",
            utilisation="Choisir le chemin dans la liste deroulante, puis cliquer sur le bouton.",
            action="Supprime l'epingle et sa case a cocher correspondante.",
            reaction="Aucun effet sur le serveur - n'affecte jamais le fichier de log lui-meme, seulement la liste des raccourcis.",
        ),
        FieldGuide(
            label="Lancer lnav",
            definition="Ouvre lnav en plein ecran dans le terminal reel.",
            utilisation="Necessite au moins un fichier existant selectionne.",
            action="Suspend l'interface et rend la main au terminal.",
            reaction="Aucun effet sur le serveur - quitter lnav (Ctrl-Q) revient a cet ecran.",
        ),
    ),
    consequences="Purement consultatif.",
    points_de_vigilance=(
        "Necessite que l'outil lnav soit installe sur le systeme - indisponible sinon, message explicite.",
    ),
)

LOG_ROTATION_SCREEN = ScreenGuide(
    screen_class_name="LogRotationScreen",
    title="Rotation / archivage des logs",
    acces="Accueil -> Gestion des logs -> Rotation / archivage des logs",
    definition="Quatre modes : rotation conditionnelle (seuil de taille), sauvegarde immediate inconditionnelle, planifier une automatisation, gerer les automatisations existantes.",
    fields=(
        FieldGuide(
            label="Action",
            definition="Choisit le mode de cet ecran.",
            utilisation=(
                "'Tourner si necessaire' (respecte le seuil de taille configure), 'Sauvegarde "
                "maintenant' (inconditionnelle), 'Configurer une automatisation', 'Gerer les "
                "automatisations'."
            ),
            action="Change les champs affiches en dessous.",
            reaction="Aucun effet en lui-meme, juste un changement d'affichage.",
        ),
        FieldGuide(
            label="Log cible",
            definition="Le fichier de log concerne par l'action.",
            utilisation="access, error ou waf_alerts.",
            action="Utilise par Valider.",
            reaction="Archive reellement le fichier immediatement (modes rotation/sauvegarde).",
        ),
        FieldGuide(
            label="Frequence (mode automatisation)",
            definition="A quelle frequence l'automatisation doit se declencher.",
            utilisation="Hebdomadaire, mensuelle, trimestrielle, semestrielle ou annuelle.",
            action="Utilise par Valider.",
            reaction="Enregistre une automatisation - ne declenche PAS une rotation immediate.",
        ),
        FieldGuide(
            label="Automatisations planifiees (mode gestion)",
            definition="Liste des automatisations deja enregistrees.",
            utilisation="Selectionner une ligne active le bouton de suppression.",
            action="Supprimer la selection retire l'automatisation (avec confirmation).",
            reaction="Suppression immediate et definitive de l'automatisation choisie.",
        ),
    ),
    consequences=(
        "'Tourner si necessaire' ne fait rien si logs.rotation.enabled est desactive dans la "
        "configuration, ou si le fichier n'a pas atteint le seuil de taille configure. "
        "'Sauvegarde maintenant' archive TOUJOURS, quelle que soit la taille."
    ),
    points_de_vigilance=(
        (
            "Les archives sont ecrites dans var/backups/logs/, un emplacement distinct de "
            "var/backups/ (reserve aux sauvegardes de configuration)."
        ),
    ),
)

RESTORE_LOG_ARCHIVE_SCREEN = ScreenGuide(
    screen_class_name="RestoreLogArchiveScreen",
    title="Restaurer une archive de log",
    acces="Accueil -> Gestion des logs -> Restaurer une archive de log",
    definition="Extrait le contenu d'une archive de log deja creee vers un repertoire de restauration.",
    fields=(
        FieldGuide(
            label="Table des archives + Restaurer",
            definition="Selectionne une archive et l'extrait.",
            utilisation="Selectionner une ligne active le bouton Restaurer.",
            action="Extrait l'archive vers var/log/restored/<nom-archive>/.",
            reaction="Ecriture reelle sur disque immediate, aucun effet sur le serveur en cours.",
        ),
    ),
    consequences="N'ecrase jamais les logs actifs - extrait toujours vers un sous-repertoire dedie.",
)

PURGE_LOG_ARCHIVES_SCREEN = ScreenGuide(
    screen_class_name="PurgeLogArchivesScreen",
    title="Purger les archives de logs",
    acces="Accueil -> Gestion des logs -> Purger les archives de logs",
    definition="Supprime definitivement une archive de log.",
    fields=(
        FieldGuide(
            label="Table des archives + Supprimer",
            definition="Selectionne une archive et la supprime.",
            utilisation="Selectionner une ligne active le bouton Supprimer, avec confirmation obligatoire.",
            action="Supprime le fichier d'archive.",
            reaction="Suppression immediate et DEFINITIVE - action destructive, jamais reversible.",
        ),
    ),
    consequences="Action irreversible - aucune corbeille ni sauvegarde prealable automatique.",
)

EXPORT_LOG_ARCHIVES_SCREEN = ScreenGuide(
    screen_class_name="ExportLogArchivesScreen",
    title="Exporter Archives",
    acces="Accueil -> Gestion des logs -> Exporter Archives",
    definition="Exporte la liste des archives de logs (metadonnees, pas leur contenu) en JSON ou HTML.",
    fields=(
        FieldGuide(
            label="Theme d'export HTML",
            definition="Palette de couleurs utilisee pour l'export HTML.",
            utilisation="5 themes disponibles.",
            action="Utilise au clic sur Exporter HTML.",
            reaction="Aucun effet sur le serveur.",
        ),
        FieldGuide(
            label="Exporter JSON / Exporter HTML",
            definition="Genere le fichier d'export dans le repertoire d'export configure.",
            utilisation="Aucune saisie supplementaire.",
            action="Ecrit un fichier horodate (jamais d'ecrasement silencieux d'un export precedent).",
            reaction="Ecriture reelle sur disque immediate, aucun effet sur le serveur.",
        ),
    ),
    consequences="Purement consultatif/export - aucun effet sur la configuration ou le serveur.",
    points_de_vigilance=(
        "Le repertoire d'export peut etre change dans l'ecran Reglages de l'application (touche 'o').",
    ),
)

LOG_STATS_SCREEN = ScreenGuide(
    screen_class_name="LogStatsScreen",
    title="Statistiques du log d'acces",
    acces="Accueil -> Gestion des logs -> Statistiques du log d'acces",
    definition="Resume et repartition horaire du log d'acces sur une periode donnee - log combine uniquement (access log).",
    fields=(
        FieldGuide(
            label="24 heures / 7 jours / 30 jours",
            definition="Choisit la periode analysee.",
            utilisation="Un clic recalcule immediatement les statistiques.",
            action="Relit et reanalyse le log d'acces.",
            reaction="Aucun effet (lecture seule).",
        ),
    ),
    consequences="Purement consultatif.",
    points_de_vigilance=(
        (
            "Ne fonctionne qu'avec le format de log 'combined' (access_format) - les autres "
            "logs (error, waf-alerts...) ne portent pas les memes informations (IP, code de statut)."
        ),
    ),
)

TOP_IPS_SCREEN = ScreenGuide(
    screen_class_name="TopIpsScreen",
    title="Top IPs du log d'acces",
    acces="Accueil -> Gestion des logs -> Top IPs du log d'acces",
    definition="Liste les IP les plus actives du log d'acces sur une periode, avec possibilite de retirer une IP du log.",
    fields=(
        FieldGuide(
            label="24 heures / 7 jours / 30 jours",
            definition="Choisit la periode analysee.",
            utilisation="Un clic recalcule immediatement la liste.",
            action="Relit et reanalyse le log d'acces.",
            reaction="Aucun effet (lecture seule).",
        ),
        FieldGuide(
            label="Retirer cette IP des logs",
            definition="Supprime toutes les lignes du log d'acces correspondant a l'IP selectionnee.",
            utilisation="Selectionner une ligne active le bouton, avec confirmation obligatoire.",
            action="Reecrit le fichier de log sans les lignes de cette IP.",
            reaction="Modification DEFINITIVE et immediate du fichier de log - action destructive.",
        ),
    ),
    consequences="Le retrait d'IP modifie directement et irreversiblement le fichier de log d'acces.",
)

ALL_LOGS_GUIDES: tuple[ScreenGuide, ...] = (
    LOGS_MENU_SCREEN,
    LOG_VIEWER_SCREEN,
    LNAV_SCREEN,
    LOG_ROTATION_SCREEN,
    RESTORE_LOG_ARCHIVE_SCREEN,
    PURGE_LOG_ARCHIVES_SCREEN,
    EXPORT_LOG_ARCHIVES_SCREEN,
    LOG_STATS_SCREEN,
    TOP_IPS_SCREEN,
)
