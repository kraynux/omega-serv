"""Implementation native Python de WafPort (doc WAF, "Decision
d'integration recommandee" : "Premiere version : WAF Python natif").
Construit les textes de scope depuis la requete deja normalisee, puis
delegue tout le calcul a domain/security/waf/{signature_engine,scoring}.py -
ce module ne fait qu'assembler, jamais de logique de detection ici."""
from __future__ import annotations

from omega_serv.domain.http.request import HttpRequest
from omega_serv.domain.security.waf.binary_formats import inspectable_body
from omega_serv.domain.security.waf.config import WafConfig
from omega_serv.domain.security.waf.entities import WafDecision
from omega_serv.domain.security.waf.normalization import decode_bounded_for_inspection
from omega_serv.domain.security.waf.scoring import compute_decision
from omega_serv.domain.security.waf.signature_engine import CompiledRulePack, evaluate_rules


class PythonWafEngine:
    def __init__(self, compiled_packs: tuple[CompiledRulePack, ...], config: WafConfig):
        self._compiled_packs = compiled_packs
        self._config = config
        # Scopes qu'au moins une regle activee lit (2026-11-04) : un texte que personne ne lit n'est pas construit
        # (aujourd'hui « headers », assemble a chaque requete sans qu'aucune regle livree ne le cible).
        self._used_scopes = frozenset(
            scope for pack in compiled_packs if pack.enabled for rule in pack.rules for scope in rule.definition.scope
        )

    def inspect(self, request: HttpRequest) -> WafDecision:
        scope_texts = self._build_scope_texts(request)
        findings = evaluate_rules(self._compiled_packs, scope_texts)
        return compute_decision(findings, self._config.scoring, self._config.mode)

    def _build_scope_texts(self, request: HttpRequest) -> dict[str, str]:
        inspect = self._config.inspect
        used = self._used_scopes
        texts: dict[str, str] = {}

        if inspect.path and "path" in used:
            # Scan de securite n° 2 (2026-11-20, F8) : chemin canonique (`\\`, `%5c`, `//` ramenes a la forme
            # servie) - les signatures ancrees sur `/x` manquaient `\\x` ou `//x`, servis pourtant comme `/x`.
            texts["path"] = decode_bounded_for_inspection(request.canonical_path or request.path, inspect.decode_depth)
        if inspect.query and "query" in used:
            texts["query"] = decode_bounded_for_inspection(request.query, inspect.decode_depth)
        if inspect.headers and "headers" in used:
            texts["headers"] = " ".join(f"{name}: {value}" for name, value in request.headers)

        if "user_agent" in used:
            user_agent = request.header("user-agent")
            if user_agent:
                texts["user_agent"] = user_agent

        if "referer" in used:
            referer = request.header("referer")
            if referer:
                texts["referer"] = referer

        if request.body and request.method in inspect.body_methods and "body" in used:
            # Lot 11 (F2) : fichier binaire reconnu a sa signature (contenu reel, jamais l'extension) et type annonce
            # non textuel -> pas lu comme du texte ; en multipart, seules ses parties fichier sont retirees.
            body = inspectable_body(request.body, request.header("content-type"), inspect.binary_formats)
            if body:
                body_text = body.decode("utf-8", errors="replace")
                texts["body"] = decode_bounded_for_inspection(body_text, inspect.decode_depth)

        return texts
