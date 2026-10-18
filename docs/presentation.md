<!-- Copyright (c) 2026 kraynux - kraynux@proton.me - Licence MIT (voir fichier LICENSE) -->
<!-- Version Markdown de presentation.html, generee pour l'archive distribuee
     (la page HTML depend de CSS/JS serveur, illisible hors serveur). -->
<div align="center">
  <img src="https://kraynux.snake-mackarel.ts.net/omega-serv/omega-serv.png" alt="Omega-Serv Logo" width="320">
</div>

# 🔒 OMEGA-SERV

**Serveur web HTTP autonome, portable et durci par défaut**

Un serveur simple à installer, agréable à administrer, sûr dès le premier lancement.
Développé en Python — Licence Open source (MIT)

`Arch Linux` · `Python pur` · `Sans dépendance` · `Durci par défaut` · `WAF optionnel` · `TUI + CLI` · `MIT`

Page officielle : [OMEGA-SERV](https://kraynux.snake-mackarel.ts.net/omega-serv/) &nbsp;·&nbsp;
Guide complet : [guide.md](guide.md) &nbsp;·&nbsp;
README complet : [readme.md](readme.md) &nbsp;·&nbsp;
Captures : [Screenshots](https://kraynux.snake-mackarel.ts.net/omega-serv/screenshots/) &nbsp;·&nbsp;
Démo : [Serveur Demo](https://craftdark.snake-mackarel.ts.net)

---

## 🚀 Un serveur web complet, sécurisé, facile à installer et à administrer

**Omega-Serv** est un serveur HTTP/1.1 qui vous permet de mettre en ligne un site statique ou une
application PHP en quelques minutes. Pas de configuration complexe à mémoriser : une interface
claire vous guide, et la sécurité est active dès le premier lancement.

- 📂 **Sert vos fichiers** — Statique ou PHP-FPM
- 🛡️ **Sécurisé par défaut** — Protections intégrées
- 🎛️ **Interface claire** — Menus guidés, aide intégrée
- 🔧 **Modules optionnels** — WAF · TLS · Auth · Cache
- ⚙️ **Service système** — Démarre tout seul
- 📊 **Suivi en direct** — Logs · Ressources · Menaces

## 🖼️ Aperçu de l'interface

| # | Écran |
|---|---|
| 1 | Splash — [capture](https://kraynux.snake-mackarel.ts.net/omega-serv/screenshots/splash.png) |
| 2 | Menu principal — [capture](https://kraynux.snake-mackarel.ts.net/omega-serv/screenshots/menu-principal.png) |
| 3 | Lecteur de logs fusionnés (lnav) — [capture](https://kraynux.snake-mackarel.ts.net/omega-serv/screenshots/5.2-voir-logs-fusion-lnav.png) |
| 4 | État & Ressources — [capture](https://kraynux.snake-mackarel.ts.net/omega-serv/screenshots/8-dashbord-etat-ressources.png) |

📸 [Voir toutes les captures d'écran](https://kraynux.snake-mackarel.ts.net/omega-serv/screenshots/)

---

## 📦 Télécharger Omega-Serv

Récupérez la dernière version de l'application.
Format : `.tar.gz` — Compatible Arch Linux et systèmes Linux, macOS, Windows (WSL) avec Python 3.10+.

⬇️ [Télécharger l'archive](https://kraynux.snake-mackarel.ts.net/omega-serv/omega-serv.tar.gz)

- 📄 Version : 1.0.0
- 📅 Dernière mise à jour : 14 septembre 2026
- 📏 Taille : ~1,1 Mo

> 🔐 **Intégrité :** vérifiez l'intégrité de l'archive :
> ```bash
> sha256sum omega-serv.tar.gz
> ```

---

# ⚡ Installation

> 💡 **Ce qu'il vous faut :**
> - Un système Linux (Arch ou tout autre distribution)
> - Python 3.10 ou plus récent
> - Aucun droit administrateur requis pour démarrer

## Installation rapide

```bash
[ -d omega-serv ] && echo "ℹ️ Déjà extrait ici, étape ignorée." || tar -xzf omega-serv.tar.gz
cd omega-serv/
chmod +x install.sh
./install.sh
```

Le script `install.sh` s'occupe de tout :

1. Crée un environnement isolé pour l'application
2. Installe le paquet (aucune dépendance externe pour le cœur du serveur)
3. Rend le lanceur exécutable
4. Ajoute la commande `serv` à votre terminal

### Lancer Omega-Serv

```bash
./omega-serv.sh
# ou simplement 'serv' dans un NOUVEAU terminal
```

Au premier lancement, un **assistant de démarrage** vous guide en 8 étapes pour créer votre
première configuration et mettre le serveur en route — sans connaître une seule commande.

### Outils optionnels recommandés

L'interface fonctionne en mode dégradé si ces outils sont absents :

- `lnav` — analyse avancée des logs fusionnée dans l'écran **Gestion des logs** ; message d'erreur
  clair et explicite si l'exécutable est introuvable, aucun crash.
- `python-psutil` — installé automatiquement par `pip install -e .` dans tous les cas, mais le
  préinstaller via le gestionnaire système évite à `pip` de devoir compiler son wheel localement.

```bash
# Arch Linux et dérivés
sudo pacman -S openssl certbot lnav python-psutil openssh

# Debian/Ubuntu et dérivées
sudo apt install openssl certbot lnav python3-psutil openssh-client

# Fedora
sudo dnf install openssl certbot lnav python3-psutil openssh-clients
```

---

## Mise à jour

Si `omega-serv/` existe déjà (installation précédente, conserve les paramètres), **ne lancez
jamais `tar` depuis l'intérieur de ce dossier** : il tenterait de créer un `omega-serv/omega-serv/`
imbriqué et échouerait. Contrairement à omega-fire, `install.sh` ne touche jamais aux permissions
du dossier (aucune étape n'y demande `sudo`) — donc pas de risque de dossier appartenant à `root`
ici, une extraction directement par-dessus l'installation existante est sûre.

### Lancer

```bash
# Depuis le dossier PARENT de omega-serv/ (jamais depuis l'intérieur)
tar -xzf omega-serv.tar.gz
cd omega-serv/
./install.sh
```

---

# 🎯 Vos premiers pas en 5 minutes

**1 — Lancez l'assistant**
Depuis l'accueil, choisissez **Assistant premier lancement**. Il vous pose quelques questions
simples : quel profil utiliser, quelle adresse et quel port écouter, voulez-vous HTTPS...

**2 — Déposez vos fichiers**
Copiez votre site dans le dossier `webroot/`. Vos fichiers sont immédiatement servis — pas de
redémarrage nécessaire.

**3 — Activez HTTPS**
L'assistant propose de générer un certificat en un clic. Pour vos tests locaux, l'auto-signé
suffit. Pour plusieurs appareils, une petite autorité locale fait le travail. Inclut aussi HTTPS
Auto (ACME via Certbot « Let's Encrypt » à activer pour renouvellement auto) pour exposition web.

**4 — Installez le service**
Pour que le serveur démarre automatiquement avec la machine, laissez-vous guider : l'installation
du service systemd est proposée à la fin de l'assistant.

**5 — Activez la sécurité**
Le WAF, l'authentification HTTP Basic, le cache, les redirections... Tout s'active depuis un menu
unique. Un tableau récapitule à chaque instant ce qui est actif.

**6 — Surveillez en direct**
L'écran **État & Ressources** vous montre en temps réel le trafic, les erreurs, les ressources
consommées, et même les menaces détectées par Active Defense.

---

## 💡 Ce qui fait la différence

**🛡️ La sécurité n'est pas une option**
- Dès le premier lancement, le serveur est protégé contre les abus basiques (méthodes dangereuses
  bloquées, en-têtes de sécurité, CSP par défaut)
- Ces protections ne peuvent pas être désactivées par erreur — elles sont dans le cœur du serveur
- Le serveur refuse de tourner en tant que root : il vous protège de vos propres erreurs

**🎛️ Une interface qui prend soin de vous**
- Chaque écran a sa propre aide contextuelle (touche `F1`)
- Les modifications sensibles demandent confirmation — jamais de mauvaise surprise
- Le serveur vous dit toujours s'il faut le recharger ou le redémarrer après un changement
- Guide complet intégré, avec FAQ et exemples concrets, exportable en HTML

**🔍 Un vrai compagnon de sécurité**
- WAF optionnel : signatures, limitation de débit, liste de blocage, et listes de chemins sensibles prêtes à l'emploi (298 + 132 chemins), éditables à la souris dans l'interface
- Active Defense : détection des comportements hostiles, leurres intelligents, journalisation
  enrichie
- Incidents documentés avec chronologie et exports d'indicateurs de compromission
- Simulation en dry-run : vérifier une règle avant de l'activer

**🧩 Une architecture modulaire**
- Vous activez uniquement ce dont vous avez besoin
- Chaque module vit dans son espace : FastCGI/PHP, TLS, redirections, cache, authentification,
  upload
- Le multi-instance vous permet de faire tourner plusieurs serveurs sur la même machine
- Sauvegarde et restauration de configuration en un clic

**📊 Un tableau de bord complet**
- Logs consultables, suivables en direct, fusionnables via lnav
- Statistiques horaires, top IPs, répartition par code de statut
- Rotation et archivage automatiques ou manuels
- Fusion multi-logs pour les enquêtes
- Bibliothèque, Favoris, et sources distantes récupérées via SSH

**🎓 Pensé pour apprendre**
- Chaque champ est expliqué avec un exemple concret
- Un simulateur de requête pour comprendre le routage
- La FAQ répond aux pièges réellement rencontrés
- Vous n'avez jamais besoin d'éditer un fichier de configuration à la main

---

## 📚 Documentation

Toute la documentation est intégrée à l'application (touche `a` pour le guide complet, `F1` pour
l'aide contextuelle). Vous pouvez aussi consulter les pages dédiées :

- 🎓 [Consulter le guide utilisateur](guide.md)
- 📖 [Lire le README complet](readme.md)
- 🖼️ [Voir toutes les captures](https://kraynux.snake-mackarel.ts.net/omega-serv/screenshots/)
- 📖 [Comparatif serveurs web](https://kraynux.snake-mackarel.ts.net/public/tutos/comparatif-serveur-web-6-models.html)
- 📖 [Serveur web de démonstration](https://craftdark.snake-mackarel.ts.net)

---

## 🧩 Modules disponibles

Tous désactivés par défaut — vous activez uniquement ce dont vous avez besoin :

| Module | Rôle |
|---|---|
| **WAF** | Filtrage applicatif (signatures, limitation de débit, liste de blocage, listes de chemins sensibles éditables avec récidive propre à chaque liste — vos propres machines ne sont jamais bannies) |
| **TLS** | HTTPS avec certificat auto-signé ou signé par une autorité locale |
| **Authentification** | HTTP Basic par zone (protège des dossiers ou applications) |
| **FastCGI/PHP-FPM** | Exécution PHP via un serveur PHP-FPM externe |
| **Reverse proxy** | Redirection vers un ou plusieurs backends avec répartition de charge (classique ou basée sur la charge réelle), affinité de session, bascule santé automatique, cache des réponses, WebSocket et supervision en direct depuis l'interface |
| **Cache** | Contrôle du cache navigateur par zone et par extension |
| **Upload** | Zones d'upload confinées avec quotas |
| **Active Defense** | Leurres intelligents, détection comportementale, incidents et exports IoC |

---

## 🔒 Une sécurité qui ne se compromet pas

- **Le serveur refuse de démarrer en tant que root** — c'est une décision volontaire pour votre
  sécurité
- Liste blanche de méthodes HTTP, validation stricte des en-têtes, rejet de l'ambiguïté
  `Content-Length`
- En-têtes de sécurité (CSP, HSTS, X-Content-Type-Options...) envoyés à toute réponse, y compris
  les erreurs
- Protection contre le path traversal, le double-encodage, les liens symboliques mal placés
- Résolution des adresses IPv4-mappées-IPv6 avant toute vérification (contre un contournement
  connu)
- Derrière un proxy, l'adresse du visiteur est lue de droite à gauche : impossible de se faire
  passer pour une machine locale en envoyant soi-même l'en-tête `X-Forwarded-For`
- Seul le trafic externe peut être banni automatiquement : hôte local, Tailscale et réseau local
  sont toujours exemptés
- Tests de propriétés (*hypothesis*) sur le parseur HTTP et le résolveur de chemin

> 💡 **Bon à savoir :** le profil `hardened` recommande explicitement de placer Omega-Serv derrière
> un reverse proxy pour une exposition Internet réelle. Ce n'est pas une limitation — c'est une
> posture prudente.

---

© 2026 — Omega-Serv — Kraynux pour Omega-Server
