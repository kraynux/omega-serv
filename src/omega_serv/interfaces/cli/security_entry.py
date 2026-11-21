"""Processus de securite du moteur natif lance comme un interpreteur neuf - repli si le superviseur reduit ne prend
pas le relais ; sinon il le fait naitre par fork (`serve_accepted_config`, etude §11) (lot 5 memoire, suite ; 2026-11-19,
OMEGA-SERV_ETUDE_PROXY_ET_MEMOIRE.md §8-§9), quand le superviseur se reduit : un fork du superviseur complet garderait
tout ce que celui-ci a charge.

Recoit la configuration ACCEPTEE (memfd, JSON de `OmegaServConfig.to_dict`, jamais le fichier relu entre-temps) et un
canal INSPECT/VERDICT par fil natif ; fait ensuite exactement ce que fait le fils d'un fork (`serve_security`) :
serveur Python construit sans port, rechargement sur SIGHUP depuis le fichier de configuration, arret sur SIGTERM."""
from __future__ import annotations

import os
import sys
from pathlib import Path


def main(argv: list[str] | None = None) -> int:
    import signal
    # Rechargement ou arret pendant le demarrage : traites une fois le serveur construit (security_worker).
    signal.pthread_sigmask(signal.SIG_BLOCK, (signal.SIGHUP, signal.SIGTERM, signal.SIGINT))
    args = sys.argv[1:] if argv is None else argv

    def value(name: str) -> str:
        return args[args.index(name) + 1]

    from omega_serv.infrastructure.process.lazy_ssl import defer_ssl_import
    defer_ssl_import()  # comme `serve` (__main__.py) : `ssl` seulement si une option en a besoin
    data_fds = [int(args[i + 1]) for i, arg in enumerate(args) if arg == "--data-fd"]
    config_fd = int(value("--config-fd"))
    text = os.pread(config_fd, int(value("--config-size")), 0)
    os.close(config_fd)
    try:
        sys.stdout.reconfigure(line_buffering=True)  # type: ignore[union-attr]  # journalctl, comme `serve`
    except (AttributeError, ValueError):
        pass
    return serve_accepted_config(value("--project-root"), value("--config-path"), text, data_fds)


def serve_accepted_config(project_root: str, config_path: str, config_json: bytes, data_fds: list[int]) -> int:
    """Corps commun : interpreteur neuf (main) ou fils du superviseur reduit (native_watch, fork apres gc.freeze)."""
    import json

    from omega_serv.bootstrap.container import DependencyContainer
    from omega_serv.domain.config.entities import OmegaServConfig
    from omega_serv.interfaces.cli.serve_native import serve_security
    config = OmegaServConfig.from_dict(json.loads(config_json))
    container = DependencyContainer(Path(project_root))
    return serve_security(container, Path(config_path), config, data_fds, None, True)


if __name__ == "__main__":
    sys.exit(main())
