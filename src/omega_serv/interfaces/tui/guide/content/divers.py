"""Fiches guide : Registre des capacites, Profils, Audit de securite,
Sauvegarde de configuration, Reglages de l'application (plan guide
d'aide, Phase 9)."""
from __future__ import annotations

from omega_serv.interfaces.tui.guide.model import FieldGuide, ScreenGuide

CAPABILITIES_SCREEN = ScreenGuide(
    screen_class_name="CapabilitiesScreen",
    title="Registre des capacites",
    acces="Accueil -> Registre des capacites",
    definition="Scan complet de l'environnement (port libre, openssl present, PHP-FPM si FastCGI actif...), avec export.",
    fields=(
        FieldGuide(
            label="Theme d'export HTML",
            definition="Palette de couleurs pour l'export HTML.",
            utilisation="5 themes disponibles.",
            action="Utilise au clic sur Exporter HTML.",
            reaction="Aucun effet sur le serveur.",
        ),
        FieldGuide(
            label="Rafraichir / Exporter JSON / Exporter HTML",
            definition="Relance le scan, ou exporte son resultat.",
            utilisation="Aucune saisie supplementaire.",
            action="Rafraichir relance le scan ; les exports ecrivent un fichier horodate.",
            reaction="Aucun effet sur le serveur ou sa configuration (lecture seule + export).",
        ),
    ),
    consequences="Purement consultatif/export.",
)

CAPABILITY_DETAIL_SCREEN = ScreenGuide(
    screen_class_name="CapabilityDetailScreen",
    title="Detail d'une capacite",
    acces="Registre des capacites -> clic sur une ligne",
    definition="Detail complet d'une capacite deja scannee (jamais un nouveau scan) : statut, raison, details techniques, date du dernier scan.",
    fields=(),
    consequences="Purement consultatif.",
)

PROFILES_SCREEN = ScreenGuide(
    screen_class_name="ProfilesScreen",
    title="Profils",
    acces="Accueil -> Profils",
    definition="Liste et decrit les 4 profils de base preconfigures (minimal/standard/hardened/development).",
    fields=(
        FieldGuide(
            label="Appliquer",
            definition="Ouvre l'ecran de confirmation d'application du profil selectionne.",
            utilisation="Selectionner un profil active ce bouton.",
            action="Ouvre ApplyProfileScreen.",
            reaction="Aucun effet ici - voir la fiche d'ApplyProfileScreen.",
        ),
    ),
    consequences="Purement consultatif - aucune modification depuis cet ecran lui-meme.",
)

APPLY_PROFILE_SCREEN = ScreenGuide(
    screen_class_name="ApplyProfileScreen",
    title="Appliquer un profil",
    acces="Profils -> Appliquer",
    definition="Affiche TOUJOURS la difference complete avant toute confirmation, puis ecrase la configuration active avec le profil choisi.",
    fields=(
        FieldGuide(
            label="Appliquer",
            definition="Confirme et ecrit le profil choisi.",
            utilisation="Le diff complet est deja affiche au-dessus - a verifier avant de cliquer.",
            action="Ecrase config/omega-serve.json avec la configuration composee du profil.",
            reaction=(
                "Un profil peut changer N'IMPORTE QUEL reglage d'un coup. Si bind/port/"
                "listen_backlog/TLS changent, un REDEMARRAGE COMPLET est necessaire ; sinon un "
                "simple rechargement suffit (automatique si un service actif existe)."
            ),
        ),
    ),
    consequences="Des conflits ou erreurs de validation bloquants demandent une confirmation supplementaire explicite pour forcer quand meme.",
    points_de_vigilance=(
        "Un profil ne modifie QUE les champs qu'il specifie explicitement - le reste de la configuration active est conserve tel quel.",
    ),
)

AUDIT_SCREEN = ScreenGuide(
    screen_class_name="AuditScreen",
    title="Audit de securite",
    acces="Accueil -> Audit de securite",
    definition="Verifications consultatives (service, rotation des logs, mode WAF...) - memes regles que l'audit CLI.",
    fields=(
        FieldGuide(
            label="Auditer",
            definition="Relance explicitement l'audit.",
            utilisation="Aucune saisie - un premier audit a deja lieu automatiquement a l'ouverture de l'ecran.",
            action="Relit la configuration et recalcule toutes les regles d'audit.",
            reaction="Aucun effet sur le serveur (lecture seule) - notifie explicitement le resultat sur un clic explicite.",
        ),
    ),
    consequences="Purement consultatif - ne modifie jamais rien.",
)

BACKUP_SCREEN = ScreenGuide(
    screen_class_name="BackupScreen",
    title="Sauvegarde de configuration",
    acces="Accueil -> Sauvegarde de configuration",
    definition="Creer, lister, restaurer ou supprimer des sauvegardes completes de la configuration - le fichier de configuration est toujours inclus, jamais chiffre par defaut.",
    fields=(
        FieldGuide(
            label="Inclure les regles WAF",
            definition="Ajoute les regles WAF et la liste de blocage a la sauvegarde.",
            utilisation="Case a cocher.",
            action="Pris en compte a la creation.",
            reaction="Aucun effet immediat - juste le contenu de la sauvegarde creee.",
        ),
        FieldGuide(
            label="Inclure les zones d'authentification",
            definition="Ajoute users.json/zones.json (SECRETS REELS : hash de mots de passe) a la sauvegarde.",
            utilisation="Case a cocher - demande une confirmation supplementaire explicite si cochee.",
            action="Pris en compte a la creation.",
            reaction="La sauvegarde contient des secrets reels, jamais chiffres.",
        ),
        FieldGuide(
            label="Inclure les certificats",
            definition="Ajoute les certificats TLS, CLES PRIVEES INCLUSES, a la sauvegarde.",
            utilisation="Case a cocher - demande une confirmation supplementaire explicite si cochee.",
            action="Pris en compte a la creation.",
            reaction="La sauvegarde contient des cles privees reelles, jamais chiffrees.",
        ),
        FieldGuide(
            label="Inclure Active Defense",
            definition="Ajoute la base de menaces/incidents Active Defense a la sauvegarde.",
            utilisation="Case a cocher.",
            action="Pris en compte a la creation.",
            reaction="Aucun effet immediat.",
        ),
        FieldGuide(
            label="Description",
            definition="Note libre associee a la sauvegarde, pour la retrouver plus tard.",
            utilisation="Texte libre, optionnel.",
            action="Enregistree avec la sauvegarde.",
            reaction="Aucun effet immediat.",
        ),
        FieldGuide(
            label="Restaurer",
            definition="Ecrase les fichiers actuels avec ceux de la sauvegarde selectionnee, AUX MEMES EMPLACEMENTS.",
            utilisation="Selectionner une sauvegarde, puis confirmer.",
            action="Ecriture reelle et immediate des fichiers concernes.",
            reaction=(
                "Necessite TOUJOURS un REDEMARRAGE COMPLET par prudence - une restauration peut "
                "ecraser n'importe quel fichier (configuration, certificats TLS...), et un "
                "certificat deja en memoire ne se recharge jamais tout seul."
            ),
        ),
        FieldGuide(
            label="Supprimer",
            definition="Supprime definitivement une sauvegarde (n'existe pas cote CLI, confort TUI uniquement).",
            utilisation="Selectionner une sauvegarde, puis confirmer.",
            action="Suppression immediate et definitive.",
            reaction="Aucun effet sur le serveur - seulement sur les sauvegardes disponibles.",
        ),
    ),
    consequences="Restaurer ecrase directement les fichiers vises, sans filet - la seule protection est la confirmation demandee avant.",
)

SETTINGS_SCREEN = ScreenGuide(
    screen_class_name="SettingsScreen",
    title="Reglages de l'application",
    acces="Raccourci clavier 'o' (footer), depuis n'importe quel ecran",
    definition=(
        "PREFERENCES D'INTERFACE uniquement (theme, rendu, chemins d'export/captures) - "
        "PAS des reglages du serveur (ceux-la vivent dans Configuration detaillee)."
    ),
    fields=(
        FieldGuide(
            label="Theme",
            definition="Theme visuel de l'interface elle-meme.",
            utilisation="Un des themes disponibles.",
            action="Applique immediatement au changement.",
            reaction="Effet immediat, aucun redemarrage necessaire.",
        ),
        FieldGuide(
            label="Profil de rendu",
            definition="Force un profil de rendu Textual particulier plutot que la detection automatique.",
            utilisation="Automatique, ou un profil precis.",
            action="Enregistre la preference.",
            reaction="Applique seulement AU PROCHAIN DEMARRAGE de l'interface, jamais a chaud.",
        ),
        FieldGuide(
            label="Export / Captures d'ecran (chemins)",
            definition="Repertoires ou sont ecrits les exports et les captures d'ecran.",
            utilisation="Chemin libre - vide revient au repertoire par defaut.",
            action="Enregistre a chaque changement de texte.",
            reaction="Effet immediat sur les prochains exports/captures.",
        ),
        FieldGuide(
            label="Supprimer les exports / Supprimer les screenshots",
            definition="Vide completement le repertoire concerne.",
            utilisation="Confirmation obligatoire.",
            action="Suppression immediate et definitive de tous les fichiers du repertoire.",
            reaction="Action irreversible.",
        ),
    ),
    consequences="Ne touche jamais config/omega-serve.json - reglages purement locaux a cette interface.",
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
