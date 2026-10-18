"""Le compte du SERVICE peut-il lire un fichier ecrit par l'UTILISATEUR ?
(OMEGA-SERV_PLAN-DETAILLE_SENSITIVE_PATHS.md §3.7, regle R3/R4.)

Contexte verifie sur la machine reelle (2026-10-18) : le service tourne sous
`User=omega-serv`, lit `secure/` uniquement grace aux bits "autres" (644/755),
et la TUI ecrit sous le compte de l'utilisateur. Un fichier rendu illisible
au service (umask 077, groupe perdu...) fait echouer silencieusement le
rechargement suivant, puis le demarrage.

Fonctions pures : les `stat` reels et l'identite du compte sont collectes
par l'infrastructure (infrastructure/filesystem/local_file_access.py).
Precedence POSIX respectee : la classe "proprietaire" s'applique SEULE si
le compte est proprietaire, sinon la classe "groupe" SEULE s'il est membre
du groupe, sinon "autres" - un bit "autres" ne sert a rien a un membre du
groupe, d'ou l'importance de corriger le BON bit (`plan_read_access_fixes`)."""
from __future__ import annotations

import stat
from dataclasses import dataclass, field


@dataclass(frozen=True)
class PathNode:
    """Un element de la chaine `/` -> ... -> fichier, tel que vu par `stat`."""
    path: str
    mode: int
    uid: int
    gid: int
    is_dir: bool


@dataclass(frozen=True)
class AccountIdentity:
    name: str
    uid: int
    gids: frozenset[int]


@dataclass(frozen=True)
class ReadabilityVerdict:
    readable: bool
    blocking: tuple[PathNode, ...] = field(default_factory=tuple)

    def explain(self, account: str) -> str:
        if self.readable:
            return f"lisible par le compte {account}"
        node = self.blocking[0]
        what = "n'est pas traversable" if node.is_dir else "n'est pas lisible"
        return f"{node.path} {what} par le compte {account}"


@dataclass(frozen=True)
class AccessFix:
    path: str
    current_mode: int
    new_mode: int


def _permission_class_shift(node: PathNode, account: AccountIdentity) -> int:
    """Decalage des bits a lire : 6 = proprietaire, 3 = groupe, 0 = autres."""
    if account.uid == node.uid:
        return 6
    if node.gid in account.gids:
        return 3
    return 0


def _has_bit(node: PathNode, account: AccountIdentity, bit: int) -> bool:
    return bool((node.mode >> _permission_class_shift(node, account)) & bit)


_READ, _EXECUTE = 0o4, 0o1


def service_can_read(chain: tuple[PathNode, ...], account: AccountIdentity) -> ReadabilityVerdict:
    """`chain` = chaque dossier depuis `/` jusqu'au fichier inclus (dernier
    element). Chaque dossier doit etre traversable (x), le fichier lisible (r).
    root (uid 0) lit tout."""
    if account.uid == 0:
        return ReadabilityVerdict(readable=True)
    blocking: list[PathNode] = []
    for node in chain:
        needed = _EXECUTE if node.is_dir else _READ
        if not _has_bit(node, account, needed):
            blocking.append(node)
    return ReadabilityVerdict(readable=not blocking, blocking=tuple(blocking))


def plan_read_access_fixes(
    verdict: ReadabilityVerdict, account: AccountIdentity, current_uid: int,
) -> tuple[tuple[AccessFix, ...], tuple[PathNode, ...]]:
    """Corrections minimales que l'UTILISATEUR peut appliquer lui-meme (regle
    R4 : jamais de sudo, jamais un chmod sur un element qu'il ne possede
    pas, ex. /home/x en 750 sur Ubuntu). Ajoute le bit de la classe qui
    s'applique REELLEMENT au compte du service (groupe s'il en est membre,
    sinon autres). Renvoie (corrections possibles, elements non corrigeables)."""
    fixes: list[AccessFix] = []
    not_fixable: list[PathNode] = []
    for node in verdict.blocking:
        if node.uid != current_uid:
            not_fixable.append(node)
            continue
        bit = _EXECUTE if node.is_dir else _READ
        new_mode = node.mode | (bit << _permission_class_shift(node, account))
        fixes.append(AccessFix(path=node.path, current_mode=stat.S_IMODE(node.mode), new_mode=stat.S_IMODE(new_mode)))
    return tuple(fixes), tuple(not_fixable)
