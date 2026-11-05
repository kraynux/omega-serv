"""Regles du WAF pour le moteur natif (OMEGA-SERV_PLAN-DETAILLE_WAF_NATIF.md, lot 0).

Le natif ne decide seul qu'une chose : « aucune regle ne correspond ». Pour cela il evalue les MEMES regles, avec
PCRE2. Recopier le texte d'un motif Python serait dangereux (les deux dialectes different sur `\\Z`, `\\s`, le repli
de casse, `$`...). Le motif est donc RETRADUIT depuis l'arbre produit par le parseur de `re` lui-meme, avec une
semantique fixee pour un texte ASCII (le natif envoie a Python tout texte non ASCII) :

- chaque caractere, classe `[...]`, `\\d`, `\\s`, `\\w` et `.` devient une classe explicite des caracteres ASCII
  que `re` accepte, calculee avec `re` lui-meme, casse comprise : le motif PCRE2 n'a ni repli de casse ni classe
  predefinie (exemple : `\\s` -> `[\\x09-\\x0d\\x1c-\\x20]`, Python comptant `\\x1c`-`\\x1f` comme des espaces) ;
- ancres, repetitions, groupes, alternatives, references arriere et assertions : equivalents PCRE2 directs ;
- toute construction non prevue -> `Untranslatable` : la regle n'est pas exportee, et le natif envoie a Python
  toute requete qu'elle pourrait lire (jamais une regle ignoree).

Regle « pliable » (voie rapide de signature_engine) : traduite sans IGNORECASE, le natif la cherche dans le texte
ASCII mis en minuscules, exactement comme `evaluate_rules`."""
from __future__ import annotations

import functools
import random
import re
from dataclasses import dataclass
from typing import Any

from omega_serv.domain.security.waf.signature_engine import CompiledRule, CompiledRulePack

try:  # Python >= 3.11
    import re._parser as _sre_parser  # type: ignore[import-not-found]
except ImportError:  # pragma: no cover - Python 3.10
    import sre_parse as _sre_parser

_ASCII = tuple(chr(code) for code in range(128))
_CATEGORY = {
    "CATEGORY_DIGIT": r"\d", "CATEGORY_NOT_DIGIT": r"\D", "CATEGORY_SPACE": r"\s",
    "CATEGORY_NOT_SPACE": r"\S", "CATEGORY_WORD": r"\w", "CATEGORY_NOT_WORD": r"\W",
}
_PCRE2_MAX_REPEAT = 65535  # borne de PCRE2 pour {m,n}


class Untranslatable(ValueError):
    """Construction sans equivalent sur garanti : la regle reste evaluee par Python seulement."""


@dataclass(frozen=True)
class NativeRule:
    rule_id: str
    pack: str
    scopes: tuple[str, ...]
    pattern: str
    exclude: str | None
    lowered: bool  # True : chercher dans le texte ASCII mis en minuscules
    # Lot 4 : textes ASCII de controle et resultat de Python (`re`, texte d'origine). Le natif les rejoue au
    # chargement : un seul desaccord -> la regle reste evaluee par Python seulement.
    controls: tuple[tuple[str, bool], ...] = ()


@dataclass(frozen=True)
class UnexportedRule:
    rule_id: str
    pack: str
    scopes: tuple[str, ...]
    reason: str


_CONTROL_COUNT = 32
_CONTROL_NOISE = "".join(chr(code) for code in range(32, 127)) + "\t\n\x0b\x0c\r\x1c\x1f"
_CONTROL_SAMPLES = ("", "/", "/index.html", "/wp-login.php", "/.git/config", "id=1 union select x", "' or 1=1 --",
                    "<script>alert(1)</script>", "; cat /etc/passwd", "Mozilla/5.0 (X11; Linux x86_64)", "sqlmap/1.8",
                    "a\nb", "x\x1cy")


def _one_char_regex(name: str, av: Any) -> str:
    """Regex Python d'un noeud « un caractere » de l'arbre (LITERAL, NOT_LITERAL, IN, CATEGORY, ANY)."""
    if name == "LITERAL":
        return f"\\U{av:08x}"
    if name == "NOT_LITERAL":
        return f"[^\\U{av:08x}]"
    if name == "IN":
        return _python_class(av)
    if name == "CATEGORY":
        return _CATEGORY.get(str(av), ".")
    return "."


def _example(nodes: Any, flags: int, rng: random.Random, depth: int = 0) -> str:
    """Un texte construit pour correspondre au motif (meilleur effort : assertions et references ignorees ; le
    resultat attendu est de toute facon calcule par `re`). Caracteres pris parmi ceux que `re` accepte."""
    out: list[str] = []
    for op, av in nodes:
        name = str(op)
        if depth > 20:
            break
        if name in ("LITERAL", "NOT_LITERAL", "IN", "CATEGORY", "ANY"):
            try:
                matcher = re.compile(_one_char_regex(name, av), flags)
            except (re.error, Untranslatable):
                continue
            chars = [c for c in _ASCII if 32 <= ord(c) < 127 and matcher.fullmatch(c)] or \
                    [c for c in _ASCII if matcher.fullmatch(c)]
            if chars:
                out.append(rng.choice(chars))
        elif name == "BRANCH":
            out.append(_example(rng.choice(av[1]), flags, rng, depth + 1))
        elif name == "SUBPATTERN":
            _group, add_flags, del_flags, sub = av
            out.append(_example(sub, (flags | add_flags) & ~del_flags, rng, depth + 1))
        elif name in ("MAX_REPEAT", "MIN_REPEAT", "POSSESSIVE_REPEAT"):
            low, high, sub = av
            upper = low + 2 if high == _sre_parser.MAXREPEAT else min(high, low + 2)
            out.extend(_example(sub, flags, rng, depth + 1) for _ in range(rng.randint(low, max(low, upper))))
        elif name == "ATOMIC_GROUP":
            out.append(_example(av, flags, rng, depth + 1))
    return "".join(out)


def control_texts(rule: CompiledRule) -> tuple[tuple[str, bool], ...]:
    """Textes de controle d'une regle, deterministes (graine = identifiant) : echantillons fixes, exemples construits
    depuis l'arbre du motif (en casse melangee, avec ou sans bruit autour : ils exercent les correspondances), bruit
    ASCII. Resultat attendu calcule par la regle Python elle-meme, exactement comme evaluate_rules."""
    rng = random.Random(f"{rule.pack}/{rule.definition.id}")
    flags = re.IGNORECASE if rule.definition.case_insensitive else 0
    try:
        parsed = _sre_parser.parse(rule.definition.pattern, flags).data
    except Exception:  # noqa: BLE001 - motif deja compile par `re` : jamais attendu, controle sans exemples
        parsed = None
    texts = list(_CONTROL_SAMPLES)
    while len(texts) < _CONTROL_COUNT:
        if parsed is not None and rng.random() < 0.6:
            example = _example(parsed, flags, rng)
            if rng.random() < 0.5:
                example = "".join(c.swapcase() if rng.random() < 0.5 else c for c in example)
            if rng.random() < 0.5:
                noise = [("".join(rng.choice(_CONTROL_NOISE) for _ in range(rng.randint(0, 4)))) for _ in range(2)]
                example = noise[0] + example + noise[1]
            texts.append(example)
        else:
            texts.append("".join(rng.choice(_CONTROL_NOISE) for _ in range(rng.randint(1, 40))))

    def matches(text: str) -> bool:
        return bool(rule.pattern.search(text)) and not (rule.exclude is not None and rule.exclude.search(text))

    return tuple((text, matches(text)) for text in texts)


@functools.lru_cache(maxsize=4096)
def _ascii_class(python_regex: str, flags: int) -> str:
    """Classe PCRE2 des caracteres ASCII que `python_regex` (un seul caractere) accepte avec `flags`."""
    matcher = re.compile(python_regex, flags)
    codes = [ord(char) for char in _ASCII if matcher.fullmatch(char)]
    if not codes:
        return "(?!)"  # n'accepte aucun caractere ASCII
    if len(codes) == 1:
        return f"\\x{{{codes[0]:02x}}}"
    parts: list[str] = []
    start = 0
    while start < len(codes):
        end = start
        while end + 1 < len(codes) and codes[end + 1] == codes[end] + 1:
            end += 1
        parts.append(f"\\x{{{codes[start]:02x}}}" + (f"-\\x{{{codes[end]:02x}}}" if end > start else ""))
        start = end + 1
    return "[" + "".join(parts) + "]"


def _python_class(items: list[tuple[Any, Any]]) -> str:
    parts: list[str] = []
    for op, av in items:
        name = str(op)
        if name == "NEGATE":
            parts.insert(0, "^")
        elif name == "LITERAL":
            parts.append(f"\\U{av:08x}")
        elif name == "RANGE":
            parts.append(f"\\U{av[0]:08x}-\\U{av[1]:08x}")
        elif name == "CATEGORY" and str(av) in _CATEGORY:
            parts.append(_CATEGORY[str(av)])
        else:
            raise Untranslatable(f"classe : {name}")
    return "[" + "".join(parts) + "]"


def _anchor(name: str, flags: int) -> str:
    multiline = bool(flags & re.MULTILINE)
    if name == "AT_BEGINNING":
        return "(?m:^)" if multiline else "(?-m:^)"
    if name == "AT_END":
        return "(?m:$)" if multiline else "(?-m:$)"
    fixed = {"AT_BEGINNING_STRING": r"\A", "AT_END_STRING": r"\z", "AT_BOUNDARY": r"\b", "AT_NON_BOUNDARY": r"\B"}
    if name not in fixed:
        raise Untranslatable(f"ancre : {name}")
    return fixed[name]


def _emit(nodes: Any, flags: int) -> str:
    out: list[str] = []
    for op, av in nodes:
        name = str(op)
        if name == "LITERAL":
            out.append(_ascii_class(f"\\U{av:08x}", flags))
        elif name == "NOT_LITERAL":
            out.append(_ascii_class(f"[^\\U{av:08x}]", flags))
        elif name == "IN":
            out.append(_ascii_class(_python_class(av), flags))
        elif name == "CATEGORY":
            if str(av) not in _CATEGORY:
                raise Untranslatable(f"categorie : {av}")
            out.append(_ascii_class(_CATEGORY[str(av)], flags))
        elif name == "ANY":
            out.append(_ascii_class(".", flags))
        elif name == "AT":
            out.append(_anchor(str(av), flags))
        elif name == "BRANCH":
            out.append("(?:" + "|".join(_emit(branch, flags) for branch in av[1]) + ")")
        elif name == "SUBPATTERN":
            group, add_flags, del_flags, sub = av
            inner = _emit(sub, (flags | add_flags) & ~del_flags)
            # jamais de groupe capturant ajoute : la numerotation reste celle de Python (references arriere)
            out.append(("(?:" if group is None else "(") + inner + ")")
        elif name in ("MAX_REPEAT", "MIN_REPEAT", "POSSESSIVE_REPEAT"):
            low, high, sub = av
            if low > _PCRE2_MAX_REPEAT or (high != _sre_parser.MAXREPEAT and high > _PCRE2_MAX_REPEAT):
                raise Untranslatable("repetition trop grande pour PCRE2")
            upper = "" if high == _sre_parser.MAXREPEAT else str(high)
            quantifier = f"{{{low},{upper}}}"
            quantifier += {"MAX_REPEAT": "", "MIN_REPEAT": "?", "POSSESSIVE_REPEAT": "+"}[name]
            out.append("(?:" + _emit(sub, flags) + ")" + quantifier)
        elif name in ("ASSERT", "ASSERT_NOT"):
            direction, sub = av
            out.append("(?" + ("<" if direction < 0 else "") + ("=" if name == "ASSERT" else "!") + _emit(sub, flags) + ")")
        elif name == "ATOMIC_GROUP":
            out.append("(?>" + _emit(av, flags) + ")")
        elif name == "GROUPREF":
            if flags & re.IGNORECASE:
                raise Untranslatable("reference arriere insensible a la casse")
            out.append(f"\\g{{{av}}}")
        else:
            raise Untranslatable(f"construction : {name}")
    return "".join(out)


def translate_pattern(pattern: str, case_insensitive: bool) -> str:
    """Motif PCRE2 (sans option de compilation) equivalent a `re.search(pattern, texte, flags)` pour tout texte
    ASCII. `Untranslatable` si une construction n'a pas d'equivalent sur."""
    flags = re.IGNORECASE if case_insensitive else 0
    try:
        parsed = _sre_parser.parse(pattern, flags)
    except re.error as e:
        raise Untranslatable(f"motif invalide : {e}") from e
    if parsed.state.flags & re.LOCALE:
        raise Untranslatable("drapeau LOCALE")
    return _emit(parsed.data, parsed.state.flags)


def export_rule(rule: CompiledRule) -> NativeRule:
    """`Untranslatable` si la regle (motif ou exception) ne peut pas etre evaluee par le natif."""
    definition = rule.definition
    lowered = rule.folded_pattern is not None  # meme choix que evaluate_rules (voie rapide prouvee)
    case_insensitive = definition.case_insensitive and not lowered
    try:
        pattern = translate_pattern(definition.pattern, case_insensitive)
        exclude = (translate_pattern(definition.exclude_pattern, case_insensitive)
                   if definition.exclude_pattern else None)
    except RecursionError as e:
        raise Untranslatable("motif trop imbrique") from e
    return NativeRule(definition.id, rule.pack, tuple(dict.fromkeys(definition.scope)), pattern, exclude, lowered,
                      control_texts(rule))


def export_rule_packs(packs: tuple[CompiledRulePack, ...]) -> tuple[tuple[NativeRule, ...], tuple[UnexportedRule, ...]]:
    """Regles des packs actives, dans l'ordre d'evaluation : exportees, et celles qui restent a Python."""
    exported: list[NativeRule] = []
    unexported: list[UnexportedRule] = []
    for pack in packs:
        if not pack.enabled:
            continue
        for rule in pack.rules:
            try:
                exported.append(export_rule(rule))
            except Untranslatable as e:
                unexported.append(UnexportedRule(rule.definition.id, pack.pack,
                                                 tuple(dict.fromkeys(rule.definition.scope)), str(e)))
    return tuple(exported), tuple(unexported)
