# Étude de faisabilité — Centraliser les logs des serveurs derrière le reverse proxy

**Statut : étude uniquement, aucun code produit.** Ce document répond à
la demande du 2026-10-15 ("Part B") : analyser la faisabilité d'un
accès réseau (SSH/Samba/autre) permettant à Omega-Serv, en reverse
proxy, de centraliser dans sa Bibliothèque les logs des serveurs backend
situés derrière lui sur le même réseau local. Aucune implémentation
n'est proposée à ce stade — uniquement les options, leurs compromis, et
une recommandation pour une décision ultérieure.

## 1. Contexte

Depuis la refonte du menu "Gestion des logs" (2026-10-15), la
Bibliothèque d'Omega-Serv référence des chemins de fichiers locaux,
ajoutés manuellement. Quand Omega-Serv fonctionne en reverse proxy
devant d'autres serveurs web (sur le même réseau local), ces derniers
ont leurs propres logs, sur leurs propres machines — inaccessibles
aujourd'hui depuis la Bibliothèque d'Omega-Serv, qui ne voit que le
système de fichiers local.

Le besoin exprimé : permettre à Omega-Serv d'aller chercher ces logs
distants pour les centraliser (les copier ou les lire à distance) dans
sa propre Bibliothèque, afin de les traiter avec les mêmes outils
(viewers, stats, "Voir et traiter IP", lnav).

## 2. Contrainte fondamentale : ne jamais sortir du périmètre d'action

C'est la contrainte posée explicitement par l'utilisateur et elle
structure toute l'étude : **contacter un serveur distant exige une
configuration qui est EXTERNE à Omega-Serv** — un compte SSH qui
existe et accepte les connexions, un partage Samba exposé, des
identifiants valides, un pare-feu qui autorise le trafic. Omega-Serv
ne contrôle rien de tout cela et ne doit jamais présumer que c'est en
place.

Conséquences directes pour toute implémentation future :

- **Jamais de scan réseau automatique.** Omega-Serv ne doit pas sonder
  le réseau local à la recherche de serveurs SSH/Samba — ce serait une
  action qui sort de son périmètre (et une activité qui ressemble à une
  reconnaissance réseau, détectable et indésirable sur l'infrastructure
  d'un tiers).
- **Jamais de connexion sans configuration explicite de l'utilisateur.**
  L'utilisateur doit fournir lui-même : l'adresse du serveur distant, le
  protocole, les identifiants (ou le chemin vers une clé déjà
  existante). Omega-Serv ne doit jamais inventer, deviner ou tenter des
  identifiants.
- **Jamais de stockage de secret en clair.** Un mot de passe Samba ou
  une phrase de passe de clé SSH ne doit jamais être écrit tel quel dans
  la configuration JSON d'Omega-Serv (qui n'a aujourd'hui aucun
  mécanisme de chiffrement de secrets — en introduire un uniquement pour
  ce besoin serait disproportionné tant que le besoin réel n'est pas
  confirmé).
- **La détection de capacité doit rester LOCALE.** Le "registre des
  capacités" existant détecte ce qui est disponible sur la machine qui
  exécute Omega-Serv (binaires installés, services actifs). Étendre ce
  registre à "ssh/samba disponibles" doit se limiter à vérifier que le
  **client** (binaire `ssh`, `smbclient`, etc.) est installé localement
  — jamais à vérifier qu'un serveur distant particulier est joignable,
  ce qui impliquerait déjà une tentative de connexion.

## 3. Options analysées

### 3.1 SSH (SFTP / SCP / commande distante)

**Principe** : utiliser un client SSH déjà présent sur la machine
(`ssh`, `sftp`, `scp`), avec une clé privée désignée par l'utilisateur
(jamais générée ni stockée par Omega-Serv), pour lire ou copier un
fichier de log distant.

**Pour** :
- Quasi universellement présent sur toute machine Linux/BSD
  administrée — aucune installation supplémentaire côté backend dans
  l'immense majorité des cas.
- Modèle d'authentification déjà robuste et audité (clé publique),
  aucune nécessité d'inventer un mécanisme de credentials maison.
- Un simple `cat`/`tail` distant via SSH suffit pour une lecture
  ponctuelle ; SFTP convient pour une copie complète (utile pour
  l'archivage/rotation).
- S'intègre naturellement au modèle Ports/Adapters déjà en place :
  un `RemoteLogAccessPort` avec une implémentation
  `infrastructure/remote/ssh_log_access.py`, invoquant le binaire `ssh`
  via `ProcessRunnerPort` (même famille de port que celui déjà utilisé
  pour `rc-service`/`rc-update` dans les gestionnaires de service) —
  aucune nouvelle dépendance Python, aucun nouveau point d'entrée
  `subprocess` à ajouter au contrat import-linter existant si l'on
  réutilise `infrastructure.process.subprocess_runner`.

**Contre** :
- Nécessite que l'utilisateur ait déjà accès SSH au backend (compte,
  clé déployée) — c'est une configuration côté backend, hors du
  périmètre d'Omega-Serv par construction (voir §2).
- Une lecture répétée (tail en direct, à la façon du Viewer Simple
  actuel) via SSH est plus coûteuse qu'une lecture locale : chaque
  rafraîchissement est un aller-retour réseau. Un vrai "live tail"
  distant demanderait soit du polling (simple mais mesurément moins
  réactif), soit un flux SSH maintenu ouvert (`ssh ... tail -f`, plus
  complexe à superviser proprement : détection de coupure, relance).

### 3.2 Samba / CIFS

**Principe** : monter ou lire un partage réseau Samba exposé par le
backend (ou par un serveur de fichiers tiers), via `smbclient` ou un
montage CIFS.

**Pour** :
- Pertinent si l'environnement est déjà un parc mixte Windows/Linux où
  Samba est le mécanisme de partage déjà en place (scénario plausible
  dans un réseau local hétérogène).
- Une fois monté, le fichier distant se comporte comme un fichier
  local — réutilise alors telle quelle toute la logique Bibliothèque/
  viewers existante (lecture, tail, parsing).

**Contre** :
- Exige qu'un service Samba soit **déjà** installé et configuré sur le
  backend — une surface d'installation bien plus lourde que SSH (qui
  est déjà quasi toujours présent) dans un contexte très majoritairement
  Linux comme celui d'Omega-Serv.
- Modèle d'authentification historiquement plus faible (mots de passe
  en clair sur le réseau dans les configurations anciennes/SMB1 — SMB3
  corrige cela mais suppose une configuration moderne correctement
  faite, qu'Omega-Serv ne peut pas vérifier).
- Un montage CIFS système (`mount -t cifs`) exigerait des privilèges
  root et une opération système persistante (un point de montage qui
  survit au-delà du processus Omega-Serv) — en tension directe avec la
  discipline déjà actée du projet d'éviter toute élévation de
  privilèges pour la gestion des logs (voir la décision documentée du
  2026-10-15 d'omettre délibérément `infrastructure/privileged/` dans
  cette refonte). Une lecture via `smbclient` en mode "client" (sans
  montage persistant) évite ce problème mais perd l'intégration
  transparente "fichier local" citée plus haut.

### 3.3 Autres protocoles envisageables

- **NFS** : écarté d'emblée — modèle d'autorisation basé sur
  l'IP/l'UID réseau (pas de credentials applicatifs), et un montage
  système comme pour Samba ; moins pertinent encore que Samba pour ce
  besoin précis.
- **Redirection syslog / agrégation (rsyslog, journald forwarding)** :
  approche *inverse* de celle demandée — ce serait le backend qui
  **pousse** ses logs vers Omega-Serv plutôt qu'Omega-Serv qui va les
  chercher. Pertinent à mentionner car potentiellement plus robuste à
  terme (pas de polling, le backend contrôle ce qu'il envoie), mais
  hors scope de la demande actuelle (qui porte sur centraliser depuis
  le reverse proxy, pas sur reconfigurer les backends pour qu'ils
  envoient leurs logs) et demanderait qu'Omega-Serv expose un
  **récepteur** réseau — une surface d'attaque entrante nouvelle,
  décision bien plus lourde que les options "client" ci-dessus.
- **Agent applicatif / API HTTP dédiée** : demanderait de développer et
  déployer un petit composant sur CHAQUE backend — hors de portée
  d'Omega-Serv seul (ce n'est plus "Omega-Serv accède à un backend
  existant" mais "Omega-Serv exige d'installer quelque chose sur le
  backend"), à écarter pour cette même raison.

## 4. Détection dans le registre des capacités

Si cette fonctionnalité est confirmée un jour, l'extension naturelle du
registre des capacités existant serait d'ajouter deux capacités
**locales** (détectées comme les capacités actuelles — présence d'un
binaire, rien de plus) :

- `ssh_client` : présence du binaire `ssh` (et `sftp`/`scp` si
  pertinent) dans le `PATH`.
- `samba_client` : présence du binaire `smbclient` dans le `PATH`.

Ces deux capacités répondraest à la question *"Omega-Serv PEUT-IL
tenter un accès distant si on le lui demande ?"* — jamais à la question
*"existe-t-il un backend distant atteignable ?"*, qui reste entièrement
du ressort de la configuration que l'utilisateur fournirait
explicitement (adresse, identifiants) au moment de configurer une
source de log distante dans la Bibliothèque — jamais détectée ou
devinée par Omega-Serv lui-même.

## 5. Recommandation

**SSH/SFTP comme option principale**, pour les trois raisons
convergentes suivantes :

1. Présence quasi garantie sur tout backend Linux déjà administré —
   le coût d'adoption réel pour l'utilisateur est proche de zéro s'il a
   déjà un accès SSH à ses serveurs (ce qui est le cas typique d'un
   administrateur gérant plusieurs machines sur son réseau local).
2. Modèle d'authentification déjà éprouvé, ne demandant à Omega-Serv
   aucune nouvelle responsabilité de gestion de secrets (la clé privée
   reste un fichier que l'utilisateur gère lui-même, en dehors
   d'Omega-Serv — seul son CHEMIN serait référencé).
3. S'intègre sans friction architecturale au modèle Ports/Adapters
   déjà en place (nouveau port, nouvelle implémentation infrastructure,
   aucune nouvelle dépendance).

**Samba resterait une option secondaire**, à n'envisager que si un
besoin réel et concret se présente (parc mixte Windows, Samba déjà en
place) — même discipline YAGNI déjà appliquée à l'alimentation
automatique de la Bibliothèque dans la Part A de cette refonte : ne pas
construire une deuxième voie d'accès tant qu'aucun cas d'usage réel ne
la justifie.

## 6. Ce qui resterait hors scope même en cas d'implémentation future

- Pas de découverte réseau automatique (voir §2).
- Pas de "live tail" distant par défaut — une récupération
  **à la demande** (bouton explicite, comme "Rafraîchir" dans la
  Bibliothèque actuelle) est suffisante pour un premier jet ; un
  rafraîchissement périodique en arrière-plan serait une décision
  distincte, plus tard, si le besoin se confirme.
- Pas de montage système persistant (CIFS/NFS) — toute lecture distante
  resterait un accès "client" ponctuel, jamais un point de montage qui
  survit à la fermeture d'Omega-Serv.
- Pas de gestion de secrets chiffrés dans la configuration JSON tant
  qu'aucun besoin ne dépasse le cas "clé SSH déjà présente sur le
  disque, référencée par son chemin".

## 7. Conclusion

La demande est **techniquement faisable**, à condition de respecter
strictement le périmètre d'action d'Omega-Serv : aucune action réseau
n'est entreprise sans configuration explicite fournie par
l'utilisateur, et la détection de capacité reste purement locale
(présence d'un client, jamais une tentative de connexion). SSH/SFTP
est l'option recommandée si une implémentation est décidée ; Samba
reste documenté comme option de repli pour un besoin spécifique non
couvert par SSH. Aucune implémentation n'est entreprise à ce stade —
cette étude attend une décision explicite avant tout développement.
