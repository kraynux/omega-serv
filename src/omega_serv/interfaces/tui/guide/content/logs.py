"""Fiches guide : Gestion des logs - menu en 2 colonnes (refonte
2026-10-15, au meme niveau qu'omega-log, OMEGA-LOG_PLAN) + sous-ecrans."""
from __future__ import annotations

from omega_serv.core.i18n import _
from omega_serv.interfaces.tui.guide.model import FieldGuide, ScreenGuide

LOGS_MENU_SCREEN = ScreenGuide(
    screen_class_name="LogsMenuScreen",
    title=_("Gestion des logs (menu)"),
    acces=_("Accueil -> Gestion des logs"),
    definition=(
        _("Sous-menu en 2 colonnes de 5 boutons : BIBLIOTHÈQUE (consultation - Bibliothèque, "
        "Favoris, Voir les logs, Voir et traiter IP, Statistiques) et MAINTENANCE (Rotate / "
        "archivage, Restaurer une archive, Purger les archives, Exporter, Santé des logs).")
    ),
    fields=(),
    consequences=_("Aucune - purement navigation."),
)

LOG_LIBRARY_SCREEN = ScreenGuide(
    screen_class_name="LogLibraryScreen",
    title=_("Bibliothèque"),
    acces=_("Accueil -> Gestion des logs -> Bibliothèque"),
    definition=(
        _("Hub central référençant tous les logs à traiter (ceux d'Omega-Serv ou tout "
        "autre fichier de log de la machine) - alimentation MANUELLE (aucun scan "
        "automatique du système pour cette passe). Source commune de 'Voir les logs', "
        "'Favoris' et 'Voir et traiter IP'.")
    ),
    fields=(
        FieldGuide(
            label=_("Chemin à ajouter manuellement"),
            definition=_("Référence un fichier de log quelconque dans la Bibliothèque."),
            utilisation=_("Chemin absolu ou relatif au projet - le fichier n'a pas besoin d'exister déjà."),
            action=_("Ajoute (ou remplace si déjà présent) une entrée."),
            reaction=_("Aucun effet sur le serveur - l'état (existe/taille) est toujours recalculé à l'affichage."),
        ),
        FieldGuide(
            label=_("Ajouter les logs connus d'Omega-Serv"),
            definition=_("Ajoute en un clic les logs propres à ce projet (access/error/waf-alerts, + magnet si actif)."),
            utilisation=_("Aucune saisie requise."),
            action=_("Ajoute (ou remplace) ces entrées dans la Bibliothèque."),
            reaction=_("Jamais un scan du reste du système - uniquement les quelques logs déjà connus de ce projet."),
        ),
        FieldGuide(
            label=_("Retirer la sélection"),
            definition=_("Retire une entrée de la Bibliothèque (ne supprime jamais le fichier lui-même)."),
            utilisation=_("Sélectionner une ligne, confirmation obligatoire."),
            action=_("Retire l'entrée du fichier var/library.json."),
            reaction=_("Le fichier de log sur disque n'est jamais touché - seule la référence est retirée."),
        ),
    ),
    consequences=_("Purement une liste de références - aucun effet sur les fichiers de log eux-mêmes."),
    points_de_vigilance=(
        (
            _("L'état affiché (OK/SUSPECT/ABSENT) est toujours recalculé en lisant le disque "
            "réellement à chaque ouverture de cet écran, jamais une donnée figée au moment "
            "de l'ajout.")
        ),
    ),
)

LOG_FAVORITES_SCREEN = ScreenGuide(
    screen_class_name="LogFavoritesScreen",
    title=_("Favoris"),
    acces=_("Accueil -> Gestion des logs -> Favoris"),
    definition=_("Combinaisons nommées (un ou plusieurs logs de la Bibliothèque + un viewer) pour un lancement direct."),
    fields=(
        FieldGuide(
            label=_("Lancer"),
            definition=_("Ouvre directement le favori sélectionné avec son viewer d'origine."),
            utilisation=_("Sélectionner une ligne dans la table des favoris."),
            action=_("Ouvre l'écran du viewer correspondant (Simple/Classique/lnav)."),
            reaction=_("Aucun effet sur le serveur (lecture seule)."),
        ),
        FieldGuide(
            label=_("Numéros + Nom du favori + Viewer + Enregistrer"),
            definition=_("Crée un nouveau favori à partir de logs choisis dans la Bibliothèque."),
            utilisation=(
                _("Numéros séparés par des virgules (ex: 1,3) - un seul log autorisé avec "
                "Simple/Classique, lnav uniquement au-delà d'un log.")
            ),
            action=_("Enregistre le favori (remplace un favori existant du même nom)."),
            reaction=_("Refuse à la création si le viewer choisi est incompatible avec le nombre de logs - jamais tronqué silencieusement."),
        ),
        FieldGuide(
            label=_("Supprimer"),
            definition=_("Retire définitivement un favori."),
            utilisation=_("Sélectionner une ligne, confirmation obligatoire."),
            action=_("Retire l'entrée du fichier var/favorites.json."),
            reaction=_("Ne touche jamais aux fichiers de log eux-mêmes ni à la Bibliothèque."),
        ),
    ),
    consequences=_("Purement des raccourcis - aucun effet sur les fichiers de log eux-mêmes."),
)

REMOTE_LOG_SOURCES_SCREEN = ScreenGuide(
    screen_class_name="RemoteLogSourcesScreen",
    title=_("Sources distantes (SSH)"),
    acces=_("Accueil -> Gestion des logs -> Bibliothèque -> Sources distantes (SSH)"),
    definition=(
        _("Permet de récupérer, à la demande, UNE COPIE du log d'un serveur backend situé sur le "
        "même réseau local (derrière le reverse proxy) via scp, puis de l'ajouter automatiquement "
        "à la Bibliothèque - ce n'est jamais une consultation en direct du serveur distant, mais "
        "un instantané figé au moment du clic sur 'Récupérer maintenant' ; une nouvelle "
        "récupération remplace la copie précédente par une plus récente. Aucun scan réseau "
        "automatique, aucune connexion sans configuration explicite de votre part.")
    ),
    fields=(
        FieldGuide(
            label=_("Label / Hôte / Chemin distant"),
            definition=_("Identifie la source : un nom de votre choix, l'adresse du serveur, et le chemin du fichier de log sur ce serveur."),
            utilisation=_("Tous les trois sont obligatoires. L'hôte peut être une adresse IP, un nom d'hôte, ou un alias déjà défini dans votre ~/.ssh/config."),
            action=_("Pris en compte au clic sur Enregistrer."),
            reaction=_("Aucun effet réseau - purement une définition locale, tant que 'Récupérer maintenant' n'est pas utilisé."),
        ),
        FieldGuide(
            label=_("Utilisateur / Port / Chemin de la clé privée"),
            definition=_("Optionnels - laissez vide pour utiliser les réglages par défaut de votre propre ssh (agent, ~/.ssh/config)."),
            utilisation=_("Ne renseignez que ce qui diffère des réglages par défaut de votre configuration SSH habituelle."),
            action=_("Pris en compte au clic sur Enregistrer."),
            reaction=_("Omega-Serv ne lit ni ne stocke JAMAIS le contenu d'une clé - uniquement son chemin, si vous en indiquez un."),
        ),
        FieldGuide(
            label=_("Récupérer maintenant"),
            definition=_("Lance scp vers l'hôte de la source sélectionnée et ajoute le résultat à la Bibliothèque."),
            utilisation=_("Sélectionner une ligne dans la table active le bouton."),
            action=_("Tourne en arrière-plan (l'interface reste utilisable) ; un message indique le résultat."),
            reaction=(
                _("Écrit un fichier dans var/log/remote/ (en écrasant une éventuelle copie "
                "précédente de la même source) et l'ajoute à la Bibliothèque (accès affiché comme "
                "'ssh', colonne 'Modifié' = date de CETTE récupération, jamais celle du fichier "
                "distant) - en cas d'échec (hôte injoignable, scp absent, droits refuses), le "
                "message d'erreur du système est affiché tel quel, aucun fichier n'est ajouté.")
            ),
        ),
        FieldGuide(
            label=_("Supprimer"),
            definition=_("Retire définitivement une source distante (ne supprime jamais un fichier déjà récupéré)."),
            utilisation=_("Sélectionner une ligne, confirmation obligatoire."),
            action=_("Retire l'entrée du fichier var/remote-log-sources.json."),
            reaction=_("Un fichier déjà récupéré dans la Bibliothèque n'est pas retiré par cette action."),
        ),
    ),
    consequences=(
        _("Aucune action réseau n'est jamais entreprise automatiquement - uniquement au clic explicite "
        "sur 'Récupérer maintenant'. Aucun mot de passe n'est jamais demandé ni stocké.")
    ),
    points_de_vigilance=(
        (
            _("Aucune vérification de taille n'est faite avant ou pendant le transfert - un fichier "
            "distant très volumineux sera récupéré en intégralité.")
        ),
        (
            _("Une adresse IPv6 écrite directement (sans alias ~/.ssh/config) n'est pas supportée par "
            "la syntaxe hôte:chemin de scp.")
        ),
    ),
)

LOG_VIEW_SCREEN = ScreenGuide(
    screen_class_name="LogViewScreen",
    title=_("Voir les logs"),
    acces=_("Accueil -> Gestion des logs -> Voir les logs"),
    definition=(
        _("Choisit un ou plusieurs logs EXCLUSIVEMENT depuis la Bibliothèque (aucun import "
        "manuel ici), puis un viewer : Simple (tail en direct + stats génériques), "
        "Classique (lecture + suivi), lnav (fusion multi-logs).")
    ),
    fields=(
        FieldGuide(
            label=_("Numéros (ex: 1,3)"),
            definition=_("Sélectionne un ou plusieurs logs de la Bibliothèque par leur numéro de ligne."),
            utilisation=_("Séparés par des virgules pour en sélectionner plusieurs."),
            action=_("Détermine les logs ouverts par les 3 boutons de viewer."),
            reaction=_("Aucun effet (lecture seule)."),
        ),
        FieldGuide(
            label=_("Voir (simple) / Voir (classique) / Voir (lnav)"),
            definition=_("Ouvre les logs sélectionnés avec le viewer choisi."),
            utilisation=_("Simple et Classique exigent exactement UN log sélectionné ; lnav fonctionne avec un ou plusieurs."),
            action=_("Ouvre l'écran du viewer correspondant."),
            reaction=_("Refus explicite si le viewer est incompatible avec le nombre de logs sélectionnés."),
        ),
    ),
    consequences=_("Purement consultatif - la sélection de logs ici n'est jamais mémorisée (voir Favoris pour cela)."),
)

LOG_SIMPLE_VIEWER_SCREEN = ScreenGuide(
    screen_class_name="LogSimpleViewerScreen",
    title=_("Voir les logs - Simple"),
    acces=_("Accueil -> Gestion des logs -> Voir les logs -> Voir (simple)"),
    definition=(
        _("Suit un log en direct avec un parseur GÉNÉRIQUE (fonctionne sur n'importe quel "
        "format - access log, auth.log, syslog...) et un petit tableau de statistiques "
        "(IPs uniques, taux d'erreur, répartition des codes HTTP si le format s'y prête).")
    ),
    fields=(),
    consequences=_("Purement consultatif, aucun effet sur le serveur."),
    points_de_vigilance=(
        (
            _("La section 'STATUTS HTTP' n'apparaît que si au moins une ligne du tampon "
            "ressemble à un access log Combined/Common - jamais affichée pour un auth.log/"
            "syslog.")
        ),
    ),
)

LOG_VIEWER_SCREEN = ScreenGuide(
    screen_class_name="LogViewerScreen",
    title=_("Voir les logs - Classique"),
    acces=_("Accueil -> Gestion des logs -> Voir les logs -> Voir (classique)"),
    definition=_("Affiche les 200 dernières lignes d'un log choisi dans la Bibliothèque et peut suivre son évolution en direct."),
    fields=(
        FieldGuide(
            label=_("Suivre en direct"),
            definition=_("Rafraîchit l'affichage automatiquement toutes les secondes avec les nouvelles lignes."),
            utilisation=_("Bascule marche/arret."),
            action=_("Demarre/arrete le suivi périodique."),
            reaction=_("Aucun effet sur le serveur (lecture seule)."),
        ),
    ),
    consequences=_("Purement consultatif, aucun effet sur le serveur ou sa configuration."),
    points_de_vigilance=(
        (
            _("Un fichier appartenant au compte système dédié du service peut rester illisible "
            "depuis une session qui n'a pas encore pris en compte son appartenance de groupe "
            "(mêmes causes que le piège déjà documenté pour SERVICE - reconnectez votre session).")
        ),
    ),
)

LNAV_SCREEN = ScreenGuide(
    screen_class_name="LnavScreen",
    title=_("Suivre les logs fusionnés (lnav)"),
    acces=_("Accueil -> Gestion des logs -> Voir les logs -> Voir (lnav), ou directement en cas de sélection multiple"),
    definition=_("Lance l'outil externe lnav sur un ou plusieurs logs fusionnés chronologiquement, dans un vrai terminal."),
    fields=(
        FieldGuide(
            label=_("Cases à cocher (Access/Error/WAF alerts log/WAF magnet)"),
            definition=(
                _("Choisit quels logs connus fusionner dans la même vue lnav - inclut d'office "
                "les 2 logs du script WAF complémentaire magnet (options.waf.magnet.paths, §7), "
                "même si le magnet n'est pas actif.")
            ),
            utilisation=(
                _("Une ou plusieurs cases, au moins un fichier existant requis. Un log coché mais "
                "absent (ex. magnet jamais activé) est simplement ignore au lancement, jamais "
                "bloquant pour les autres.")
            ),
            action=_("Pris en compte au clic sur Lancer lnav."),
            reaction=_("Aucun effet sur le serveur (lecture seule)."),
        ),
        FieldGuide(
            label=_("Logs sélectionnés depuis la Bibliothèque (si ouvert via 'Voir les logs')"),
            definition=_("Pré-coche les logs choisis dans l'écran 'Voir les logs' - jamais ajouté aux épingles persistées."),
            utilisation=_("Décocher pour exclure un log de cette fusion ponctuelle."),
            action=_("Pris en compte au clic sur Lancer lnav."),
            reaction=_("Une sélection ponctuelle depuis la Bibliothèque, contrairement à une épingle, ne survit pas à cet écran."),
        ),
        FieldGuide(
            label=_("Chemins épinglés (cases à cocher dynamiques)"),
            definition=(
                _("Chemins manuels ajoutés par 'Épingler ce chemin' - persistent entre sessions "
                "(contrairement au champ manuel ci-dessous), affiches comme des logs connus "
                "supplémentaires.")
            ),
            utilisation=_("Une case par chemin épinglé - coché ou non, comme les logs connus."),
            action=_("Pris en compte au clic sur Lancer lnav."),
            reaction=_("Aucun effet sur le serveur (lecture seule)."),
        ),
        FieldGuide(
            label=_("Chemin manuel + Épingler ce chemin"),
            definition=_("Saisit un chemin de log hors des logs connus, et le conserve pour les prochains lancements."),
            utilisation=(
                _("Chemin relatif au projet ou absolu. 'Épingler ce chemin' l'ajoute à la liste "
                "des épingles (ci-dessus) ET vide ce champ - sans epinglage, le chemin ne sert "
                "qu'une seule fois, pour ce lancement.")
            ),
            action=_("Chemin non épinglé : pris en compte au clic sur Lancer lnav, pour cette fois seulement. Épinglé : persiste (voir settings.json) jusqu'à retrait explicite."),
            reaction=_("Aucun effet sur le serveur."),
        ),
        FieldGuide(
            label=_("Retirer une épingle choisie"),
            definition=_("Retire définitivement un chemin de la liste des épingles."),
            utilisation=_("Choisir le chemin dans la liste déroulante, puis cliquer sur le bouton."),
            action=_("Supprime l'épingle et sa case à cocher correspondante."),
            reaction=_("Aucun effet sur le serveur - n'affecte jamais le fichier de log lui-même, seulement la liste des raccourcis."),
        ),
        FieldGuide(
            label=_("Lancer lnav"),
            definition=_("Ouvre lnav en plein écran dans le terminal réel."),
            utilisation=_("Nécessite au moins un fichier existant sélectionné."),
            action=_("Suspend l'interface et rend la main au terminal."),
            reaction=_("Aucun effet sur le serveur - quitter lnav (Ctrl-Q) revient à cet écran."),
        ),
    ),
    consequences=_("Purement consultatif."),
    points_de_vigilance=(
        _("Nécessite que l'outil lnav soit installé sur le système - indisponible sinon, message explicite."),
    ),
)

PROCESS_IP_SCREEN = ScreenGuide(
    screen_class_name="ProcessIpScreen",
    title=_("Voir et traiter IP"),
    acces=_("Accueil -> Gestion des logs -> Voir et traiter IP"),
    definition=(
        _("Liste les IP les plus actives parmi un ou plusieurs logs de la Bibliothèque "
        "(n'importe quel format, pas seulement l'access log), avec possibilité de "
        "retirer une IP des logs analyses.")
    ),
    fields=(
        FieldGuide(
            label=_("Numéros (ex: 1,2)"),
            definition=_("Sélectionne un ou plusieurs logs de la Bibliothèque à analyser."),
            utilisation=_("Séparés par des virgules pour en analyser plusieurs ensemble."),
            action=_("Détermine les logs lus par les boutons de période."),
            reaction=_("Aucun effet (lecture seule)."),
        ),
        FieldGuide(
            label=_("24h / 7j / 30j / Tout (fichier entier)"),
            definition=_("Choisit la période analysée."),
            utilisation=_("24h, 7j et 30j lisent depuis la fin du fichier (rapide) ; « Tout » lit le fichier "
                          "entier, de quelques secondes à plusieurs minutes pour un gros log. La taille et le "
                          "nombre de lignes estimé de la sélection s'affichent avant le clic."),
            action=_("Relit et analyse les logs sélectionnés en arrière-plan, sur plusieurs cœurs pour un gros "
                     "fichier : une roue, des messages, le temps écoulé et une barre de progression montrent "
                     "que le calcul avance. Les boutons de période restent grisés jusqu'à la fin."),
            reaction=_("Aucun effet (lecture seule). Échap arrête l'analyse : il faudra la relancer."),
        ),
        FieldGuide(
            label=_("IP à rechercher / Rechercher cette IP"),
            definition=_("Cherche une IP précise dans les logs sélectionnés, sans attendre qu'elle apparaisse "
                         "dans le top."),
            utilisation=_("Saisissez l'adresse (IPv4 ou IPv6, ex: 203.0.113.42), puis le bouton ou Entrée. Le "
                          "fichier entier est lu, en arrière-plan."),
            action=_("Compte les lignes de cette IP dans chaque log : le total et le détail par log s'affichent "
                     "au-dessus du tableau. Ce sont exactement les lignes que le retrait supprimerait."),
            reaction=_("Aucun effet (lecture seule). Si l'IP est présente, elle est déjà sélectionnée : « Retirer "
                       "cette IP » est actif ; après le retrait, l'IP est recomptée."),
        ),
        FieldGuide(
            label=_("Retirer cette IP des logs analyses"),
            definition=_("Supprime toutes les lignes contenant l'IP sélectionnée, dans TOUS les logs analyses."),
            utilisation=_("Sélectionner une ligne active le bouton, avec confirmation obligatoire."),
            action=_("Réécrit chaque fichier de log concerne sans les lignes de cette IP."),
            reaction=_("Modification DÉFINITIVE et immédiate des fichiers de log - action destructive."),
        ),
    ),
    consequences=_("Le retrait d'IP modifie directement et irréversiblement les fichiers de log concernés."),
    points_de_vigilance=(
        _("La reconnaissance d'une IP dans une ligne ne dépend d'aucun format particulier - fonctionne identiquement quel que soit le type de log."),
        _("Un log illisible par votre compte (par exemple /var/log/auth.log) : votre mot de passe sudo est "
          "demandé, puis le log est lu avec sudo. Refus : le chemin en cause est affiché."),
    ),
)

LOG_STATS_SCREEN = ScreenGuide(
    screen_class_name="LogStatsScreen",
    title=_("Statistiques"),
    acces=_("Accueil -> Gestion des logs -> Statistiques"),
    definition=_("Rapport de statistiques d'un ou plusieurs logs de la Bibliothèque, quel que soit leur format : "
                 "synthèse, statuts HTTP en jauges, top IP, chemins demandés et en 404, répartition horaire et "
                 "tendance par jour. Même écran qu'omega-log."),
    fields=(
        FieldGuide(
            label=_("Numéros (ex: 1,2)"),
            definition=_("Sélectionne un ou plusieurs logs de la Bibliothèque à analyser."),
            utilisation=_("Séparés par des virgules ; sans saisie, la ligne surlignée est utilisée."),
            action=_("Détermine les logs lus par les boutons de période."),
            reaction=_("Aucun effet (lecture seule)."),
        ),
        FieldGuide(
            label=_("24h / 7j / 30j / Tout (fichier entier)"),
            definition=_("Choisit la période et lance le calcul."),
            utilisation=_("Même fonctionnement que dans Voir et traiter IP : indicateur d'attente, barre de "
                          "progression, un seul calcul à la fois."),
            action=_("Calcule le rapport en arrière-plan et l'affiche sous les boutons."),
            reaction=_("Aucun effet (lecture seule)."),
        ),
        FieldGuide(
            label=_("Exporter JSON / Exporter HTML"),
            definition=_("Enregistre le dernier rapport calculé dans le répertoire d'export."),
            utilisation=_("Calculez d'abord une période ; choisissez le thème avant l'export HTML."),
            action=_("JSON : les données brutes. HTML : le rapport complet avec cartes, histogramme et jauges, "
                     "dans la langue des exports (Options)."),
            reaction=_("Écriture d'un fichier horodaté, aucun effet sur le serveur."),
        ),
    ),
    consequences=_("Purement consultatif - les logs ne sont jamais modifiés."),
    points_de_vigilance=(
        _("Les heures du log sont lues telles qu'elles sont écrites (fuseau ignoré) : la répartition horaire "
          "suit l'horloge du programme qui a écrit le log."),
        _("Un log illisible par votre compte (par exemple /var/log/auth.log) : votre mot de passe sudo est "
          "demandé, puis le log est lu avec sudo. Refus : le chemin en cause est affiché."),
    ),
)

LOG_ROTATION_SCREEN = ScreenGuide(
    screen_class_name="LogRotationScreen",
    title=_("Rotation / archivage des logs"),
    acces=_("Accueil -> Gestion des logs -> Rotation / archivage des logs"),
    definition=_("Quatre modes : rotation conditionnelle (seuil de taille), sauvegarde immédiate inconditionnelle, planifier une automatisation, gérer les automatisations existantes."),
    fields=(
        FieldGuide(
            label=_("Action"),
            definition=_("Choisit le mode de cet écran."),
            utilisation=(
                _("'Tourner si nécessaire' (respecte le seuil de taille configuré), 'Sauvegarde "
                "maintenant' (inconditionnelle), 'Configurer une automatisation', 'Gérer les "
                "automatisations'.")
            ),
            action=_("Change les champs affiches en dessous."),
            reaction=_("Aucun effet en lui-même, juste un changement d'affichage."),
        ),
        FieldGuide(
            label=_("Log cible"),
            definition=_("Le fichier de log concerne par l'action."),
            utilisation=_("access, error ou waf_alerts."),
            action=_("Utilisé par Valider."),
            reaction=_("Archive réellement le fichier immédiatement (modes rotation/sauvegarde)."),
        ),
        FieldGuide(
            label=_("Fréquence (mode automatisation)"),
            definition=_("À quelle fréquence l'automatisation doit se déclencher."),
            utilisation=_("Hebdomadaire, mensuelle, trimestrielle, semestrielle ou annuelle."),
            action=_("Utilisé par Valider."),
            reaction=_("Enregistre une automatisation, sans rotation immédiate. La première installe la tâche "
                       "planifiée qui l'exécute chaque nuit : timer systemd (mot de passe sudo demandé), sinon "
                       "ligne de votre crontab (OpenRC, runit, aucun gestionnaire), sinon la ligne à ajouter "
                       "vous-même est affichée."),
        ),
        FieldGuide(
            label=_("Automatisations planifiées (mode gestion)"),
            definition=_("Liste des automatisations, avec leur dernière et leur prochaine exécution, et l'état "
                         "de la tâche planifiée au-dessus."),
            utilisation=_("Sélectionner une ligne active le bouton de suppression."),
            action=_("Supprimer la sélection retire l'automatisation (avec confirmation). La dernière retirée "
                     "retire aussi la tâche planifiée."),
            reaction=_("Suppression immédiate et définitive de l'automatisation choisie."),
        ),
        FieldGuide(
            label=_("Réinstaller l'exécution"),
            definition=_("Réinstalle la tâche planifiée si elle a disparu (timer désactivé, crontab vidée)."),
            utilisation=_("Visible en mode gestion ; l'état affiché dit si c'est nécessaire."),
            action=_("Même installation qu'à la première automatisation."),
            reaction=_("Les automatisations s'exécutent de nouveau chaque nuit."),
        ),
    ),
    consequences=(
        _("'Tourner si nécessaire' ne fait rien si logs.rotation.enabled est désactivé dans la "
        "configuration, ou si le fichier n'a pas atteint le seuil de taille configuré. "
        "'Sauvegarde maintenant' archive TOUJOURS, quelle que soit la taille.")
    ),
    points_de_vigilance=(
        (
            _("Les archives sont écrites dans var/backups/logs/, un emplacement distinct de "
            "var/backups/ (réservé aux sauvegardes de configuration).")
        ),
        _("Chaque nuit, la tâche planifiée lance « omega-serv logs run-automations » sous votre compte, jamais "
          "root : chaque log dont l'échéance est passée est archivé comme avec « Sauvegarde maintenant ». Un échec "
          "est retenté la nuit suivante."),
        _("Sans systemd, la ligne crontab ne rattrape pas une nuit où la machine était éteinte : l'échéance part la "
          "première nuit où elle est allumée. Santé des logs signale une automatisation en retard."),
    ),
)

RESTORE_LOG_ARCHIVE_SCREEN = ScreenGuide(
    screen_class_name="RestoreLogArchiveScreen",
    title=_("Restaurer une archive de log"),
    acces=_("Accueil -> Gestion des logs -> Restaurer une archive de log"),
    definition=_("Extrait le contenu d'une archive de log déjà créée vers un répertoire de restauration."),
    fields=(
        FieldGuide(
            label=_("Table des archives + Restaurer"),
            definition=_("Sélectionne une archive et l'extrait."),
            utilisation=_("Sélectionner une ligne active le bouton Restaurer."),
            action=_("Extrait l'archive vers var/log/restored/<nom-archive>/."),
            reaction=_("Écriture réelle sur disque immédiate, aucun effet sur le serveur en cours."),
        ),
    ),
    consequences=_("N'écrase jamais les logs actifs - extrait toujours vers un sous-répertoire dédié."),
)

PURGE_LOG_ARCHIVES_SCREEN = ScreenGuide(
    screen_class_name="PurgeLogArchivesScreen",
    title=_("Purger les archives de logs"),
    acces=_("Accueil -> Gestion des logs -> Purger les archives de logs"),
    definition=_("Supprime définitivement une archive de log."),
    fields=(
        FieldGuide(
            label=_("Table des archives + Supprimer"),
            definition=_("Sélectionne une archive et la supprime."),
            utilisation=_("Sélectionner une ligne active le bouton Supprimer, avec confirmation obligatoire."),
            action=_("Supprime le fichier d'archive."),
            reaction=_("Suppression immédiate et DÉFINITIVE - action destructive, jamais réversible."),
        ),
    ),
    consequences=_("Action irréversible - aucune corbeille ni sauvegarde préalable automatique."),
)

EXPORT_LOG_ARCHIVES_SCREEN = ScreenGuide(
    screen_class_name="ExportLogArchivesScreen",
    title=_("Exporter Archives"),
    acces=_("Accueil -> Gestion des logs -> Exporter Archives"),
    definition=_("Exporte la liste des archives de logs (métadonnées, pas leur contenu) en JSON ou HTML."),
    fields=(
        FieldGuide(
            label=_("Thème d'export HTML"),
            definition=_("Palette de couleurs utilisée pour l'export HTML."),
            utilisation=_("5 thèmes disponibles."),
            action=_("Utilisé au clic sur Exporter HTML."),
            reaction=_("Aucun effet sur le serveur."),
        ),
        FieldGuide(
            label=_("Exporter JSON / Exporter HTML"),
            definition=_("Génère le fichier d'export dans le répertoire d'export configuré."),
            utilisation=_("Aucune saisie supplémentaire."),
            action=_("Écrit un fichier horodate (jamais d'écrasement silencieux d'un export précédent)."),
            reaction=_("Écriture réelle sur disque immédiate, aucun effet sur le serveur."),
        ),
    ),
    consequences=_("Purement consultatif/export - aucun effet sur la configuration ou le serveur."),
    points_de_vigilance=(
        _("Le répertoire d'export peut être changé dans l'écran Réglages de l'application (touche 'o')."),
    ),
)

LOG_HEALTH_SCREEN = ScreenGuide(
    screen_class_name="LogHealthScreen",
    title=_("Santé des logs"),
    acces=_("Accueil -> Gestion des logs -> Santé des logs"),
    definition=_("Contrôle en lecture seule des logs d'omega-serv et de ceux de la Bibliothèque, du disque qui "
                 "les porte et des archives. Chaque log reçoit un niveau : OK, Info, Attention ou Problème."),
    fields=(
        FieldGuide(
            label=_("Tableau des logs"),
            definition=_("Une ligne par log : état (niveau), chemin, taille, dernière écriture et constat le "
                         "plus grave."),
            utilisation=_("Surlignez une ligne pour voir sous le tableau tous ses constats et, pour chacun, ce "
                          "que vous pouvez faire (commande ou écran à ouvrir)."),
            action=_("Contrôles : fichier absent ou lien cassé, droits (lecture par votre compte, écriture "
                     "par le compte du service, écriture par tout le monde), log muet depuis plus de 7 jours, "
                     "fichier vide, dates non reconnues ou dans le futur, octets nuls (log abîmé), seuil de "
                     "rotation dépassé, gros log sans règle logrotate, doublon dans la Bibliothèque."),
            reaction=_("Aucun effet : seuls le début et la fin de chaque log sont lus."),
        ),
        FieldGuide(
            label=_("Corriger les droits"),
            definition=_("Rend un log d'omega-serv de nouveau inscriptible par le compte du service."),
            utilisation=_("Actif seulement si vous êtes propriétaire du fichier et que le compte du service est "
                          "dans son groupe. Confirmation obligatoire."),
            action=_("Ajoute le droit d'écriture du groupe (par exemple 644 → 664), jamais avec sudo, jamais pour "
                     "tout le monde."),
            reaction=_("Le service peut de nouveau écrire ses lignes ; l'analyse est relancée."),
        ),
        FieldGuide(
            label=_("Corriger avec sudo"),
            definition=_("Corrige les droits quand « Corriger les droits » ne suffit pas (fichier à root, groupe "
                         "étranger au service) ou qu'un log est inscriptible par tout le monde."),
            utilisation=_("La commande exacte est montrée avant ; votre mot de passe sudo est demandé ensuite."),
            action=_("chgrp vers le compte du service puis chmod g+w, ou chmod o-w : jamais chown, jamais "
                     "récursif, un seul fichier."),
            reaction=_("Droits corrigés ; l'analyse est relancée."),
        ),
        FieldGuide(
            label=_("Analyser avec sudo"),
            definition=_("Complète l'analyse des logs illisibles par votre compte."),
            utilisation=_("Actif seulement si au moins un log est illisible ; mot de passe sudo demandé."),
            action=_("Lit avec sudo le début et la fin de ces logs : dates, format, octets nuls."),
            reaction=_("Le constat « illisible par votre compte » reste affiché : il est toujours vrai."),
        ),
        FieldGuide(
            label=_("Exporter JSON / Exporter HTML / Exporter TXT"),
            definition=_("Enregistre le rapport dans le répertoire d'export."),
            utilisation=_("Choisissez le thème avant l'export HTML."),
            action=_("JSON : les codes et valeurs (données). HTML et TXT : le rapport lisible, avec les "
                     "conseils, dans la langue des exports (Options)."),
            reaction=_("Écriture d'un fichier horodaté, aucun effet sur le serveur."),
        ),
    ),
    consequences=_("Lecture seule, sauf « Corriger les droits » et « Corriger avec sudo », après confirmation."),
    points_de_vigilance=(
        _("La croissance par jour est estimée d'après la première et la dernière date du log : elle sert à "
          "prévoir dans combien de jours le disque sera plein."),
        _("Au-delà du seuil de rotation, utilisez Rotate / archivage : sauvegarde immédiate, ou automatisation "
          "planifiée exécutée chaque nuit."),
        _("Section AUTOMATISATIONS : signale une automatisation de rotation en échec ou en retard de plus de 2 jours, "
          "et des automatisations sans tâche planifiée pour les exécuter."),
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
    LOG_STATS_SCREEN,
    LOG_ROTATION_SCREEN,
    RESTORE_LOG_ARCHIVE_SCREEN,
    PURGE_LOG_ARCHIVES_SCREEN,
    EXPORT_LOG_ARCHIVES_SCREEN,
    LOG_HEALTH_SCREEN,
)
