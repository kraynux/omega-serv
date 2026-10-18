"""Cas d'usage "Charger une liste dans le WAF" (assistant WAF Custom,
OMEGA-SERV_PLAN-DETAILLE_SENSITIVE_PATHS.md lot 6.3) - action EXPLICITE et
distincte (decision A5 : aucun chargement par defaut).

Ordre des verifications, la configuration n'etant JAMAIS modifiee tant
qu'une seule echoue :
1. nom de fichier sur (`[a-z0-9-]+.txt`, directement dans keywords/) ;
2. fichier local absent -> cree par copie de la reference (premier
   chargement, §3.11) ou depuis le modele vide (nouveau fichier), via
   `save_list_file` (droits, liens symboliques - lot 3) ;
3. liste de chemins : aucune erreur de validation ;
4. lisible par le compte du service (R3) ;
5. pas deja chargee ;
6. definition structurellement valide ;
7. validation d'environnement de la NOUVELLE configuration (conflits de
   routes, etc. - §3.10-2) : aucune erreur concernant cette liste.
Puis : reputation + auto-ban actives s'ils etaient eteints (A15), avec un
message pour chacun. L'appelant enregistre la configuration renvoyee et
declenche le rechargement."""
from __future__ import annotations

import re
from collections.abc import Callable
from dataclasses import dataclass, field, replace
from pathlib import Path
from typing import Any

from omega_serv.application.security.editable_list_file import (
    KEYWORDS_DIR,
    inspect_list_file,
    save_list_file,
)
from omega_serv.domain.config.entities import OmegaServConfig
from omega_serv.domain.config.option import Option
from omega_serv.domain.security.waf.config import with_reputation_enabled_for_lists
from omega_serv.domain.security.waf.keyword_list import (
    NEW_KEYWORD_LIST_TEMPLATE,
    NEW_PATH_LIST_TEMPLATE,
    analyze_path_list_text,
    parse_keyword_list_definition,
    validate_keyword_list_definition,
)
from omega_serv.ports.file_access_port import FileAccessPort
from omega_serv.ports.filesystem_port import FilesystemPort
from omega_serv.ports.keyword_reference_port import KeywordReferencePort

_SAFE_FILE_NAME = re.compile(r"[a-z0-9][a-z0-9-]*\.txt")

ConfigCheck = Callable[[OmegaServConfig, FilesystemPort, Path, bool, bool], list[str]]


@dataclass(frozen=True)
class ListLoadRequest:
    file_name: str
    match: str = "path"
    scope: tuple[str, ...] = ("path",)
    anchor: str = "any_segment"
    weight: int = 3
    observe_only: bool = False
    escalation_threshold: int = 0
    escalation_window_seconds: int = 600
    auto_block_duration_seconds: int | None = None
    label: str = ""
    reference_name: str | None = None  # reference a copier si le fichier local n'existe pas encore


@dataclass(frozen=True)
class ListLoadResult:
    loaded: bool
    list_id: str | None = None
    error: str | None = None
    messages: tuple[str, ...] = field(default_factory=tuple)
    config: OmegaServConfig | None = None


def sanitize_list_file_name(raw: str) -> str | None:
    """'Mes Chemins!' -> 'mes-chemins.txt' ; None si rien d'utilisable."""
    stem = raw.strip().lower().removesuffix(".txt")
    stem = re.sub(r"[^a-z0-9]+", "-", stem).strip("-")
    return f"{stem}.txt" if stem else None


def _keyword_lists(config: OmegaServConfig) -> list[dict[str, Any]]:
    option = config.options.get("waf")
    settings = option.settings if option is not None else {}
    return [dict(item) for item in settings.get("rules", {}).get("keyword_lists", [])]


def _unique_id(stem: str, existing: set[str]) -> str:
    candidate, index = stem, 2
    while candidate in existing:
        candidate, index = f"{stem}-{index}", index + 1
    return candidate


def with_keyword_lists(config: OmegaServConfig, lists: list[dict[str, Any]]) -> OmegaServConfig:
    """Remplace UNIQUEMENT `rules.keyword_lists` (meme discipline que
    _waf_rule_paths.with_waf_rule_paths apres sa correction du 2026-10-18)."""
    existing = config.options.get("waf")
    settings = dict(existing.settings) if existing is not None else {}
    settings["rules"] = {**settings.get("rules", {}), "keyword_lists": lists}
    options = dict(config.options)
    options["waf"] = Option(name="waf", enabled=existing.enabled if existing else False, settings=settings)
    return replace(config, options=options)


def load_keyword_list_into_config(
    config: OmegaServConfig,
    request: ListLoadRequest,
    *,
    file_access: FileAccessPort,
    filesystem: FilesystemPort,
    references: KeywordReferencePort,
    project_root: Path,
    service_account: str | None,
    config_check: ConfigCheck | None,
) -> ListLoadResult:
    if not _SAFE_FILE_NAME.fullmatch(request.file_name):
        return ListLoadResult(False, error=f"nom de fichier refuse : {request.file_name!r} (lettres, chiffres, '-', .txt)")
    relative = f"{KEYWORDS_DIR}/{request.file_name}"
    path = project_root / relative
    messages: list[str] = []

    if file_access.fingerprint(path) is None:
        reference_text = references.read(request.reference_name) if request.reference_name else None
        template = NEW_PATH_LIST_TEMPLATE if request.match == "path" else NEW_KEYWORD_LIST_TEMPLATE
        created = save_list_file(
            file_access, project_root, relative, reference_text or template, service_account, None,
        )
        if not created.saved:
            return ListLoadResult(False, error=f"creation du fichier impossible : {created.refused_reason}")
        messages.append(
            f"Copie locale creee depuis la reference : {relative}" if reference_text else f"Fichier cree : {relative}"
        )
        status = created.status
    else:
        status = inspect_list_file(file_access, project_root, relative, service_account)
        if status.location_error is not None:
            return ListLoadResult(False, error=status.location_error)

    if request.match == "path":
        errors = analyze_path_list_text(filesystem.read_text(path), request.anchor).errors
        if errors:
            first = errors[0]
            return ListLoadResult(
                False, error=f"la liste contient {len(errors)} erreur(s), ligne {first.line} : {first.message} "
                "- corrigez-la dans l'editeur",
            )
    if status.service_check == "unreadable":
        return ListLoadResult(
            False, error=f"{status.service_message()} - utilisez 'Corriger les droits' dans l'editeur",
        )

    lists = _keyword_lists(config)
    if any(item.get("file") == relative for item in lists):
        return ListLoadResult(False, error=f"{relative} est deja chargee (modifiez-la depuis l'ecran Custom)")
    list_id = _unique_id(request.file_name.removesuffix(".txt"), {str(item.get("id")) for item in lists})
    entry: dict[str, Any] = {
        "id": list_id, "label": request.label or list_id, "file": relative, "scope": list(request.scope),
        "match": request.match, "weight": request.weight, "enabled": True,
        "observe_only": request.observe_only,
        "escalation_threshold": 0 if request.observe_only else request.escalation_threshold,
        "escalation_window_seconds": request.escalation_window_seconds,
    }
    if request.match == "path":
        entry["anchor"] = request.anchor
    if request.auto_block_duration_seconds is not None:
        entry["auto_block_duration_seconds"] = request.auto_block_duration_seconds
    definition_errors = validate_keyword_list_definition(parse_keyword_list_definition(entry))
    if definition_errors:
        return ListLoadResult(False, error=definition_errors[0])

    new_config = with_keyword_lists(config, [*lists, entry])
    waf_option = new_config.options["waf"]
    settings, reputation_changes = with_reputation_enabled_for_lists(dict(waf_option.settings))
    options = dict(new_config.options)
    options["waf"] = Option(name="waf", enabled=waf_option.enabled, settings=settings)
    new_config = replace(new_config, options=options)

    if config_check is not None:
        relevant = [e for e in config_check(new_config, filesystem, project_root, False, False)
                    if f"keyword_lists[{list_id!r}]" in e]
        if relevant:
            return ListLoadResult(False, error=relevant[0])

    messages.extend(f"Active : {change}" for change in reputation_changes)
    if not waf_option.enabled:
        messages.append("WAF desactive : la liste s'appliquera des que le WAF sera active (WAF -> Modules).")
    if request.observe_only:
        messages.append("Mode Observation : alertes journalisees, aucun blocage ni ban tant que la gravite n'est pas changee.")
    return ListLoadResult(True, list_id=list_id, messages=tuple(messages), config=new_config)


def update_keyword_list_entry(
    config: OmegaServConfig,
    list_id: str,
    changes: dict[str, Any],
    *,
    filesystem: FilesystemPort,
    project_root: Path,
    config_check: ConfigCheck | None,
) -> ListLoadResult:
    """Ecran Custom (lot 7) : "Modifier" (gravite, recidive, ancrage, nom) et
    "Activer/Desactiver" d'une liste DEJA chargee. Memes garde-fous qu'au
    chargement : definition valide, aucune erreur d'environnement sur cette
    liste (ex. passer d'Observation a Eleve sur une liste qui toucherait une
    route du site est refuse). Rendre une liste bloquante reactive la
    reputation et l'auto-ban s'ils avaient ete eteints entre-temps (A15)."""
    lists = _keyword_lists(config)
    index = next((i for i, item in enumerate(lists) if item.get("id") == list_id), None)
    if index is None:
        return ListLoadResult(False, error=f"liste {list_id!r} introuvable dans la configuration")
    entry = {**lists[index], **changes}
    if entry.get("observe_only"):
        entry["escalation_threshold"] = 0
    definition = parse_keyword_list_definition(entry)
    definition_errors = validate_keyword_list_definition(definition)
    if definition_errors:
        return ListLoadResult(False, error=definition_errors[0])
    lists[index] = entry
    new_config = with_keyword_lists(config, lists)

    reputation_changes: tuple[str, ...] = ()
    if definition.enabled and not definition.observe_only:
        waf_option = new_config.options["waf"]
        settings, reputation_changes = with_reputation_enabled_for_lists(dict(waf_option.settings))
        options = dict(new_config.options)
        options["waf"] = Option(name="waf", enabled=waf_option.enabled, settings=settings)
        new_config = replace(new_config, options=options)

    if config_check is not None:
        relevant = [e for e in config_check(new_config, filesystem, project_root, False, False)
                    if f"keyword_lists[{list_id!r}]" in e]
        if relevant:
            return ListLoadResult(False, error=relevant[0])
    messages = tuple(f"Active : {change}" for change in reputation_changes)
    return ListLoadResult(True, list_id=list_id, messages=messages, config=new_config)


def remove_keyword_list_entry(config: OmegaServConfig, list_id: str) -> OmegaServConfig:
    """"Retirer" (lot 7) : la liste n'est plus chargee, son FICHIER est
    conserve (toujours disponible dans l'assistant) - jamais de suppression
    de fichier depuis la TUI."""
    return with_keyword_lists(config, [item for item in _keyword_lists(config) if item.get("id") != list_id])
