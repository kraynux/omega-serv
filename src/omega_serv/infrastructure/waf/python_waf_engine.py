# Copyright (c) 2026 kraynux - kraynux@proton.me - Licence MIT (voir fichier LICENSE)
"""Implementation native Python de WafPort (doc WAF, "Decision
d'integration recommandee" : "Premiere version : WAF Python natif").
Construit les textes de scope depuis la requete deja normalisee, puis
delegue tout le calcul a domain/security/waf/{signature_engine,scoring}.py -
ce module ne fait qu'assembler, jamais de logique de detection ici."""
from __future__ import annotations

from omega_serv.domain.http.request import HttpRequest
from omega_serv.domain.security.waf.config import WafConfig
from omega_serv.domain.security.waf.entities import WafDecision
from omega_serv.domain.security.waf.normalization import decode_bounded_for_inspection
from omega_serv.domain.security.waf.scoring import compute_decision
from omega_serv.domain.security.waf.signature_engine import CompiledRulePack, evaluate_rules


class PythonWafEngine:
    def __init__(self, compiled_packs: tuple[CompiledRulePack, ...], config: WafConfig):
        self._compiled_packs = compiled_packs
        self._config = config

    def inspect(self, request: HttpRequest) -> WafDecision:
        scope_texts = self._build_scope_texts(request)
        findings = evaluate_rules(self._compiled_packs, scope_texts)
        return compute_decision(findings, self._config.scoring, self._config.mode)

    def _build_scope_texts(self, request: HttpRequest) -> dict[str, str]:
        inspect = self._config.inspect
        texts: dict[str, str] = {}

        if inspect.path:
            texts["path"] = decode_bounded_for_inspection(request.path, inspect.decode_depth)
        if inspect.query:
            texts["query"] = decode_bounded_for_inspection(request.query, inspect.decode_depth)
        if inspect.headers:
            texts["headers"] = " ".join(f"{name}: {value}" for name, value in request.headers)

        user_agent = request.header("user-agent")
        if user_agent:
            texts["user_agent"] = user_agent

        if request.body and request.method in inspect.body_methods:
            body_text = request.body.decode("utf-8", errors="replace")
            texts["body"] = decode_bounded_for_inspection(body_text, inspect.decode_depth)

        return texts
