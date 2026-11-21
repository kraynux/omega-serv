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
        _("Liste des zones PHP : chaque zone relaie un préfixe d'URL vers un serveur PHP-FPM (sa socket), avec "
          "ses propres scripts, délais, extensions, fichiers d'index et liste blanche, et son propre "
          "interrupteur. Plusieurs applications PHP peuvent ainsi tourner sur une même instance (/blog/ et "
          "/wiki/, par exemple) ; le préfixe le plus long l'emporte. L'option fastcgi du menu Options reste "
          "l'interrupteur général. Une ancienne configuration à une seule zone s'affiche comme une ligne de la "
          "liste et passe au nouveau format au premier enregistrement.")
    ),
    fields=(
        FieldGuide(
            label=_("Ajouter / Modifier (une zone)"),
            definition=_("Ouvre le formulaire de la zone : préfixe, racine des scripts, socket, délais, extensions, "
                         "fichiers d'index, liste blanche."),
            utilisation=_("Deux zones ne peuvent pas avoir le même préfixe (/blog et /blog/ comptent pour un)."),
            action=_("Valider enregistre la zone, après validation ; une erreur reste affichée dans le "
                     "formulaire, saisie intacte."),
            reaction=(
                _("Si l'option fastcgi est déjà activé : rechargement suffit (automatique si un "
                "service actif existe). Sinon, sa PREMIÈRE activation exige un redémarrage complet.")
            ),
        ),
        FieldGuide(
            label=_("Préfixe URL (url_prefix)"),
            definition=_("Le préfixe d'URL sous lequel les requêtes sont relayées vers PHP-FPM."),
            utilisation=_("Doit commencer par '/'. Valeur par défaut : /app/."),
            action=_("Enregistre avec le reste des champs."),
            reaction=_("Même réaction que Ajouter / Modifier."),
        ),
        FieldGuide(
            label=_("Racine d'exécution (script_root)"),
            definition=_("Répertoire, relatif au projet, contenant les scripts PHP exécutables."),
            utilisation=_("Chemin relatif - ne peut jamais être à l'intérieur du webroot (vérifié structurellement)."),
            action=_("Enregistre avec le reste des champs."),
            reaction=_("Même réaction que Ajouter / Modifier."),
        ),
        FieldGuide(
            label=_("Socket PHP-FPM (socket_path)"),
            definition=_("Chemin du socket Unix utilisé pour communiquer avec PHP-FPM."),
            utilisation=_("Chemin relatif. Valeur par défaut : var/run/php-fpm.sock. Plusieurs zones peuvent "
                          "partager une socket ; une socket par zone (un pool PHP-FPM par zone) donne à chaque "
                          "zone ses propres réglages PHP et son propre compte système."),
            action=_("Enregistre avec le reste des champs."),
            reaction=_("Même réaction que Ajouter / Modifier."),
        ),
        FieldGuide(
            label=_("Délai de connexion / Délai de lecture"),
            definition=_("Délais réseau appliqués à la communication avec PHP-FPM."),
            utilisation=_("Nombres en secondes. Valeurs par défaut : 5 (connexion), 30 (lecture)."),
            action=_("Enregistre avec le reste des champs."),
            reaction=_("Même réaction que Ajouter / Modifier."),
        ),
        FieldGuide(
            label=_("Taille maximale de requête"),
            definition=_("Taille maximale du corps d'une requête vers cette zone, en octets (envoi de fichiers, "
                         "formulaires)."),
            utilisation=_("Nombre entier d'octets (10485760 = 10 Mo). Vide : la taille de l'écran Limites "
                          "s'applique. Plus grande pour une zone d'administration qui reçoit de gros fichiers, ou "
                          "plus petite pour une zone ouverte au public."),
            action=_("Enregistre avec le reste des champs."),
            reaction=_("Même réaction que Ajouter / Modifier."),
        ),
        FieldGuide(
            label=_("Extensions autorisées"),
            definition=_("Extensions de fichiers exécutées via PHP-FPM."),
            utilisation=_("Liste séparée par des virgules. Valeur par défaut : .php."),
            action=_("Enregistre avec le reste des champs."),
            reaction=_("Même réaction que Ajouter / Modifier."),
        ),
        FieldGuide(
            label=_("Fichiers d'index"),
            definition=_("Fichiers cherches quand une URL sous ce préfixe pointe vers un répertoire."),
            utilisation=_("Liste séparée par des virgules. Valeur par défaut : index.php."),
            action=_("Enregistre avec le reste des champs."),
            reaction=_("Même réaction que Ajouter / Modifier."),
        ),
        FieldGuide(
            label=_("Liste blanche de scripts"),
            definition=(
                _("Restreint les scripts réellement exécutables (chemins relatifs à script_root) - "
                "vide signifie 'tout fichier avec une extension autorisée sous script_root reste exécutable'.")
            ),
            utilisation=_("Liste séparée par des virgules, ex: index.php, api/router.php. Vide par défaut."),
            action=_("Enregistre avec le reste des champs."),
            reaction=_("Même réaction que Ajouter / Modifier."),
        ),
        FieldGuide(
            label=_("Désactiver / Activer (une zone)"),
            definition=_("Interrupteur de la zone choisie, pour une maintenance de ses fichiers sans couper les "
                         "autres zones."),
            utilisation=_("Choisissez la zone dans le tableau ; le bouton indique l'action possible. Colonne "
                          "« Active » : oui ou non."),
            action=_("Enregistre aussitôt l'état de la zone."),
            reaction=_("Rechargement suffit. Une zone désactivée répond 503 (maintenance) sur tout son préfixe, "
                       "sans servir un fichier du webroot à sa place ; son dossier et sa socket ne sont plus "
                       "exigés au démarrage."),
        ),
        FieldGuide(
            label=_("Supprimer (une zone)"),
            definition=_("Retire la zone choisie de la liste, après confirmation."),
            utilisation=_("Les scripts ne sont pas effacés : seule la zone disparaît de la configuration."),
            action=_("Enregistre aussitôt."),
            reaction=_("Rechargement suffit ; les URL de ce préfixe reviennent au reste du site."),
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
        _("Une zone désactivée garde cette règle : elle peut être réactivée à tout moment."),
        _("omega-serv n'installe, n'écrit ni ne vérifie la configuration de PHP-FPM : son édition reste de la "
          "responsabilité de l'administrateur. omega-serv ne transmet jamais de valeur PHP par requête "
          "(PHP_VALUE) : sur un pool partagé, elle déborderait sur les autres zones. Des réglages PHP "
          "différents (mémoire, taille d'envoi, open_basedir) passent par un pool par zone ; le minimum que "
          "chaque pool doit contenir est décrit dans la FAQ « réglages PHP différents par zone »."),
        _("Chaque zone peut fixer sa propre taille maximale de requête (en octets), plus grande ou plus petite "
          "que celle de l'écran Limites ; vide, c'est celle de l'écran Limites qui s'applique. Un envoi plus gros "
          "est refusé (413) avant d'atteindre PHP, quel que soit le réglage du pool."),
        _("Depuis la 3.0.0, un en-tête de requête nommé Proxy n'est jamais transmis à PHP (HTTP_PROXY servirait à "
          "détourner les appels sortants du script, faille « httpoxy »), ni un en-tête dont le nom contient « _ » "
          "(X_Forwarded_For se confondrait avec X-Forwarded-For une fois traduit en HTTP_X_FORWARDED_FOR)."),
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
            definition=_("Liste les zones existantes - cliquer une ligne la SÉLECTIONNE (active Modifier et Supprimer)."),
            utilisation=_("Sélection par clic, une seule ligne à la fois."),
            action=_("Aucune écriture - lecture seule."),
            reaction=_("Active/desactive les boutons Modifier et Supprimer."),
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
            label=_("Modifier (zone)"),
            definition=_("Corrige la zone SÉLECTIONNÉE : préfixe, realm, utilisateurs autorisés, méthodes."),
            utilisation=_("Le formulaire s'ouvre déjà rempli. Une saisie invalide (préfixe sans « / », aucun "
                          "utilisateur, préfixe déjà pris par une autre zone) est signalée dans le formulaire, et "
                          "ce que vous avez tapé est gardé."),
            action=_("Écrit directement dans zones.json ; la zone garde sa place dans la liste."),
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
            label=_("Protection des mots de passe"),
            definition=(
                _("Réglages du cache des succès et de la limite des échecs (valeurs par défaut entre parenthèses) : "
                  "succès retenu (300 s, renouvelées à chaque requête ; 0 = aucun cache), durée maximale d'un succès "
                  "retenu (3600 s), succès retenus au plus (4096), fenêtre de comptage des échecs (300 s), échecs par "
                  "adresse avant 429 (10), échecs par nom d'utilisateur avant 429 (30), vérifications en attente au "
                  "plus avant 503 (10).")
            ),
            utilisation=_("Modifier les réglages : un formulaire, un nombre entier par réglage ; une valeur hors bornes est refusée avec ses limites."),
            action=_("Écrit dans config/omega-serve.json (options.auth.password_protection)."),
            reaction=_("Appliqué au prochain rechargement ; les succès retenus sont alors oubliés et les compteurs repartent de zéro."),
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
        _("Coût d'une vérification : environ 0,3 à 0,5 s de calcul (scrypt). Un succès est retenu 5 minutes, "
          "renouvelées à chaque requête, une heure au plus, puis vérifié à nouveau ; tout est oublié à chaque "
          "modification d'utilisateur ou de zone. Après 10 mauvais mots de passe d'une même adresse (ou 30 pour un "
          "même nom d'utilisateur) en 5 minutes, réponse 429 immédiate, sans calcul, jusqu'à la fin des 5 minutes. "
          "Plus de 10 vérifications en attente : 503 immédiat."),
        _("Ces valeurs sont celles par défaut, réglables dans « Protection des mots de passe ». Un seuil trop bas "
          "bloque vite un utilisateur qui se trompe ; un succès retenu à 0 relance le calcul à chaque requête."),
    ),
)
