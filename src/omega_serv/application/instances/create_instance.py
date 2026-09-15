# Copyright (c) 2026 kraynux - kraynux@proton.me - Licence MIT (voir fichier LICENSE)
"""Cas d'usage : creer une nouvelle instance OMEGA-SERV secondaire
depuis l'interface (OMEGA-SERV_PLAN-DETAILLE_MULTI_INSTANCE.md §5,
Architecture A - repertoires separes complets, §2.1). Decoupe en 6
etapes NOMMEES et EXECUTEES SEPAREMENT (retour utilisateur : jamais un
seul appel opaque a install.sh, jamais un simple spinner generique)
plutot qu'un unique sous-processus opaque - chaque etape appelle
`on_step` avant de s'executer, pour qu'un ecran de progression reel
puisse se mettre a jour entre chacune.

Ce module importe directement infrastructure/ (JsonConfigRepository,
JsonSettingsStore) - sans probleme pour le contrat import-linter
puisque `application/` en est exclue (comme start_server.py deja), a
CONDITION que `interfaces.tui/` n'importe JAMAIS ce module directement :
il est expose via `DependencyContainer.create_instance_runner`, injecte
depuis `omega_serv/__main__.py` (meme regime que `audit_runner`/
`config_check_runner`), jamais importe par bootstrap/ ni interfaces.tui/.

Fonction volontairement SYNCHRONE (meme regime que ProcessRunnerPort,
deja synchrone partout ailleurs dans ce projet - venv/pip sont des
appels bloquants reels) : l'appelant TUI est responsable de
l'executer dans un thread de travail Textual (`run_worker(thread=True)`)
et de relayer `on_step` vers l'UI via `App.call_from_thread` - jamais
appelee directement depuis la boucle asyncio principale, qui gelerait
sinon l'interface entiere pendant l'operation (jusqu'a ~1 minute)."""
from __future__ import annotations

import importlib.metadata
import json
import sys
from collections.abc import Callable
from dataclasses import replace
from pathlib import Path
from urllib.parse import urlparse
from urllib.request import url2pathname

from omega_serv.application.instances.register_instance import register_instance
from omega_serv.domain.config.defaults import builtin_safe_defaults
from omega_serv.domain.instances.registry import validate_new_instance
from omega_serv.infrastructure.config.json_config_repository import JsonConfigRepository
from omega_serv.infrastructure.config.json_settings_store import JsonSettingsStore
from omega_serv.ports.clock_port import ClockPort
from omega_serv.ports.filesystem_port import FilesystemPort
from omega_serv.ports.instance_registry_port import InstanceRegistryPort
from omega_serv.ports.process_runner_port import ProcessRunnerPort

TOTAL_STEPS = 6

# Copie tel quel (jamais .venv/, jamais var/ ni secure/ - donnees/secrets
# propres a CHAQUE instance, §5 etape 3 : "jamais copier la config
# existante telle quelle").
_FILES_TO_COPY = ("pyproject.toml", "omega-serv.sh", "install.sh", "LICENSE")
_DIRECTORIES_TO_COPY = ("src", "config/profiles", "vendor")
_EMPTY_DIRECTORIES = ("webroot", "secure", "var")


def _resolve_omega_lib_editable_source() -> Path | None:
    """Retrouve le chemin source reel d'omega-lib installee en editable
    dans le venv COURANT (celui de l'instance source qui execute ce
    code, jamais la cible) via le `direct_url.json` (PEP 610) que pip
    ecrit pour tout `pip install -e <chemin>`.

    Bug reel corrige ici : `vendor/omega-lib/` n'etait JAMAIS copie vers
    la nouvelle instance (absent de `_DIRECTORIES_TO_COPY`), et en clone
    de developpement il n'existe meme pas du tout - omega-lib vient
    alors du monorepo local `~/DEV/LIB/omega-lib`, installee a part
    (voir install.sh). Dans les deux cas, l'ancien code retombait
    silencieusement sur `pip install -e .` seul, qui tente de resoudre
    `omega-lib>=0.1.0` sur PyPI (jamais publiee la) et echoue toujours
    a l'etape 4/6. Lire `direct_url.json` fonctionne pour les deux
    scenarios sans avoir a deviner un chemin fixe : il pointe vers
    `vendor/omega-lib` dans l'archive distribuable, ou vers le monorepo
    local en developpement."""
    try:
        distribution = importlib.metadata.distribution("omega-lib")
    except importlib.metadata.PackageNotFoundError:
        return None
    direct_url_text = distribution.read_text("direct_url.json")
    if direct_url_text is None:
        return None
    direct_url = json.loads(direct_url_text)
    if not direct_url.get("dir_info", {}).get("editable"):
        return None
    parsed = urlparse(direct_url["url"])
    if parsed.scheme != "file":
        return None
    return Path(url2pathname(parsed.path))


def _report(on_step: Callable[[int, int, str], None] | None, index: int, label: str) -> None:
    if on_step is not None:
        on_step(index, TOTAL_STEPS, label)


def _copy_tree(filesystem: FilesystemPort, source_root: Path, target_root: Path) -> None:
    for relative in _FILES_TO_COPY:
        source = source_root / relative
        if filesystem.exists(source):
            filesystem.copy_file(source, target_root / relative)
    for relative in _DIRECTORIES_TO_COPY:
        source = source_root / relative
        if filesystem.exists(source):
            filesystem.copy_directory(source, target_root / relative)
    for relative in _EMPTY_DIRECTORIES:
        filesystem.make_directory(target_root / relative)


def _write_fresh_config(filesystem: FilesystemPort, target_root: Path, bind: str, port: int) -> None:
    configuration = JsonConfigRepository(filesystem, backups_dir=target_root / "var" / "backups")
    defaults = builtin_safe_defaults()
    config = replace(defaults, server=replace(defaults.server, bind=bind, port=port))
    configuration.save(target_root / "config" / "omega-serve.json", config)


def _attempt_create(
    filesystem: FilesystemPort,
    process_runner: ProcessRunnerPort,
    registry: InstanceRegistryPort,
    clock: ClockPort,
    *,
    source_root: Path,
    name: str,
    target_root: Path,
    bind: str,
    port: int,
    service_name: str,
    on_step: Callable[[int, int, str], None] | None,
) -> str | None:
    _report(on_step, 3, "Creation de l'environnement virtuel")
    venv_result = process_runner.run([sys.executable, "-m", "venv", str(target_root / ".venv")], timeout=120)
    if not venv_result.ok:
        return f"Echec de la creation du venv : {venv_result.stderr.strip() or venv_result.stdout.strip()}"

    _report(on_step, 4, "Installation des dependances")
    pip = str(target_root / ".venv" / "bin" / "pip")
    upgrade_result = process_runner.run([pip, "install", "-q", "--upgrade", "pip"], timeout=120)
    if not upgrade_result.ok:
        return f"Echec de la mise a jour de pip : {upgrade_result.stderr.strip()}"
    vendored_lib = target_root / "vendor" / "omega-lib"
    lib_source = vendored_lib if filesystem.exists(vendored_lib) else _resolve_omega_lib_editable_source()
    if lib_source is not None and filesystem.exists(lib_source):
        lib_result = process_runner.run([pip, "install", "-q", "-e", str(lib_source)], timeout=120)
        if not lib_result.ok:
            return f"Echec de l'installation de omega-lib ({lib_source}) : {lib_result.stderr.strip()}"
    install_result = process_runner.run([pip, "install", "-q", "-e", str(target_root)], timeout=180)
    if not install_result.ok:
        return f"Echec de l'installation des dependances : {install_result.stderr.strip()}"

    _report(on_step, 5, "Generation de la configuration")
    try:
        _write_fresh_config(filesystem, target_root, bind, port)
        JsonSettingsStore(target_root / "var" / "settings.json").set("service_name", service_name)
    except OSError as e:
        return f"Echec de la generation de la configuration : {e}"

    _report(on_step, 6, "Enregistrement dans le registre")
    return register_instance(
        registry, filesystem, clock, name=name, path=target_root, bind=bind, port=port, service_name=service_name,
    )


def create_instance(
    filesystem: FilesystemPort,
    process_runner: ProcessRunnerPort,
    registry: InstanceRegistryPort,
    clock: ClockPort,
    *,
    source_root: Path,
    name: str,
    target_parent_dir: Path,
    bind: str,
    port: int,
    service_name: str,
    on_step: Callable[[int, int, str], None] | None = None,
) -> str | None:
    """Retourne un message d'erreur (arrete a la premiere etape en
    echec, aucune ecriture de registre dans ce cas) ou None si les 6
    etapes ont reussi.

    Retour utilisateur (bug reel) : un echec a n'importe quelle etape
    2-6 laissait `target_root` a moitie cree sur le disque (arborescence
    copiee, parfois venv/dependances partiels) SANS jamais l'enregistrer
    dans le registre (etape 6, la derniere) - le nom semblait alors
    "reserve" (l'etape 1 le refuse ensuite via `filesystem.exists`) tout
    en etant invisible dans l'ecran Instances (qui ne liste que le
    registre). Desormais : toute etape 2-6 qui echoue supprime
    integralement `target_root` avant de retourner l'erreur, pour que
    le nom redevienne immediatement reutilisable."""
    target_root = target_parent_dir / name

    _report(on_step, 1, "Validation des parametres")
    if filesystem.exists(target_root):
        return f"{target_root} existe deja - choisissez un autre nom ou repertoire"
    resolved_parent = filesystem.resolve_real_path(target_parent_dir)
    error = validate_new_instance(
        registry.load(), name=name, path=resolved_parent / name, bind=bind, port=port,
    )
    if error is not None:
        return error

    _report(on_step, 2, "Copie de l'arborescence")
    try:
        _copy_tree(filesystem, source_root, target_root)
    except OSError as e:
        if filesystem.exists(target_root):
            filesystem.delete_directory(target_root)
        return f"Echec de la copie de l'arborescence : {e}"

    error = _attempt_create(
        filesystem, process_runner, registry, clock,
        source_root=source_root, name=name, target_root=target_root,
        bind=bind, port=port, service_name=service_name, on_step=on_step,
    )
    if error is not None:
        filesystem.delete_directory(target_root)
    return error
