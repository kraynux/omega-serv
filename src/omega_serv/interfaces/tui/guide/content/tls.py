# Copyright (c) 2026 kraynux - kraynux@proton.me - Licence MIT (voir fichier LICENSE)
"""Fiches guide : TLS - menu + 5 sous-ecrans (plan guide d'aide, Phase 5)."""
from __future__ import annotations

from omega_serv.interfaces.tui.guide.model import FieldGuide, ScreenGuide

TLS_MENU_SCREEN = ScreenGuide(
    screen_class_name="TlsMenuScreen",
    title="TLS (menu)",
    acces="Accueil -> Configuration detaillee -> TLS",
    definition="Sous-menu regroupant les 5 ecrans lies a TLS : statut, generation, CA locale, revocation, activation.",
    fields=(),
    consequences="Aucune - purement navigation.",
)

TLS_STATUS_SCREEN = ScreenGuide(
    screen_class_name="TlsStatusScreen",
    title="Statut TLS",
    acces="Configuration detaillee -> TLS -> Statut TLS",
    definition="Inspecte le certificat actuellement configure : validite, expiration, correspondance avec la cle privee, permissions.",
    fields=(
        FieldGuide(
            label="Rafraichir",
            definition="Relit et reanalyse le certificat configure.",
            utilisation="Aucune saisie.",
            action="Relance l'inspection.",
            reaction="Aucun effet (lecture seule).",
        ),
    ),
    consequences="Aucune - purement consultatif.",
    points_de_vigilance=(
        (
            "Inspecte le FICHIER sur disque, pas necessairement celui reellement servi par un "
            "serveur deja lance si celui-ci a change depuis le dernier redemarrage."
        ),
    ),
)

GENERATE_SELF_SIGNED_SCREEN = ScreenGuide(
    screen_class_name="GenerateSelfSignedScreen",
    title="Generer un certificat auto-signe",
    acces="Configuration detaillee -> TLS -> Generer un certificat auto-signe",
    definition="Genere un certificat auto-signe (jamais reconnu par defaut par les navigateurs) et l'ecrit sur disque.",
    fields=(
        FieldGuide(
            label="Nom commun (CN)",
            definition="Nom commun du certificat.",
            utilisation="Chaine libre, generalement le nom d'hote du serveur.",
            action="Utilise a la generation.",
            reaction="Ecrit reellement le certificat/la cle sur disque immediatement.",
        ),
        FieldGuide(
            label="SAN DNS / SAN IP",
            definition="Noms DNS et adresses IP alternatifs couverts par le certificat.",
            utilisation="Listes separees par des virgules, optionnelles.",
            action="Utilise a la generation.",
            reaction="Ecrit sur disque immediatement.",
        ),
        FieldGuide(
            label="Organisation / Unite / Ville / Region / Pays",
            definition="Champs d'identite du certificat (sujet X.509).",
            utilisation="Chaines libres, tous optionnels sauf Organisation (pre-rempli : OMEGA-SERV).",
            action="Utilise a la generation.",
            reaction="Ecrit sur disque immediatement.",
        ),
        FieldGuide(
            label="Validite en jours",
            definition="Duree de validite du certificat genere.",
            utilisation="Entier positif, en jours. Valeur par defaut : 365.",
            action="Utilise a la generation.",
            reaction="Ecrit sur disque immediatement.",
        ),
        FieldGuide(
            label="Type de cle",
            definition="Algorithme et taille de la cle privee generee.",
            utilisation="Valeurs valides indiquees dans le sous-titre. Valeur par defaut : rsa2048.",
            action="Utilise a la generation.",
            reaction="Ecrit sur disque immediatement.",
        ),
        FieldGuide(
            label="Mot de passe de cle (optionnel)",
            definition="Passphrase protegeant la cle privee generee.",
            utilisation="Chaine libre, optionnelle - saisie masquee.",
            action="Utilise a la generation.",
            reaction="Ecrit sur disque immediatement.",
        ),
    ),
    consequences=(
        "Genere reellement des fichiers sur disque des le clic sur Generer. Si TLS est DEJA "
        "actif, le serveur en cours d'execution continue de servir l'ANCIEN certificat jusqu'a "
        "un REDEMARRAGE COMPLET, meme si le fichier a change (le contexte SSL n'est construit "
        "qu'une seule fois au demarrage)."
    ),
)

CA_WIZARD_SCREEN = ScreenGuide(
    screen_class_name="CaWizardScreen",
    title="Assistant CA locale",
    acces="Configuration detaillee -> TLS -> Assistant CA locale",
    definition=(
        "Enchaine trois etapes independantes : generer une autorite de certification locale, "
        "generer une demande de signature (CSR) pour ce serveur, signer cette CSR avec la CA - "
        "permet d'obtenir un certificat reconnu par les clients ayant importe la CA, sans passer "
        "par une autorite publique."
    ),
    fields=(
        FieldGuide(
            label="1. Generer la CA",
            definition="Cree l'autorite de certification locale (cle + certificat racine).",
            utilisation="CN, organisation, validite (defaut 3650 jours), type de cle, passphrase OBLIGATOIRE (saisie deux fois).",
            action="Ecrit root-ca.key/root-ca.pem/serial.txt/index.txt sous secure/certificates/ca/.",
            reaction="Ecrit reellement sur disque immediatement. A faire une seule fois.",
        ),
        FieldGuide(
            label="2. Generer la CSR",
            definition="Cree une demande de signature de certificat pour CE serveur.",
            utilisation="CN, SAN DNS/IP, identite, type de cle - pas de passphrase ici.",
            action="Ecrit le fichier .csr a cote de la cle privee du serveur.",
            reaction="Ecrit reellement sur disque immediatement.",
        ),
        FieldGuide(
            label="3. Signer la CSR",
            definition="Signe la CSR generee a l'etape 2 avec la CA de l'etape 1, produit le certificat final.",
            utilisation="Chemin de la CSR (pre-rempli), passphrase de la CA (resaisie), validite en jours (defaut 365).",
            action="Ecrit le certificat signe (et la chaine complete) sur disque.",
            reaction=(
                "Ecrit reellement sur disque immediatement. Si TLS est DEJA actif, un "
                "REDEMARRAGE COMPLET reste necessaire pour que le serveur serve ce nouveau "
                "certificat (le contexte SSL en memoire ne se recharge jamais tout seul)."
            ),
        ),
    ),
    consequences=(
        "Le certificat racine de la CA (root-ca.pem) doit etre importe manuellement dans le "
        "magasin de confiance de chaque client pour que le certificat final soit reconnu - "
        "rappele dans le journal de l'assistant apres chaque etape reussie."
    ),
    points_de_vigilance=(
        (
            "La passphrase de la CA n'est jamais conservee en memoire entre les etapes - elle "
            "est resaisie explicitement a l'etape 3."
        ),
    ),
)

REVOKE_CERTIFICATE_SCREEN = ScreenGuide(
    screen_class_name="RevokeCertificateScreen",
    title="Revoquer un certificat",
    acces="Configuration detaillee -> TLS -> Revoquer un certificat",
    definition="Marque un certificat comme revoque dans le registre de la CA (index.txt) - action irreversible pour ce certificat.",
    fields=(
        FieldGuide(
            label="Certificat a revoquer",
            definition="Chemin du certificat a marquer comme revoque.",
            utilisation="Chemin relatif au projet.",
            action="Utilise a la confirmation.",
            reaction="Modifie index.txt immediatement apres confirmation.",
        ),
        FieldGuide(
            label="Cle / Certificat de la CA",
            definition="Identite de l'autorite de certification qui a signe le certificat vise.",
            utilisation="Chemins pre-remplis vers secure/certificates/ca/.",
            action="Utilise a la confirmation.",
            reaction="Modifie index.txt immediatement.",
        ),
        FieldGuide(
            label="Passphrase de la cle CA",
            definition="Necessaire pour prouver l'autorite sur la CA avant de revoquer.",
            utilisation="Saisie masquee.",
            action="Utilise a la confirmation.",
            reaction="Modifie index.txt immediatement.",
        ),
    ),
    consequences=(
        "Demande une confirmation explicite (action irreversible pour ce certificat). Si le "
        "certificat revoque est celui ACTUELLEMENT utilise par un serveur TLS deja actif, un "
        "REDEMARRAGE COMPLET est necessaire, sinon il continue d'etre presente aux clients "
        "malgre sa revocation."
    ),
    points_de_vigilance=(
        (
            "Pas de distribution CRL complete en V1 - la revocation reste locale (index.txt), "
            "jamais publiee vers les clients automatiquement."
        ),
    ),
)

TLS_TOGGLE_SCREEN = ScreenGuide(
    screen_class_name="TlsToggleScreen",
    title="Activer / desactiver TLS",
    acces="Configuration detaillee -> TLS -> Activer / desactiver TLS",
    definition="Active ou desactive TLS, et choisit son mode (direct ou derriere un proxy qui termine deja le TLS).",
    fields=(
        FieldGuide(
            label="Mode",
            definition="Comment TLS est gere par ce serveur.",
            utilisation=(
                "direct (ce serveur termine TLS lui-meme, via ssl.SSLContext local) ou "
                "behind_proxy (TLS deja termine en amont, ce serveur reste en HTTP simple)."
            ),
            action="Enregistre au clic sur Activer TLS.",
            reaction="Necessite TOUJOURS un REDEMARRAGE COMPLET, jamais un simple rechargement.",
        ),
        FieldGuide(
            label="Chemin du certificat / de la cle privee",
            definition="Fichiers utilises si le mode est 'direct'. Optionnels : conservent la valeur actuelle si vides.",
            utilisation="Chemins relatifs au projet.",
            action="Enregistre avec le mode.",
            reaction="Necessite TOUJOURS un REDEMARRAGE COMPLET.",
        ),
    ),
    consequences=(
        "Le contexte SSL n'est construit qu'une seule fois au demarrage - activer, desactiver, "
        "ou changer le mode TLS exige SYSTEMATIQUEMENT un redemarrage complet, que ce soit pour "
        "l'activation ou la desactivation."
    ),
    points_de_vigilance=(
        (
            "A ne pas confondre avec le reglage 'reverse_proxy' (Configuration detaillee -> "
            "Reverse Proxy) : ici, 'behind_proxy' signifie qu'OMEGA-SERV est DERRIERE un proxy "
            "TLS externe, l'inverse d'agir soi-meme comme proxy."
        ),
    ),
)

ALL_TLS_GUIDES: tuple[ScreenGuide, ...] = (
    TLS_MENU_SCREEN,
    TLS_STATUS_SCREEN,
    GENERATE_SELF_SIGNED_SCREEN,
    CA_WIZARD_SCREEN,
    REVOKE_CERTIFICATE_SCREEN,
    TLS_TOGGLE_SCREEN,
)
