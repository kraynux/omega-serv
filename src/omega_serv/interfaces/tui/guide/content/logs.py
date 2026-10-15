"""Fiches guide : Gestion des logs - menu en 2 colonnes (refonte
2026-10-15, au meme niveau qu'omega-log, OMEGA-LOG_PLAN) + sous-ecrans."""
from __future__ import annotations

from omega_serv.interfaces.tui.guide.model import FieldGuide, ScreenGuide

LOGS_MENU_SCREEN = ScreenGuide(
    screen_class_name="LogsMenuScreen",
    title="Gestion des logs (menu)",
    acces="Accueil -> Gestion des logs",
    definition=(
        "Sous-menu en 2 colonnes : BIBLIOTHEQUE (consultation - Bibliotheque/Favoris/"
        "Voir les logs/Voir et traiter IP) et MAINTENANCE (rotation/archivage - "
        "inchangee depuis la Phase 6)."
    ),
    fields=(),
    consequences="Aucune - purement navigation.",
)

LOG_LIBRARY_SCREEN = ScreenGuide(
    screen_class_name="LogLibraryScreen",
    title="Bibliotheque",
    acces="Accueil -> Gestion des logs -> Bibliotheque",
    definition=(
        "Hub central referencant tous les logs a traiter (ceux d'Omega-Serv ou tout "
        "autre fichier de log de la machine) - alimentation MANUELLE (aucun scan "
        "automatique du systeme pour cette passe). Source commune de 'Voir les logs', "
        "'Favoris' et 'Voir et traiter IP'."
    ),
    fields=(
        FieldGuide(
            label="Chemin a ajouter manuellement",
            definition="Reference un fichier de log quelconque dans la Bibliotheque.",
            utilisation="Chemin absolu ou relatif au projet - le fichier n'a pas besoin d'exister deja.",
            action="Ajoute (ou remplace si deja present) une entree.",
            reaction="Aucun effet sur le serveur - l'etat (existe/taille) est toujours recalcule a l'affichage.",
        ),
        FieldGuide(
            label="Ajouter les logs connus d'Omega-Serv",
            definition="Ajoute en un clic les logs propres a ce projet (access/error/waf-alerts, + magnet si actif).",
            utilisation="Aucune saisie requise.",
            action="Ajoute (ou remplace) ces entrees dans la Bibliotheque.",
            reaction="Jamais un scan du reste du systeme - uniquement les quelques logs deja connus de ce projet.",
        ),
        FieldGuide(
            label="Retirer la selection",
            definition="Retire une entree de la Bibliotheque (ne supprime jamais le fichier lui-meme).",
            utilisation="Selectionner une ligne, confirmation obligatoire.",
            action="Retire l'entree du fichier var/library.json.",
            reaction="Le fichier de log sur disque n'est jamais touche - seule la reference est retiree.",
        ),
    ),
    consequences="Purement une liste de references - aucun effet sur les fichiers de log eux-memes.",
    points_de_vigilance=(
        (
            "L'etat affiche (OK/SUSPECT/ABSENT) est toujours recalcule en lisant le disque "
            "reellement a chaque ouverture de cet ecran, jamais une donnee figee au moment "
            "de l'ajout."
        ),
    ),
)

LOG_FAVORITES_SCREEN = ScreenGuide(
    screen_class_name="LogFavoritesScreen",
    title="Favoris",
    acces="Accueil -> Gestion des logs -> Favoris",
    definition="Combinaisons nommees (un ou plusieurs logs de la Bibliotheque + un viewer) pour un lancement direct.",
    fields=(
        FieldGuide(
            label="Lancer",
            definition="Ouvre directement le favori selectionne avec son viewer d'origine.",
            utilisation="Selectionner une ligne dans la table des favoris.",
            action="Ouvre l'ecran du viewer correspondant (Simple/Classique/lnav).",
            reaction="Aucun effet sur le serveur (lecture seule).",
        ),
        FieldGuide(
            label="Numeros + Nom du favori + Viewer + Enregistrer",
            definition="Cree un nouveau favori a partir de logs choisis dans la Bibliotheque.",
            utilisation=(
                "Numeros separes par des virgules (ex: 1,3) - un seul log autorise avec "
                "Simple/Classique, lnav uniquement au-dela d'un log."
            ),
            action="Enregistre le favori (remplace un favori existant du meme nom).",
            reaction="Refuse a la creation si le viewer choisi est incompatible avec le nombre de logs - jamais tronque silencieusement.",
        ),
        FieldGuide(
            label="Supprimer",
            definition="Retire definitivement un favori.",
            utilisation="Selectionner une ligne, confirmation obligatoire.",
            action="Retire l'entree du fichier var/favorites.json.",
            reaction="Ne touche jamais aux fichiers de log eux-memes ni a la Bibliotheque.",
        ),
    ),
    consequences="Purement des raccourcis - aucun effet sur les fichiers de log eux-memes.",
)

REMOTE_LOG_SOURCES_SCREEN = ScreenGuide(
    screen_class_name="RemoteLogSourcesScreen",
    title="Sources distantes (SSH)",
    acces="Accueil -> Gestion des logs -> Bibliotheque -> Sources distantes (SSH)",
    definition=(
        "Permet de recuperer, a la demande, UNE COPIE du log d'un serveur backend situe sur le "
        "meme reseau local (derriere le reverse proxy) via scp, puis de l'ajouter automatiquement "
        "a la Bibliotheque - ce n'est jamais une consultation en direct du serveur distant, mais "
        "un instantane fige au moment du clic sur 'Recuperer maintenant' ; une nouvelle "
        "recuperation remplace la copie precedente par une plus recente. Aucun scan reseau "
        "automatique, aucune connexion sans configuration explicite de votre part."
    ),
    fields=(
        FieldGuide(
            label="Label / Hote / Chemin distant",
            definition="Identifie la source : un nom de votre choix, l'adresse du serveur, et le chemin du fichier de log sur ce serveur.",
            utilisation="Tous les trois sont obligatoires. L'hote peut etre une adresse IP, un nom d'hote, ou un alias deja defini dans votre ~/.ssh/config.",
            action="Pris en compte au clic sur Enregistrer.",
            reaction="Aucun effet reseau - purement une definition locale, tant que 'Recuperer maintenant' n'est pas utilise.",
        ),
        FieldGuide(
            label="Utilisateur / Port / Chemin de la cle privee",
            definition="Optionnels - laissez vide pour utiliser les reglages par defaut de votre propre ssh (agent, ~/.ssh/config).",
            utilisation="Ne renseignez que ce qui differe des reglages par defaut de votre configuration SSH habituelle.",
            action="Pris en compte au clic sur Enregistrer.",
            reaction="Omega-Serv ne lit ni ne stocke JAMAIS le contenu d'une cle - uniquement son chemin, si vous en indiquez un.",
        ),
        FieldGuide(
            label="Recuperer maintenant",
            definition="Lance scp vers l'hote de la source selectionnee et ajoute le resultat a la Bibliotheque.",
            utilisation="Selectionner une ligne dans la table active le bouton.",
            action="Tourne en arriere-plan (l'interface reste utilisable) ; un message indique le resultat.",
            reaction=(
                "Ecrit un fichier dans var/log/remote/ (en ecrasant une eventuelle copie "
                "precedente de la meme source) et l'ajoute a la Bibliotheque (acces affiche comme "
                "'ssh', colonne 'Modifie' = date de CETTE recuperation, jamais celle du fichier "
                "distant) - en cas d'echec (hote injoignable, scp absent, droits refuses), le "
                "message d'erreur du systeme est affiche tel quel, aucun fichier n'est ajoute."
            ),
        ),
        FieldGuide(
            label="Supprimer",
            definition="Retire definitivement une source distante (ne supprime jamais un fichier deja recupere).",
            utilisation="Selectionner une ligne, confirmation obligatoire.",
            action="Retire l'entree du fichier var/remote-log-sources.json.",
            reaction="Un fichier deja recupere dans la Bibliotheque n'est pas retire par cette action.",
        ),
    ),
    consequences=(
        "Aucune action reseau n'est jamais entreprise automatiquement - uniquement au clic explicite "
        "sur 'Recuperer maintenant'. Aucun mot de passe n'est jamais demande ni stocke."
    ),
    points_de_vigilance=(
        (
            "Aucune verification de taille n'est faite avant ou pendant le transfert - un fichier "
            "distant tres volumineux sera recupere en integralite."
        ),
        (
            "Une adresse IPv6 ecrite directement (sans alias ~/.ssh/config) n'est pas supportee par "
            "la syntaxe hote:chemin de scp."
        ),
    ),
)

LOG_VIEW_SCREEN = ScreenGuide(
    screen_class_name="LogViewScreen",
    title="Voir les logs",
    acces="Accueil -> Gestion des logs -> Voir les logs",
    definition=(
        "Choisit un ou plusieurs logs EXCLUSIVEMENT depuis la Bibliotheque (aucun import "
        "manuel ici), puis un viewer : Simple (tail en direct + stats generiques), "
        "Classique (lecture + suivi), lnav (fusion multi-logs)."
    ),
    fields=(
        FieldGuide(
            label="Numeros (ex: 1,3)",
            definition="Selectionne un ou plusieurs logs de la Bibliotheque par leur numero de ligne.",
            utilisation="Separes par des virgules pour en selectionner plusieurs.",
            action="Determine les logs ouverts par les 3 boutons de viewer.",
            reaction="Aucun effet (lecture seule).",
        ),
        FieldGuide(
            label="Voir (simple) / Voir (classique) / Voir (lnav)",
            definition="Ouvre les logs selectionnes avec le viewer choisi.",
            utilisation="Simple et Classique exigent exactement UN log selectionne ; lnav fonctionne avec un ou plusieurs.",
            action="Ouvre l'ecran du viewer correspondant.",
            reaction="Refus explicite si le viewer est incompatible avec le nombre de logs selectionnes.",
        ),
    ),
    consequences="Purement consultatif - la selection de logs ici n'est jamais memorisee (voir Favoris pour cela).",
)

LOG_SIMPLE_VIEWER_SCREEN = ScreenGuide(
    screen_class_name="LogSimpleViewerScreen",
    title="Voir les logs - Simple",
    acces="Accueil -> Gestion des logs -> Voir les logs -> Voir (simple)",
    definition=(
        "Suit un log en direct avec un parseur GENERIQUE (fonctionne sur n'importe quel "
        "format - access log, auth.log, syslog...) et un petit tableau de statistiques "
        "(IPs uniques, taux d'erreur, repartition des codes HTTP si le format s'y prete)."
    ),
    fields=(),
    consequences="Purement consultatif, aucun effet sur le serveur.",
    points_de_vigilance=(
        (
            "La section 'STATUTS HTTP' n'apparait que si au moins une ligne du tampon "
            "ressemble a un access log Combined/Common - jamais affichee pour un auth.log/"
            "syslog."
        ),
    ),
)

LOG_VIEWER_SCREEN = ScreenGuide(
    screen_class_name="LogViewerScreen",
    title="Voir les logs - Classique",
    acces="Accueil -> Gestion des logs -> Voir les logs -> Voir (classique)",
    definition="Affiche les 200 dernieres lignes d'un log choisi dans la Bibliotheque et peut suivre son evolution en direct.",
    fields=(
        FieldGuide(
            label="Suivre en direct",
            definition="Rafraichit l'affichage automatiquement toutes les secondes avec les nouvelles lignes.",
            utilisation="Bascule marche/arret.",
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
    acces="Accueil -> Gestion des logs -> Voir les logs -> Voir (lnav), ou directement en cas de selection multiple",
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
            label="Logs selectionnes depuis la Bibliotheque (si ouvert via 'Voir les logs')",
            definition="Pre-coche les logs choisis dans l'ecran 'Voir les logs' - jamais ajoute aux epingles persistees.",
            utilisation="Decocher pour exclure un log de cette fusion ponctuelle.",
            action="Pris en compte au clic sur Lancer lnav.",
            reaction="Une selection ponctuelle depuis la Bibliotheque, contrairement a une epingle, ne survit pas a cet ecran.",
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

PROCESS_IP_SCREEN = ScreenGuide(
    screen_class_name="ProcessIpScreen",
    title="Voir et traiter IP",
    acces="Accueil -> Gestion des logs -> Voir et traiter IP",
    definition=(
        "Liste les IP les plus actives parmi un ou plusieurs logs de la Bibliotheque "
        "(n'importe quel format, pas seulement l'access log), avec possibilite de "
        "retirer une IP des logs analyses."
    ),
    fields=(
        FieldGuide(
            label="Numeros (ex: 1,2)",
            definition="Selectionne un ou plusieurs logs de la Bibliotheque a analyser.",
            utilisation="Separes par des virgules pour en analyser plusieurs ensemble.",
            action="Determine les logs lus par les boutons de periode.",
            reaction="Aucun effet (lecture seule).",
        ),
        FieldGuide(
            label="24 heures / 7 jours / 30 jours / Tout",
            definition="Choisit la periode analysee.",
            utilisation="Un clic recalcule immediatement la liste.",
            action="Relit et reanalyse les logs selectionnes.",
            reaction="Aucun effet (lecture seule).",
        ),
        FieldGuide(
            label="Retirer cette IP des logs analyses",
            definition="Supprime toutes les lignes contenant l'IP selectionnee, dans TOUS les logs analyses.",
            utilisation="Selectionner une ligne active le bouton, avec confirmation obligatoire.",
            action="Reecrit chaque fichier de log concerne sans les lignes de cette IP.",
            reaction="Modification DEFINITIVE et immediate des fichiers de log - action destructive.",
        ),
    ),
    consequences="Le retrait d'IP modifie directement et irreversiblement les fichiers de log concernes.",
    points_de_vigilance=(
        "La reconnaissance d'une IP dans une ligne ne depend d'aucun format particulier - fonctionne identiquement quel que soit le type de log.",
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

ALL_LOGS_GUIDES: tuple[ScreenGuide, ...] = (
    LOGS_MENU_SCREEN,
    LOG_LIBRARY_SCREEN,
    REMOTE_LOG_SOURCES_SCREEN,
    LOG_FAVORITES_SCREEN,
    LOG_VIEW_SCREEN,
    LOG_SIMPLE_VIEWER_SCREEN,
    LOG_VIEWER_SCREEN,
    LNAV_SCREEN,
    PROCESS_IP_SCREEN,
    LOG_ROTATION_SCREEN,
    RESTORE_LOG_ARCHIVE_SCREEN,
    PURGE_LOG_ARCHIVES_SCREEN,
    EXPORT_LOG_ARCHIVES_SCREEN,
)
