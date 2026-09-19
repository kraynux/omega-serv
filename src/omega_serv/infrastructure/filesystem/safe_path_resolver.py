"""Resolution de chemin sure complete (spec §11.2, les 8 etapes).

Delegue les etapes 1-4 (decodage, normalisation, detection NUL/
traversal) a domain/security/path_policy.py (pure, testable sans
disque) ; effectue ici les etapes 5-7, qui exigent un acces filesystem
reel : construction depuis la racine autorisee, resolution des liens
symboliques, verification de confinement. Politique par defaut de la
spec respectee sans cas particulier : un lien symbolique qui sort du
webroot est rejete exactement comme une remontee '..' explicite,
puisque la verification de confinement porte sur le chemin REEL apres
resolution, pas sur le chemin demande.
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from omega_serv.domain.http.status_codes import HttpStatus
from omega_serv.domain.security.path_policy import PathRejectionReason, normalize_uri_path
from omega_serv.ports.filesystem_port import FilesystemPort


@dataclass(frozen=True)
class ResolvedPath:
    ok: bool
    absolute_path: Path | None = None
    segments: tuple[str, ...] = ()
    rejection_reason: PathRejectionReason | None = None
    suggested_status: HttpStatus | None = None


class SafePathResolver:
    """Resout un chemin d'URI brut en chemin filesystem absolu,
    garanti sous `webroot` ou rejete explicitement - jamais un simple
    test `'../' in url` (spec §11.2, insuffisant par nature)."""

    def __init__(self, filesystem: FilesystemPort, webroot: Path):
        self._fs = filesystem
        self._webroot = filesystem.resolve_real_path(webroot)

    @property
    def webroot(self) -> Path:
        return self._webroot

    def resolve(self, raw_uri_path: str) -> ResolvedPath:
        return self.resolve_against_root(raw_uri_path, self._webroot)

    def resolve_against_root(self, raw_uri_path: str, root: Path) -> ResolvedPath:
        """Meme algorithme que resolve(), mais confine a `root` plutot
        qu'au webroot - utilise pour les cibles d'alias (spec §17.1),
        qui peuvent legitimement pointer hors webroot avec autorisation
        explicite. `root` est toujours resolu (liens symboliques compris)
        avant la verification de confinement, jamais suppose deja
        canonique."""
        decision = normalize_uri_path(raw_uri_path)
        if not decision.ok:
            return ResolvedPath(
                ok=False,
                rejection_reason=decision.rejection_reason,
                suggested_status=decision.suggested_status,
            )

        real_root = self._fs.resolve_real_path(root)
        candidate = real_root.joinpath(*decision.segments) if decision.segments else real_root
        real = self._fs.resolve_real_path(candidate)

        try:
            real.relative_to(real_root)
        except ValueError:
            return ResolvedPath(
                ok=False,
                rejection_reason=PathRejectionReason.TRAVERSAL_ATTEMPT,
                suggested_status=HttpStatus.FORBIDDEN,
            )

        return ResolvedPath(ok=True, absolute_path=real, segments=decision.segments)
