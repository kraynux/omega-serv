"""Fiches guide : Registre des capacites, Profils, Audit de securite,
Sauvegarde de configuration, Reglages de l'application (plan guide
d'aide, Phase 9)."""
from __future__ import annotations

from omega_serv.core.i18n import _
from omega_serv.interfaces.tui.guide.model import FieldGuide, ScreenGuide

CAPABILITIES_SCREEN = ScreenGuide(
    screen_class_name="CapabilitiesScreen",
    title=_("Registre des capacités"),
    acces=_("Accueil -> Registre des capacités"),
    definition=_("Scan complet de l'environnement (port libre, openssl présent, PHP-FPM si FastCGI actif...), avec export."),
    fields=(
        FieldGuide(
            label=_("Thème d'export HTML"),
            definition=_("Palette de couleurs pour l'export HTML."),
            utilisation=_("5 thèmes disponibles."),
            action=_("Utilisé au clic sur Exporter HTML."),
            reaction=_("Aucun effet sur le serveur."),
        ),
        FieldGuide(
            label=_("Rafraîchir / Exporter JSON / Exporter HTML"),
            definition=_("Relance le scan, ou exporte son résultat."),
            utilisation=_("Aucune saisie supplémentaire."),
            action=_("Rafraîchir relance le scan ; les exports écrivent un fichier horodate."),
            reaction=_("Aucun effet sur le serveur ou sa configuration (lecture seule + export)."),
        ),
    ),
    consequences=_("Purement consultatif/export."),
)

CAPABILITY_DETAIL_SCREEN = ScreenGuide(
    screen_class_name="CapabilityDetailScreen",
    title=_("Détail d'une capacité"),
    acces=_("Registre des capacités -> clic sur une ligne"),
    definition=_("Détail complet d'une capacité déjà scannee (jamais un nouveau scan) : statut, raison, détails techniques, date du dernier scan."),
    fields=(),
    consequences=_("Purement consultatif."),
)

PROFILES_SCREEN = ScreenGuide(
    screen_class_name="ProfilesScreen",
    title=_("Profils"),
    acces=_("Accueil -> Profils"),
    definition=_("Liste les 4 profils fournis (minimal/standard/hardened/development) et vos profils "
                 "personnalisés (colonne Type), avec leur libellé."),
    fields=(
        FieldGuide(
            label=_("Appliquer"),
            definition=_("Ouvre l'écran de confirmation d'application du profil sélectionné."),
            utilisation=_("Sélectionner un profil active ce bouton."),
            action=_("Ouvre ApplyProfileScreen."),
            reaction=_("Un profil personnalisé ne fixe que la sécurité et l'état des options : adresse, port, TLS, "
                       "chemins, journaux et réglages des options (zones, listes) restent ceux de l'instance."),
        ),
        FieldGuide(
            label=_("Créer un profil personnalisé"),
            definition=_("Ouvre l'assistant. Si un profil personnalisé est sélectionné, l'assistant repart de ses "
                         "choix (un profil personnalisé ne se modifie pas : on en recrée un)."),
            utilisation=_("Aucune limite de nombre : un seul profil est appliqué à la fois."),
            action=_("Enregistre config/profiles/custom/<nom>.json ; la configuration n'est pas touchée."),
            reaction=_("Compris dans toute sauvegarde de configuration et repris lors d'une mise à jour."),
        ),
        FieldGuide(
            label=_("Supprimer"),
            definition=_("Supprime le profil personnalisé sélectionné, après confirmation."),
            utilisation=_("Grisé pour les profils fournis."),
            action=_("Efface son fichier ; la configuration actuelle n'est pas modifiée."),
            reaction=_("Aucun effet sur le serveur."),
        ),
    ),
    consequences=_("Aucune modification de la configuration depuis cet écran lui-même."),
)

CUSTOM_PROFILE_SCREEN = ScreenGuide(
    screen_class_name="CustomProfileScreen",
    title=_("Créer un profil personnalisé"),
    acces=_("Accueil -> Profils -> Créer un profil personnalisé"),
    definition=_("Assistant guidé : on part d'un serveur web minimal sans protection et on choisit chaque réglage "
                 "dans une liste. Ce que le cœur HTTP impose (analyse stricte, confinement au webroot, rejet de la "
                 "traversée, normalisation, HSTS jamais sans TLS) reste toujours actif et n'est pas proposé."),
    fields=(
        FieldGuide(
            label=_("Nom, libellé, description"),
            definition=_("Identification du profil, relue par le tableau de bord."),
            utilisation=_("Nom : 3 à 32 caractères a-z, 0-9, « - », « _ » (nom du fichier), jamais celui d'un autre "
                          "profil. Libellé : 3 à 40 caractères imprimables. Description : 200 au plus."),
            action=_("Vérifiés à chaque frappe ; l'erreur s'affiche sous le champ, rien n'est effacé."),
            reaction=_("Enregistrer reste grisé tant qu'un champ est faux."),
        ),
        FieldGuide(
            label=_("Choix"),
            definition=_("En-têtes de sécurité, CSP, fichiers cachés, Host, méthodes HTTP, WAF, authentification, "
                         "directory listing, FastCGI, cache, proxy de confiance, contrôle d'accès, reverse proxy."),
            utilisation=_("Listes déroulantes uniquement : aucune valeur à deviner ou à taper."),
            action=_("La vérification se met à jour à chaque changement."),
            reaction=_("Les réglages détaillés (zones, listes, règles) se font ensuite dans la Configuration "
                       "détaillée, comme pour tout profil."),
        ),
        FieldGuide(
            label=_("Vérification"),
            definition=_("Les « trous » de la combinaison choisie : bloquants (ex. FastCGI sans POST) ou à accepter "
                         "(ex. pas d'en-têtes de sécurité, fichiers cachés servis, pas de WAF), plus les contrôles "
                         "de la configuration qui en résulterait."),
            utilisation=_("Un trou bloquant se corrige en changeant un choix ; chaque trou à accepter est décrit, "
                          "suivi de sa propre case « J'accepte ce point »."),
            action=_("Enregistrer n'est actif que sans trou bloquant et avec chaque trou accepté."),
            reaction=_("Jamais une erreur découverte après coup."),
        ),
    ),
    consequences=_("Enregistrer crée le profil sans l'appliquer : appliquez-le ensuite depuis l'écran Profils, "
                   "avec la différence complète affichée avant."),
)

APPLY_PROFILE_SCREEN = ScreenGuide(
    screen_class_name="ApplyProfileScreen",
    title=_("Appliquer un profil"),
    acces=_("Profils -> Appliquer"),
    definition=_("Affiche TOUJOURS la différence complète avant toute confirmation, puis écrase la configuration active avec le profil choisi."),
    fields=(
        FieldGuide(
            label=_("Appliquer"),
            definition=_("Confirme et écrit le profil choisi."),
            utilisation=_("Le diff complet est déjà affiché au-dessus - à vérifier avant de cliquer."),
            action=_("Écrase config/omega-serve.json avec la configuration composée du profil."),
            reaction=(
                _("Un profil peut changer N'IMPORTE QUEL réglage d'un coup. Si bind/port/"
                "listen_backlog/TLS changent, un REDÉMARRAGE COMPLET est nécessaire ; sinon un "
                "simple rechargement suffit (automatique si un service actif existe).")
            ),
        ),
    ),
    consequences=_("Des conflits ou erreurs de validation bloquants demandent une confirmation supplémentaire explicite pour forcer quand même."),
    points_de_vigilance=(
        _("Un profil ne modifie QUE les champs qu'il spécifie explicitement - le reste de la configuration active est conservé tel quel."),
    ),
)

AUDIT_SCREEN = ScreenGuide(
    screen_class_name="AuditScreen",
    title=_("Audit de sécurité"),
    acces=_("Accueil -> Audit de sécurité"),
    definition=_("Vérifications consultatives (service, rotation des logs, mode WAF...) - mêmes règles que l'audit CLI."),
    fields=(
        FieldGuide(
            label=_("Auditer"),
            definition=_("Relance explicitement l'audit."),
            utilisation=_("Aucune saisie - un premier audit a déjà lieu automatiquement à l'ouverture de l'écran."),
            action=_("Relit la configuration et recalculé toutes les règles d'audit."),
            reaction=_("Aucun effet sur le serveur (lecture seule) - notifie explicitement le résultat sur un clic explicite."),
        ),
        FieldGuide(
            label=_("Fichiers sensibles sous webroot (PERM-003, PERM-004)"),
            definition=_("Chaque fichier est nommé sous le constat, avec la raison (nom connu comme .env, ou "
                         "extension comme .key) et ce qu'il contient vraiment, lu dans le fichier et non deviné "
                         "d'après son nom : clé privée, certificat, conteneur PKCS#12, dossier, contenu présent ou "
                         "fichier vide."),
            utilisation=_("Un fichier qui a du contenu est critique (PERM-003). Un fichier vide, par exemple un "
                          "exemple posé pour l'icône du directory listing, est seulement une information (PERM-004)."),
            action=_("Dix fichiers au plus sont listés à l'écran, puis « et N autres » ; la liste complète est "
                     "dans « omega-serv audit security --format json »."),
            reaction=_("Rien n'est déplacé ni supprimé : à vous de sortir ces fichiers du webroot (ex. secure/)."),
        ),
    ),
    consequences=_("Purement consultatif - ne modifie jamais rien."),
)

BACKUP_SCREEN = ScreenGuide(
    screen_class_name="BackupScreen",
    title=_("Sauvegarde de configuration"),
    acces=_("Accueil -> Sauvegarde de configuration"),
    definition=_("Créer, lister, restaurer ou supprimer des sauvegardes complètes de la configuration - le fichier de configuration est toujours inclus, jamais chiffre par défaut."),
    fields=(
        FieldGuide(
            label=_("Tout sauvegarder (configuration complète)"),
            definition=_("Coche toutes les cases : de quoi retrouver la configuration entière et ses modules."),
            utilisation=_("Case à cocher ; les secrets (zones Auth, clés TLS) restent confirmés à la création."),
            action=_("Pris en compte à la création."),
            reaction=_("Ce qui est désigné hors du dossier omega-serv (ex. un certificat dans /etc) n'est jamais "
                       "archivé, et c'est indiqué après la création."),
        ),
        FieldGuide(
            label=_("RIPOSTE, pages d'erreur, préférences, bibliothèque des journaux"),
            definition=_("Base RIPOSTE ; pages d'erreur personnalisées ; thème, langues et nom du service ; "
                         "favoris, sources distantes et rotations planifiées des journaux."),
            utilisation=_("Cases à cocher. Les règles WAF comprennent aussi les listes de mots-clés et les scripts Magnet."),
            action=_("Pris en compte à la création ; les bases (Active Defense, RIPOSTE) sont copiées de façon "
                     "cohérente, serveur en marche."),
            reaction=_("Une sauvegarde qui contient une base n'est jamais restaurée sous un serveur actif : "
                       "« Arrêter, restaurer, redémarrer » est proposé, et les bases actuelles sont mises de côté."),
        ),
        FieldGuide(
            label=_("Inclure les règles WAF"),
            definition=_("Ajoute les règles WAF et la liste de blocage à la sauvegarde."),
            utilisation=_("Case à cocher."),
            action=_("Pris en compte à la création."),
            reaction=_("Aucun effet immédiat - juste le contenu de la sauvegarde créée."),
        ),
        FieldGuide(
            label=_("Inclure les zones d'authentification"),
            definition=_("Ajoute users.json/zones.json (SECRETS RÉELS : hash de mots de passe) à la sauvegarde."),
            utilisation=_("Case à cocher - demande une confirmation supplémentaire explicite si cochée."),
            action=_("Pris en compte à la création."),
            reaction=_("La sauvegarde contient des secrets réels, jamais chiffres."),
        ),
        FieldGuide(
            label=_("Inclure les certificats"),
            definition=_("Ajoute les certificats TLS, CLÉS PRIVÉES INCLUSES, à la sauvegarde."),
            utilisation=_("Case à cocher - demande une confirmation supplémentaire explicite si cochée."),
            action=_("Pris en compte à la création."),
            reaction=_("La sauvegarde contient des clés privées réelles, jamais chiffrées."),
        ),
        FieldGuide(
            label=_("Inclure Active Defense"),
            definition=_("Ajoute la base de menaces/incidents Active Defense à la sauvegarde."),
            utilisation=_("Case à cocher."),
            action=_("Pris en compte à la création."),
            reaction=_("Aucun effet immédiat."),
        ),
        FieldGuide(
            label=_("Inclure le contenu du site (webroot)"),
            definition=_("Ajoute tout le dossier du site (pages, images, fichiers), en plus de la configuration."),
            utilisation=_("Case à cocher, jamais comprise dans « Tout sauvegarder » : ce n'est pas de la "
                          "configuration, et un gros site rend la sauvegarde longue et lourde."),
            action=_("La liste affiche un indicateur d'attente pendant la création ; l'écran reste utilisable."),
            reaction=_("La configuration, elle, contient déjà tout ce qui a été saisi à la main (alias, rewrites, "
                       "redirections, directory listing, cache, reverse proxy et ses zones)."),
        ),
        FieldGuide(
            label=_("Inclure les données des zones personnalisées"),
            definition=_("Ajoute les dossiers vers lesquels pointent les zones : cible des alias, dossiers du "
                         "listing (avec leurs fichiers HEADER et README), scripts FastCGI (hors du site par "
                         "construction). Les réglages de toutes les zones sont déjà dans la configuration."),
            utilisation=_("Case à cocher, jamais comprise dans « Tout sauvegarder ». Rewrites, redirections et cache "
                          "n'ont que des réglages ; le cache du reverse proxy se reconstruit et n'est jamais sauvegardé."),
            action=_("Un dossier déjà couvert par le contenu du site n'est archivé qu'une fois. Une cible hors du "
                     "dossier omega-serv (alias vers /srv/..., par exemple) est signalée après la création, pas "
                     "sauvegardée."),
            reaction=_("À l'import, ces dossiers sont acceptés seulement si la configuration de l'archive les "
                       "désigne, jamais un emplacement de l'installation (src, tools, native...)."),
        ),
        FieldGuide(
            label=_("Inclure les rapports d'export"),
            definition=_("Ajoute le dossier des exports (rapports HTML, TXT, JSON, IoC...) : celui choisi dans "
                         "Réglages, var/exports par défaut."),
            utilisation=_("Case à cocher, jamais comprise dans « Tout sauvegarder » : ce sont des documents produits, "
                          "pas de la configuration."),
            action=_("Un dossier d'export hors du dossier omega-serv est signalé, pas sauvegardé."),
            reaction=_("Aucun effet immédiat - juste le contenu de la sauvegarde créée."),
        ),
        FieldGuide(
            label=_("Exporter"),
            definition=_("Copie la sauvegarde SÉLECTIONNÉE hors du dossier omega-serv, avec son empreinte .sha256."),
            utilisation=_("Dossier de destination (votre dossier personnel par défaut). Un fichier déjà présent "
                          "n'est jamais écrasé ; l'archive est lisible par vous seul (elle peut contenir des secrets)."),
            action=_("Écrit omega-serv-<instance>-<id>.tar.gz et le fichier .sha256 à côté."),
            reaction=_("Une sauvegarde exportée survit à la désinstallation d'omega-serv (le dossier var/backups "
                       "est supprimé avec l'instance)."),
        ),
        FieldGuide(
            label=_("Importer une sauvegarde"),
            definition=_("Ajoute à la liste une sauvegarde exportée, par exemple sur une installation neuve."),
            utilisation=_("Chemin de l'archive ; son fichier .sha256 doit être à côté. Refusée si l'empreinte est "
                          "absente ou fausse, si l'archive contient un chemin absolu, « .. », un lien ou un "
                          "emplacement qu'une sauvegarde omega-serv ne contient pas, ou si elle n'a pas de "
                          "config/omega-serve.json."),
            action=_("Copie l'archive vérifiée dans la liste ; rien n'est encore restauré."),
            reaction=_("La restauration reste une étape à part, confirmée : la fenêtre signale une version "
                       "d'omega-serv différente et un conflit de port avec une autre instance (on peut alors "
                       "garder l'adresse, le port et le nom de service de l'instance actuelle)."),
        ),
        FieldGuide(
            label=_("Description"),
            definition=_("Note libre associée à la sauvegarde, pour la retrouver plus tard."),
            utilisation=_("Texte libre, optionnel."),
            action=_("Enregistrée avec la sauvegarde."),
            reaction=_("Aucun effet immédiat."),
        ),
        FieldGuide(
            label=_("Restaurer"),
            definition=_("Écrase les fichiers actuels avec ceux de la sauvegarde sélectionnée, AUX MÊMES EMPLACEMENTS."),
            utilisation=_("Sélectionner une sauvegarde, puis confirmer."),
            action=_("Écriture réelle et immédiate des fichiers concernés."),
            reaction=(
                _("Nécessite TOUJOURS un REDÉMARRAGE COMPLET par prudence - une restauration peut "
                "écraser n'importe quel fichier (configuration, certificats TLS...), et un "
                "certificat déjà en mémoire ne se recharge jamais tout seul.")
                + " "
                + _("Après la restauration, les dossiers des zones actives qui manquent sur le disque (cible d'un "
                "alias, dossier d'un listing, scripts d'une zone FastCGI) sont listés sous la liste des "
                "sauvegardes : un alias ou un listing absent répond 404, une zone FastCGI active sans dossier "
                "empêche le serveur de démarrer.")
            ),
        ),
        FieldGuide(
            label=_("Supprimer"),
            definition=_("Supprime définitivement une sauvegarde (n'existe pas côté CLI, confort TUI uniquement)."),
            utilisation=_("Sélectionner une sauvegarde, puis confirmer."),
            action=_("Suppression immédiate et définitive."),
            reaction=_("Aucun effet sur le serveur - seulement sur les sauvegardes disponibles."),
        ),
    ),
    consequences=_("Restaurer écrase directement les fichiers vises, sans filet - la seule protection est la confirmation demandée avant."),
)

SETTINGS_SCREEN = ScreenGuide(
    screen_class_name="SettingsScreen",
    title=_("Réglages de l'application"),
    acces=_("Raccourci clavier 'o' (footer), depuis n'importe quel écran"),
    definition=(
        _("PRÉFÉRENCES D'INTERFACE uniquement (thème, rendu, chemins d'export/captures) - "
        "PAS des réglages du serveur (ceux-là vivent dans Configuration détaillée).")
    ),
    fields=(
        FieldGuide(
            label=_("Thème"),
            definition=_("Thème visuel de l'interface elle-même."),
            utilisation=_("Un des thèmes disponibles."),
            action=_("Appliqué immédiatement au changement."),
            reaction=_("Effet immédiat, aucun redémarrage nécessaire."),
        ),
        FieldGuide(
            label=_("Profil de rendu"),
            definition=_("Force un profil de rendu Textual particulier plutôt que la détection automatique."),
            utilisation=_("Automatique, ou un profil précis."),
            action=_("Enregistre la préférence."),
            reaction=_("Appliqué seulement AU PROCHAIN DÉMARRAGE de l'interface, jamais à chaud."),
        ),
        FieldGuide(
            label="Langue / Language",
            definition=(
                _("Langue de l'interface. Chaque langue est écrite dans sa propre langue, Français "
                "toujours en tête ; le libellé 'Langue / Language' n'est jamais traduit, pour être "
                "retrouvé même dans une langue qu'on ne lit pas. Une langue non encore validée "
                "porte la mention 'en test'.")
            ),
            utilisation=_("Choisir une langue dans la liste, puis confirmer le redémarrage de l'interface."),
            action=(
                _("Enregistre la langue puis redémarre L'INTERFACE (pas le service : le serveur continue "
                "de tourner). Un écran de confirmation affiche la langue et la phrase d'invite déjà traduite.")
            ),
            reaction=(
                _("Retour au français toujours possible : ce même réglage ; ou lancer une fois "
                "'OMEGA_SERV_LANG=fr serv' ; ou retirer la clé 'language' de var/settings.json. Langue "
                "indisponible ou catalogue illisible : l'interface démarre en français avec un message. "
                "Les journaux du serveur (journalctl) restent toujours en français.")
            ),
        ),
        FieldGuide(
            label=_("Export / Captures d'écran (chemins)"),
            definition=_("Répertoires où sont écrits les exports et les captures d'écran."),
            utilisation=_("Chemin libre - vide revient au répertoire par défaut."),
            action=_("Enregistre à chaque changement de texte."),
            reaction=_("Effet immédiat sur les prochains exports/captures."),
        ),
        FieldGuide(
            label=_("Langue des exports"),
            definition=_(
                "Langue des exports HTML (registre des capacités, archives de logs, guide d'aide) et du "
                "rapport d'incident Markdown - un fichier qui se diffuse, pas forcément à quelqu'un qui "
                "lit la langue de l'interface. Les exports JSON et CSV n'ont pas de texte à traduire."
            ),
            utilisation=_("« Comme l'interface » (défaut) ou une des langues de la liste."),
            action=_(
                "Enregistre immédiatement. Dans une autre langue que l'interface, chaque export est "
                "produit par un processus séparé lancé dans cette langue : quelques secondes, "
                "l'interface reste utilisable."
            ),
            reaction=_(
                "Si ce processus échoue, l'export HTML n'est pas écrit (raison affichée) ; le rapport "
                "d'incident, lui, est quand même écrit dans la langue de l'interface, avec un avertissement."
            ),
        ),
        FieldGuide(
            label=_("Supprimer les exports / Supprimer les screenshots"),
            definition=_("Vide complètement le répertoire concerne."),
            utilisation=_("Confirmation obligatoire."),
            action=_("Suppression immédiate et définitive de tous les fichiers du répertoire."),
            reaction=_("Action irréversible."),
        ),
    ),
    consequences=_("Ne touche jamais config/omega-serve.json - réglages purement locaux à cette interface."),
)

CONTACT_SUPPORT_SCREEN = ScreenGuide(
    screen_class_name="ContactSupportScreen",
    title=_("Contact et support"),
    acces=_("Guide d'aide (touche a) -> Contact et support"),
    definition=_("Payer un café au développeur, se déclarer utilisateur anonyme d'omega-serv, contacter le "
                 "support, ou vérifier si une nouvelle version est publiée. Les adresses sont toujours affichées "
                 "en clair."),
    fields=(
        FieldGuide(
            label=_("Payer un café"),
            definition=_("Ouvre la page PayPal du développeur (https://paypal.me/kraynux)."),
            utilisation=_("Aucune saisie."),
            action=_("Ouvre l'adresse dans votre navigateur, même si l'interface tourne sous sudo."),
            reaction=_("Sans session graphique (SSH, serveur), un message rappelle l'adresse à ouvrir vous-même."),
        ),
        FieldGuide(
            label=_("Se déclarer utilisateur (anonyme) / Modifier ma déclaration"),
            definition=_("Ouvre le formulaire de déclaration anonyme."),
            utilisation=_("Le libellé devient « Modifier ma déclaration » une fois déclaré."),
            action=_("Ouvre le formulaire Se déclarer utilisateur (anonyme)."),
            reaction=_("Aucun effet ici - voir la fiche du formulaire."),
        ),
        FieldGuide(
            label=_("Ne plus me déclarer"),
            definition=_("Retire la déclaration."),
            utilisation=_("Actif seulement une fois déclaré ; une confirmation est demandée."),
            action=_("Envoie un retrait : votre entrée est supprimée du compteur, puis la clé est effacée de cette "
                     "installation et les envois quotidiens s'arrêtent."),
            reaction=_("Réception injoignable : la clé est quand même effacée ; l'entrée disparaît seule (90 jours "
                       "en envoi quotidien, 1 an en envoi unique)."),
        ),
        FieldGuide(
            label=_("Contacter le support"),
            definition=_("Ouvre le formulaire de contact du site (https://kraynux.snake-mackarel.ts.net/contact/). "
                         "L'adresse kraynux@proton.me est aussi affichée."),
            utilisation=_("Aucune saisie : omega-serv n'envoie jamais de message lui-même."),
            action=_("Ouvre l'adresse dans votre navigateur."),
            reaction=_("Sans session graphique, recopiez l'adresse affichée."),
        ),
        FieldGuide(
            label=_("Vérifier les mises à jour / Voir les nouveautés"),
            definition=_("Compare la version installée (aussi affichée dans la barre de titre) à la liste des "
                         "versions publiées sur le site (download/sha.txt)."),
            utilisation=_("Seulement sur votre clic : aucune vérification automatique, rien n'est envoyé. Même "
                          "vérification en ligne de commande : omega-serv version --check."),
            action=_("Affiche « à jour », la nouvelle version avec l'adresse de son archive, ou une version en "
                     "cours plus récente que la dernière publiée."),
            reaction=_("Si une version plus récente existe, « Voir les nouveautés » ouvre son résumé dans votre "
                       "navigateur. Rien n'est installé : la mise à jour se fait comme décrit dans le README."),
        ),
    ),
    consequences=_("Rien n'est envoyé sans un clic explicite sur Envoyer (formulaire de déclaration) ou sur Ne plus "
                   "me déclarer."),
)

DECLARATION_SCREEN = ScreenGuide(
    screen_class_name="DeclarationScreen",
    title=_("Se déclarer utilisateur (anonyme)"),
    acces=_("Contact et support -> Se déclarer utilisateur (anonyme)"),
    definition=_("Déclaration volontaire et anonyme : elle compte les utilisateurs d'omega-serv et, si vous le "
                 "souhaitez, leur continent ou leur pays. Rien n'est activé par défaut."),
    fields=(
        FieldGuide(
            label=_("Envoi"),
            definition=_("Une seule fois, ou chaque jour."),
            utilisation=_("Obligatoire, aucun choix présélectionné : Envoyer reste grisé tant qu'il n'est pas choisi."),
            action=_("Une seule fois : un envoi maintenant. Chaque jour : le service omega-serv renvoie le même "
                     "message au plus une fois par 24 h, ce qui permet de compter les installations actives."),
            reaction=_("L'envoi quotidien tourne dans un processus à part : il ne ralentit jamais le serveur, ni au "
                       "démarrage ni à l'arrêt. DO_NOT_TRACK=1 dans l'environnement du service le désactive."),
        ),
        FieldGuide(
            label=_("Continent / Pays"),
            definition=_("Deux listes indépendantes, facultatives, chacune avec « Autre (non référencé) »."),
            utilisation=_("Laisser « Non précisé » pour ne rien envoyer de ce champ."),
            action=_("Ajoute le code choisi au message (EU, FR... ou autre)."),
            reaction=_("Ni ville, ni texte libre."),
        ),
        FieldGuide(
            label=_("Message envoyé"),
            definition=_("Le message exact, mis à jour à chaque choix."),
            utilisation=_("Lecture seule."),
            action=_("Aucune."),
            reaction=_("Une clé tirée au hasard (32 caractères) est créée au premier envoi, sous "
                       "var/lib/declaration/ ; elle ne dérive ni de la machine ni de vous."),
        ),
        FieldGuide(
            label=_("Envoyer"),
            definition=_("Envoie la déclaration en HTTPS vers le site du développeur."),
            utilisation=_("5 secondes au plus ; l'écran ne se fige pas."),
            action=_("Succès : retour à Contact et support, état « déclaré »."),
            reaction=_("Réception injoignable : en « une seule fois », rien n'est enregistré ; en « chaque jour », "
                       "l'accord est gardé et le service réessaie dans 24 h."),
        ),
    ),
    points_de_vigilance=(
        _("L'adresse IP n'est pas enregistrée dans les déclarations, mais comme pour toute visite d'un site, elle "
          "passe par les contrôles de sécurité et le journal technique du serveur de réception."),
        _("Ligne de commande : omega-serv declaration status | declare --mode unique|quotidien [--continent X] "
          "[--pays Y] --yes | withdraw."),
    ),
)

FULL_REPORT_SCREEN = ScreenGuide(
    screen_class_name="FullReportScreen",
    title=_("Rapport complet"),
    acces=_("Accueil -> Rapport complet"),
    definition=_("Ce qui est configuré et actif, d'un coup d'œil, sans passer par chaque menu : réglages et système, "
                 "jamais le trafic des visiteurs. Aucun secret : mots de passe, clés et jetons apparaissent au plus "
                 "comme « défini » ou « absent »."),
    fields=(
        FieldGuide(
            label=_("Sommaire"),
            definition=_("Le minimum, toujours présent : identité (instance, dossier, version, profil, machine), "
                         "fonctionnement (service, unité, en marche, démarrage, uptime, compte, processus), adresse "
                         "et mode (site web, reverse proxy ou les deux), moteur utilisé, TLS (expiration), options, "
                         "nombres de zones, sécurité, contrôles de la configuration, sauvegardes, journaux."),
            utilisation=_("Actualiser relit tout ; un indicateur d'attente s'affiche pendant la génération."),
            action=_("Lecture seule."),
            reaction=_("L'écran ne gèle jamais, même sur un serveur très configuré."),
        ),
        FieldGuide(
            label=_("Détail à inclure dans l'export"),
            definition=_("Zones détaillées, reverse proxy, règles WAF, Active Defense et RIPOSTE, journaux suivis, "
                         "réglages de toutes les options, audit de sécurité complet."),
            utilisation=_("Cases à cocher ; le détail ne s'affiche pas à l'écran, il va seulement dans l'export."),
            action=_("L'audit complet peut prendre quelques secondes."),
            reaction=_("Les clés qui évoquent un secret (mot de passe, jeton, clé, hachage) sont remplacées par "
                       "vrai ou faux."),
        ),
        FieldGuide(
            label=_("Exporter"),
            definition=_("HTML dans l'un des 5 thèmes d'export, TXT, ou JSON (données brutes, comparables d'une date "
                         "à l'autre)."),
            utilisation=_("Choisir le format, le thème pour le HTML, puis Exporter."),
            action=_("Écrit omega-serv-rapport.<date>.<format> dans le dossier d'exports (Options), dans la langue "
                     "des exports."),
            reaction=_("Aucun effet sur le serveur."),
        ),
    ),
    consequences=_("Purement consultatif - ne modifie jamais rien."),
)

ALL_DIVERS_GUIDES: tuple[ScreenGuide, ...] = (
    CAPABILITIES_SCREEN,
    CAPABILITY_DETAIL_SCREEN,
    PROFILES_SCREEN,
    CUSTOM_PROFILE_SCREEN,
    APPLY_PROFILE_SCREEN,
    AUDIT_SCREEN,
    BACKUP_SCREEN,
    FULL_REPORT_SCREEN,
    SETTINGS_SCREEN,
    CONTACT_SUPPORT_SCREEN,
    DECLARATION_SCREEN,
)
