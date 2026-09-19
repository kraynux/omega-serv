"""Implementation reelle de LoggerPort - ajout de ligne en mode append.

Volontairement sans rotation ici (spec Phase 2/4 : reutilisation du
mecanisme deja valide dans omega-fire, voir
OMEGA-SERV_PLAN_DEVELOPPEMENT.md §5) - ce module se contente d'ecrire,
la rotation est une preoccupation separee branchee plus tard sur les
memes fichiers.

Retour utilisateur reel (2026-09-14) : un fichier de log jamais ecrit
avant (ex. `waf-alerts.log`) cree par un premier appel CLI/TUI interactif
(utilisateur `kraynux`, umask usuel 022) se retrouve en mode 644 - lisible
mais PAS inscriptible par le groupe. Le service systemd dedie (compte
`omega-serv`, `UMask=0007` dans l'unite - voir `systemd_service_manager.
py::grant_directory_access`) ne peut alors PLUS jamais y ecrire une fois
lance : `PermissionError` non rattrapee dans la boucle de connexion,
requete plantee sans reponse (jamais un simple 500 propre). `UMask=0007`
resout deja le sens service -> fichier (ses propres fichiers naissent
group-inscriptibles), mais jamais l'inverse (fichier deja cree par un
humain avant que le service n'y touche) - `chmod` explicite ici rend le
partage symetrique quel que soit l'acteur qui cree le fichier en premier,
plutot que de rester a la merci de l'umask de celui qui gagne la course.

Deuxieme filet de securite, meme retour utilisateur : une journalisation
est un effet de bord, jamais une raison valable d'interrompre une requete
reelle deja en cours de traitement (meme principe deja applique ailleurs
dans ce projet - fail-open du WAF, "jamais interrompre le trafic
legitime" d'Active Defense) - toute `OSError` residuelle (autre souci de
permissions, disque plein...) est donc avalee ici plutot que remontee,
avec un signalement sur stderr (visible via `journalctl` sous systemd)
pour ne jamais la rendre totalement invisible non plus.

Retour utilisateur (audit performance, 2026-09-14) : `append_line` est
appelee sur CHAQUE requete HTTP (acces/erreur/alerte WAF - jamais une
operation rare) et faisait jusque-la 4-5 appels systeme bloquants a
chaque fois (`mkdir`, `exists`, `open`, `write`, `close`) sur le thread
unique de la boucle asyncio - le goulot d'etranglement n°1 du serveur a
forte charge, une simple ecriture disque suffisant a geler TOUTES les
connexions concurrentes pendant sa duree. Un descripteur ouvert est
desormais garde par chemin (jamais ferme explicitement - voir plus bas
pourquoi ce n'est pas necessaire), le `mkdir`/`exists`/`chmod` ne
s'executant plus qu'une seule fois par chemin, a la premiere ecriture.

Survit a la rotation (`application/logs/rotate_log.py::rotate_log_if_needed`)
sans code special : la rotation TRONQUE le fichier en place
(`FilesystemPort.write_text(log_path, "")`, jamais un
unlink+recreation - verifie dans `LocalFilesystem.write_text` qui
delegue a `Path.write_text`, toujours une ouverture en mode "w" sur le
MEME inode) et le descripteur est ouvert en mode append (`"a"`, drapeau
`O_APPEND` cote noyau) : chaque `write()` se repositionne alors
TOUJOURS sur la fin reelle du fichier au moment de l'appel, meme si un
AUTRE acteur (ici notre propre rotation) l'a tronque entre-temps -
propriete atomique du noyau, jamais une simple convention Python.

Pas de `close()` explicite : le mode ligne (`buffering=1`) fait deja
atteindre le tampon du noyau a chaque saut de ligne (aucune perte en cas
d'arret brutal), et les descripteurs sont de toute facon liberes par
l'OS a la fin du processus - ajouter un cycle de vie explicite ici
n'apporterait rien de plus, pour une ressource qui vit aussi longtemps
que le processus serveur lui-meme."""
from __future__ import annotations

import sys
import threading
from pathlib import Path
from typing import IO

_SHARED_LOG_FILE_MODE = 0o664


class FileLineLogger:
    def __init__(self) -> None:
        self._handles: dict[Path, IO[str]] = {}
        self._lock = threading.Lock()

    def append_line(self, path: Path, line: str) -> None:
        try:
            with self._lock:
                handle = self._handles.get(path)
                if handle is None:
                    handle = self._open(path)
                    self._handles[path] = handle
                handle.write(line + "\n")
        except (OSError, ValueError) as exc:
            print(f"Avertissement : echec d'ecriture du journal {path} : {exc}", file=sys.stderr)
            self._handles.pop(path, None)

    def _open(self, path: Path) -> IO[str]:
        path.parent.mkdir(parents=True, exist_ok=True)
        is_new_file = not path.exists()
        handle = open(path, "a", encoding="utf-8", buffering=1)  # noqa: SIM115 - garde volontairement ouvert au-dela de cette fonction, voir docstring du module
        if is_new_file:
            path.chmod(_SHARED_LOG_FILE_MODE)
        return handle
