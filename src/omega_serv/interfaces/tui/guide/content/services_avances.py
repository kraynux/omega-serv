# Copyright (c) 2026 kraynux - kraynux@proton.me - Licence MIT (voir fichier LICENSE)
"""Fiches guide : FastCGI/PHP-FPM et Authentification (plan guide
d'aide, Phase 4)."""
from __future__ import annotations

from omega_serv.interfaces.tui.guide.model import FieldGuide, ScreenGuide

FASTCGI_SCREEN = ScreenGuide(
    screen_class_name="FastCgiScreen",
    title="FastCGI / PHP-FPM",
    acces="Accueil -> Configuration detaillee -> FastCGI / PHP-FPM",
    definition=(
        "Un seul enregistrement (jamais une liste) : proxy vers un serveur PHP-FPM pour executer "
        "du PHP sous un prefixe d'URL donne."
    ),
    fields=(
        FieldGuide(
            label="Prefixe URL (url_prefix)",
            definition="Le prefixe d'URL sous lequel les requetes sont relayees vers PHP-FPM.",
            utilisation="Doit commencer par '/'. Valeur par defaut : /app/.",
            action="Enregistre au clic sur Enregistrer, apres validation structurelle.",
            reaction=(
                "Si l'option fastcgi est deja active : rechargement suffit (automatique si un "
                "service actif existe). Sinon, sa PREMIERE activation exige un redemarrage complet."
            ),
        ),
        FieldGuide(
            label="Racine d'execution (script_root)",
            definition="Repertoire, relatif au projet, contenant les scripts PHP executables.",
            utilisation="Chemin relatif - ne peut jamais etre a l'interieur du webroot (verifie structurellement).",
            action="Enregistre avec le reste des champs.",
            reaction="Meme reaction que url_prefix.",
        ),
        FieldGuide(
            label="Socket PHP-FPM (socket_path)",
            definition="Chemin du socket Unix utilise pour communiquer avec PHP-FPM.",
            utilisation="Chemin relatif. Valeur par defaut : var/run/php-fpm.sock.",
            action="Enregistre avec le reste des champs.",
            reaction="Meme reaction que url_prefix.",
        ),
        FieldGuide(
            label="Delai de connexion / Delai de lecture",
            definition="Delais reseau appliques a la communication avec PHP-FPM.",
            utilisation="Nombres en secondes. Valeurs par defaut : 5 (connexion), 30 (lecture).",
            action="Enregistre avec le reste des champs.",
            reaction="Meme reaction que url_prefix.",
        ),
        FieldGuide(
            label="Extensions autorisees",
            definition="Extensions de fichiers executees via PHP-FPM.",
            utilisation="Liste separee par des virgules. Valeur par defaut : .php.",
            action="Enregistre avec le reste des champs.",
            reaction="Meme reaction que url_prefix.",
        ),
        FieldGuide(
            label="Fichiers d'index",
            definition="Fichiers cherches quand une URL sous ce prefixe pointe vers un repertoire.",
            utilisation="Liste separee par des virgules. Valeur par defaut : index.php.",
            action="Enregistre avec le reste des champs.",
            reaction="Meme reaction que url_prefix.",
        ),
        FieldGuide(
            label="Liste blanche de scripts",
            definition=(
                "Restreint les scripts reellement executables (chemins relatifs a script_root) - "
                "vide signifie 'tout fichier avec une extension autorisee sous script_root reste executable'."
            ),
            utilisation="Liste separee par des virgules, ex: index.php, api/router.php. Vide par defaut.",
            action="Enregistre avec le reste des champs.",
            reaction="Meme reaction que url_prefix.",
        ),
    ),
    consequences=(
        "La PREMIERE activation de l'option fastcgi (ecran Options) exige un REDEMARRAGE "
        "COMPLET (le client FastCGI n'est construit qu'au demarrage). Une fois deja active, "
        "modifier ces reglages ici ne demande plus qu'un simple rechargement."
    ),
    points_de_vigilance=(
        (
            "script_root ne peut structurellement jamais se trouver a l'interieur du webroot - "
            "bloque avant meme l'enregistrement, pas seulement par 'Verifier la configuration'."
        ),
    ),
)

AUTH_MENU_SCREEN = ScreenGuide(
    screen_class_name="AuthMenuScreen",
    title="Authentification",
    acces="Accueil -> Configuration detaillee -> Authentification",
    definition=(
        "Gestion des utilisateurs et des zones protegees par authentification HTTP. Les "
        "identifiants et zones sont stockes dans des fichiers SEPARES (users.json/zones.json), "
        "jamais dans config/omega-serve.json."
    ),
    fields=(
        FieldGuide(
            label="Ajouter un utilisateur / Changer un mot de passe",
            definition="Cree un compte utilisateur ou change son mot de passe.",
            utilisation="Nom d'utilisateur + mot de passe saisi deux fois (jamais affiche en clair).",
            action="Ecrit directement dans users.json.",
            reaction="Aucun effet sans rechargement du service (automatique si actif).",
        ),
        FieldGuide(
            label="Supprimer un utilisateur",
            definition="Retire definitivement un compte utilisateur.",
            utilisation="Nom d'utilisateur exact, avec confirmation.",
            action="Ecrit directement dans users.json.",
            reaction="Aucun effet sans rechargement du service.",
        ),
        FieldGuide(
            label="Creer une zone protegee",
            definition="Protege un prefixe d'URL par authentification HTTP.",
            utilisation=(
                "Prefixe URL (ex: /admin/), realm (texte affiche par le navigateur), "
                "utilisateurs autorises (separes par des virgules), methodes autorisees "
                "(vide = toutes)."
            ),
            action="Ecrit directement dans zones.json.",
            reaction="Aucun effet sans rechargement du service.",
        ),
        FieldGuide(
            label="Supprimer une zone",
            definition="Retire la protection d'un prefixe d'URL.",
            utilisation="Prefixe URL exact, avec confirmation.",
            action="Ecrit directement dans zones.json.",
            reaction="Aucun effet sans rechargement du service.",
        ),
        FieldGuide(
            label="Verifier les permissions",
            definition="Verifie que users.json/zones.json ne sont pas lisibles par d'autres utilisateurs du systeme.",
            utilisation="Aucune saisie - lecture seule.",
            action="Affiche le mode de permission reel de chaque fichier.",
            reaction="Aucun effet (lecture seule).",
        ),
    ),
    consequences=(
        "L'option auth doit etre activee (ecran Options) pour que les zones protegees soient "
        "reellement appliquees. Toute modification d'utilisateur/zone se recharge a chaud."
    ),
    points_de_vigilance=(
        (
            "Une authentification active SANS TLS transmet les identifiants en clair sur le "
            "reseau - l'assistant premier lancement demande une confirmation explicite dans ce cas."
        ),
    ),
)
