# Copyright (c) 2026 kraynux - kraynux@proton.me - Licence MIT (voir fichier LICENSE)
"""Contrat d'acces au systeme de fichiers.

Toute lecture/ecriture/verification de chemin passe par ce port -
domain/ et application/ ne connaissent jamais pathlib.Path ni les
appels systeme reels directement (charte §2.3)."""
from __future__ import annotations

from pathlib import Path
from typing import Protocol


class FilesystemPort(Protocol):
    def exists(self, path: Path) -> bool:
        ...

    def is_file(self, path: Path) -> bool:
        ...

    def is_dir(self, path: Path) -> bool:
        ...

    def read_text(self, path: Path) -> str:
        ...

    def read_bytes(self, path: Path) -> bytes:
        ...

    def write_bytes(self, path: Path, content: bytes) -> None:
        """Ecriture binaire brute (pas d'ecriture atomique - utilisee
        pour les fichiers uploades, dont le nom de stockage final est
        genere aleatoirement donc jamais en conflit avec un fichier deja
        servi, contrairement a la configuration active protegee par
        atomic_write_text)."""
        ...

    def file_size(self, path: Path) -> int:
        """Taille en octets, sans lire le contenu - necessaire pour
        repondre a une requete HEAD sans charger le fichier entier en
        memoire."""
        ...

    def file_mtime(self, path: Path) -> float:
        """Date de derniere modification (timestamp Unix), sans lire le
        contenu - necessaire pour invalider un cache en memoire par un
        simple `stat()` plutot qu'une relecture/re-analyse complete a
        chaque acces (retour utilisateur, audit performance : la
        blocklist WAF etait relue et re-parsee depuis le disque a
        CHAQUE requete)."""
        ...

    def write_text(self, path: Path, content: str) -> None:
        ...

    def atomic_write_text(self, path: Path, content: str) -> None:
        """Ecriture atomique (spec §5.3) : fichier temporaire, fsync,
        remplacement atomique (os.replace) - jamais un write_text()
        direct sur une configuration active, pour ne jamais laisser un
        fichier a moitie ecrit en cas d'interruption."""
        ...

    def copy_file(self, source: Path, destination: Path) -> None:
        """Copie un fichier existant vers `destination` (sauvegarde
        avant remplacement, spec §5.3 etape 7)."""
        ...

    def copy_directory(self, source: Path, destination: Path) -> None:
        """Copie recursive d'un repertoire existant vers `destination`
        (`destination` ne doit pas deja exister) - necessaire pour la
        creation d'instance multi-instance (copie de `src/` d'une
        instance vers une nouvelle, OMEGA-SERV_PLAN-DETAILLE_
        MULTI_INSTANCE.md §5 etape 3)."""
        ...

    def make_directory(self, path: Path, mode: int = 0o750) -> None:
        ...

    def delete_file(self, path: Path) -> None:
        """Supprime un fichier existant (spec §24.4 : suppression
        d'une definition de service au 'uninstall') - jamais utilise
        pour un repertoire."""
        ...

    def delete_directory(self, path: Path) -> None:
        """Suppression RECURSIVE et DEFINITIVE d'un repertoire existant
        (`shutil.rmtree`) - necessaire pour la desinstallation complete
        d'une instance multi-instance (OMEGA-SERV_PLAN-DETAILLE_
        MULTI_INSTANCE.md §8.5/§9 Phase E). Jamais appelee sans
        confirmation explicite forte cote appelant : irreversible,
        efface du code/de la config/des donnees reelles."""
        ...

    def file_mode(self, path: Path) -> int:
        """Permissions Unix du fichier (les 9 bits bas, ex. 0o600) -
        necessaire pour les portes de validation TLS bloquantes (cle
        privee lisible par groupe/autres, spec TLS §4.1/§21)."""
        ...

    def set_file_mode(self, path: Path, mode: int) -> None:
        ...

    def resolve_real_path(self, path: Path) -> Path:
        """Resout les liens symboliques et retourne le chemin absolu
        canonique (equivalent de Path.resolve()) - necessaire pour
        l'etape 6/7 de la resolution de chemin sure (spec §11.2)."""
        ...

    def list_json_files(self, directory: Path) -> list[Path]:
        """Liste les fichiers .json d'un dossier, tries par nom (dossier
        absent -> liste vide) - utilise pour enumerer les profils
        disponibles (config/profiles/)."""
        ...

    def list_directory_entries(self, directory: Path) -> list[str]:
        """Liste les noms d'entrees (fichiers et dossiers) d'un
        repertoire - utilise pour le directory listing (spec §16).
        Ne filtre rien (dotfiles compris) : le filtrage relatif aux
        regles d'acces est une responsabilite du domaine
        (access_policy.is_denied_path), pas de l'infrastructure."""
        ...
