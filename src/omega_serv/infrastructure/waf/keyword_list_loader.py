"""Chargement des listes de mots-clefs WAF depuis le disque (meme
repartition que rule_pack_loader.py : ce module ne fait que l'I/O,
toute la logique de construction/validation est deleguee a
domain/security/waf/keyword_list.py, la compilation finale a
signature_engine.compile_rule_pack - aucune seconde logique de
compilation a maintenir)."""
from __future__ import annotations

from pathlib import Path

from omega_serv.core.i18n import _
from omega_serv.domain.security.waf.entities import KeywordListDefinition
from omega_serv.domain.security.waf.exceptions import WafRuleLoadError
from omega_serv.domain.security.waf.keyword_list import (
    analyze_path_list_text,
    build_rule_pack_from_keyword_list,
    tokens_from_text,
)
from omega_serv.domain.security.waf.signature_engine import CompiledRulePack, compile_rule_pack
from omega_serv.ports.filesystem_port import FilesystemPort


def load_keyword_list(filesystem: FilesystemPort, definition: KeywordListDefinition, path: Path) -> CompiledRulePack:
    if not filesystem.exists(path):
        raise WafRuleLoadError(_("Fichier de liste de mots-clefs introuvable : {path}").format(path=path))
    try:
        raw = filesystem.read_text(path)
    except OSError as e:
        raise WafRuleLoadError(_("Impossible de lire {path} : {e}").format(path=path, e=e)) from e
    if definition.match == "path":
        # Meme severite bloquante qu'un pack JSON invalide : une liste de
        # chemins en erreur (syntaxe, chemin vital touche) n'est JAMAIS
        # chargee a moitie - refus net, avec les numeros de ligne
        # (OMEGA-SERV_PLAN-DETAILLE_SENSITIVE_PATHS.md §3.1). Les
        # avertissements (doublons, taille) ne bloquent pas.
        errors = analyze_path_list_text(raw, definition.anchor).errors
        if errors:
            details = " ; ".join(f"ligne {e.line} : {e.message}" for e in errors[:5])
            more = _(" (+{value} autre(s))").format(value=len(errors) - 5) if len(errors) > 5 else ""
            raise WafRuleLoadError(_("Liste de chemins invalide {path} : {details}{more}").format(path=path, details=details, more=more))
    tokens = tokens_from_text(raw)
    pack = build_rule_pack_from_keyword_list(definition, tokens)
    return compile_rule_pack(pack)


def load_keyword_lists(
    filesystem: FilesystemPort, project_root: Path, definitions: tuple[KeywordListDefinition, ...],
) -> tuple[CompiledRulePack, ...]:
    return tuple(
        load_keyword_list(filesystem, definition, project_root / definition.file)
        for definition in definitions
    )
