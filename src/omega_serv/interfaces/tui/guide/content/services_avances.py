"""Fiches guide : FastCGI/PHP-FPM et Authentification (plan guide
d'aide, Phase 4)."""
from __future__ import annotations

from omega_serv.core.i18n import _
from omega_serv.interfaces.tui.guide.model import FieldGuide, ScreenGuide

FASTCGI_SCREEN = ScreenGuide(
    screen_class_name="FastCgiScreen",
    title=_("FastCGI / PHP-FPM"),
    acces=_("Accueil -> Configuration détaillée -> FastCGI / PHP-FPM"),
    definition=(
        _("Un seul enregistrement (jamais une liste) : proxy vers un serveur PHP-FPM pour exécuter "
        "du PHP sous un préfixe d'URL donné.")
    ),
    fields=(
        FieldGuide(
            label=_("Préfixe URL (url_prefix)"),
            definition=_("Le préfixe d'URL sous lequel les requêtes sont relayées vers PHP-FPM."),
            utilisation=_("Doit commencer par '/'. Valeur par défaut : /app/."),
            action=_("Enregistre au clic sur Enregistrer, après validation structurelle."),
            reaction=(
                _("Si l'option fastcgi est déjà activé : rechargement suffit (automatique si un "
                "service actif existe). Sinon, sa PREMIÈRE activation exige un redémarrage complet.")
            ),
        ),
        FieldGuide(
            label=_("Racine d'exécution (script_root)"),
            definition=_("Répertoire, relatif au projet, contenant les scripts PHP exécutables."),
            utilisation=_("Chemin relatif - ne peut jamais être à l'intérieur du webroot (vérifié structurellement)."),
            action=_("Enregistre avec le reste des champs."),
            reaction=_("Même réaction que url_prefix."),
        ),
        FieldGuide(
            label=_("Socket PHP-FPM (socket_path)"),
            definition=_("Chemin du socket Unix utilisé pour communiquer avec PHP-FPM."),
            utilisation=_("Chemin relatif. Valeur par défaut : var/run/php-fpm.sock."),
            action=_("Enregistre avec le reste des champs."),
            reaction=_("Même réaction que url_prefix."),
        ),
        FieldGuide(
            label=_("Délai de connexion / Délai de lecture"),
            definition=_("Délais réseau appliqués à la communication avec PHP-FPM."),
            utilisation=_("Nombres en secondes. Valeurs par défaut : 5 (connexion), 30 (lecture)."),
            action=_("Enregistre avec le reste des champs."),
            reaction=_("Même réaction que url_prefix."),
        ),
        FieldGuide(
            label=_("Extensions autorisées"),
            definition=_("Extensions de fichiers exécutées via PHP-FPM."),
            utilisation=_("Liste séparée par des virgules. Valeur par défaut : .php."),
            action=_("Enregistre avec le reste des champs."),
            reaction=_("Même réaction que url_prefix."),
        ),
        FieldGuide(
            label=_("Fichiers d'index"),
            definition=_("Fichiers cherches quand une URL sous ce préfixe pointe vers un répertoire."),
            utilisation=_("Liste séparée par des virgules. Valeur par défaut : index.php."),
            action=_("Enregistre avec le reste des champs."),
            reaction=_("Même réaction que url_prefix."),
        ),
        FieldGuide(
            label=_("Liste blanche de scripts"),
            definition=(
                _("Restreint les scripts réellement exécutables (chemins relatifs à script_root) - "
                "vide signifie 'tout fichier avec une extension autorisée sous script_root reste exécutable'.")
            ),
            utilisation=_("Liste séparée par des virgules, ex: index.php, api/router.php. Vide par défaut."),
            action=_("Enregistre avec le reste des champs."),
            reaction=_("Même réaction que url_prefix."),
        ),
    ),
    consequences=(
        _("La PREMIÈRE activation de l'option fastcgi (écran Options) exige un REDÉMARRAGE "
        "COMPLET (le client FastCGI n'est construit qu'au démarrage). Une fois déjà activé, "
        "modifier ces réglages ici ne demande plus qu'un simple rechargement.")
    ),
    points_de_vigilance=(
        (
            _("script_root ne peut structurellement jamais se trouver à l'intérieur du webroot - "
            "bloqué avant même l'enregistrement, pas seulement par 'Vérifier la configuration'.")
        ),
    ),
)

AUTH_MENU_SCREEN = ScreenGuide(
    screen_class_name="AuthMenuScreen",
    title=_("Authentification"),
    acces=_("Accueil -> Configuration détaillée -> Authentification"),
    definition=(
        _("Gestion des utilisateurs et des zones protégées par authentification HTTP. Les "
        "identifiants et zones sont stockés dans des fichiers SÉPARÉS (users.json/zones.json), "
        "jamais dans config/omega-serve.json.")
    ),
    fields=(
        FieldGuide(
            label=_("Table Utilisateurs"),
            definition=(
                _("Liste les comptes existants - cliquer une ligne la SÉLECTIONNE (active "
                "Changer le mot de passe/Supprimer) sans jamais retaper le nom d'utilisateur.")
            ),
            utilisation=_("Sélection par clic, une seule ligne à la fois."),
            action=_("Aucune écriture - lecture seule."),
            reaction=_("Active/desactive les boutons Changer le mot de passe et Supprimer."),
        ),
        FieldGuide(
            label=_("Ajouter"),
            definition=_("Crée un compte utilisateur."),
            utilisation=_("Nom d'utilisateur + mot de passe saisi deux fois (jamais affiché en clair)."),
            action=_("Écrit directement dans users.json."),
            reaction=_("Aucun effet sans rechargement du service (automatique si actif)."),
        ),
        FieldGuide(
            label=_("Changer le mot de passe"),
            definition=_("Change le mot de passe de l'utilisateur SÉLECTIONNÉ dans la table."),
            utilisation=(
                _("Sélectionner une ligne d'abord (le nom d'utilisateur n'est jamais retape) - "
                "puis le nouveau mot de passe, saisi deux fois.")
            ),
            action=_("Écrit directement dans users.json."),
            reaction=_("Aucun effet sans rechargement du service."),
        ),
        FieldGuide(
            label=_("Supprimer (utilisateur)"),
            definition=_("Retire définitivement le compte utilisateur SÉLECTIONNÉ dans la table."),
            utilisation=_("Sélectionner une ligne d'abord, puis confirmer - aucune saisie."),
            action=_("Écrit directement dans users.json."),
            reaction=_("Aucun effet sans rechargement du service."),
        ),
        FieldGuide(
            label=_("Table Zones protégées"),
            definition=_("Liste les zones existantes - cliquer une ligne la SÉLECTIONNE (active Supprimer)."),
            utilisation=_("Sélection par clic, une seule ligne à la fois."),
            action=_("Aucune écriture - lecture seule."),
            reaction=_("Active/desactive le bouton Supprimer."),
        ),
        FieldGuide(
            label=_("Créer une zone"),
            definition=_("Protège un préfixe d'URL par authentification HTTP."),
            utilisation=(
                _("Préfixe URL (ex: /admin/), realm (texte affiché par le navigateur), "
                "utilisateurs autorisés (séparés par des virgules), méthodes autorisées "
                "(vide = toutes).")
            ),
            action=_("Écrit directement dans zones.json."),
            reaction=_("Aucun effet sans rechargement du service."),
        ),
        FieldGuide(
            label=_("Supprimer (zone)"),
            definition=_("Retire la protection de la zone SÉLECTIONNÉE dans la table."),
            utilisation=_("Sélectionner une ligne d'abord, puis confirmer - aucune saisie."),
            action=_("Écrit directement dans zones.json."),
            reaction=_("Aucun effet sans rechargement du service."),
        ),
        FieldGuide(
            label=_("Vérifier les permissions"),
            definition=_("Vérifie que users.json/zones.json ne sont pas lisibles par d'autres utilisateurs du système."),
            utilisation=_("Aucune saisie - lecture seule."),
            action=_("Affiche le mode de permission réel de chaque fichier."),
            reaction=_("Aucun effet (lecture seule)."),
        ),
    ),
    consequences=(
        _("L'option auth doit être activée (écran Options) pour que les zones protégées soient "
        "réellement appliquées. Toute modification d'utilisateur/zone se recharge à chaud.")
    ),
    points_de_vigilance=(
        (
            _("Une authentification active SANS TLS transmet les identifiants en clair sur le "
            "réseau - l'assistant premier lancement demande une confirmation explicite dans ce cas.")
        ),
    ),
)
