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
    definition=_("Liste et décrit les 4 profils de base preconfigures (minimal/standard/hardened/development)."),
    fields=(
        FieldGuide(
            label=_("Appliquer"),
            definition=_("Ouvre l'écran de confirmation d'application du profil sélectionné."),
            utilisation=_("Sélectionner un profil active ce bouton."),
            action=_("Ouvre ApplyProfileScreen."),
            reaction=_("Aucun effet ici - voir la fiche d'ApplyProfileScreen."),
        ),
    ),
    consequences=_("Purement consultatif - aucune modification depuis cet écran lui-même."),
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

ALL_DIVERS_GUIDES: tuple[ScreenGuide, ...] = (
    CAPABILITIES_SCREEN,
    CAPABILITY_DETAIL_SCREEN,
    PROFILES_SCREEN,
    APPLY_PROFILE_SCREEN,
    AUDIT_SCREEN,
    BACKUP_SCREEN,
    SETTINGS_SCREEN,
)
