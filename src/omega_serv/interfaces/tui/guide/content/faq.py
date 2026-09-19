"""FAQ du guide d'aide (plan guide d'aide §3.7, Phase 0 - amorcee avec
l'incident fondateur de ce chantier ; completee Phase 10 avec les
pieges reels deja documentes au fil de OMEGA-SERV_PLAN-DETAILLE_
INTERFACE.md et plan_active_defense_omega_serv.md)."""
from __future__ import annotations

from omega_serv.interfaces.tui.guide.model import FaqEntry

FAQ_ENTRIES: tuple[FaqEntry, ...] = (
    FaqEntry(
        category="Redemarrage et rechargement",
        question="J'ai active/modifie une option, mais rien ne change sur le serveur - pourquoi ?",
        answer=(
            "Le serveur tourne dans un PROCESSUS DEJA LANCE, separe de l'interface. Ecrire un "
            "changement dans le fichier de configuration ne le fait jamais relire tout seul par "
            "ce processus : il faut soit le RECHARGER (SIGHUP, ecran SERVICE -> Recharger - "
            "leger, aucune coupure de connexion), soit le REDEMARRER COMPLETEMENT (coupe toutes "
            "les connexions en cours). La plupart des ecrans de configuration detaillee "
            "declenchent desormais ce rechargement automatiquement des qu'un service systemd "
            "actif est detecte, et vous avertissent sinon. Quelques reglages (bind/port, "
            "listen_backlog, TLS, 1ere activation de fastcgi/reverse_proxy, active_defense) "
            "exigent toujours un redemarrage complet - jamais un simple rechargement - car ils "
            "touchent le socket d'ecoute ou des composants construits une seule fois au demarrage."
        ),
    ),
    FaqEntry(
        category="Redemarrage et rechargement",
        question="Comment savoir si un changement precis a besoin d'un rechargement ou d'un redemarrage complet ?",
        answer=(
            "La reaction exacte de chaque champ est indiquee dans sa fiche du guide (touche F1 "
            "depuis l'ecran concerne). En regle generale : tout ce qui touche le socket "
            "d'ecoute (adresse, port, listen_backlog), le contexte TLS, ou un composant "
            "construit une seule fois au demarrage (client FastCGI/reverse proxy a la premiere "
            "activation, Active Defense) exige un redemarrage complet. Tout le reste se "
            "recharge a chaud."
        ),
    ),
    FaqEntry(
        category="Redemarrage et rechargement",
        question="Le rechargement/redemarrage automatique ne s'est pas declenche - pourquoi ?",
        answer=(
            "Le declenchement automatique ne fonctionne que si un gestionnaire de service "
            "systeme (systemd/OpenRC/runit) est reconnu ET qu'un service est reellement ACTIF "
            "pour ce repertoire. Si vous faites tourner le serveur via l'assistant premier "
            "lancement (\"Lancer maintenant\", sans service installe), aucun rechargement "
            "automatique n'est possible - relancez manuellement, ou installez le service depuis "
            "l'ecran SERVICE."
        ),
    ),
    FaqEntry(
        category="Service systeme",
        question="Juste apres 'Installer l'unite', l'ecran Etat & Ressources affiche 'Arrete' alors que le service tourne - pourquoi ?",
        answer=(
            "L'installation cree un compte systeme dedie et ajoute votre session au groupe "
            "correspondant, mais l'appartenance a un NOUVEAU groupe Unix ne s'applique jamais a "
            "une session deja ouverte (meme terminal deja lance avant l'installation). "
            "Deconnectez-vous puis reconnectez-vous UNE SEULE FOIS - l'ecran affichera alors "
            "l'etat reel. En attendant, verifiez via l'ecran SERVICE ou `systemctl status`."
        ),
    ),
    FaqEntry(
        category="Service systeme",
        question="Le champ 'Nom du service' dans l'ecran SERVICE ne correspond pas a ce que je pilote ailleurs - pourquoi ?",
        answer=(
            "Ce champ persiste une preference d'interface, distincte de la configuration serveur. "
            "Si cette instance est enregistree en multi-instance, le nom est FIGE (celui choisi a "
            "la creation) - jamais improvise ici. Une seule interface peut deja piloter "
            "n'importe quelle unite installee en tapant simplement son nom exact, meme celle "
            "d'une autre copie du projet."
        ),
    ),
    FaqEntry(
        category="Multi-instance",
        question="Puis-je installer une seconde unite systemd qui pointe vers le meme repertoire, sous un autre nom ?",
        answer=(
            "Non - deux garde-fous bloquent explicitement cette situation avant toute ecriture : "
            "une unite differente pointant deja vers ce repertoire (partagerait silencieusement "
            "var/, la configuration et le compte systeme dedie), et un nom deja utilise par une "
            "unite pointant vers un AUTRE repertoire (volerait ce nom, ecrasant l'unite "
            "existante). Pour heberger plusieurs serveurs, utilisez Multi-instance : chaque "
            "instance a son propre repertoire, sa propre configuration et son propre compte systeme."
        ),
    ),
    FaqEntry(
        category="Multi-instance",
        question="La creation d'une nouvelle instance echoue a l'etape 4/6 (Installation des dependances) - pourquoi ?",
        answer=(
            "Piege reel corrige : si le message d'echec mentionne 'omega-lib' et 'No matching "
            "distribution found', c'etait un bug de la creation d'instance elle-meme, pas une "
            "erreur de votre part - omega-lib n'est pas publiee sur PyPI, et l'ancienne version "
            "ne savait retrouver sa source reelle (vendoree ou depuis un clone de developpement) "
            "que dans un seul des deux cas. Corrige : la nouvelle instance reutilise desormais "
            "la meme source qu'omega-lib deja installee pour l'instance en cours, quelle que "
            "soit sa provenance. Si l'echec persiste malgre une version a jour, verifiez que le "
            "reseau est disponible pour les AUTRES dependances (`textual`, `pyte`, `jinja2`, "
            "`psutil`), qui viennent bien de PyPI."
        ),
    ),
    FaqEntry(
        category="WAF/Active Defense",
        question="Le WAF est actif mais ne bloque jamais rien - pourquoi ?",
        answer=(
            "Verifiez d'abord l'ecran WAF - Etat : si 'Packs de regles references' est a zero, le "
            "WAF ne peut RIEN detecter meme actif (piege reel deja rencontre). Ajoutez au moins "
            "un pack depuis WAF - Modules. Verifiez ensuite le mode : 'log-only' journalise sans "
            "jamais bloquer, seul 'block' bloque reellement."
        ),
    ),
    FaqEntry(
        category="WAF/Active Defense",
        question="J'ai active l'option 'active_defense' mais rien ne se passe jamais (aucune menace, aucun incident) - pourquoi ?",
        answer=(
            "Activer l'option elle-meme (menu Options) ne suffit PAS. Un second interrupteur, "
            "`war_mode.enabled`, vaut FALSE par defaut - activez-le depuis Active Defense -> "
            "Reglages -> 'Mode guerre actif'. Verifiez la ligne 'Mode guerre' sur l'ecran "
            "Active Defense - Etat : si elle affiche 'inactif', c'est la cause. Un REDEMARRAGE "
            "COMPLET est ensuite necessaire (active_defense n'est jamais recharge a chaud). Une "
            "fois actif, tout devient automatique - le score de chaque source est alimente par "
            "les decisions WAF deja calculees a chaque requete, sans aucune action manuelle."
        ),
    ),
    FaqEntry(
        category="WAF/Active Defense",
        question="J'ai cree une regle WAF personnalisee mais elle ne se declenche jamais - pourquoi ?",
        answer=(
            "Utilisez l'ecran WAF - Regles personnalisees (pas 'Modules') pour CREER la regle "
            "elle-meme - il l'ecrit dans custom.json ET reference automatiquement ce pack. "
            "Ajouter seulement le pack custom.json comme reference depuis 'Modules' ne cree "
            "aucune regle si le fichier est encore vide. Utilisez l'ecran 'Tester une requete' "
            "pour verifier qu'une regle se declenche bien avant de compter dessus en production."
        ),
    ),
    FaqEntry(
        category="WAF/Active Defense",
        question="Quelle classe d'attaque choisir pour un profil de leurre ?",
        answer=(
            "Les 8 classes possibles et ce qu'elles ciblent concretement : scan (sondage "
            "d'URLs/ports, scanners automatises), credential_stuffing (essais massifs de "
            "mots de passe sur un formulaire de login), sqli (tentative d'injection SQL), "
            "xss (script injecte dans un parametre), path_traversal (tentative de sortir du "
            "dossier servi, ex : ../../etc/passwd), upload_probe (upload de fichier suspect), "
            "api_probe (sondage d'endpoints /api/...), unknown (tout ce qui ne correspond a "
            "aucune des categories precedentes - un filet de securite generique). Exemple : "
            "un profil nomme fake_admin avec les classes scan,credential_stuffing attirera les "
            "scanners et les tentatives de bruteforce de connexion vers une fausse page "
            "d'authentification. Plusieurs classes peuvent etre listees, separees par des virgules."
        ),
    ),
    FaqEntry(
        category="WAF/Active Defense",
        question="Mon profil de leurre en isolation 'fixture' ne se declenche jamais - pourquoi ?",
        answer=(
            "Le NOM du profil doit correspondre EXACTEMENT a l'une des 4 fixtures reellement "
            "implementees : fake_admin, fake_cms, fake_api, fake_secrets. Tout autre nom "
            "(meme descriptif, ex : 'mon-leurre-perso') faisait auparavant que le leurre ne "
            "se declenchait jamais, sans aucune erreur visible - le trafic suivait alors le "
            "comportement de secours (pass_through ou reject) comme si aucun profil n'existait. "
            "L'ecran Active Defense -> Reglages refuse desormais d'enregistrer un tel nom et "
            "indique clairement le probleme."
        ),
    ),
    FaqEntry(
        category="WAF/Active Defense",
        question="J'ai cree une zone de leurre avec une adresse qui n'existe pas encore - que se passe-t-il ?",
        answer=(
            "Rien de special a l'enregistrement : une zone de leurre (Niveau 2, isolation "
            "'proxy') est une simple cible reseau (host:port), jamais un dossier - aucune "
            "creation automatique, aucune verification que l'adresse existe ou repond au "
            "moment de la sauvegarde. La consequence n'apparait que lors d'une VRAIE requete "
            "routee vers cette zone : si rien n'ecoute a cette adresse, l'attaquant recoit "
            "simplement une erreur HTTP 502 Bad Gateway (la meme mecanique que le reverse "
            "proxy de production) - jamais de crash du serveur, jamais de creation silencieuse "
            "de quoi que ce soit."
        ),
    ),
    FaqEntry(
        category="TLS et certificats",
        question="J'ai regenere/revoque le certificat TLS mais le serveur sert toujours l'ancien - pourquoi ?",
        answer=(
            "Le contexte SSL n'est construit qu'UNE SEULE FOIS au demarrage du serveur, jamais "
            "retouche par un simple rechargement. Regenerer ou revoquer un certificat pendant "
            "que TLS est deja actif necessite TOUJOURS un redemarrage complet pour que le "
            "changement soit reellement pris en compte, meme si le fichier sur disque a deja change."
        ),
    ),
    FaqEntry(
        category="Sauvegarde et restauration",
        question="Mes sauvegardes de configuration sont-elles chiffrees ?",
        answer=(
            "Non, jamais par defaut. Si vous incluez les zones d'authentification (hash de mots "
            "de passe) ou les certificats (cles privees TLS), la sauvegarde contient des secrets "
            "reels en clair - une confirmation explicite supplementaire est demandee avant de "
            "creer ce type de sauvegarde. Protegez ces fichiers comme n'importe quel secret."
        ),
    ),
    FaqEntry(
        category="TLS et certificats",
        question="Comment m'auto-heberger avec un vrai certificat public, de bout en bout (schema DDNS -> Certbot -> OMEGA-SERV) ?",
        answer=(
            "Le schema complet : un service DDNS (Dynu ou equivalent) fait pointer un nom de "
            "domaine public (ex. monserveur.dynu.com) vers votre IP, mise a jour automatiquement "
            "par leur client a chaque changement - ENTIEREMENT hors du perimetre d'OMEGA-SERV, "
            "a installer et configurer vous-meme. Vous devez aussi rediriger les ports 80 et 443 "
            "de votre routeur/pare-feu vers cette machine. Une fois cela fait : Assistant Let's "
            "Encrypt (Configuration detaillee -> TLS) obtient le premier certificat (defi HTTP-01, "
            "webroot - port 80 doit etre joignable depuis Internet le temps de la demande), "
            "l'importe et vous rappelle d'activer TLS (ecran Activer/desactiver TLS) puis de "
            "redemarrer. Ensuite, Renouvellement automatique (meme sous-menu) installe la "
            "planification (timer systemd ou crontab) qui renouvelle et redemarre tout seul, "
            "sans plus jamais intervenir manuellement pour cette partie."
        ),
    ),
    FaqEntry(
        category="TLS et certificats",
        question="OMEGA-SERV tourne dans un conteneur - comment obtenir un certificat Let's Encrypt ?",
        answer=(
            "N'executez PAS l'Assistant Let's Encrypt/le renouvellement automatique a l'interieur "
            "du conteneur qui sert deja le trafic public. Executez-les sur l'hote (ou dans un "
            "conteneur/sidecar distinct dedie a l'administration) en partageant avec le conteneur "
            "serveur : le meme volume de webroot (Certbot y depose son defi, ce que le conteneur "
            "sert deja via le port 80 qu'il expose), et le meme volume secure/certificates/ - le "
            "conteneur serveur peut monter ce dernier en LECTURE SEULE, puisque l'import du "
            "certificat (ecriture) se fait toujours cote hote/sidecar, jamais depuis le conteneur "
            "servant le trafic. Un redemarrage du conteneur serveur reste necessaire apres chaque "
            "renouvellement (meme regle que partout ailleurs : le contexte SSL n'est jamais "
            "recharge a chaud) - le hook de renouvellement redemarre le SERVICE qu'il connait "
            "(hote/sidecar), pensez a l'adapter si le conteneur serveur est pilote separement "
            "(ex. `docker restart`) plutot que par un service systemd/OpenRC/runit classique."
        ),
    ),
    FaqEntry(
        category="TLS et certificats",
        question="L'Assistant Let's Encrypt echoue (defi HTTP-01) - pourquoi ?",
        answer=(
            "Les causes les plus frequentes, dans l'ordre a verifier : (1) le port 80 n'est pas "
            "reellement joignable depuis Internet (redirection de port manquante ou incorrecte "
            "sur le routeur/pare-feu, ou un autre service occupe deja ce port sur la machine), "
            "(2) le domaine ne pointe pas encore vers cette IP (DNS/DDNS pas encore propage - "
            "verifiez avec `dig`/`nslookup` depuis une machine externe), (3) en mode test "
            "(staging, coche par defaut) tout fonctionne mais le certificat obtenu n'est jamais "
            "reconnu par les navigateurs - c'est normal, decochez la case une fois le domaine et "
            "le webroot verifies. Le message d'erreur affiche est directement celui renvoye par "
            "Certbot - il precise generalement laquelle de ces causes s'applique."
        ),
    ),
)
