"""Listes de mots-clefs WAF (OMEGA-SERV_PLAN-DETAILLE_REFERER_ET_MAGNET_
WAF.md, lot B) : format texte "un mot-clef par ligne", pense pour une
liste qui s'allonge dans le temps (ex. mots-clefs de spam Referer) sans
avoir a reecrire un `RuleDefinition` JSON complet a chaque ajout.

Fonctions pures uniquement - aucune I/O ici (ca, c'est infrastructure/
waf/keyword_list_loader.py). Chaque mot-clef est echappe (`re.escape`)
avant d'etre joint en alternance : l'utilisateur ecrit des mots/sous-
chaines simples, jamais une regex brute a ecrire a la main - ce qui
elimine par construction tout risque de regex catastrophiquement
retro-active (ReDoS) ou de syntaxe cassee via un simple mot-clef."""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any, Literal

from omega_serv.domain.config.validation import is_safe_relative_path
from omega_serv.domain.security.waf.entities import (
    _VALID_SCOPES,
    KeywordListDefinition,
    RuleDefinition,
    RulePack,
)
from omega_serv.domain.security.waf.rule_validation import build_path_segment_pattern

_VALID_MATCH_MODES: frozenset[str] = frozenset({"substring", "path"})
_VALID_ANCHORS: frozenset[str] = frozenset({"any_segment", "root"})

# Chemins qu'AUCUNE liste en mode "path" ne doit jamais pouvoir matcher
# (OMEGA-SERV_PLAN-DETAILLE_SENSITIVE_PATHS.md §3.10-1) : une entree qui
# en matche un est une ERREUR (liste refusee au chargement), jamais un
# simple avertissement - c'est le garde-fou contre un blocage du site
# entier (/), de l'indexation (robots.txt, sitemap.xml) ou du
# renouvellement TLS (acme-challenge, certbot --webroot : §3.2).
VITAL_PATHS: tuple[str, ...] = (
    "/",
    "/index.html",
    "/robots.txt",
    "/favicon.ico",
    "/sitemap.xml",
    "/.well-known/acme-challenge/AbC_dEf-123",
    "/.well-known/security.txt",
    "/.well-known/change-password",
)

# Limite indicative (OMEGA-SERV_PLAN-DETAILLE_REFERER_ET_MAGNET_WAF.md, D5) :
# au-dela, simple avertissement recommandant de scinder la liste.
RECOMMENDED_MAX_ENTRIES = 500

_SUFFIX_TOKEN = re.compile(r"/\*\.[A-Za-z0-9][A-Za-z0-9._-]*")
_EXCEPTION_PREFIX = "!"

# Aide de syntaxe affichee en tete de chaque liste de chemins (references
# livrees, nouveau fichier cree par l'assistant) - source unique.
PATH_LIST_SYNTAX_HELP = """# Syntaxe (une entree par ligne, '#' = commentaire) :
#   /admin    -> /admin et /admin/xxx, jamais /administrator
#   /.git/    -> tout ce qui est sous /.git/
#   /*.bak    -> tout fichier dont le nom finit par .bak
#   !/api/v1  -> exception : ce chemin n'est jamais compte par cette liste
#               (prioritaire sur les entrees, quel que soit l'ordre des lignes)"""

NEW_PATH_LIST_TEMPLATE = "# Liste de chemins personnelle (omega-serv)\n#\n" + PATH_LIST_SYNTAX_HELP + "\n"
NEW_KEYWORD_LIST_TEMPLATE = (
    "# Liste de mots-clefs personnelle (omega-serv)\n"
    "# Un mot-clef par ligne, recherche n'importe ou dans la partie choisie de la requete\n"
    "# (casse ignoree). '#' = commentaire. Ecrivez le texte tel quel, jamais une regex.\n"
)


def is_suffix_entry(token: str) -> bool:
    """Entree de forme `/*.ext` (joker d'extension)."""
    return _SUFFIX_TOKEN.fullmatch(token) is not None


def tokens_from_text(text: str) -> tuple[str, ...]:
    """Une ligne = un mot-clef. Lignes vides et lignes commencant par
    '#' (apres espaces de tete) ignorees - jamais de syntaxe plus
    riche que ca (pas de guillemets, pas d'echappement a la charge de
    l'utilisateur, voir note de securite en tete de module)."""
    tokens: list[str] = []
    for raw_line in text.splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        tokens.append(line)
    return tuple(tokens)


def compile_keyword_pattern(tokens: tuple[str, ...]) -> str:
    """Construit une alternance regex a partir de mots-clefs en clair,
    chacun echappe individuellement (`re.escape`) - jamais une regex
    utilisateur assemblee telle quelle."""
    return "(" + "|".join(re.escape(token) for token in tokens) + ")"


def compile_path_token(token: str, anchor: str) -> str:
    """Motif d'UNE entree d'une liste en mode "path" (plan §3.1) :
    - `/*.ext` : suffixe `\\.ext$` (un suffixe n'a pas d'ancrage) ;
    - toute autre forme (`/x`, `/x/`, `/a/b`) : EXACTEMENT la regle
      "chemin precis" de l'assistant WAF Custom (build_path_segment_pattern,
      `/x(/|$)` - `/admin` ne matche jamais `/administrator`), precedee
      de `^` si `anchor == "root"`.
    La partie saisie par l'utilisateur est TOUJOURS echappee (re.escape,
    via build_path_segment_pattern) : jamais de regex utilisateur brute."""
    if _SUFFIX_TOKEN.fullmatch(token):
        return re.escape(token[2:]) + "$"
    segment_pattern = build_path_segment_pattern(token)
    return ("^" if anchor == "root" else "") + segment_pattern


def compile_path_list_pattern(tokens: tuple[str, ...], anchor: str) -> str:
    """Alternance de toutes les entrees (compilee une seule fois, comme
    `compile_keyword_pattern`). Liste vide = motif qui ne matche jamais."""
    if not tokens:
        return r"(?!)"
    return "(?:" + "|".join(compile_path_token(t, anchor) for t in tokens) + ")"


@dataclass(frozen=True)
class KeywordListDiagnostic:
    """Un probleme localise sur une ligne d'un fichier de liste (numero
    de ligne 1-based du fichier REEL, commentaires compris - c'est celui
    que l'utilisateur voit dans son editeur)."""
    line: int
    severity: Literal["error", "warning"]
    message: str


@dataclass(frozen=True)
class PathListAnalysis:
    entries: tuple[str, ...]
    exceptions: tuple[str, ...]
    diagnostics: tuple[KeywordListDiagnostic, ...] = field(default_factory=tuple)

    @property
    def errors(self) -> tuple[KeywordListDiagnostic, ...]:
        return tuple(d for d in self.diagnostics if d.severity == "error")

    @property
    def warnings(self) -> tuple[KeywordListDiagnostic, ...]:
        return tuple(d for d in self.diagnostics if d.severity == "warning")


def _token_syntax_error(token: str) -> str | None:
    if not token.startswith("/"):
        return "doit commencer par '/' (ou '!/' pour une exception)"
    if any(ch.isspace() for ch in token):
        return "ne doit pas contenir d'espace"
    if "*" in token and not _SUFFIX_TOKEN.fullmatch(token):
        return "le joker '*' n'est accepte que sous la forme '/*.extension' (ex: /*.bak)"
    if not build_path_segment_pattern(token) and not _SUFFIX_TOKEN.fullmatch(token):
        return "entree vide : '/' seul matcherait tous les chemins"
    return None


def analyze_path_list_text(text: str, anchor: str) -> PathListAnalysis:
    """Validateur UNIQUE d'un fichier de liste en mode "path" (plan §3.1) -
    utilise par le chargeur (refus au demarrage/SIGHUP/config check en
    cas d'erreur) ET, plus tard, par l'editeur integre de la TUI
    (diagnostics en direct) : une seule logique de validation.

    Erreurs : syntaxe (voir `_token_syntax_error`), entree qui matche un
    chemin vital (VITAL_PATHS). Avertissements : doublon (insensible a la
    casse, comme le matching reel), liste au-dela de RECOMMENDED_MAX_ENTRIES."""
    entries: list[str] = []
    exceptions: list[str] = []
    diagnostics: list[KeywordListDiagnostic] = []
    first_seen: dict[str, int] = {}

    for line_number, raw_line in enumerate(text.splitlines(), start=1):
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        is_exception = line.startswith(_EXCEPTION_PREFIX)
        token = line[len(_EXCEPTION_PREFIX):] if is_exception else line

        syntax_error = _token_syntax_error(token)
        if syntax_error is not None:
            diagnostics.append(KeywordListDiagnostic(line_number, "error", f"'{line}' : {syntax_error}"))
            continue

        key = line.lower()
        if key in first_seen:
            diagnostics.append(KeywordListDiagnostic(
                line_number, "warning", f"'{line}' : doublon de la ligne {first_seen[key]}",
            ))
            continue
        first_seen[key] = line_number

        if is_exception:
            exceptions.append(token)
            continue

        compiled = re.compile(compile_path_token(token, anchor), re.IGNORECASE)
        blocked_vital = [vital for vital in VITAL_PATHS if compiled.search(vital)]
        if blocked_vital:
            diagnostics.append(KeywordListDiagnostic(
                line_number, "error", f"'{line}' : bloquerait le chemin vital {blocked_vital[0]}",
            ))
            continue
        entries.append(token)

    if len(entries) > RECOMMENDED_MAX_ENTRIES:
        diagnostics.append(KeywordListDiagnostic(
            0, "warning",
            f"{len(entries)} entrees : au-dela de {RECOMMENDED_MAX_ENTRIES}, scinder la liste par categorie est recommande",
        ))
    return PathListAnalysis(entries=tuple(entries), exceptions=tuple(exceptions), diagnostics=tuple(diagnostics))


@dataclass(frozen=True)
class RouteConflict:
    """Une entree de liste qui toucherait une route REELLEMENT servie par le
    site (plan §3.10-2) - `source` = d'ou vient la route (aliases,
    reverse_proxy, webroot...), `route` = son prefixe ou son chemin."""
    entry: str
    route: str
    source: str


def is_excepted(path: str, exceptions: tuple[str, ...], anchor: str) -> bool:
    """Le chemin est-il couvert par une exception `!/x` de la liste ?"""
    if not exceptions:
        return False
    return re.search(compile_path_list_pattern(exceptions, anchor), path, re.IGNORECASE) is not None


def find_route_conflicts(
    entries: tuple[str, ...],
    anchor: str,
    routes: tuple[tuple[str, str], ...],
    exceptions: tuple[str, ...] = (),
) -> tuple[RouteConflict, ...]:
    """`routes` = paires (source, prefixe d'URL) deja collectees depuis la
    configuration (aucune I/O ici). Conflit si l'entree matche le prefixe
    de la route (ex. `/api` contre une route proxy `/api/`) OU si l'entree
    designe une partie de cette route (ex. `/api/v1` sous `/api/`).
    Ignores : les jokers `/*.ext` (impossible a trancher sur un simple
    prefixe) et une route `/` (le site entier est servi par elle : toute
    entree serait en conflit, ce qui n'apporterait aucune information).
    Une route couverte par une exception `!/x` de la liste n'est plus un
    conflit : c'est precisement la facon de le resoudre."""
    conflicts: list[RouteConflict] = []
    for entry in entries:
        if _SUFFIX_TOKEN.fullmatch(entry):
            continue
        compiled = re.compile(compile_path_token(entry, anchor), re.IGNORECASE)
        entry_path = entry.rstrip("/").lower()
        for source, prefix in routes:
            route_path = prefix.rstrip("/").lower()
            if not route_path or is_excepted(route_path, exceptions, anchor):
                continue
            if compiled.search(route_path) or entry_path == route_path or entry_path.startswith(route_path + "/"):
                conflicts.append(RouteConflict(entry=entry, route=prefix, source=source))
    return tuple(conflicts)


def parse_keyword_list_definition(data: dict[str, Any]) -> KeywordListDefinition:
    scope = data.get("scope", [])
    return KeywordListDefinition(
        id=str(data.get("id", "")),
        scope=tuple(scope) if isinstance(scope, list) else tuple(scope.split(",")),
        file=str(data.get("file", "")),
        weight=int(data.get("weight", 1)),
        enabled=bool(data.get("enabled", True)),
        match=data.get("match", "substring"),
        anchor=data.get("anchor", "any_segment"),
        observe_only=bool(data.get("observe_only", False)),
        escalation_threshold=int(data.get("escalation_threshold", 0)),
        escalation_window_seconds=int(data.get("escalation_window_seconds", 600)),
        auto_block_duration_seconds=(
            int(data["auto_block_duration_seconds"])
            if data.get("auto_block_duration_seconds") is not None else None
        ),
        label=str(data.get("label", "")),
    )


def validate_keyword_list_definition(definition: KeywordListDefinition) -> list[str]:
    """Validation structurelle pure (pas d'I/O - l'existence reelle du
    fichier est verifiee par application/config/validate_config.py,
    meme repartition que RulePack/rule_validation.py)."""
    errors: list[str] = []
    if not definition.id:
        errors.append("keyword_lists : 'id' ne peut pas etre vide")
    if not definition.scope:
        errors.append(f"keyword_lists[{definition.id!r}] : 'scope' ne peut pas etre vide")
    unknown_scopes = set(definition.scope) - _VALID_SCOPES
    if unknown_scopes:
        errors.append(f"keyword_lists[{definition.id!r}] : scope inconnu : {sorted(unknown_scopes)}")
    if not is_safe_relative_path(definition.file):
        errors.append(
            f"keyword_lists[{definition.id!r}] : 'file' doit etre un chemin relatif au projet, "
            f"sans '..' : {definition.file!r}"
        )
    if definition.weight < 0:
        errors.append(f"keyword_lists[{definition.id!r}] : 'weight' doit etre >= 0")
    if definition.match not in _VALID_MATCH_MODES:
        errors.append(
            f"keyword_lists[{definition.id!r}] : 'match' inconnu : {definition.match!r} "
            f"(attendu : {sorted(_VALID_MATCH_MODES)})"
        )
    if definition.anchor not in _VALID_ANCHORS:
        errors.append(
            f"keyword_lists[{definition.id!r}] : 'anchor' inconnu : {definition.anchor!r} "
            f"(attendu : {sorted(_VALID_ANCHORS)})"
        )
    if definition.match == "path" and tuple(definition.scope) != ("path",):
        errors.append(f"keyword_lists[{definition.id!r}] : match='path' exige scope=['path'] uniquement")
    if definition.escalation_threshold < 0:
        errors.append(f"keyword_lists[{definition.id!r}] : 'escalation_threshold' doit etre >= 0")
    if definition.escalation_window_seconds <= 0:
        errors.append(f"keyword_lists[{definition.id!r}] : 'escalation_window_seconds' doit etre > 0")
    if definition.auto_block_duration_seconds is not None and definition.auto_block_duration_seconds <= 0:
        errors.append(f"keyword_lists[{definition.id!r}] : 'auto_block_duration_seconds' doit etre > 0")
    return errors


def validate_keyword_list_definitions(definitions: tuple[KeywordListDefinition, ...]) -> list[str]:
    errors: list[str] = []
    for definition in definitions:
        errors.extend(validate_keyword_list_definition(definition))
    ids = [d.id for d in definitions]
    duplicates = {i for i in ids if ids.count(i) > 1}
    if duplicates:
        errors.append(f"keyword_lists : id duplique(s) : {sorted(duplicates)}")
    return errors


def build_rule_pack_from_keyword_list(definition: KeywordListDefinition, tokens: tuple[str, ...]) -> RulePack:
    """Construit un `RulePack` synthetique a une seule regle - jamais
    compile ici (voir infrastructure/waf/keyword_list_loader.py, qui
    delegue la compilation reelle a signature_engine.compile_rule_pack,
    exactement comme un pack JSON classique : aucune seconde logique de
    compilation a maintenir).

    En mode "path", `tokens` est la sortie brute de `tokens_from_text` :
    les lignes `!/x` y sont separees en exceptions (`exclude_pattern`,
    prioritaires). Le texte est suppose deja valide par
    `analyze_path_list_text` (le chargeur refuse une liste en erreur avant
    d'arriver ici). Une liste `observe_only` garde ses findings (journal)
    mais pese 0 dans le score de blocage."""
    exclude_pattern: str | None = None
    if definition.match == "path":
        entries = tuple(t for t in tokens if not t.startswith(_EXCEPTION_PREFIX))
        exceptions = tuple(t[len(_EXCEPTION_PREFIX):] for t in tokens if t.startswith(_EXCEPTION_PREFIX))
        rule_pattern = compile_path_list_pattern(entries, definition.anchor)
        if exceptions:
            exclude_pattern = compile_path_list_pattern(exceptions, definition.anchor)
        description = f"Liste de chemins ({len(entries)} entree(s), {len(exceptions)} exception(s))"
    else:
        if not tokens:
            rule_pattern = r"(?!)"  # liste vide = ne matche jamais, jamais une erreur de compilation
        else:
            rule_pattern = compile_keyword_pattern(tokens)
        description = f"Liste de mots-clefs ({len(tokens)} entree(s))"
    return RulePack(
        version=1,
        pack=definition.id,
        enabled=definition.enabled,
        rules=(
            RuleDefinition(
                id=definition.id,
                description=description,
                scope=definition.scope,
                pattern=rule_pattern,
                case_insensitive=True,
                weight=0 if definition.observe_only else definition.weight,
                enabled=definition.enabled,
                exclude_pattern=exclude_pattern,
            ),
        ),
    )
